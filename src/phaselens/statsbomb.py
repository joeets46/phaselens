"""StatsBomb Open Data: where it is published and how its files are named.

The repository location and layout were checked against the source; see
docs/data_sources.md. Nothing in this module stores data.
"""

import re

from phaselens.fetch import FetchError

REPOSITORY_URL = "https://github.com/hudl/open-data"
DEFAULT_REF = "master"

_RAW_URL = "https://raw.githubusercontent.com/hudl/open-data"
_COMMIT_API_URL = "https://api.github.com/repos/hudl/open-data/commits"
_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")

COMPETITIONS_PATH = "data/competitions.json"


def matches_path(competition_id, season_id):
    return f"data/matches/{competition_id}/{season_id}.json"


def lineups_path(match_id):
    return f"data/lineups/{match_id}.json"


def events_path(match_id):
    return f"data/events/{match_id}.json"


def three_sixty_path(match_id):
    return f"data/three-sixty/{match_id}.json"


def source_url(commit_sha, path):
    """URL of a repository file as it was at one commit."""
    return f"{_RAW_URL}/{commit_sha}/{path}"


def commit_lookup_url(ref=DEFAULT_REF):
    """URL of the GitHub API call that names the commit `ref` points to."""
    return f"{_COMMIT_API_URL}/{ref}"


def is_commit_sha(text):
    return isinstance(text, str) and _COMMIT_SHA.fullmatch(text) is not None


def resolve_commit(fetch, ref=DEFAULT_REF):
    """Ask GitHub which commit `ref` points to right now.

    A branch moves; a commit SHA does not. Resolving once and using the
    SHA everywhere keeps every file of a run on the same revision.
    """
    url = commit_lookup_url(ref)
    body = fetch(url, accept="application/vnd.github.sha")
    commit_sha = body.decode("ascii", errors="replace").strip()
    if not is_commit_sha(commit_sha):
        raise FetchError(f"{url}: expected a 40-character commit SHA in the response")
    return commit_sha
