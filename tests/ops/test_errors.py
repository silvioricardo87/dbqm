"""`OperationError` carries a token and a sentence, and is an Exception."""
from __future__ import annotations

import pytest

from dbqm.ops.errors import OperationError


def test_it_carries_the_token_and_the_message():
    e = OperationError("not_found", "no such thing")
    assert e.code == "not_found"
    assert e.message == "no such thing"
    assert str(e) == "no such thing"


def test_it_is_raised_and_caught_as_an_exception():
    with pytest.raises(OperationError) as caught:
        raise OperationError("usage", "bad")
    assert caught.value.code == "usage"
