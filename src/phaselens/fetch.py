"""HTTP access with the standard library only.

Every failure becomes a FetchError whose message names the URL and the
cause. A 404 is a NotFoundError, so callers can tell "the file is not
there" apart from "the request did not succeed".
"""

import http.client
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 30
USER_AGENT = "phaselens/0.1"


class FetchError(Exception):
    """A request did not produce a usable response."""


class NotFoundError(FetchError):
    """The server answered HTTP 404."""


def fetch_bytes(url, accept=None, timeout=TIMEOUT_SECONDS):
    """Return the body of a GET request exactly as the server sent it."""
    return _send("GET", url, accept, timeout)


def url_exists(url, timeout=TIMEOUT_SECONDS):
    """Return True for HTTP 200 and False for HTTP 404, using a HEAD request.

    Any other outcome raises FetchError: a failed request is not evidence
    that the resource is absent.
    """
    try:
        _send("HEAD", url, None, timeout)
    except NotFoundError:
        return False
    return True


def _send(method, url, accept, timeout):
    # "identity" asks the server not to compress, so the bytes received are
    # the bytes of the file.
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise NotFoundError(f"{url}: HTTP 404, not found") from error
        if error.code in (401, 403, 429):
            raise FetchError(
                f"{url}: HTTP {error.code}, access denied or rate limited"
            ) from error
        raise FetchError(f"{url}: HTTP {error.code} {error.reason}") from error
    except TimeoutError as error:
        raise FetchError(f"{url}: timed out after {timeout} seconds") from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise FetchError(f"{url}: timed out after {timeout} seconds") from error
        raise FetchError(f"{url}: network error ({error.reason})") from error
    except (OSError, http.client.HTTPException) as error:
        raise FetchError(f"{url}: connection failed ({error!r})") from error
