import pytest
import os
import sys
from pathlib import Path

# Add scripts to path to import secrets module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import secrets as s

@pytest.fixture
def mock_store(tmp_path):
    # Set up mock secret store
    store_root = tmp_path / "secrets"
    store_root.mkdir()

    # Valid secret file
    secret_file = store_root / "test.secret"
    secret_file.write_text("my_super_secret")

    # Secret in subdir
    subdir = store_root / "group"
    subdir.mkdir()
    sub_secret = subdir / "sub.secret"
    sub_secret.write_text("my_sub_secret")

    # Outside file to attempt to traverse to
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("sensitive_outside_data")

    # Patch STORE_ROOT
    original_store = s.STORE_ROOT
    s.STORE_ROOT = store_root
    yield store_root
    s.STORE_ROOT = original_store

def test_resolve_valid_secret(mock_store):
    path = s._resolve("test.secret")
    assert path.name == "test.secret"
    assert "my_super_secret" in path.read_text()

def test_resolve_subdir_secret(mock_store):
    # Testing that implicit subdir search works
    path = s._resolve("sub.secret")
    assert path.name == "sub.secret"
    assert "my_sub_secret" in path.read_text()

def test_resolve_path_traversal_direct(mock_store):
    with pytest.raises(ValueError, match="Attempted path traversal for secret"):
        s._resolve("../outside.txt")

def test_resolve_path_traversal_from_subdir(mock_store):
    with pytest.raises(ValueError, match="Attempted path traversal for secret"):
        s._resolve("group/../../outside.txt")

def test_resolve_not_found(mock_store):
    with pytest.raises(FileNotFoundError):
        s._resolve("does_not_exist.secret")
