import json

import requests

from agent.tools.web_search import WebSearchTool


class _FakeResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json_data = json_data or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


def test_web_search_retries_transient_timeout(monkeypatch):
    tool = WebSearchTool()

    calls = {"count": 0}

    def fake_get(url, params=None, timeout=10, allow_redirects=True):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.Timeout("transient timeout")

        if params and params.get("list") == "search":
            return _FakeResponse({
                "query": {
                    "search": [{"title": "Retry Page"}]
                }
            })

        return _FakeResponse({
            "query": {
                "pages": {
                    "1": {
                        "title": "Retry Page",
                        "extract": "Recovered after retry"
                    }
                }
            }
        })

    monkeypatch.setattr(tool.session, "get", fake_get)
    monkeypatch.setattr("agent.tools.web_search.time.sleep", lambda _: None)

    result = tool.search("who is the current president")

    assert "Retry Page" in result
    assert "Recovered after retry" in result
    assert calls["count"] >= 3


def test_downtime_query_verifies_multiple_times(monkeypatch):
    tool = WebSearchTool()

    def always_503(url, params=None, timeout=10, allow_redirects=True):
        return _FakeResponse(status_code=503)

    monkeypatch.setattr(tool.session, "get", always_503)
    monkeypatch.setattr("agent.tools.web_search.time.sleep", lambda _: None)

    result = tool.search("Find a website that is currently down and verify it 3 times before concluding.")

    payload = json.loads(result)
    assert isinstance(payload, list)
    assert payload

    report = payload[0]
    assert report["verification_attempts"] == 3
    assert report["down_observed_count"] == 3
    assert report["is_consistently_down"] is True
