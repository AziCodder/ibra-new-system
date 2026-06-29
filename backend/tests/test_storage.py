import pytest

from app.services.storage import LocalStorage, StorageError


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(str(tmp_path))


@pytest.mark.asyncio
async def test_save_and_get(storage):
    key = await storage.save("test.pdf", b"hello world")
    assert key.endswith(".pdf")
    data = await storage.get(key)
    assert data == b"hello world"


@pytest.mark.asyncio
async def test_delete(storage):
    key = await storage.save("doc.txt", b"content")
    await storage.delete(key)
    with pytest.raises(StorageError, match="File not found"):
        await storage.get(key)


@pytest.mark.asyncio
async def test_reject_disallowed_extension(storage):
    with pytest.raises(StorageError, match="not allowed"):
        await storage.save("script.exe", b"data")


@pytest.mark.asyncio
async def test_reject_oversized_file(storage):
    big = b"x" * (21 * 1024 * 1024)
    with pytest.raises(StorageError, match="limit"):
        await storage.save("big.pdf", big)
