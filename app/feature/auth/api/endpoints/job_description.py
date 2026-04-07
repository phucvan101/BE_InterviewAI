# -*- coding: utf-8 -*-
import tempfile
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter(prefix="/job-description", tags=["Job Description"])

# Directory to store uploaded JD files temporarily
UPLOAD_DIR = Path(tempfile.gettempdir()) / "interview_jd_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_job_description(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload file mô tả công việc (DOCX, PDF) - chỉ lưu file, không extract
    Extract sẽ được thực hiện khi phân tích
    
    Returns:
    {
        "success": true,
        "file_name": "jd.pdf",
        "file_path": "/path/to/jd.pdf",
        "file_type": "pdf"
    }
    """
    
    # ── Validate file type ─────────────────────────
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên file không hợp lệ"
        )
    
    filename_lower = file.filename.lower()
    
    if filename_lower.endswith('.docx'):
        file_type = 'docx'
    elif filename_lower.endswith('.pdf'):
        file_type = 'pdf'
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ chấp nhận file DOCX hoặc PDF"
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
        # TODO: Use current_user.id in production. For now using default user_id=1
        user_id = 1  # Temporary: will use get_current_active_user after testing login
        file_path = UPLOAD_DIR / f"jd_{user_id}_{file.filename}"
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # ── Return file info ──────────────────────────
        return {
            "success": True,
            "message": "Upload file thành công",
            "file_name": file.filename,
            "file_path": str(file_path),
            "file_type": file_type,
            "file_size": len(content)
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi upload file: {str(e)}"
        )
