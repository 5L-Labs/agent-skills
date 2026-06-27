"""Confirm .env loading only touches skill dir + CWD, never walks up."""
import os
import subprocess
import sys
import textwrap
from pathlib import Path


def _run(code: str, cwd: Path, extra_env=None):
    env = {k: v for k, v in os.environ.items()
           if k not in ("FT_COOKIE", "FT_SESSION_S", "FT_CLIENT_SESSION_ID",
                        "FT_APP_USER", "FT_CSRF")}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(cwd), env=env, capture_output=True, text=True,
    )


def test_does_not_walk_up_from_module(tmp_path):
    bogus_parent = tmp_path / "outer"
    bogus_parent.mkdir()
    (bogus_parent / ".env").write_text("FT_COOKIE=POISON\n")
    inner = bogus_parent / "inner"
    inner.mkdir()
    code = textwrap.dedent(f"""
        import os, sys
        from pathlib import Path
        from news_reader_base import load_dotenv
        load_dotenv(Path({str(Path(__file__).resolve().parent.parent / 'src')!r}))
        print('FT_COOKIE=' + os.environ.get('FT_COOKIE', '<unset>'))
    """)
    result = _run(code, cwd=inner)
    assert "POISON" not in result.stdout, result.stdout


def test_loads_from_cwd_when_present(tmp_path):
    (tmp_path / ".env").write_text("FT_COOKIE=cwd-loaded\n")
    code = textwrap.dedent("""
        import os
        from pathlib import Path
        from news_reader_base import load_dotenv
        load_dotenv(Path("/does/not/exist"))
        print(os.environ.get('FT_COOKIE', '<unset>'))
    """)
    result = _run(code, cwd=tmp_path)
    assert "cwd-loaded" in result.stdout
