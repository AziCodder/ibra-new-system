import mimetypes

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response

from app.models.user import User
from app.routers.auth import get_current_user
from app.services.storage import StorageError, storage

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    _user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    data = await file.read()
    try:
        key = await storage.save(file.filename, data)
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return {"key": key, "filename": file.filename, "size": len(data)}


@router.get("/{file_key}")
async def download_file(
    file_key: str,
    _user: User = Depends(get_current_user),
):
    try:
        data = await storage.get(file_key)
    except StorageError:
        raise HTTPException(status_code=404, detail="File not found") from None

    media_type, _ = mimetypes.guess_type(file_key)
    media_type = media_type or "application/octet-stream"
    # Images render inline (e.g. product photo previews); other files force a download.
    disposition = "inline" if media_type.startswith("image/") else "attachment"

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'{disposition}; filename="{file_key}"'},
    )


@router.delete("/{file_key}", status_code=204)
async def delete_file(
    file_key: str,
    _user: User = Depends(get_current_user),
):
    await storage.delete(file_key)
