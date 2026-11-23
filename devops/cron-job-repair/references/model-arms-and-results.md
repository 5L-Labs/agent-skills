# Model arms and measured results (this host)

Arms are defined in `scripts/cron-model-bench.py`:

- `default` — `--unpin --provider nous`: the job rides `model.default` from
  config.yaml (`deepseek/deepseek-v4.1-flash` at the time of writing).
- `qwen` — `--model qwen3.8-27b-instruct --provider ollama-qwen3.6:27b --pin`
  (the local inference box, `http://host.containers.internal:11434/v1`).
- `inkling` — `--model inkling-mini --provider ollama-qwen3.6:27b --pin`.
  The bare name resolves; `openai/inkling-mini` 404s on that endpoint.

## Findings that generalise

- **Unpinning is the cheapest fix for a dead pin.** A job pinned to a model
  without credits fails in ~1.3 s with HTTP 404; unpinned it runs normally on the
  config default.
- **Local qwen works but misreports.** On the Jira reminder job it finished in
  117 s (4.7x the hosted default's 25 s), ran the tool call correctly, then
  printed header counts that disagreed with the list under them and leaked
  "Let me format the daily reminder" into the delivered text. Timings alone would
  have called this arm a success.
- **Local inkling-mini cannot read these jobs.** With `inkling-mini` the run dies
  with `conversation has grown too long for inkling-mini to read`; a 30k-token
  probe succeeds, so its usable context is small. Large agent jobs are the wrong
  fit for it.
- **`prompt_tokens` is a sum over turns.** Audit rows showing 1.5M-3.5M tokens
  are the total across an agent run, not one context window. Budget on the total;
  diagnose context ceilings on the largest single turn.
- **A run that looks hung is usually loading.** Cold-loading a 27B model takes
  minutes before the first token; wait on the audit row rather than cancelling.

## Per-job verdicts

Recorded per job in `/opt/data/cache/cron-model-bench/results.jsonl`
(`duration_ms`, `prompt_tokens`, `completion_tokens`, `error`, output path).
Re-run the harness after any prompt or model change — the numbers move.
