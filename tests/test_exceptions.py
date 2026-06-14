from pyatrea.exceptions import (
    AtreaError, AtreaConnectionError, AtreaAuthError, AtreaResponseError,
)


def test_exception_hierarchy():
    assert issubclass(AtreaConnectionError, AtreaError)
    assert issubclass(AtreaAuthError, AtreaError)
    assert issubclass(AtreaResponseError, AtreaError)
