#!/usr/bin/env python3
"""Generate Luna-style digest from timestamped transcript."""

import sys
from pathlib import Path

import json

def load_video_info(vid, raw_dir):
    """Load video metadata from raw JSON."""
    json_path = raw_dir / f"{vid}.json"
    if json_path.exists():
        return json.loads(json_path.read_text())
    return None

def generate_digest(ts_file, info=None):
    """Generate Luna digest from timestamped transcript."""
    lines = ts_file.read_text().strip().split('\n')
    
    # Extract video ID from filename
    vid = ts_file.stem.replace('_timestamped', '')
    
    # Build digest
    digest = []
    
    # Header with URL
    digest.append(f"https://www.youtube.com/watch?v={vid}")
    digest.append("")
    
    # Title line
    if info and info.get('video_title'):
        title = info['video_title']
    else:
        title = "Video"
    duration = info.get('duration', '') if info else ''
    
    digest.append(f"{title} ({duration}) transcript (what matters):")
    digest.append("")
    
    # Process transcript lines into thematic sections
    # Simple approach: group contiguous segments
    current_section = []
    for line in lines:
        if not line.strip():
            continue
        current_section.append(line)
    
    # Use first ~10 lines as key points
    key_lines = lines[:40]
    
    # Create digest structure
    if key_lines:
        # Introduction from first line
        first = key_lines[0]
        time_marker = first.split(' ', 1)[0] if first else ''
        first_text = first.split(' ', 1)[1] if ' ' in first else first
        
        digest.append("    •    Introduction:")
        digest.append(f"    ◦    {first_text}")
        
        # Key points from subsequent lines
        for line in key_lines[1:]:
            if not line.strip():
                continue
            parts = line.split(' ', 1)
            if len(parts) == 2:
                _, text = parts
                # Check if this is a natural break point
                if any(word in text.lower() for word in 
                       ['first', 'second', 'key', 'important', 'main', 'however', 'but', 'so']):
                    digest.append("")
                    digest.append(f"    •    {text}")
                elif len(text) < 120:
                    digest.append(f"    ◦    {text}")
        
        digest.append("")
        digest.append("    •    Big Insight: Key takeaway in one line.")
        digest.append("")
    
    return '\n'.join(digest)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: generate_luna_digest.py <timestamped_transcript.txt>")
        sys.exit(1)
    
    ts_file = Path(sys.argv[1])
    if not ts_file.exists():
        print(f"File not found: {ts_file}")
        sys.exit(1)
    
    # Load raw info
    vid = ts_file.stem.replace('_timestamped', '')
    raw_dir = ts_file.parent
    info = load_video_info(vid, raw_dir)
    
    # Generate
    digest = generate_digest(ts_file, info)
    print(digest)
