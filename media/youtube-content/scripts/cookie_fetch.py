#!/usr/bin/env python3
"""
Fetch YouTube transcript using cookie authentication.
This script bypasses YouTube's IP blocking by using logged-in user cookies.
"""

import argparse
import json
import os
import sys
from youtube_transcript_api import YouTubeTranscriptApi, cookies

def fetch_transcript_with_cookies(video_id, language=None, cookie_file=None):
    """
    Fetch transcript using cookies to avoid IP blocking.
    
    Args:
        video_id: YouTube video ID
        language: Language code (e.g., 'en', 'tr', 'en,tr' for fallback)
        cookie_file: Path to Netscape-format cookie file
    
    Returns:
        Dict with full_text and timestamped_text, or error JSON
    """
    # Parse languages
    languages = None
    if language:
        languages = [lang.strip() for lang in language.split(',')]
    
    # Load cookies
    cookie_jar = None
    if cookie_file and os.path.exists(cookie_file):
        try:
            with open(cookie_file, 'r') as f:
                cookie_jar = cookies.CookieJar.from_netscape(f.read())
        except Exception as e:
            return {"error": f"Failed to load cookies: {str(e)}"}
    
    try:
        # Fetch transcript
        transcript_list = YouTubeTranscriptApi.get_transcripts(
            [video_id],
            languages=languages,
            cookie_jar=cookie_jar
        )
        
        # Get the first (and hopefully only) transcript
        transcript = transcript_list[0] if transcript_list else None
        
        if not transcript:
            return {"error": "No transcript found for video"}
        
        # Build full text
        full_text = ' '.join([segment['text'] for segment in transcript])
        
        # Build timestamped text
        timestamped_segments = []
        for segment in transcript:
            # Format: MM:SS text
            minutes = int(segment['start'] // 60)
            seconds = int(segment['start'] % 60)
            timestamp = f"{minutes}:{seconds:02d}"
            timestamped_segments.append(f"{timestamp} {segment['text']}")
        timestamped_text = '\n'.join(timestamped_segments)
        
        return {
            "video_id": video_id,
            "language": transcript.language,
            "full_text": full_text,
            "timestamped_text": timestamped_text
        }
        
    except Exception as e:
        error_msg = str(e)
        if "blocked" in error_msg.lower() or "IP" in error_msg.lower():
            error_msg = f"IP_BLOCKED: {error_msg}"
        return {"error": error_msg}

def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube transcript with cookie support")
    parser.add_argument("video_id", help="YouTube video ID or full URL")
    parser.add_argument("--language", default="en", help="Comma-separated list of language codes (e.g., 'en,tr')")
    parser.add_argument("--cookie-file", default="/opt/data/.hermes/cookies/youtube.com_cookie.txt", 
                       help="Path to Netscape-format cookie file (default: /opt/data/.hermes/cookies/youtube.com_cookie.txt)")
    parser.add_argument("--text-only", action="store_true", help="Output only plain text (no JSON)")
    parser.add_argument("--timestamps", action="store_true", help="Include timestamps in output")
    parser.add_argument("--save-dir", help="Directory to save raw transcript files")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-essential output")
    
    args = parser.parse_args()
    
    # Extract video ID from URL if needed
    video_id = args.video_id
    if len(video_id) > 11 or any(segment in video_id for segment in ['youtube.com', 'youtu.be']):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(video_id)
            if 'v=' in parsed.query:
                video_id = parsed.query.split('v=')[1].split('&')[0]
            elif parsed.path and 'embed' in parsed.path:
                video_id = parsed.path.split('/')[-1]
            elif parsed.netloc == 'youtu.be':
                video_id = parsed.path.lstrip('/')
        except:
            pass
    
    if len(video_id) != 11:
        print(json.dumps({"error": f"Invalid video ID: {video_id}"}))
        sys.exit(1)
    
    # Fetch transcript
    result = fetch_transcript_with_cookies(video_id, args.language, args.cookie_file)
    
    # Handle error
    if "error" in result:
        print(json.dumps(result))
        sys.exit(1)
    
    # Handle output format
    if args.text_only and args.timestamps:
        # Timestamped plain text
        output = result.get('timestamped_text', '')
    elif args.text_only:
        # Plain text only
        output = result.get('full_text', '')
    else:
        # Full JSON with metadata
        output = json.dumps(result, indent=2)
    
    # Save to file if requested
    if args.save_dir:
        os.makedirs(args.save_dir, exist_ok=True)
        base_path = os.path.join(args.save_dir, video_id)
        
        # Save JSON
        with open(f"{base_path}.json", 'w') as f:
            json.dump(result, f, indent=2)
        
        # Save timestamped text
        with open(f"{base_path}_timestamped.txt", 'w') as f:
            f.write(result.get('timestamped_text', ''))
        
        # Save plain text
        with open(f"{base_path}.txt", 'w') as f:
            f.write(result.get('full_text', ''))
    
    # Print output
    print(output)
    
    # Exit with success
    sys.exit(0)

if __name__ == '__main__':
    main()