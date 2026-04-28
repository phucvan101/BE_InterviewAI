# -*- coding: utf-8 -*-
import os
import json
import tempfile
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User

router = APIRouter(prefix="/cv-profiles", tags=["CV Upload"])

# Directory to store uploaded CVs temporarily
UPLOAD_DIR = Path(tempfile.gettempdir()) / "interview_cv_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_cv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload CV file PDF - chỉ lưu file, không extract
    Extract sẽ được thực hiện khi phân tích
    
    Returns:
    {
        "success": true,
        "file_name": "cv.pdf",
        "file_path": "/path/to/cv.pdf"
    }
    """
    
    # ── Validate file type ─────────────────────────
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ chấp nhận file PDF"
        )
    
    try:
        # ── Read and save file ────────────────────────
        content = await file.read()
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File rỗng"
            )
        
        # ── Save file to temporary directory ───────────
        user_id = 1
        file_path = UPLOAD_DIR / f"cv_{user_id}_{file.filename}"
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # ── Return file info ──────────────────────────
        return {
            "success": True,
            "message": "Upload file thành công",
            "file_name": file.filename,
            "file_path": str(file_path),
            "file_size": len(content)
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi upload file: {str(e)}"
        )
