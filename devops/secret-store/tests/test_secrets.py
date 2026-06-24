from pathlib import Path
import pytest
import importlib.util

def load_local_secrets_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "secrets.py"
    spec = importlib.util.spec_from_file_location("local_secrets", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

sec = load_local_secrets_module()

def test_resolve_path_traversal(tmp_path):
    sec.STORE_ROOT = tmp_path

    with pytest.raises(PermissionError):
        sec._resolve("../../etc/passwd")

def test_resolve_absolute_path(tmp_path):
    sec.STORE_ROOT = tmp_path

    with pytest.raises(PermissionError):
        sec._resolve("/etc/passwd")

def test_resolve_valid(tmp_path):
    sec.STORE_ROOT = tmp_path
    secret_file = tmp_path / "my_secret"
    secret_file.write_text("hello")

    path = sec._resolve("my_secret")
    assert path.name == "my_secret"
