from __future__ import annotations
import os

from news_reader_base import load_dotenv


def test_load_dotenv_from_skill_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("READER_TEST_KEY", raising=False)
    (tmp_path / ".env").write_text('READER_TEST_KEY="value-1"\n# comment\n')
    load_dotenv(tmp_path)
    assert os.environ["READER_TEST_KEY"] == "value-1"


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("READER_TEST_KEY", "preset")
    (tmp_path / ".env").write_text("READER_TEST_KEY=fromfile\n")
    load_dotenv(tmp_path)
    assert os.environ["READER_TEST_KEY"] == "preset"


def test_load_dotenv_missing_file_is_noop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    load_dotenv(tmp_path / "does-not-exist")  # should not raise
