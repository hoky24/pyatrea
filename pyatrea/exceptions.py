class AtreaError(Exception):
    """Base error for all pyatrea failures."""


class AtreaConnectionError(AtreaError):
    """Network failure, timeout, or non-200 transport error."""


class AtreaAuthError(AtreaError):
    """Authentication denied (wrong password / persistent 403)."""


class AtreaResponseError(AtreaError):
    """The unit returned a 200 with malformed or unexpected content."""
