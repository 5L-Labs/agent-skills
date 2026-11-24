#!/usr/bin/env python3
"""Fixture-based regression tests for generate_baseline.py.

Run:  /usr/bin/python3 scripts/test_generate_baseline.py

Each fixture is a tiny skill written into a temp directory at test time, so the
suite needs no checked-in corpus and finishes in about a second. Every check
below pins a bug that reached review at least once.

Author: Hermes Agent 01
"""
import importlib.util
import os
import pathlib
import shutil
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("generate_baseline",
                                              HERE / "generate_baseline.py")
assert _spec is not None and _spec.loader is not None
gb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gb)

TOOLSETS_PY = '''
_HERMES_CORE_TOOLS = ["read_file", "write_file", "search_files", "terminal", "web_search"]
TOOLSETS = {
    "web": _ts("web", ["web_search", "web_extract"]),
    "terminal": _ts("shell", ["terminal", "process_manage"]),
    "file": _ts("files", ["read_file", "write_file", "search_files"]),
    "delegation": _ts("children", ["delegate_task"]),
    "code_execution": _ts("python", ["execute_code"]),
}
'''


def skill(body, platforms="[linux, macos]"):
    return f"---\nname: fixture\ndescription: fixture\nplatforms: {platforms}\n---\n\n{body}\n"


FIXTURES = {
    # no network, no credentials, local commands only
    "narrow-demo": skill(
        "# Narrow\n\nUse `terminal` to run the local script.\n\n"
        "```bash\npython3 scripts/report.py --out report.json\n```\n"),

    # a fixed host reached from a command: medium, and `terminal` must be seen
    "medium-demo": skill(
        "# Medium\n\nUse `terminal` to fetch the metrics.\n\n"
        "```bash\ncurl -sS https://api.datadoghq.com/api/v1/metrics\n```\n"),

    # open-world egress through a Hermes tool
    "wide-demo": skill(
        "# Wide\n\nUse `web_extract` to read the page the user names.\n"),

    # delegation: the child's toolset is not pinned at Stage 1
    "delegating-demo": skill(
        "# Delegating\n\nHand the work to `delegate_task` and wait.\n"),

    # a local app reached through AppleScript in a command
    "localapp-demo": skill(
        "# Local app\n\n```bash\nosascript -e 'tell application \"Messages\" "
        "to send \"running late\"'\n```\n",
        platforms="[macos]"),

    # prose that must never be read as tools or runtime hosts
    "prose-demo": skill(
        "# Prose\n\nOpen your web browser and read the file. "
        "See [the docs](https://docs.python.org/3/library/socket.html) for "
        "whois and telnet notes. Use `search_files` to find it.\n"),

    # a raw socket used in real code
    "socket-demo": skill(
        "# Socket\n\n```python\nimport socket\n"
        "s = socket.create_connection((\"whois.iana.org\", 43))\n```\n"),
}


class GeneratorFixtureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gb-fixture-")
        for name, body in FIXTURES.items():
            d = os.path.join(self.tmp, "skills", name)
            os.makedirs(d)
            with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as fh:
                fh.write(body)
        with open(os.path.join(self.tmp, "toolsets.py"), "w", encoding="utf-8") as fh:
            fh.write(TOOLSETS_PY)
        gb.__dict__["TOOL_VOCAB_SOURCE"] = "builtin-fallback"
        gb.load_tool_vocabulary(self.tmp)
        self.commit = "a" * 40

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def scan(self, name):
        manifest, evidence = gb.scan_skill(self.tmp, f"skills/{name}", self.commit)
        return manifest, evidence

    @staticmethod
    def reach(manifest, tool):
        for entry in manifest["tools"]:
            if entry["name"] == tool:
                return entry["reach"]
        return None

    # --- vocabulary ------------------------------------------------------
    def test_vocabulary_comes_from_toolsets_py(self):
        self.assertEqual(gb.TOOL_VOCAB_SOURCE, "toolsets.py")
        self.assertIn("terminal", gb.ALL_TOOLS)
        self.assertIn("execute_code", gb.ALL_TOOLS)
        self.assertIn("delegate_task", gb.ALL_TOOLS)
        # toolset names are not tools
        self.assertNotIn("file", gb.ALL_TOOLS)
        self.assertNotIn("web", gb.ALL_TOOLS)

    # --- 1. shell tools are detected -------------------------------------
    def test_terminal_is_detected_with_egress_reach(self):
        manifest, _ = self.scan("medium-demo")
        self.assertIn("terminal", {t["name"] for t in manifest["tools"]})
        reach = self.reach(manifest, "terminal")
        assert reach is not None, "terminal must be recorded"
        self.assertGreaterEqual(
            {"narrow": 0, "medium": 1, "wide": 2}[reach], 1,
            "a skill with a curl command must record terminal reach >= medium")

    def test_narrow_skill_has_narrow_terminal(self):
        manifest, _ = self.scan("narrow-demo")
        self.assertEqual(manifest["shape"], "narrow")
        self.assertEqual(self.reach(manifest, "terminal"), "narrow")

    def test_medium_skill_is_medium(self):
        manifest, _ = self.scan("medium-demo")
        self.assertEqual(manifest["shape"], "medium")
        self.assertIn("api.datadoghq.com",
                      [h["host"] for h in manifest["resources"]["network"]["runtime"]])

    # --- 2. delegate_task is not narrow ----------------------------------
    def test_delegate_task_inherits_and_floors_at_medium(self):
        manifest, _ = self.scan("delegating-demo")
        self.assertEqual(self.reach(manifest, "delegate_task"), "inherits")
        self.assertEqual(manifest["delegation"],
                         {"inherits": "inherits-toolsets", "rule": "narrow-only"})
        self.assertIn(manifest["shape"], ("medium", "wide"))

    # --- 3. local_apps is a vocabulary, not a raw line -------------------
    def test_local_apps_uses_fixed_vocabulary(self):
        manifest, _ = self.scan("localapp-demo")
        apps = manifest["resources"]["local_apps"]
        self.assertIn({"name": "Messages", "syncs_to": "iCloud/SMS"}, apps)
        for entry in apps:
            name = entry["name"]
            self.assertLess(len(name), 40, f"local_apps entry is a copied line: {name!r}")
            for ch in "\n#?\"'":
                self.assertNotIn(ch, name)

    def test_local_apps_needs_code_context(self):
        manifest, _ = self.scan("prose-demo")
        self.assertEqual(manifest["resources"]["local_apps"], [])

    # --- wide reach ------------------------------------------------------
    def test_wide_tool_makes_wide(self):
        manifest, _ = self.scan("wide-demo")
        self.assertEqual(manifest["shape"], "wide")
        self.assertEqual(self.reach(manifest, "web_extract"), "wide")

    # --- prose is not a tool, docs are not a host ------------------------
    def test_prose_words_are_not_tools(self):
        manifest, _ = self.scan("prose-demo")
        names = {t["name"] for t in manifest["tools"]}
        self.assertEqual(names, {"search_files"})
        self.assertEqual(manifest["resources"]["network"]["runtime"], [])
        self.assertEqual(manifest["shape"], "narrow")

    def test_raw_sockets_need_code_context(self):
        prose, _ = self.scan("prose-demo")
        self.assertFalse(prose["resources"]["network"]["raw_sockets"])
        code, _ = self.scan("socket-demo")
        self.assertTrue(code["resources"]["network"]["raw_sockets"])
        # a raw socket alone is a flag, not open-world egress
        self.assertNotEqual(code["shape"], "wide")

    # --- stage-1 invariants ---------------------------------------------
    def test_ceiling_is_null_at_static(self):
        for name in FIXTURES:
            manifest, _ = self.scan(name)
            self.assertIsNone(manifest["ceiling"], name)
            self.assertEqual(manifest["provenance"]["method"], "static")
            self.assertLessEqual(manifest["provenance"]["confidence"], 0.5)

    def test_inputs_are_recorded(self):
        manifest, _ = self.scan("medium-demo")
        inputs = manifest["provenance"]["inputs"]
        for key in ("files_scanned", "files_skipped", "hosts_runtime", "hosts_setup",
                    "tools", "review", "dynamic", "backtest"):
            self.assertIn(key, inputs)

    def test_platforms_fall_back_to_frontmatter(self):
        manifest, _ = self.scan("localapp-demo")
        self.assertEqual(manifest["resources"]["hardware"]["platforms"], ["macos"])

    def test_actions_drafted_for_detected_write(self):
        manifest, _ = self.scan("socket-demo")
        for action in manifest["actions"]:
            self.assertIn(action["class"],
                          ("read", "draft", "write-shared", "irreversible"))
            self.assertIn(action["review_gate"], ("autorun", "human"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
