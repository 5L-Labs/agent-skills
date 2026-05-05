---
name: paper-vocabulary-analyzer
description: Scan papers for specialist language, score concepts, and generate daily reviews
version: 1.0
author: Hermes Agent
tags: [vocabulary, papers, specialist-language, flashcards, daily-review]
related_skills: [paper-publish, arxiv, web-search]
---

# Paper Vocabulary Analyzer

## When to use this workflow
When you need to systematically extract, score, and learn specialist vocabulary from academic papers. This workflow helps identify key concepts, understand their relationships, and build a daily review process for mastering technical terminology.

## Prerequisites
- Paper PDFs (from backlog or local files)
- Text extraction tools (pdftotext, pdfplumber, or similar)
- Access to web search for frequency analysis
- Review system (flashcards, quizzes, or daily prompts)

## Steps

### 1. Extract Text from Papers
```python
import pdfplumber
import os
from pathlib import Path

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        # Fallback to system pdftotext
        import subprocess
        try:
            result = subprocess.run(['pdftotext', str(pdf_path), '-'], 
                                  capture_output=True, text=True)
            text = result.stdout
        except:
            pass
    return text
```

### 2. Identify Candidate Terms
```python
import re
from collections import Counter

def find_candidate_terms(text, min_length=5, min_frequency=2):
    # Remove common stop words and boilerplate
    stop_words = set(["abstract", "introduction", "conclusion", "section", "figure", "table", 
                      "algorithm", "method", "result", "experiment", "dataset", "model"])
    
    # Find acronyms (ALL CAPS or with numbers)
    acronym_pattern = r'\b[A-Z0-9]{2,}\b'
    acronyms = re.findall(acronym_pattern, text)
    
    # Find technical terms (words not in common vocabulary)
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    word_counts = Counter(words)
    
    # Filter out common words
    with open('common_words.txt', 'r') as f:
        common = set(f.read().splitlines())
    
    technical_terms = [word for word, count in word_counts.items() 
                      if count >= min_frequency and word not in common and word not in stop_words]
    
    return acronyms + technical_terms
```

### 3. Analyze Each Term
For each candidate term, determine:

#### a) Paper-specificity
```python
def is_paper_specific(term, paper_text, other_papers_dir):
    """Check if term appears only in this paper."""
    # Search in current paper
    in_current = term.lower() in paper_text.lower()
    
    # Search in other papers
    other_count = 0
    for other_pdf in Path(other_papers_dir).rglob("*.pdf"):
        if other_pdf.name != Path(paper_path).name:
            other_text = extract_text_from_pdf(str(other_pdf))
            if term.lower() in other_text.lower():
                other_count += 1
    
    return other_count == 0 and in_current
```

#### b) Cross-references
```python
def find_cross_references(term, text):
    """Look for mentions of other papers or definitions."""
    # Check for citation patterns (e.g., [1], (Smith et al., 2023))
    citation_pattern = r'\[[0-9]+\]|\(([A-Za-z]+\s+[A-Za-z]+,\s+\d{4})\)'
    citations = re.findall(citation_pattern, text)
    
    # Check for phrases like "as defined in", "see [1]", etc.
    ref_patterns = [
        r'as defined in\s+\[(\d+)\]',
        r'see\s+\[(\d+)\]',
        r'from\s+\[(\d+)\]',
        r'(?:Proposition|Definition|Theorem)\s+\d+'
    ]
    
    references = []
    for pattern in ref_patterns:
        refs = re.findall(pattern, text, re.IGNORECASE)
        references.extend(refs)
    
    return citations, references
```

#### c) Frequency Analysis
```python
def assess_frequency(term):
    """Determine how common the term is."""
    # Check everyday frequency via web search
    everyday_result = web_search(f"\"{term}\" definition meaning", limit=5)
    everyday_common = len(everyday_result) > 0
    
    # Check ML/programming frequency
    ml_result = web_search(f"\"{term}\" machine learning", limit=5)
    programming_result = web_search(f"\"{term}\" programming", limit=5)
    
    everyday_freq = "high" if everyday_common else "low"
    ml_freq = "high" if len(ml_result) > 0 or len(programming_result) > 0 else "low"
    
    return everyday_freq, ml_freq
```

### 4. Score and Rank Terms
```python
def score_term(term_info):
    """
    Score terms based on obscurity and independence.
    Higher score = more obscure/independent.
    Lower score = more common/cross-referenced.
    """
    score = 0
    
    # Paper-specificity (0 if not specific, 1 if paper-specific)
    if term_info['paper_specific']:
        score += 3
    
    # Cross-references (0 if has references, -1 if no references)
    if not term_info['cross_references']:
        score -= 1
    else:
        score -= len(term_info['cross_references'])
    
    # Frequency (0 if high frequency, +1 for low everyday, +1 for low ML)
    if term_info['everyday_frequency'] == 'low':
        score += 1
    if term_info['ml_frequency'] == 'low':
        score += 1
    
    return score

def rank_terms(terms):
    """Rank terms by score (lower is better) and then by frequency."""
    return sorted(terms, key=lambda x: (score_term(x), x['everyday_frequency'], x['ml_frequency']))
```

### 5. Generate Layman Explanations
```python
def generate_layman_explanation(term, domain):
    """Create a high school-level explanation."""
    explanations = {
        'mathematics': {
            'gradient': 'The rate and direction of fastest increase of a function, like the slope of a hill',
            'derivative': 'How much a function changes as its input changes, like speed being the derivative of position',
            'matrix': 'A rectangular grid of numbers, like a spreadsheet',
            'eigenvalue': 'A special number associated with a matrix that describes how it stretches space'
        },
        'computer science': {
            'algorithm': 'A step-by-step recipe for solving a problem',
            'data structure': 'A way of organizing and storing data for efficient access',
            'recursion': 'When a function calls itself to solve smaller instances of the same problem',
            'hash table': 'A data structure that maps keys to values using a hash function'
        },
        'machine learning': {
            'neural network': 'A computing system inspired by biological brains, made of interconnected nodes',
            'training': 'The process of teaching a model by showing it many examples',
            'overfitting': 'When a model learns training data too well and fails on new data',
            'regularization': 'A technique to prevent overfitting by adding constraints'
        },
        'mathematics (linear algebra)': {
            'vector': 'A quantity with both magnitude and direction, often represented as an arrow',
            'tensor': 'A generalization of vectors and matrices to higher dimensions'
        }
    }
    
    domain_terms = explanations.get(domain, {})
    if term.lower() in domain_terms:
        return domain_terms[term.lower()]
    
    # Fallback: use web search to find simple definition
    try:
        result = web_search(f"\"{term}\" simple definition for kids", limit=3)
        if result:
            # Extract a simple definition from results
            for item in result:
                if 'definition' in item['description'].lower():
                    return item['description'].split(':')[-1].strip()
    except:
        pass
    
    return f"A technical term from the {domain} domain"
```

### 6. Daily Review System
```python
def generate_daily_review(terms, count=5):
    """Generate a daily review set with questions."""
    import random
    
    review_set = random.sample(terms, min(count, len(terms)))
    
    review_questions = []
    for term in review_set:
        question = {
            'term': term['term'],
            'question_type': random.choice(['definition', 'explanation', 'example']),
            'options': generate_distractors(term),
            'answer': term['layman_explanation']
        }
        review_questions.append(question)
    
    return review_questions

def generate_distractors(term):
    """Generate multiple-choice distractors."""
    # This would use related terms or common misconceptions
    return ["Option A", "Option B", "Option C"]
```

## Automation Options

### Batch Processing
For 200+ papers, use a cron job or batch process:

```python
# Process all papers in backlog
for paper in backlog["papers"]:
    if paper["status"] == "unread":
        analyze_paper(paper)
        paper["status"] = "processed"
```

### Parallel Processing
Use delegate_task to spawn multiple workers for large batches.

## Quality Control

1. **Verify term extraction** - Ensure terms are correctly identified
2. **Check explanations** - Make sure layman explanations are accurate
3. **Consistent scoring** - All terms should be scored using same rubric
4. **Link validation** - Ensure cross-references are correctly identified

## Error Handling

- Skip papers with extraction errors
- Retry failed web searches
- Log errors and continue with next paper
- Alert on persistent failures

## Verification

After processing:
- Check that terms are correctly categorized
- Verify layman explanations make sense
- Spot-check random samples for accuracy

## Maintenance

- Regularly update term database with new papers
- Re-run scoring as more papers are processed
- Update explanations based on feedback
- Clean up outdated or incorrect entries

## Daily Review Process

1. Generate daily review questions
2. Present to user for self-assessment
3. Track performance over time
4. Adjust difficulty based on mastery