#!/usr/bin/env bash
# render.sh — Draft render loop → concat → ffmpeg stitch → Done
#
# Convention: one echo line per scene for clear terminal progress.
# concat.txt is hard-coded here; edit it whenever the scene list changes.
#
# Quick-start: chmod +x render.sh && ./render.sh
# Production:   rerun each manim line with -qh instead of -ql

set -e
cd "$(dirname "$0")"

PROJECT_NAME="${PROJECT_NAME:-[Project Name]}"

echo "=== Rendering $PROJECT_NAME ==="
echo ""

# ── Draft render all scenes ──────────────────────────────────
echo "[1/3] Scene 1: scene_name..."
manim -ql script.py Scene1_SceneName

echo "[2/3] Scene 2: scene_name..."
manim -ql script.py Scene2_SceneName

# ...add echo lines next to every manim call above──

echo "[3/3] Stitching…";
# ── Build scene list (auto-generated from render calls) ───────
cat > concat.txt << 'EOF'
file 'media/videos/script/480p15/Scene1_SceneName.mp4'
file 'media/videos/script/480p15/Scene2_SceneName.mp4'
EOF

ffmpeg -y -f concat -safe 0 -i concat.txt -c copy final.mp4

echo ""
echo "=== Done! Output: final.mp4 ==="
echo ""
echo "For production quality, rerun each manim line with -qh instead of -ql:"
echo "  manim -qh script.py Scene1_SceneName Scene2_SceneName ..."
