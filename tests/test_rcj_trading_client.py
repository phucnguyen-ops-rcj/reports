from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from src.clients.rcj_trading import RcjTradingClient


def test_get_analyze_builds_expected_request(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "src.clients.rcj_trading.urllib.request.urlopen",
        fake_urlopen,
    )

    client = RcjTradingClient(base_url="https://1rf9t4k2tc.xyz")
    payload = client.get_analyze(
        symbols=["IKA", "TREE", "GRASS"],
        period_ms=43_200_000,
    )

    parsed = urlparse(str(captured["url"]))
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "1rf9t4k2tc.xyz"
    assert parsed.path == "/api/v1/analyze"
    assert params == {
        "symbol": ["IKA,TREE,GRASS"],
        "period": ["43200000"],
        "type": ["Spot"],
        "version": ["Net"],
    }
    assert captured["method"] == "GET"
    assert captured["timeout"] == 10.0
    assert payload == {"ok": True}


def test_get_analyze_rejects_empty_symbols():
    client = RcjTradingClient(base_url="https://1rf9t4k2tc.xyz")

    try:
        client.get_analyze(symbols=[" ", ""], period_ms=43_200_000)
    except ValueError as exc:
        assert str(exc) == "symbols must contain at least one non-empty symbol."
    else:
        raise AssertionError("Expected ValueError for empty symbols.")
