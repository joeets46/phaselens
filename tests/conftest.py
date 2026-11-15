"""Fixtures shared by all tests."""

import pytest

from synthetic import FakeSource


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any test that reaches the real network."""

    def refuse(*args, **kwargs):
        raise AssertionError("tests must not access the network")

    monkeypatch.setattr("urllib.request.urlopen", refuse)


@pytest.fixture
def source():
    return FakeSource()


@pytest.fixture
def project(tmp_path):
    """An empty directory standing in for the project root."""
    return tmp_path
