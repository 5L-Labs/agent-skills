import json

import pytest
import responses

from wsj_reader.cli import main


@responses.activate
def test_headlines_cli_defaults_to_homepage_without_cookie(monkeypatch, tmp_path, fx, capsys):
    monkeypatch.setenv("WSJ_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("WSJ_COOKIE", raising=False)
    responses.add(
        responses.GET,
        "https://www.wsj.com/",
        body=fx("homepage.html"),
        status=200,
        content_type="text/html",
    )

    rc = main(["headlines", "--limit", "1", "--no-cache"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["via"] == "homepage"
    assert payload["articles"][0]["headline"] == "Synthetic homepage lead story"
    assert "Cookie" not in responses.calls[0].request.headers


def test_headlines_cli_rejects_collection_without_graphql(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["headlines", "--collection", "most-popular"])

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert "--collection requires --via=graphql" in captured.err


def test_headlines_cli_rejects_homepage_audio_only(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["headlines", "--audio-only"])

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert "--audio-only requires --via=graphql" in captured.err
