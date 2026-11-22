#!/usr/bin/env python3
"""HN Brief daily email — deterministic, no LLM.

Reads /opt/shared_space/hn-brief-data and emails the day's briefing:
  20 headlines (points + article link + HN discussion link), then the digest.

Skip rules (silent, exit 0):
  * latest.json date is not today in America/New_York
  * quality.digestValid is false

Sender resolution (first that works):
  1. SMTP via secret store: /opt/data/secrets/mail.env  (EMAIL_ADDRESS,
     EMAIL_PASSWORD, EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) or the same EMAIL_* vars
     already present in the process environment
  2. local `msmtp` binary if installed
  3. `msmtp` on a remote host over ssh when HN_MAIL_SSH_HOST is set

Usage
-----
  hn-brief-email.py                 # send (or skip)
  hn-brief-email.py --dry-run       # render only; print where the file is
  hn-brief-email.py --date D --to X --allow-stale --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import smtplib
import ssl
import subprocess
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_ROOT = Path("/opt/shared_space/hn-brief-data")
CACHE_DIR = Path("/opt/data/cache/hn-brief-email")
LOG = Path("/opt/data/logs/hn-brief-email.log")
SECRET_ENV = Path("/opt/data/secrets/mail.env")
NY = ZoneInfo("America/New_York")
DEFAULT_TO = "nick.lange@gmail.com"
MAX_HEADLINES = 20


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(NY).strftime("%Y-%m-%d %H:%M:%S %Z")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {msg}\n")


def load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def build_body(day: dict) -> str:
    stories = day["stories"][:MAX_HEADLINES]
    lines = [
        f"HN Brief — {day['date']}",
        f"{len(stories)} stories · generated {day.get('generatedAt', '?')} · run {day.get('runId', '?')}",
        "",
        "HEADLINES",
        "",
    ]
    for i, s in enumerate(stories, 1):
        comments = s.get("num_comments", 0)
        lines.append(f"{i}. {s['title']}  ({s['points']} points, {comments} comments)")
        lines.append(f"   {s['url']}")
        lines.append(f"   HN: https://news.ycombinator.com/item?id={s['id']}")
        lines.append("")
    lines += ["-" * 60, "", "DIGEST", "", (day.get("digest") or "(digest missing)").strip(), ""]
    return "\n".join(lines)


def render_subject(date: str) -> str:
    return f"HN Brief — {date}"


def send_smtp(subject: str, body: str, to: str, env: dict[str, str]) -> str:
    user = env.get("EMAIL_ADDRESS") or env.get("EMAIL_USER")
    pwd = env.get("EMAIL_PASSWORD")
    host = env.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
    port = int(env.get("EMAIL_SMTP_PORT", "465"))
    sender = env.get("EMAIL_FROM") or user
    if not (user and pwd and sender):
        raise RuntimeError("SMTP credentials incomplete")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=45, context=ssl.create_default_context()) as s:
            s.login(user, pwd)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=45) as s:
            s.ehlo()
            s.starttls(context=ssl.create_default_context())
            s.login(user, pwd)
            s.send_message(msg)
    return f"smtp:{host}:{port} as {sender}"


def send_msmtp_local(subject: str, body: str, to: str, sender: str | None) -> str:
    exe = shutil.which("msmtp")
    if not exe:
        raise RuntimeError("msmtp not installed")
    raw = f"From: {sender or 'Hermes <hermes@localhost>'}\nTo: {to}\nSubject: {subject}\n\n{body}\n"
    cmd = [exe]
    if sender:
        cmd += ["--from", sender]
    cmd.append(to)
    subprocess.run(cmd, input=raw.encode(), check=True, timeout=90)
    return f"msmtp:{exe}"


def send_msmtp_ssh(subject: str, body: str, to: str, ssh_host: str, sender: str | None) -> str:
    raw = f"From: {sender or 'Hermes <hermes@localhost>'}\nTo: {to}\nSubject: {subject}\n\n{body}\n"
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", ssh_host,
           "msmtp" + (f" --from {sender}" if sender else "") + f" {to}"]
    subprocess.run(cmd, input=raw.encode(), check=True, timeout=120)
    return f"ssh-msmtp:{ssh_host}"


def resolve_env(cli_env: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    env.update(load_env_file(SECRET_ENV))
    env.update(cli_env)
    return env


def have_sender(env: dict[str, str]) -> bool:
    """True when at least one send path looks provisioned."""
    if env.get("EMAIL_ADDRESS") and env.get("EMAIL_PASSWORD"):
        return True
    if shutil.which("msmtp"):
        return True
    return bool(env.get("HN_MAIL_SSH_HOST"))


def try_senders(subject: str, body: str, to: str, env: dict[str, str]) -> tuple[str, str]:
    errors = []
    if env.get("EMAIL_ADDRESS") and env.get("EMAIL_PASSWORD"):
        try:
            return send_smtp(subject, body, to, env), ""
        except Exception as exc:  # noqa: BLE001
            errors.append(f"smtp: {exc}")
    try:
        return send_msmtp_local(subject, body, to, env.get("EMAIL_FROM")), ""
    except Exception as exc:  # noqa: BLE001
        errors.append(f"msmtp: {exc}")
    ssh_host = env.get("HN_MAIL_SSH_HOST")
    if ssh_host:
        try:
            return send_msmtp_ssh(subject, body, to, ssh_host, env.get("EMAIL_FROM")), ""
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ssh-msmtp: {exc}")
    return "", "; ".join(errors) or "no sender configured"


def main() -> int:
    ap = argparse.ArgumentParser(description="HN Brief daily email")
    ap.add_argument("--date", help="force a date (YYYY-MM-DD)")
    ap.add_argument("--to", default=os.environ.get("HN_BRIEF_EMAIL_TO", DEFAULT_TO))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-stale", action="store_true")
    ap.add_argument("--out", help="write rendered email to this path")
    args = ap.parse_args()

    meta = json.loads((DATA_ROOT / "latest.json").read_text(encoding="utf-8"))
    today = datetime.now(NY).strftime("%Y-%m-%d")
    if args.date and args.date != meta["date"]:
        date = args.date
        y, m, d = date.split("-")
        path = DATA_ROOT / "daily" / y / m / f"{d}.json"
    else:
        date, path = meta["date"], DATA_ROOT / meta["path"]
    day = json.loads(path.read_text(encoding="utf-8"))

    if not args.allow_stale:
        if date != today:
            log(f"skip: latest date {date} != today {today}")
            return 0
        if not (day.get("quality") or {}).get("digestValid", False):
            log(f"skip: digestValid=false for {date}")
            return 0

    subject = render_subject(day["date"])
    body = build_body(day)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else CACHE_DIR / f"{day['date']}.txt"
    out.write_text(f"To: {args.to}\nSubject: {subject}\n\n{body}", encoding="utf-8")

    if args.dry_run:
        print(f"rendered: {out} ({len(body)} chars)")
        return 0

    env = resolve_env({})
    if not have_sender(env):
        # No email channel provisioned yet — log and stay silent rather than
        # firing a failure notice every day. Real send errors still exit 2.
        log(f"NOT SENT {day['date']}: no email channel configured")
        return 0
    how, err = try_senders(subject, body, args.to, env)
    if how:
        log(f"sent {day['date']} to {args.to} via {how} ({len(body)} chars)")
        return 0
    log(f"SEND FAILED {day['date']}: {err}")
    print(f"HN Brief email NOT sent ({day['date']}): {err}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
