#!/usr/bin/env python3
"""Smoke test for generate_luna_digest.py — pass a sample file and check output."""
import subprocess
import sys
import tempfile
import os

SAMPLE_TRANSCRIPT = """0:05 This is the opening sentence of a video about machine learning.
0:30 Deep learning models have transformed the field of natural language processing.
1:05 Transformers use attention mechanisms to process sequences in parallel.
1:30 The key innovation is self-attention, which allows each token to attend to all others.
2:00 This enables capturing long-range dependencies without sequential processing.
2:30 BERT and GPT are two dominant architectures based on transformers.
3:00 Pretraining on large corpora followed by fine-tuning is the standard approach.
3:30 Applications include translation, summarization, question answering, and code generation.
4:00 Future work focuses on efficiency, robustness, and multi-modal understanding.
"""

def main():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(SAMPLE_TRANSCRIPT)
        tmp = f.name

    try:
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'generate_luna_digest.py'), tmp],
            capture_output=True, text=True
        )
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print("EXIT CODE:", result.returncode)
        if result.returncode == 0 and result.stdout.strip():
            print("PASS: script produced output")
        else:
            print("FAIL: script produced no output or non-zero exit")
            sys.exit(1)
    finally:
        os.unlink(tmp)


if __name__ == '__main__':
    main()
