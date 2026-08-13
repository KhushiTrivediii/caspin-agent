import os
import aiofiles
import uuid
import logging
from typing import Dict, Any, List, Optional
from fastapi import UploadFile

from backend.database import add_attachment, list_attachments, get_attachment

logger = logging.getLogger("attachments")

# Configure upload constraints
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".txt", ".csv"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

class AttachmentService:
    """
    Asynchronously manages the ingestion, storage, and retrieval of supporting documents
    (spec sheets, vendor quotes PDFs, signed compliance forms).
    """
    def __init__(self, upload_dir: str = "./uploads"):
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    async def save_uploaded_file(
        self,
        procurement_id: str,
        file: UploadFile,
        uploaded_by: str = "System"
    ) -> Dict[str, Any]:
        """
        Validate, save to disk asynchronously, and save metadata to database.
        """
        filename = file.filename
        file_ext = os.path.splitext(filename)[1].lower()

        # 1. Validate File Extension
        if file_ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"File extension '{file_ext}' is not permitted. Permitted: {', '.join(ALLOWED_EXTENSIONS)}")

        # 2. Validate file size (check content-length if available, or track bytes during read)
        # Read contents
        contents = await file.read()
        file_size = len(contents)

        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds 10MB threshold limit. Current: {file_size / 1024 / 1024:.2f}MB")

        # 3. Create destination directory
        dest_dir = os.path.join(self.upload_dir, procurement_id)
        os.makedirs(dest_dir, exist_ok=True)

        attachment_id = f"ATT-{uuid.uuid4().hex[:10].upper()}"
        safe_filename = f"{attachment_id}_{filename}"
        dest_path = os.path.join(dest_dir, safe_filename)

        # 4. Write to disk asynchronously using aiofiles
        async with aiofiles.open(dest_path, "wb") as out_file:
            await out_file.write(contents)

        logger.info(f"File saved successfully: {dest_path} ({file_size} bytes)")

        # 5. Persist metadata in SQLite
        attachment_record = await add_attachment(
            attachment_id=attachment_id,
            procurement_id=procurement_id,
            filename=filename,
            file_path=dest_path,
            file_size=file_size,
            mime_type=file.content_type,
            uploaded_by=uploaded_by,
        )

        return attachment_record

    async def get_attachment_path(self, attachment_id: str) -> Optional[str]:
        """Fetch file path from DB and verify existence on disk."""
        meta = await get_attachment(attachment_id)
        if not meta:
            return None
        file_path = meta["file_path"]
        if os.path.exists(file_path):
            return file_path
        return None

# Global singleton service
attachment_service = AttachmentService()
