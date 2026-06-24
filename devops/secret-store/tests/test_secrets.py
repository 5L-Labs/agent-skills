import pytest
from pathlib import Path
import importlib.util

# Load the secrets module dynamically as its name conflicts with stdlib `secrets`
spec = importlib.util.spec_from_file_location("secrets_store", "devops/secret-store/scripts/secrets.py")
secrets_store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(secrets_store)

def test_resolve_path_traversal():
    with pytest.raises(ValueError, match="Path traversal detected"):
        secrets_store._resolve("../../../../etc/passwd")

def test_resolve_valid_path(monkeypatch, tmp_path):
    # Mock STORE_ROOT
    monkeypatch.setattr(secrets_store, "STORE_ROOT", tmp_path)

    # Create dummy secret file
    secret_file = tmp_path / "mysecret.txt"
    secret_file.write_text("topsecret")

    resolved_path = secrets_store._resolve("mysecret.txt")
    assert resolved_path == secret_file

def test_resolve_valid_path_in_subdir(monkeypatch, tmp_path):
    # Mock STORE_ROOT
    monkeypatch.setattr(secrets_store, "STORE_ROOT", tmp_path)

    # Create dummy secret file in subdir
    subdir = tmp_path / "myapp"
    subdir.mkdir()
    secret_file = subdir / "mysecret.txt"
    secret_file.write_text("topsecret")

    resolved_path = secrets_store._resolve("mysecret.txt")
    assert resolved_path == secret_file

def test_resolve_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(secrets_store, "STORE_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        secrets_store._resolve("nonexistent.txt")
