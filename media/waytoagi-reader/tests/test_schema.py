"""Validate render() output against the published JSON schema."""
from __future__ import annotations

import json
from pathlib import Path

import sys

import jsonschema

from waytoagi_reader.update_log import render

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_blocks import SYNTH_BLOCKS  # noqa: E402

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "update_log.schema.json"


def _wire_synth_for_real_layout():
    """Match the real Feishu layout: bullets are children of the day heading."""
    blocks = {bid: {**b, "data": {**b["data"]}} for bid, b in SYNTH_BLOCKS.items()}
    blocks["root"]["data"]["children"] = ["h_target", "d_one", "d_two", "h_next"]
    blocks["d_one"]["data"]["children"] = ["i_one"]
    blocks["i_one"]["data"]["parent_id"] = "d_one"
    blocks["d_two"]["data"]["children"] = ["i_two"]
    blocks["i_two"]["data"]["parent_id"] = "d_two"
    return blocks


def test_render_output_matches_schema():
    schema = json.loads(SCHEMA_PATH.read_text())
    out = render(_wire_synth_for_real_layout(), heading="Foo日志", source_url="https://example/")
    jsonschema.validate(instance=out, schema=schema)


def test_render_not_found_matches_schema():
    schema = json.loads(SCHEMA_PATH.read_text())
    out = render(_wire_synth_for_real_layout(), heading="MissingNeedle", source_url="https://example/")
    jsonschema.validate(instance=out, schema=schema)


def test_flatten_output_matches_schema():
    """Reviewer-flagged P1: the --flatten shape must also validate against the
    published schema. The schema accepts either day-grouped or flat output via
    `oneOf` — this exercises the flat branch."""
    schema = json.loads(SCHEMA_PATH.read_text())
    base = render(_wire_synth_for_real_layout(), heading="Foo日志", source_url="https://example/")
    # Replicate the CLI's flatten transformation (cli.py:_cmd_update_log).
    flat = {
        "schema_version": 1,
        "source_url": base["source_url"],
        "heading": base["heading"],
        "heading_id": base["heading_id"],
        "items": [
            {**it, "day": d.get("heading"), "day_heading_id": d.get("heading_id")}
            for d in base["days"]
            for it in d.get("items", [])
        ],
    }
    jsonschema.validate(instance=flat, schema=schema)
