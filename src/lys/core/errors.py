import logging
from typing import Tuple

from fastapi import HTTPException


class LysError(HTTPException):
    def __init__(
            self,
            message_tuple: Tuple[int, str],
            debug_message: str,
            extensions: dict | None = None
    ) -> None:
        (code, message) = message_tuple
        self.debug_message = debug_message

        # Add HTTP status code to extensions
        self.extensions = extensions or {}
        self.extensions['status_code'] = code

        super().__init__(
            status_code=code,
            detail=message
        )
        logging.debug(debug_message)

    def __str__(self) -> str:
        """Return only the error message without status code."""
        return self.detail
