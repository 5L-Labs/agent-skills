---
name: paper-publish
description: Workflow for publishing academic papers to a knowledge base or website
version: 1.0
author: Hermes Agent
tags: [publishing, papers, knowledge-base, markdown, arxiv]
related_skills: [paper-summary-workflow, arxiv, web-extract]
---

# Paper Publishing Workflow

## When to use this workflow
When you need to publish academic papers from a backlog to a public or private knowledge base, website, or documentation system. This workflow covers extracting metadata, generating summaries, and formatting for publication.

## Prerequisites
- Paper backlog file (JSON or markdown)
- Access to paper PDFs (local filesystem or URLs)
- Optional: arXiv API for metadata
- Optional: Summary content (generated or manual)

## Steps

### 1. Prepare the backlog
```python
# Load the backlog
from pathlib import Path
import json

backlog_file = Path("~/backlog/papers_backlog.json").expanduser()
with open(backlog_file, 'r') as f:
    backlog = json.load(f)
```

### 2. For each paper to publish:

#### a) Extract metadata
- Use arXiv ID if available to fetch title, authors, abstract, publication date
- Otherwise, extract from PDF filename or content

#### b) Generate or use existing summary
- Use paper-summary-workflow to create a concise summary
- Include key claims, contributions, and findings
- Note any limitations or nuances

#### c) Format for publication
Create a markdown file with the following structure:

```markdown
---
title: "Paper Title"
authors: Author1, Author2, Author3
date: YYYY-MM-DD
categories: [AI, ML, CV, NLP, etc.]
tags: [keyword1, keyword2]
arxiv: arXiv:ID [vVERSION]
---

## Summary

[2-3 sentence summary of the paper's main contribution]

## Key Claims

- Claim 1
- Claim 2
- Claim 3

## Methodology

[Description of the approach, architecture, or experiments]

## Results

- Key metrics and benchmarks
- Performance numbers
- Comparisons to baselines

## Limitations

- Known limitations
- Scope constraints
- Future work

## Thoughts

[Your analysis, connections to other work, potential applications]
```

### 3. Publish to destination
Depending on the target platform:

#### Static website (Hugo, Jekyll, etc.)
- Place markdown file in `content/papers/` directory
- Include front matter with metadata
- Add to table of contents or index page

#### Notion/Database
- Use API to create page in database
- Map fields: Title, Authors, Date, Summary, Tags, PDF Link

#### GitHub Wiki/GitHub Pages
- Commit markdown file to appropriate location
- Update index or listing pages

#### Obsidian Vault
- Place in papers folder with proper front matter
- Link to related notes

### 4. Update backlog status
Mark the paper as "published" in the backlog:
```python
paper["status"] = "published"
paper["published_at"] = datetime.datetime.now().isoformat()
paper["publication_url"] = "https://..."
```

## Automation Options

### Batch publishing
For 200+ papers, use a cron job or batch process:

```python
import json
from datetime import datetime

# Load backlog
with open('papers_backlog.json', 'r') as f:
    backlog = json.load(f)

# Process all unread papers
for paper in backlog["papers"]:
    if paper["status"] == "unread":
        publish_paper(paper)
        paper["status"] = "published"
        paper["published_at"] = datetime.now().isoformat()

# Save updated backlog
with open('papers_backlog.json', 'w') as f:
    json.dump(backlog, f, indent=2)
```

### Parallel processing
Use delegate_task to spawn multiple workers for large batches.

## Quality Control

1. **Verify metadata** - Ensure titles, authors, and arXiv IDs are correct
2. **Check summaries** - Make sure summaries accurately represent the paper
3. **Consistent formatting** - All published papers should follow the same template
4. **Link validation** - Ensure PDF links work and are accessible

## Error Handling

- Skip papers with missing PDFs
- Retry failed arXiv API calls
- Log errors and continue with next paper
- Alert on persistent failures

## Verification

After publishing:
- Check that the paper appears correctly in the destination
- Verify all links and metadata
- Spot-check random samples for accuracy

## Maintenance

- Regularly update backlog with new papers
- Re-run publishing process for new additions
- Clean up old or outdated publications
- Update summaries if better ones are generated