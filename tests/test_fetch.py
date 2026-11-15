"""HTTP outcomes are turned into clear, distinguishable results."""

import http.client
import urllib.error

import pytest

from phaselens.fetch import FetchError, NotFoundError, fetch_bytes, url_exists

URL = "https://example.invalid/file.json"


class FakeResponse:
    """Minimal stand-in for the object urlopen returns."""

    def __init__(self, body=b"", read_error=None):
        self.body = body
        self.read_error = read_error

    def read(self):
        if self.read_error is not None:
            raise self.read_error
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def http_error(code):
    return urllib.error.HTTPError(URL, code, "reason", None, None)


@pytest.fixture
def urlopen(monkeypatch):
    """Replace urlopen; returns a function that sets its next outcome."""
    state = {"outcome": FakeResponse(), "calls": []}

    def fake_urlopen(request, timeout=None):
        state["calls"].append((request, timeout))
        if isinstance(state["outcome"], Exception):
            raise state["outcome"]
        return state["outcome"]

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    def set_outcome(outcome):
        state["outcome"] = outcome
        return state["calls"]

    return set_outcome


def test_fetch_bytes_returns_the_body_unchanged(urlopen):
    body = b'\xef\xbb\xbf[ {"a": 1} ]\r\n'
    urlopen(FakeResponse(body))
    assert fetch_bytes(URL) == body


def test_requests_use_a_finite_timeout(urlopen):
    calls = urlopen(FakeResponse(b"[]"))
    fetch_bytes(URL)
    _, timeout = calls[0]
    assert timeout is not None and 0 < timeout < float("inf")


def test_http_404_is_reported_as_not_found(urlopen):
    urlopen(http_error(404))
    with pytest.raises(NotFoundError):
        fetch_bytes(URL)


@pytest.mark.parametrize("code", [403, 429])
def test_permission_and_rate_limit_failures_are_not_reported_as_not_found(urlopen, code):
    urlopen(http_error(code))
    with pytest.raises(FetchError, match="access denied or rate limited") as raised:
        fetch_bytes(URL)
    assert not isinstance(raised.value, NotFoundError)


def test_server_error_is_a_fetch_error_naming_the_status(urlopen):
    urlopen(http_error(503))
    with pytest.raises(FetchError, match="HTTP 503") as raised:
        fetch_bytes(URL)
    assert not isinstance(raised.value, NotFoundError)


def test_timeout_while_connecting_is_reported(urlopen):
    urlopen(urllib.error.URLError(TimeoutError("timed out")))
    with pytest.raises(FetchError, match="timed out"):
        fetch_bytes(URL)


def test_timeout_while_reading_the_body_is_reported(urlopen):
    urlopen(FakeResponse(read_error=TimeoutError("timed out")))
    with pytest.raises(FetchError, match="timed out"):
        fetch_bytes(URL)


def test_connection_dropped_mid_body_is_a_fetch_error(urlopen):
    urlopen(FakeResponse(read_error=http.client.IncompleteRead(b"[{")))
    with pytest.raises(FetchError, match="connection failed"):
        fetch_bytes(URL)


def test_unreachable_host_is_a_network_error(urlopen):
    urlopen(urllib.error.URLError(OSError("getaddrinfo failed")))
    with pytest.raises(FetchError, match="network error"):
        fetch_bytes(URL)


def test_url_exists_is_true_for_200_and_asks_with_head(urlopen):
    calls = urlopen(FakeResponse())
    assert url_exists(URL) is True
    request, _ = calls[0]
    assert request.get_method() == "HEAD"


def test_url_exists_is_false_for_404(urlopen):
    urlopen(http_error(404))
    assert url_exists(URL) is False


@pytest.mark.parametrize(
    "failure", [http_error(403), http_error(503), urllib.error.URLError(TimeoutError())]
)
def test_url_exists_raises_when_the_answer_is_unknown(urlopen, failure):
    urlopen(failure)
    with pytest.raises(FetchError):
        url_exists(URL)
