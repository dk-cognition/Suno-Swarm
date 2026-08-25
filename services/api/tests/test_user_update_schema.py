import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.schemas import UserUpdate  # noqa: E402


def test_allows_profile_fields():
    payload = UserUpdate(fields={"display_name": "Ada"})
    assert payload.fields.dict(exclude_unset=True) == {"display_name": "Ada"}


@pytest.mark.parametrize("field", ["is_admin", "workspace_id", "email", "password_hash"])
def test_rejects_protected_fields(field):
    with pytest.raises(ValidationError):
        UserUpdate(fields={field: "x"})
