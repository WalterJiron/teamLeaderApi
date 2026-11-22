from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PaginationInfo(BaseModel):
    page: int
    limit: int
    total: int


class PaginatedResponseSchema(BaseModel, Generic[T]):
    info: PaginationInfo
    data: list[T]


class ResponseSchema(BaseModel, Generic[T]):
    data: T


class ErrorResponseSchema(BaseModel):
    code: str
    message: str
