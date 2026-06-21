# translate

JSON-in/JSON-out translation pipe. Composable post-processor for the reader-skill family (`waytoagi`, `wsj`, future `nyt`/`ft`/etc).

## Install

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Use

```sh
waytoagi update-log | translate --target en
waytoagi update-log | translate --target en --backend noop   # echo only, no LLM
TRANSLATE_MODEL=qwen2.5:32b-instruct translate --target en < some.json
```

See `SKILL.md` for the full agent contract, exit codes, and backend list.
