import os
import time
import shutil
from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/api/upload", tags=["Upload"])

os.makedirs("uploads", exist_ok=True)

@router.post("/")
async def upload_file(image: UploadFile = File(...)):
    timestamp = int(time.time() * 1000)
    extension = os.path.splitext(image.filename)[1]
    filename = f"image-{timestamp}{extension}"
    file_path = f"uploads/{filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    return f"/{file_path}"