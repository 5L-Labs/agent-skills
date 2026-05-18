---
name: ft-saved-articles-digest/references/archive-format
description: >
  Canonical format for raw article files in ~/.hermes/content/ft-raw/.
  Filenames are date-stamped then numbered, one per article.
  Digest is YYYY-MM-DD-digest.md.
---

## Per-article raw file

Naming: `YYYY-MM-DD-NN-{slug}.md`

NN = two-digit sequence number (01 … 10)
slug = lowercase-hyphenated version of article headline, stopwords stripped

Front-matter block (NOT YAML, just markdown text):
```md
# Full Article Headline

Source: <source name>
Authors: First Last, · <platform>
URL: https://www.ft.com/content/<uuid>
```

Body: Retrieve what's visible — this will be truncated at the paywall for
non-subscribers. Note [PAYWALL] if full content wasn't retrievable, and
include the visible teaser verbatim if it's a unique quote.

## Digest file

Naming: `YYYY-MM-DD-digest.md`

Prepend with a date header and refresh instructions. List chunk per sorted
NN order. 15 or fewer articles: treat as a "bulletin" style mailing; 16+
should be compressed to news highlights.

## Example snippet (from 2026-05-15)

```
# Starmer leadership crisis worsens as health secretary quits

Source: AP News
Date: May 14, 2026
URL: https://apnews.com/article/britain-politics-starmer-streeting-rayner-...

Prime minister faces intense pressure after more than 70 MPs call ...
```
