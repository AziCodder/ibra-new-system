import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".txt", ".csv", ".zip", ".rar",
}


class StorageError(Exception):
    pass


class Storage(ABC):
    @abstractmethod
    async def save(self, filename: str, data: bytes) -> str:
        ...

    @abstractmethod
    async def get(self, key: str) -> bytes:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...


class LocalStorage(Storage):
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.upload_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _validate(self, filename: str, data: bytes) -> None:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise StorageError(f"File type '{ext}' not allowed")
        if len(data) > MAX_FILE_SIZE:
            raise StorageError(f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit")

    async def save(self, filename: str, data: bytes) -> str:
        self._validate(filename, data)
        ext = Path(filename).suffix.lower()
        key = f"{uuid.uuid4().hex}{ext}"
        filepath = self.base_dir / key
        filepath.write_bytes(data)
        return key

    async def get(self, key: str) -> bytes:
        filepath = self.base_dir / key
        if not filepath.exists():
            raise StorageError("File not found")
        safe = os.path.commonpath([self.base_dir.resolve(), filepath.resolve()])
        if safe != str(self.base_dir.resolve()):
            raise StorageError("Invalid file path")
        return filepath.read_bytes()

    async def delete(self, key: str) -> None:
        filepath = self.base_dir / key
        if filepath.exists():
            filepath.unlink()


storage = LocalStorage()
