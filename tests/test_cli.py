"""The command line workflow: discover, ingest, rerun, and fail clearly."""

import pytest

from phaselens import cli, statsbomb
from phaselens.fetch import FetchError
from synthetic import COMMIT, EVENTS_PATH, files_under, source_url

MANIFEST = f"manifests/statsbomb/open-data/{COMMIT}/match_700.json"
SELECTION = ["--competition-id", "900", "--season-id", "800", "--match-id", "700"]


@pytest.fixture
def project(tmp_path, monkeypatch, source):
    """A project root as the CLI sees it, wired to the fake upstream."""
    (tmp_path / "pyproject.toml").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "fetch_bytes", source.fetch)
    monkeypatch.setattr(cli, "url_exists", source.exists)
    return tmp_path


def test_ingest_then_rerun_from_the_manifest(project, capsys):
    assert cli.main(["ingest", "--commit", COMMIT, *SELECTION]) == 0
    first_output = capsys.readouterr().out
    assert first_output.count("  downloaded ") == 4
    assert f"{MANIFEST} (written)" in first_output
    manifest_before = (project / MANIFEST).read_bytes()

    assert cli.main(["ingest", "--manifest", MANIFEST]) == 0
    second_output = capsys.readouterr().out
    assert second_output.count("  reused ") == 4
    assert f"{MANIFEST} (unchanged)" in second_output
    assert (project / MANIFEST).read_bytes() == manifest_before


def test_ingest_without_commit_resolves_once_and_pins_every_file(project, source, capsys):
    source.responses[statsbomb.commit_lookup_url()] = COMMIT.encode() + b"\n"

    assert cli.main(["ingest", *SELECTION]) == 0

    lookups = [url for url in source.fetched if url == statsbomb.commit_lookup_url()]
    data_urls = [url for url in source.fetched if url != statsbomb.commit_lookup_url()]
    assert len(lookups) == 1
    assert len(data_urls) == 4 and all(f"/{COMMIT}/" in url for url in data_urls)
    assert COMMIT in capsys.readouterr().out


def test_unusable_commit_lookup_response_is_an_error(project, source, capsys):
    source.responses[statsbomb.commit_lookup_url()] = b'{"message": "rate limit exceeded"}'
    assert cli.main(["ingest", *SELECTION]) == 1
    assert "commit SHA" in capsys.readouterr().err
    assert files_under(project) == ["pyproject.toml"]


def test_failed_download_exits_nonzero_with_a_message_and_no_files(project, source, capsys):
    source.responses[source_url(EVENTS_PATH)] = FetchError(
        f"{source_url(EVENTS_PATH)}: timed out after 30 seconds"
    )
    assert cli.main(["ingest", "--commit", COMMIT, *SELECTION]) == 1
    error_output = capsys.readouterr().err
    assert error_output.startswith("error: ") and "timed out" in error_output
    assert files_under(project) == ["pyproject.toml"]


def test_discovery_commands_list_the_source_and_save_nothing(project, capsys):
    assert cli.main(["competitions", "--commit", COMMIT]) == 0
    assert "Synthetic Cup / 2000" in capsys.readouterr().out

    arguments = ["matches", "--commit", COMMIT, "--competition-id", "900", "--season-id", "800"]
    assert cli.main(arguments) == 0
    assert "700  2000-01-02" in capsys.readouterr().out

    assert files_under(project) == ["pyproject.toml"]


def test_ingest_outside_a_project_root_is_refused(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["ingest", "--commit", COMMIT, *SELECTION]) == 1
    assert "project root" in capsys.readouterr().err
