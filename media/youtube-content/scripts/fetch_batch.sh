#!/bin/bash
# ================================================================
# YouTube batch transcript fetcher (yt-dlp, VTT)
#
# Usage:
#   # provide a tab-separated list of VIDEO_ID<TAB>OPTIONAL_TITLE
#   printf "abc123<Tab>Video Title\nxyz789<Tab>Another\n" | bash /path/to/fetch_batch.sh
#
# Environment
#   Must have yt-dlp at $YT_DLP (defaults to /tmp/yt-venv/bin/yt-dlp)
#   Sets SSL_CERT_FILE=/usr/lib/ssl/cert.pem (fixes Python SSL in this env)
#
# Notes
#   - Per-video dirs under SUB_BASE prevent yt-dlp from silent-skipping
#   - Sleep 5 s between videos (YouTube rate-limit guard)
#   - Only processes videos missing {VIDEO_ID}_transcript.txt in SAVE_DIR
# ================================================================

export SSL_CERT_FILE="/usr/lib/ssl/cert.pem"

YT_DLP="${YT_DLP:-/tmp/yt-venv/bin/yt-dlp}"
SAVE_DIR="${SAVE_DIR:-/opt/data/content/youtube-raw}"
SUB_BASE="${SUB_BASE:-/tmp/subs_ytbatch}"

mkdir -p "$SAVE_DIR" "$SUB_BASE"

ok=0
fail=0

while IFS=$'\t' read -r vid title; do
    [ -z "$vid" ] && continue

    # Skip if already fetched
    [ -f "${SAVE_DIR}/${vid}_transcript.txt" ] && { echo "[SKIP] $vid"; continue; }

    echo "### $vid : ${title:-Unknown} ###"
    url="https://www.youtube.com/watch?v=${vid}"
    viddir="${SUB_BASE}/${vid}"
    mkdir -p "$viddir"

    # 1. Metadata
    "$YT_DLP" --dump-single-json --quiet --no-warnings \
        --no-check-certificate --extractor-retries 3 --sleep-requests 1 \
        "$url" > "/tmp/ymeta_${vid}.json" 2>/tmp/yerr_${vid}.txt || true

    if [ ! -s "/tmp/ymeta_${vid}.json" ] || ! python3 -c "import json; json.load(open('/tmp/ymeta_${vid}.json'))" 2>/dev/null; then
        echo "  META FAIL: $(head -c 120 /tmp/yerr_${vid}.txt)"
        echo "FAIL: metadata" > "${SAVE_DIR}/${vid}_status.txt"
        fail=$((fail+1)); continue
    fi

    duration=$(python3 -c "import json; print(json.load(open('/tmp/ymeta_${vid}.json')).get('duration',0) or 0)")
    echo "  duration: ${duration}s"

    # 2. VTT via --write-auto-subs (per-video dir prevents cache-skip)
    "$YT_DLP" --skip-download --write-auto-subs \
        --sub-langs "en,en-US" --sub-format "vtt/srt" \
        --output "${viddir}/${vid}.%(ext)s" \
        --quiet --no-warnings --no-check-certificate \
        --extractor-retries 3 --sleep-subtitles 3 --sleep-requests 1 \
        "$url" >/dev/null 2>/tmp/yerr_sub_${vid}.txt

    vtt=""
    for ext in vtt srt; do
        [ -f "${viddir}/${vid}.${ext}" ] && vtt="${viddir}/${vid}.${ext}" && break
    done

    if [ -z "$vtt" ]; then
        echo "  SUB FAIL"
        echo "FAIL: no subtitle" > "${SAVE_DIR}/${vid}_status.txt"
        fail=$((fail+1)); continue
    fi

    fsize=$(wc -c < "$vtt")
    echo "  VTT: ${fsize} bytes"
    [ "$fsize" -lt 30 ] && {
        echo "  FAIL: VTT too small ($fsize bytes)"
        echo "FAIL: VTT too small" > "${SAVE_DIR}/${vid}_status.txt"
        fail=$((fail+1)); continue
    }

    # 3. Parse and save
    if python3 -c "
import sys, re, json
vid, vtt_path, save, full_title, duration = sys.argv[1:]
raw = open(vtt_path, encoding='utf-8', errors='replace').read()
g = re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?\.\d{3})\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?\.\d{3}\n(.*?)(?=\n\n|\Z)', re.DOTALL)
lines = []
for m in g.finditer(raw):
    ts = m.group(1).rsplit('.',1)[0]
    t  = re.sub(r'<[^>]+>','',m.group(2)).strip()
    t  = re.sub(r'\s+',' ',t).strip()
    if t: lines.append('['+ts+'] '+t)
if not lines:
    s = re.compile(r'^\d+\n(\d{1,2}:\d{2}(?::\d{2})?\.\d{3})\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?\.\d{3}\n(.*?)(?=^\d+\n|\Z)', re.DOTALL|re.MULTILINE)
    for m in s.finditer(raw):
        ts = m.group(1).rsplit('.',1)[0]
        t  = re.sub(r'<[^>]+>','',m.group(2)).strip()
        t  = re.sub(r'\s+',' ',t).strip()
        if t: lines.append('['+ts+'] '+t)
if not lines:
    sys.stderr.write('EMPTY\n'); sys.exit(1)
ts_text   = '\n'.join(lines)
fulltext  = re.sub(r'^\[\d{1,2}:\d{2}(?::\d{2})?\] ','',ts_text,flags=re.MULTILINE)
fulltext  = re.sub(r'\s+',' ',fulltext).strip()
segments  = len(ts_text.strip().split('\n'))
meta = {'video_id':vid,'title':full_title,'segments':segments,
        'duration':int(float(duration)),'chapters':[]}
open(f'{save}/{vid}_transcript.txt','w').write(ts_text)
open(f'{save}/{vid}_fulltext.txt','w').write(fulltext)
json.dump(meta,open(f'{save}/{vid}_meta.json','w'),indent=2)
open(f'{save}/{vid}_status.txt','w').write(f'OK: {segments} segments\n')
print(f'OK: {segments} segments, {len(fulltext)} chars')
" "$vid" "$vtt" "$SAVE_DIR" "${title:-Unknown}" "$duration"; then
        echo "  SAVED ✓"; ok=$((ok+1))
    else
        echo "  PARSE FAIL"
        echo "FAIL: parse" > "${SAVE_DIR}/${vid}_status.txt"
        fail=$((fail+1))
    fi

    sleep 5
done

echo ""
echo "=== COMPLETE ==="
echo "Succeeded: $ok"
echo "Failed:    $fail"
