# Batch Audit Discrepancy Patterns

Shorthand diagnostic table: when `reconcile_batch_state.py` returns
exit-code 1, the Psychoanalyze block describes the symptom; the cause
and fix are listed here.

| Psychoanalyze message | Root cause | Fix |
|---|---|---|
| `backlog unique_videos >> playlist DONE` | Playlist missed entries when previous run skipped backfill | Run `Playlist backfill` section; add `\tDONE` for every missing ID |
| `N IDs in backlog have no valid raw transcript` (N == stub) | Stubs already present in `youtube-raw/` but audit can't confirm they match backlog | Run **backfill-stub-check**: verify every stub file's `video_id` header is in `unique_videos` |
| `playlist has 1 IDs not yet marked DONE` | New entry in `unique_videos` has no playlist line yet | `echo "${VID}\tDONE"` → append in **Python**, not bash `echo`, to avoid literal `\t` bug |
| `confirmed_permanent no stub file` > 0 | `failed_videos` has a permanent-failure ID with no corresponding `_transcript.txt` on disk | Write an intentionally-stub file (220 bytes minimal) before marking DONE |
| `N IDs not accounted for` but script appears idle | All three sources agree but `reconcile_batch_state.py` showed 0 raw files | `glob` bug: install/fresh-script has `f'{RAW_DIR}*_transcript.txt'` instead of `os.path.join`; patch and re-run |

## Backfill-stub-check routine

Use this when the audit shows stub count but some stubs may not be tied to
`failed_videos` entries:

```python
import json, glob, os

BACKLOG = '/opt/data/content/yt-backlog.json'
RAW_DIR = '/opt/data/content/youtube-raw/'

with open(BACKLOG) as f:
    bl = json.load(f)
fv_ids = {v['video_id'] for v in bl['failed_videos'] if v['status'] == 'confirmed_permanent'}

stub_files = [f for f in glob.glob(os.path.join(RAW_DIR, '*_transcript.txt')) if is_stub(f)]
stub_ids   = {os.path.basename(f).replace('_transcript.txt', '') for f in stub_files}

untracked = stub_ids - fv_ids
for vid in sorted(untracked):
    print(f"STUB NOT LOGGED as confirmed_permanent: {vid}")
```

If `untracked` is non-empty, decide whether each represents a genuine
video that needs a `confirmed_permanent` entry, or a stale stub that can
be discarded.
