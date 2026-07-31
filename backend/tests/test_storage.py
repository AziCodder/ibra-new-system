import pytest

from app.services.storage import CONTEXT_MAX_SIZES, LocalStorage, StorageError


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


@pytest.mark.asyncio
async def test_order_context_rejects_file_over_3mb(storage):
    over_limit = b"x" * (CONTEXT_MAX_SIZES["order"] + 1)
    with pytest.raises(StorageError, match="3MB limit"):
        await storage.save("big.pdf", over_limit, max_size=CONTEXT_MAX_SIZES["order"])


@pytest.mark.asyncio
async def test_order_context_accepts_file_at_3mb(storage):
    at_limit = b"x" * CONTEXT_MAX_SIZES["order"]
    key = await storage.save("ok.pdf", at_limit, max_size=CONTEXT_MAX_SIZES["order"])
    assert key.endswith(".pdf")


@pytest.mark.asyncio
async def test_payment_request_context_rejects_file_over_5mb(storage):
    over_limit = b"x" * (CONTEXT_MAX_SIZES["payment_request"] + 1)
    with pytest.raises(StorageError, match="5MB limit"):
        await storage.save("big.pdf", over_limit, max_size=CONTEXT_MAX_SIZES["payment_request"])
