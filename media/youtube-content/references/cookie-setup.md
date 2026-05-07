# YouTube Cookie Setup and IP Blocking Workarounds

## The Problem

YouTube aggressively blocks transcript requests from cloud provider IPs (AWS, GCP, Azure). This is a fundamental access restriction, not a temporary rate limit. When blocked, the API returns:

```json
{"error": "Could not retrieve a transcript for the video..."}
```

This affects all cloud IPs, including the environment where this agent runs. To fetch new transcripts, you must either:
- Route requests through a non-cloud IP (residential proxy/VPN)
- Use authenticated cookies from a real YouTube session
- Pre-fetch transcripts from a non-cloud machine

## Solution 1: Using YouTube Cookies (Recommended)

The most reliable workaround is to use cookies from a logged-in YouTube session. This makes requests appear as if they're coming from a real user.

### Step 1: Extract YouTube Cookies

1. Use Chrome/Firefox with a YouTube account that has watched videos (to ensure subtitles are available).
2. Install a cookie extraction extension (e.g., "Get cookies.txt" for Chrome or Firefox).
3. Navigate to youtube.com while logged in.
4. Run the extension and export cookies for `youtube.com`.
5. Save the cookies in Netscape format (the extension will provide this).

### Step 2: Save Cookies to File

Save the extracted cookies to a file, typically named `youtube.com_cookie.txt` in the agent's working directory or a known location.

The expected format is the standard Netscape cookie file format:

```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	1700000000	SESSION	IDS	SESSION_ID_VALUE
...
```

### Step 3: Configure the Agent

The youtube-transcript-api library supports cookies via the `cookies` parameter when creating a `YouTubeTranscriptApi` instance. However, the `fetch_transcript.py` script in this skill does not natively support cookies.

You have two options:

#### Option A: Modify fetch_transcript.py to Support Cookies

Edit `/opt/data/.hermes/skills/media/youtube-content/scripts/fetch_transcript.py`:

1. After importing `YouTubeTranscriptApi`, add:
   ```python
   from youtube_transcript_api import YouTubeTranscriptApi, cookies
   ```

2. In the `fetch_transcript` function, before creating the API instance, load cookies:
   ```python
   def fetch_transcript(video_id: str, languages: list = None, cookie_file: str = None):
       # ...
       # Load cookies if provided
       cookie_jar = None
       if cookie_file and os.path.exists(cookie_file):
           with open(cookie_file, 'r') as f:
               cookie_jar = cookies.CookieJar.from_netscape(f.read())
       
       # Create API with cookies
       if cookie_jar:
           api = YouTubeTranscriptApi(cookie_jar=cookie_jar)
       else:
           api = YouTubeTranscriptApi()
   ```

3. Update the argument parser to accept a `--cookie-file` option:
   ```python
   parser.add_argument('--cookie-file', type=str, help='Path to Netscape-format YouTube cookie file')
   ```

4. Pass the cookie file to the function:
   ```python
   args = parser.parse_args()
   # ...
   result = fetch_transcript(args.video_id, languages, args.cookie_file)
   ```

#### Option B: Use a Wrapper Script

Create a wrapper that sets cookies and calls the API directly:

```python
#!/usr/bin/env python3
import sys
import json
from youtube_transcript_api import YouTubeTranscriptApi, cookies
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('video_id')
    parser.add_argument('--language', default='en')
    parser.add_argument('--cookie-file', help='Path to cookie file')
    args = parser.parse_args()

    # Load cookies
    cookie_jar = None
    if args.cookie_file:
        with open(args.cookie_file, 'r') as f:
            cookie_jar = cookies.CookieJar.from_netscape(f.read())

    try:
        transcript_list = YouTubeTranscriptApi.get_transcripts(
            [args.video_id],
            languages=[args.language],
            cookie_jar=cookie_jar
        )
        # ... process and output as needed
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()
```

## Solution 2: Using a Residential Proxy or VPN

If cookies are not available or practical, route requests through a residential proxy:

1. Set up a proxy service (e.g., Bright Data, Oxylabs, Smartproxy) that provides residential IPs.
2. Configure the environment variables for the proxy:
   ```bash
   export HTTP_PROXY=http://proxy-user:proxy-pass@proxy-ip:proxy-port
   export HTTPS_PROXY=http://proxy-user:proxy-pass@proxy-ip:proxy-port
   ```
3. The underlying `requests` library used by youtube-transcript-api will automatically use these proxies.

## Solution 3: Pre-fetching Transcripts

For batch processing where real-time fetching is not required:

1. From a non-cloud machine (e.g., your home computer), run the fetch script for all backlog videos.
2. Copy the resulting transcript files to `/opt/data/.hermes/content/youtube-raw/`.
3. The agent will use the cached transcripts and bypass the IP block entirely.

## Verifying Cookie/Proxy Setup

After configuring cookies or proxy, test with:

```bash
# Test with cookie file
python fetch_transcript.py VIDEO_ID --cookie-file /path/to/cookies.txt

# Test with proxy environment variables set
python fetch_transcript.py VIDEO_ID
```

If successful, you should receive transcript JSON instead of an IP block error.

## Important Notes

- YouTube's terms of service prohibit automated access. Use cookies or proxies responsibly and at your own risk.
- Cookie files contain sensitive authentication data. Store them securely and never commit them to version control.
- Residential proxies may have rate limits. Monitor your usage to avoid being blocked.
- The IP block is persistent — once your cloud IP is blocked, it typically stays blocked. You must use one of these workarounds for all future requests.

## Troubleshooting

**"Invalid cookie file format"**: Ensure you're using Netscape format and that the file includes all necessary headers and fields.

**"Cookie authentication failed"**: The cookies may be expired or from an account without access to subtitles. Extract fresh cookies from an account that has watched videos.

**"Still getting IP block error after setting cookies"**: Some cloud IPs may be blocked even with cookies. Try a different workaround (proxy or pre-fetching).

## Best Practice for Automated Workflows

1. **Cache-first strategy**: Always check the local cache before attempting to fetch. If cached, use it.
2. **Cookie-based fetching**: For videos not in cache, use cookie authentication as the primary fetch method.
3. **Fallback to proxy**: If cookies fail, try a residential proxy.
4. **Skip on persistent failure**: If both cookie and proxy fail, log the video ID and continue — do not block the entire batch.
5. **Regular cookie refresh**: Cookies expire; set up a process to refresh them periodically.

## Related Files

- `/opt/data/.hermes/content/youtube-raw/` — Raw transcript cache
- `scripts/fetch_transcript.py` — Main fetch script (modify to add cookie support)
- `references/cookie-setup.md` — This document
- `scripts/cookie_fetch.py` — (Optional) A dedicated cookie-aware fetch script

## See Also

- youtube-transcript-api documentation: https://github.com/jdepoix/youtube-transcript-api
- Get cookies.txt extension: https://chrome.google.com/webstore/detail/get-cookiestxt/bgionfninlfaeghplihhkipjkjflcijm