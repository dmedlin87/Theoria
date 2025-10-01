"""Shared constants and helpers for AI workflow routers."""

from fastapi import status

__all__ = [
    "BAD_REQUEST_RESPONSE",
    "NOT_FOUND_RESPONSE",
    "BAD_REQUEST_NOT_FOUND_RESPONSES",
]

BAD_REQUEST_RESPONSE = {
    status.HTTP_400_BAD_REQUEST: {"description": "Invalid request"}
}
NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {"description": "Resource not found"}
}
BAD_REQUEST_NOT_FOUND_RESPONSES = {
    **BAD_REQUEST_RESPONSE,
    **NOT_FOUND_RESPONSE,
}
