import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB — default, used where ТЗ doesn't specify a context limit
# Per-context limits from ТЗ §6/§8: order attachments 3 MB, payment-request attachments 5 MB.
CONTEXT_MAX_SIZES = {
    "order": 3 * 1024 * 1024,
    "payment_request": 5 * 1024 * 1024,
}
ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".txt", ".csv", ".zip", ".rar",
}


class StorageError(Exception):
    pass


class Storage(ABC):
    @abstractmethod
    async def save(self, filename: str, data: bytes, max_size: int = MAX_FILE_SIZE) -> str:
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

    def _validate(self, filename: str, data: bytes, max_size: int) -> None:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise StorageError(f"File type '{ext}' not allowed")
        if len(data) > max_size:
            raise StorageError(f"File exceeds {max_size // (1024 * 1024)}MB limit")

    async def save(self, filename: str, data: bytes, max_size: int = MAX_FILE_SIZE) -> str:
        self._validate(filename, data, max_size)
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
        if not filepath.exists():
            return
        safe = os.path.commonpath([self.base_dir.resolve(), filepath.resolve()])
        if safe != str(self.base_dir.resolve()):
            raise StorageError("Invalid file path")
        filepath.unlink()


storage = LocalStorage()
