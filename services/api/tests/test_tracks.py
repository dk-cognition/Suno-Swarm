import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers.tracks import SEARCH_SORT_COLUMNS, search_tracks  # noqa: E402


class FakeResult:
    def fetchall(self):
        return []


class FakeSession:
    def __init__(self):
        self.executions = []

    def execute(self, statement, params):
        self.executions.append((statement, params))
        return FakeResult()


def test_search_rejects_invalid_sort_without_executing():
    session = FakeSession()

    with pytest.raises(HTTPException) as exc_info:
        search_tracks(
            q="dream pop",
            sort="created_at; DROP TABLE users --",
            session=session,
            user=object(),
        )

    assert exc_info.value.status_code == 400
    assert session.executions == []


@pytest.mark.parametrize("sort", sorted(SEARCH_SORT_COLUMNS))
def test_search_accepts_allowlisted_sort(sort):
    session = FakeSession()

    assert search_tracks(q="dream pop", sort=sort, session=session, user=object()) == []
    assert len(session.executions) == 1


def test_search_binds_malicious_query_parameter():
    q = "%' UNION SELECT password_hash FROM users --"
    session = FakeSession()

    assert search_tracks(q=q, sort="created_at", session=session, user=object()) == []

    statement, params = session.executions[0]
    sql = str(statement)
    assert ":pattern" in sql
    assert "UNION" not in sql
    assert q not in sql
    assert params == {"pattern": f"%{q}%"}
