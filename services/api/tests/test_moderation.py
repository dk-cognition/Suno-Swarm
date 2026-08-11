import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import moderation  # noqa: E402


def test_allows_ordinary_prompt():
    state, reason = moderation.review_prompt("dream pop with shoegaze guitars")
    assert state == "allowed"
    assert reason == ""


def test_blocks_artist_imitation():
    state, reason = moderation.review_prompt("a ballad in the exact voice of a famous singer")
    assert state == "blocked"
    assert reason == "artist imitation"


def test_blocks_blocklisted_term():
    state, _ = moderation.review_prompt("HATE SPEECH anthem")
    assert state == "blocked"
