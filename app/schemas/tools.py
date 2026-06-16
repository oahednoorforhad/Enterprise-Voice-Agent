from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ToolResult(BaseModel, Generic[T]):  # noqa: UP046
    success: bool
    data: T | None = None
    error: str | None = None

    @classmethod
    def ok(cls, data: T) -> "ToolResult[T]":
        return cls(success=True, data=data, error=None)

    @classmethod
    def fail(cls, error: str) -> "ToolResult[T]":
        return cls(success=False, data=None, error=error)
