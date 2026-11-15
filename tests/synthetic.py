"""Synthetic source files and a fake upstream for the ingestion tests.

The contents are invented. They are shaped only as far as the ingestion
code needs (JSON arrays of objects, plus the lookup keys) and say
nothing about the real StatsBomb schema.
"""

from phaselens import statsbomb
from phaselens.fetch import NotFoundError

COMMIT = "a" * 40
COMPETITION_ID = 900
SEASON_ID = 800
MATCH_ID = 700

COMPETITIONS_PATH = statsbomb.COMPETITIONS_PATH
MATCHES_PATH = statsbomb.matches_path(COMPETITION_ID, SEASON_ID)
LINEUPS_PATH = statsbomb.lineups_path(MATCH_ID)
EVENTS_PATH = statsbomb.events_path(MATCH_ID)
THREE_SIXTY_PATH = statsbomb.three_sixty_path(MATCH_ID)

# Odd spacing, CRLF line endings, non-ASCII text and missing final newlines
# are deliberate: none would survive a parse-and-rewrite, so byte-for-byte
# equality proves the files were not reserialized.
SOURCE_FILES = {
    COMPETITIONS_PATH: (
        b'[ {"competition_id": 900, "season_id": 800,\r\n'
        b'   "competition_name": "Synthetic Cup", "season_name": "2000"} ]'
    ),
    MATCHES_PATH: (
        '[{"match_id":700,"match_date":"2000-01-02",'
        '"competition":{"competition_id":900,"competition_name":"Synthetic Cup"},'
        '"season":{"season_id":800,"season_name":"2000"},'
        '"home_team":{"home_team_id":1,"home_team_name":"Ünited","extra":"ignored"},'
        '"away_team":{"away_team_id":2,"away_team_name":"City"}},\n'
        ' {"match_id":701,"match_date":"2000-01-09",'
        '"competition":{"competition_id":900,"competition_name":"Synthetic Cup"},'
        '"season":{"season_id":800,"season_name":"2000"},'
        '"home_team":{"home_team_id":2,"home_team_name":"City"},'
        '"away_team":{"away_team_id":3,"away_team_name":"Rovers"}}]\n'
    ).encode("utf-8"),
    LINEUPS_PATH: b'[{"team_id": 1, "lineup": []},\n {"team_id": 2, "lineup": []}]',
    EVENTS_PATH: b'[\n  {"id": "e1",   "index": 1},\n  {"id": "e2",   "index": 2}\n]\n\n',
}

# A second match of the same competition-season. It shares the competition
# index and the match list above and has its own lineups and events.
SECOND_MATCH_ID = 701
SECOND_LINEUPS_PATH = statsbomb.lineups_path(SECOND_MATCH_ID)
SECOND_EVENTS_PATH = statsbomb.events_path(SECOND_MATCH_ID)
SECOND_MATCH_FILES = {
    SECOND_LINEUPS_PATH: b'[{"team_id": 2, "lineup": []}, {"team_id": 3, "lineup": []}]',
    SECOND_EVENTS_PATH: b'[{"id": "f1", "index": 1}]\n',
}


def source_url(source_path):
    return statsbomb.source_url(COMMIT, source_path)


def files_under(directory):
    """Every file below `directory`, as sorted POSIX-style relative paths."""
    return sorted(
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
    )


def snapshot(directory):
    """Content and modification time of every file below `directory`."""
    return {
        path: ((directory / path).read_bytes(), (directory / path).stat().st_mtime_ns)
        for path in files_under(directory)
    }


class FakeSource:
    """Stands in for the upstream repository and records every request."""

    def __init__(self):
        # URL -> bytes to return, or an exception to raise.
        self.responses = {
            source_url(path): data
            for path, data in {**SOURCE_FILES, **SECOND_MATCH_FILES}.items()
        }
        # True or False for the three-sixty check, or an exception to raise.
        self.three_sixty = True
        self.fetched = []
        self.checked = []

    def fetch(self, url, accept=None):
        self.fetched.append(url)
        response = self.responses.get(url)
        if response is None:
            raise NotFoundError(f"{url}: HTTP 404, not found")
        if isinstance(response, Exception):
            raise response
        return response

    def exists(self, url):
        self.checked.append(url)
        if isinstance(self.three_sixty, Exception):
            raise self.three_sixty
        return self.three_sixty
