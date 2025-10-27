import uuid

from lys.core.consts.errors import NOT_UUID_ERROR
from lys.core.errors import LysError


def validate_uuid(id_: str | None, error: tuple[int, str] = NOT_UUID_ERROR):
    try:
        uuid.UUID(str(id_))
    except ValueError:
        raise LysError(
            error,
            "expected an uuid"
        )