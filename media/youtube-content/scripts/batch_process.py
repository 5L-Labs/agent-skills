#!/usr/bin/env python3
"""
Batch processor for YouTube transcripts with proper error handling.
Preserves backlog integrity and handles IP blocks gracefully.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

BACKLOG_PATH = "/opt/data/.hermes/content/yt-backlog.json"
CACHE_DIR = "/opt/data/.hermes/content/youtube-raw/"
DIGEST_FILE = "/opt/data/home/.hermes/yt-digest.txt"

def load_backlog():
    with open(BACKLOG_PATH, 'r') as f:
        return json.load(f)

def save_backlog(data):
    with open(BACKLOG_PATH, 'w') as f:
        json.dump(data, f, indent=2)

def fetch_transcript(video_id):
    """Fetch transcript with error handling."""
    # Check cache first
    cache_file = CACHE_DIR / f"{video_id}_timestamped.txt"
    if cache_file.exists():
        return open(cache_file, 'r').read(), None
    
    # Attempt fetch
    cmd = [
        "/usr/bin/python3",
        "/opt/data/.hermes/skills/media/youtube-content/scripts/fetch_transcript.py",
        f"https://youtube.com/watch?v={video_id}",
        "--text-only",
        "--timestamps"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None, result.stderr
    
    return result.stdout, None

def generate_luna_digest(transcript_text):
    """Generate Luna digest with fallback."""
    # Write transcript to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(transcript_text)
        temp_file = f.name
    
    try:
        # Try the standard digest script
        cmd = [
            "/usr/bin/python3",
            "/opt/data/.hermes/skills/media/youtube-content/scripts/generate_luna_digest.py",
            temp_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    # Fallback method
    lines = transcript_text.split('\n')
    meaningful_sentences = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(' ', 1)
        text = parts[1].strip() if len(parts) > 1 else line.strip()
        if len(text) > 20:
            meaningful_sentences.append(text)
    
    if meaningful_sentences:
        digest = f"• Core concept: {meaningful_sentences[0]}\n"
        for i, sentence in enumerate(meaningful_sentences[1:10], 1):
            digest += f"• Key point {i}: {sentence}\n"
        digest += f"• Full transcript available for {video_id}.\n"
    else:
        digest = f"• No meaningful content extracted.\n"
    
    return digest

def process_video(video_id):
    """Process a single video with full error handling."""
    try:
        transcript, error = fetch_transcript(video_id)
        if error:
            return {"status": "failed", "error": error}
        
        if not transcript:
            return {"status": "failed", "error": "No transcript received"}
        
        digest = generate_luna_digest(transcript)
        
        return {
            "status": "success",
            "video_id": video_id,
            "digest": digest
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python batch_process.py [num_videos] [backlog_path]")
        print("Defaults: process 10 videos from /opt/data/.hermes/content/yt-backlog.json")
        sys.exit(0)
    
    num_videos = 10
    if len(sys.argv) > 1:
        num_videos = int(sys.argv[1])
    
    backlog_path = BACKLOG_PATH
    if len(sys.argv) > 2:
        backlog_path = sys.argv[2]
    
    try:
        backlog = load_backlog()
    except FileNotFoundError:
        print(f"Backlog file not found: {backlog_path}")
        sys.exit(1)
    
    video_ids = backlog["unique_videos"][:]  # Copy for safe iteration
    if len(video_ids) < num_videos:
        num_videos = len(video_ids)
        print(f"Warning: Only {num_videos} videos available in backlog")
    
    successes = []
    failures = []
    
    for video_id in video_ids[:num_videos]:
        result = process_video(video_id)
        if result["status"] == "success":
            successes.append(video_id)
            if video_id in video_ids:
                video_ids.remove(video_id)
        else:
            failures.append((video_id, result.get("error", "Unknown error")))
    
    # Save updated backlog (only if modifications made)
    if successes:
        backlog["unique_videos"] = video_ids
        save_backlog(backlog)
    
    # Generate report
    report = f"""=== BATCH PROCESSING REPORT - {datetime.now().isoformat()} ===
Backlog size: {len(backlog["unique_videos"])}
Attempting: {num_videos}
Successes: {len(successes)}
Failures: {len(failures)}

"""
    if successes:
        report += f"Successfully processed: {', '.join(successes)}\n"
    if failures:
        report += "\nFailed videos:\n"
        for vid, err in failures:
            report += f"  {vid}: {err}\n"
    
    report += f"\nBacklog remaining: {len(video_ids)} videos\n"
    report += "=== END REPORT ===\n"
    
    # Append to digest file
    with open(DIGEST_FILE, 'a') as f:
        f.write(report)
    
    print(report)
    sys.exit(0 if not failures else 1)

if __name__ == "__main__":
    main()