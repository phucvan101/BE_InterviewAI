# -*- coding: utf-8 -*-
import os
import json
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.feature_up_cv.file_storage import (
    save_raw_file,
    compute_text_hash,
    delete_file,
    FILE_TYPE_CV,
)
from app.feature.feature_up_cv.text_extract import extract_text_auto
from app.feature.feature_up_cv.auth.services.cv_profile_service import CVProfileService
from app.feature.feature_up_cv.auth.schemas.cv_profile import CVProfileCreate

router = APIRouter(prefix="/cv-profiles", tags=["CV Upload"])


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_cv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload CV file PDF.
    - Sử dụng UPSERT: nếu user đã có record thì update, chưa có thì tạo mới
    - Giữ nguyên id_cv khi re-upload (tránh id tăng vô nghĩa)
    - Nếu nội dung file không đổi (cùng hash) → giữ nguyên parser cache
    - Nếu nội dung thay đổi → xóa parser cache cũ, đợi analysis tạo lại

    Returns:
    {
        "success": true,
        "file_name": "cv.pdf",
        "file_path": "/path/to/raw/cv.pdf",
        "id_cv": 1,
        "text_hashed": "abc123...",
        "cache_preserved": true/false
    }
    """

    # ── Validate file type ─────────────────────────
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ chấp nhận file PDF"
        )

    try:
        # ── Read file content ────────────────────────
        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File rỗng"
            )

        user_id = current_user.id
        cv_service = CVProfileService(db)

        # ── Extract text & compute hash FIRST ────────
        # Save to temp location to extract text
        extension = Path(file.filename).suffix
        temp_path = save_raw_file(
            content=content,
            file_type=FILE_TYPE_CV,
            user_id=user_id,
            record_id=0,  # temp id, will rename later if needed
            extension=extension,
        )

        extracted_text = extract_text_auto(str(temp_path))
        text_hash = compute_text_hash(extracted_text) if extracted_text else None

        # ── UPSERT logic ─────────────────────────────
        existing_cvs = await cv_service.get_by_user(user_id)
        cache_preserved = False

        # Find matching record by hash
        cv_record = next((cv for cv in existing_cvs if cv.text_hashed == text_hash and text_hash is not None), None)

        if cv_record:
            # ── Same content → reuse existing record ──
            cache_preserved = True
            print(f"[UPLOAD] CV same content detected (hash match), preserving cache for id_cv={cv_record.id_cv}")
            
            # Update created_at to now
            from sqlalchemy import func
            cv_record.created_at = func.now()
            
            final_path = Path(cv_record.raw_file_url) if cv_record.raw_file_url else temp_path
            if cv_record.raw_file_url:
                delete_file(temp_path)  # we don't need the new file, reuse old
            else:
                # Edge case where raw_file_url was somehow missing
                final_path = save_raw_file(
                    content=content,
                    file_type=FILE_TYPE_CV,
                    user_id=user_id,
                    record_id=cv_record.id_cv,
                    extension=extension,
                )
                cv_record.raw_file_url = str(final_path)
                delete_file(temp_path)

            await db.flush()
            await db.refresh(cv_record)
        else:
            # ── No matching record → create new ──────
            cv_record = await cv_service.create(
                user_id=user_id,
                data=CVProfileCreate(),
            )
            await db.flush()

            # Rename temp file to use the new record's id_cv
            final_path = save_raw_file(
                content=content,
                file_type=FILE_TYPE_CV,
                user_id=user_id,
                record_id=cv_record.id_cv,
                extension=extension,
            )
            # Delete the temp file
            delete_file(temp_path)

            cv_record.raw_file_url = str(final_path)
            cv_record.text_hashed = text_hash
            await db.flush()
            await db.refresh(cv_record)
            print(f"[UPLOAD] CV new record created: id_cv={cv_record.id_cv}, user={user_id}")

        print(f"[UPLOAD] CV uploaded: id_cv={cv_record.id_cv}, user={user_id}, cache_preserved={cache_preserved}")

        # ── Return file info ──────────────────────────
        return {
            "success": True,
            "message": "Upload file thành công",
            "file_name": file.filename,
            "file_path": str(final_path),
            "file_size": len(content),
            "id_cv": cv_record.id_cv,
            "text_hashed": text_hash,
            "cache_preserved": cache_preserved,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi upload file: {str(e)}"
        )
