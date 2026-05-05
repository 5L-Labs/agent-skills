#!/usr/bin/env python3
"""Generate Luna-style digest from timestamped transcript."""
import re
import sys

USAGE = "Usage: generate_luna_digest.py <timestamped_transcript_file>"


def strip_timestamp(line):
    """Remove timestamp prefix like 0:05, 12:34, 1:02:05 from a line."""
    return re.sub(r'^\d{1,2}:\d{2}(:\d{2})?\s+', '', line)


def extract_sentences(text):
    """Split text into sentences, filter noise."""
    # Split on sentence-ending punctuation followed by space or end
    sentences = re.split(r'(?<=[.!?])\s+', text)
    cleaned = []
    for s in sentences:
        s = s.strip()
        # Filter out very short or non-sentence fragments
        if len(s) > 20 and not s.startswith(('http', 'www', '@', '#')):
            cleaned.append(s)
    return cleaned


def group_sentences_into_sections(sentences, target_sections=4):
    """Group sentences into roughly equal thematic sections."""
    n = len(sentences)
    if n == 0:
        return []
    # Aim for 3-6 sections
    per_section = max(2, n // target_sections)
    sections = []
    for i in range(0, n, per_section):
        chunk = ' '.join(sentences[i:i + per_section])
        if chunk.strip():
            sections.append(chunk.strip())
    return sections


def make_bullets(text, max_chars=120, max_bullets=3):
    """Break text into short bullet points."""
    sentences = extract_sentences(text)
    bullets = []
    current = []
    current_len = 0

    for s in sentences:
        if current_len + len(s) > max_chars and current:
            bullets.append(' '.join(current))
            current = [s]
            current_len = len(s)
        else:
            current.append(s)
            current_len += len(s) + 1

        if len(bullets) >= max_bullets:
            break

    if current and len(bullets) < max_bullets:
        bullets.append(' '.join(current))

    return bullets[:max_bullets]


def generate_digest(input_file):
    """Read transcript, produce Luna-style digest to stdout."""
    try:
        with open(input_file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # Extract timestamped lines (lines that look like transcripts)
    timestamped = []
    for line in lines:
        stripped = strip_timestamp(line)
        if stripped != line and stripped.strip():
            timestamped.append(stripped)

    if not timestamped:
        print("Error: no timestamped lines found", file=sys.stderr)
        sys.exit(1)

    # Join all text
    full_text = ' '.join(ts.strip() for ts in timestamped)
    sentences = extract_sentences(full_text)

    if not sentences:
        print("Error: no sentences found after parsing", file=sys.stderr)
        sys.exit(1)

    sections = group_sentences_into_sections(sentences, target_sections=4)

    # Build Luna digest
    print(f"[Unknown Video] transcript (what matters):")

    for i, section_text in enumerate(sections):
        bullets = make_bullets(section_text)
        for bullet in bullets:
            print(f"    -    {bullet}")
        if i < len(sections) - 1:
            print()

    print()
    print("    -    Big insight:")
    print("    -    See above sections for key points and takeaways.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(USAGE, file=sys.stderr)
        sys.exit(1)
    generate_digest(sys.argv[1])
