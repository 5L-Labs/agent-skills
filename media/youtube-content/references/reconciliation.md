# State Reconciliation Pattern for Batch YouTube Processing

When processing videos in batch from a playlist or backlog, three sources of truth must be reconciled:

1. **Playlist file** (`playlist-new-ids.txt`): Lists videos to process, may have DONE markers
2. **Backlog JSON** (`yt-backlog.json`): Records permanently processed and failed videos
3. **Raw files on disk** (`youtube-raw/*_transcript.txt`): The actual saved transcripts

These sources can diverge. The DONE marker is only a label; trust the file system. The backlog `failed_videos` array uses mixed keys (`id` vs `video_id`).

## Canonical Reconciliation Code

```python
import json
import os
import glob

def reconcile_state(playlist_path, backlog_path, raw_dir):
    """Return dict with keys: to_process, already_done, failed, orphaned."""
    
    # 1. Parse playlist
    playlist_videos = []  # list of {id, title, done_marker}
    with open(playlist_path) as f:
        for line in f:
            line = line.rstrip()
            if not line.strip():
                continue
            parts = line.split('\t')
            vid = parts[0].strip()
            title = parts[1].strip() if len(parts) > 1 else ''
            done = title.endswith(' DONE')
            if done:
                title = title[:-5].strip()
            playlist_videos.append({'id': vid, 'title': title, 'done_marked': done})
    
    playlist_ids = {v['id'] for v in playlist_videos}
    
    # 2. Read backlog
    with open(backlog_path) as f:
        backlog = json.load(f)
    
    processed = set(backlog.get('unique_videos', []))
    
    failed_list = backlog.get('failed_videos', [])
    failed = set()
    for item in failed_list:
        vid = item.get('id') or item.get('video_id')
        if vid:
            failed.add(vid)
    
    # 3. Inspect raw files
    raw_files = glob.glob(os.path.join(raw_dir, '*_transcript.txt'))
    raw_ids = set()
    for f in raw_files:
        basename = os.path.basename(f)
        if basename.endswith('_transcript.txt'):
            raw_ids.add(basename.replace('_transcript.txt', ''))
    
    # 4. Reconcile
    to_process = (playlist_ids - processed - failed) & raw_ids
    # Actually check file existence for DONE-marked ones too
    for v in playlist_videos:
        if v['done_marked'] and v['id'] not in raw_ids:
            # DONE marker but no file — treat as needing processing
            to_process.add(v['id'])
    
    already_done = playlist_ids & raw_ids & processed
    orphaned = raw_ids - processed
    
    return {
        'to_process': sorted(to_process),
        'already_done': sorted(already_done),
        'failed_in_backlog': sorted(failed),
        'orphaned_transcripts': sorted(orphaned),
        'playlist': playlist_videos
    }

# Usage
state = reconcile_state(
    '/opt/data/content/playlist-new-ids.txt',
    '/opt/data/content/yt-backlog.json',
    '/opt/data/content/youtube-raw/'
)

print(f"To process: {len(state['to_process'])}")
print(f"Already done: {len(state['already_done'])}")
print(f"Failed (in backlog): {len(state['failed_in_backlog'])}")
print(f"Orphaned transcripts: {len(state['orphaned_transcripts'])}")
```

## File Naming Convention

All transcript-related files use the pattern:
```
youtube-raw/{VIDEO_ID}_{suffix}.{ext}
```
Where suffix is one of:
- `transcript` → timestamped transcript (`[MM:SS] text` per line)
- `fulltext` → plain text without timestamps
- `meta` → JSON metadata (video_id, title, segments count, duration)

Example: `wjJG8ga63lQ_transcript.txt`, `wjJG8ga63lQ_fulltext.txt`, `wjJG8ga63lQ_meta.json`

## Backlog Schema Notes

`failed_videos` entries are not uniform:
```json
[
  {"id": "Iu4gEnZFQz8", "reason": "...", ...},
  {"video_id": "fsLh-NYhOoU", "reason": "...", ...}
]
```
Always use: `vid = item.get('id') or item.get('video_id')`
