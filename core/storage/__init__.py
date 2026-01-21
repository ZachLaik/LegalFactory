"""Storage layer for Legal Data Factory."""

from core.storage.database import Database, get_database
from core.storage.repository import DocumentRepository, RunRepository, WatermarkRepository

__all__ = [
    "Database",
    "get_database",
    "DocumentRepository",
    "RunRepository",
    "WatermarkRepository",
]
