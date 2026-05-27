# -*- coding: utf-8 -*-
import os
import tempfile
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.feature_up_cv.core.file_storage import (
    save_raw_file,
    compute_text_hash,
    delete_file,
    FILE_TYPE_CI,
)
from app.feature.feature_up_cv.core.text_extract import extract_text_auto
from app.feature.feature_up_cv.auth.services.company_info_service import CompanyInfoService
from app.feature.feature_up_cv.auth.schemas.company_info import CompanyInfoCreate

router = APIRouter(prefix="/company-research", tags=["Company Research"])


class CompanyResearchTextUploadRequest(BaseModel):
    text: str
    file_name: str | None = None


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_company_research(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload file nghiên cứu công ty (DOCX, PDF).
    - Sử dụng UPSERT: nếu user đã có record thì update, chưa có thì tạo mới
    - Giữ nguyên id_ci khi re-upload (tránh id tăng vô nghĩa)
    - Nếu nội dung file không đổi (cùng hash) → giữ nguyên parser cache
    - Nếu nội dung thay đổi → xóa parser cache cũ, đợi analysis tạo lại
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
        # ── Read file content ────────────────────────
        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File rỗng"
            )

        user_id = current_user.id
        ci_service = CompanyInfoService(db)

        # ── Extract text & compute hash FIRST ────────
        extension = Path(file.filename).suffix
        temp_path = save_raw_file(
            content=content,
            file_type=FILE_TYPE_CI,
            user_id=user_id,
            record_id=0,
            extension=extension,
        )

        extracted_text = extract_text_auto(str(temp_path))
        text_hash = compute_text_hash(extracted_text) if extracted_text else None

        # ── UPSERT logic ─────────────────────────────
        existing_cis = await ci_service.get_by_user(user_id)
        cache_preserved = False

        ci_record = next((ci for ci in existing_cis if ci.text_hashed == text_hash and text_hash is not None), None)

        if ci_record:
            # ── Check if physical files exist ────────
            raw_exists = bool(ci_record.raw_file_url and os.path.exists(ci_record.raw_file_url))
            parser_exists = bool(not ci_record.parser_file_url or os.path.exists(ci_record.parser_file_url))

            from sqlalchemy import func
            ci_record.created_at = func.now()

            if raw_exists and parser_exists:
                # ── Same content & files exist → reuse existing record ──
                cache_preserved = True
                print(f"[UPLOAD] CI same content detected (hash match) and files exist, preserving cache for id_ci={ci_record.id_ci}")
                final_path = Path(ci_record.raw_file_url)
                delete_file(temp_path)
            else:
                # ── Hash matched but files missing → replace files ──
                cache_preserved = False
                print(f"[UPLOAD] CI hash matched but physical files missing. Re-saving for id_ci={ci_record.id_ci}")
                
                final_path = save_raw_file(
                    content=content,
                    file_type=FILE_TYPE_CI,
                    user_id=user_id,
                    record_id=ci_record.id_ci,
                    extension=extension,
                )
                ci_record.raw_file_url = str(final_path)
                if not parser_exists:
                    ci_record.parser_file_url = None
                
                delete_file(temp_path)

            await db.flush()
            await db.refresh(ci_record)

        else:
            # ── No existing record → create new ──────
            ci_record = await ci_service.create(
                user_id=user_id,
                data=CompanyInfoCreate(text_content=extracted_text),
            )
            await db.flush()

            final_path = save_raw_file(
                content=content,
                file_type=FILE_TYPE_CI,
                user_id=user_id,
                record_id=ci_record.id_ci,
                extension=extension,
            )
            delete_file(temp_path)

            ci_record.raw_file_url = str(final_path)
            ci_record.text_hashed = text_hash
            ci_record.text_content = extracted_text
            await db.flush()
            await db.refresh(ci_record)
            print(f"[UPLOAD] CI new record created: id_ci={ci_record.id_ci}, user={user_id}")

        print(f"[UPLOAD] CI uploaded: id_ci={ci_record.id_ci}, user={user_id}, cache_preserved={cache_preserved}")

        # ── Return file info ──────────────────────────
        return {
            "success": True,
            "message": "Upload file thành công",
            "file_name": file.filename,
            "file_path": str(final_path),
            "file_type": file_type,
            "file_size": len(content),
            "id_ci": ci_record.id_ci,
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


@router.post("/upload-text", status_code=status.HTTP_200_OK)
async def upload_company_research_text(
    request_body: CompanyResearchTextUploadRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload company research dưới dạng text.
    - Sử dụng UPSERT: nếu user đã có record thì update, chưa có thì tạo mới
    - Giữ nguyên id_ci khi re-upload (tránh id tăng vô nghĩa)
    - Nếu nội dung text không đổi (cùng hash) → giữ nguyên parser cache
    """
    text_content = (request_body.text or "").strip()
    if not text_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nội dung nghiên cứu công ty không được để trống",
        )

    try:
        user_id = current_user.id
        ci_service = CompanyInfoService(db)

        # ── Compute hash FIRST ───────────────────────
        text_hash = compute_text_hash(text_content)

        # ── UPSERT logic ─────────────────────────────
        existing_cis = await ci_service.get_by_user(user_id)
        cache_preserved = False

        ci_record = next((ci for ci in existing_cis if ci.text_hashed == text_hash and text_hash is not None), None)

        if ci_record:
            # ── Check if physical files exist ────────
            raw_exists = bool(ci_record.raw_file_url and os.path.exists(ci_record.raw_file_url))
            parser_exists = bool(not ci_record.parser_file_url or os.path.exists(ci_record.parser_file_url))

            from sqlalchemy import func
            ci_record.created_at = func.now()

            if raw_exists and parser_exists:
                # ── Same content & files exist → reuse existing record ──
                cache_preserved = True
                print(f"[UPLOAD] CI text same content detected (hash match) and files exist, preserving cache for id_ci={ci_record.id_ci}")
                raw_path = Path(ci_record.raw_file_url)
            else:
                # ── Hash matched but files missing → replace files ──
                cache_preserved = False
                print(f"[UPLOAD] CI text hash matched but physical files missing. Re-saving for id_ci={ci_record.id_ci}")
                
                raw_path = save_raw_file(
                    content=text_content.encode("utf-8"),
                    file_type=FILE_TYPE_CI,
                    user_id=user_id,
                    record_id=ci_record.id_ci,
                    extension="txt",
                )
                ci_record.raw_file_url = str(raw_path)
                if not parser_exists:
                    ci_record.parser_file_url = None

            await db.flush()
            await db.refresh(ci_record)

        else:
            # ── No existing record → create new ──────
            ci_record = await ci_service.create(
                user_id=user_id,
                data=CompanyInfoCreate(text_content=text_content),
            )
            await db.flush()

            raw_path = save_raw_file(
                content=text_content.encode("utf-8"),
                file_type=FILE_TYPE_CI,
                user_id=user_id,
                record_id=ci_record.id_ci,
                extension="txt",
            )

            ci_record.raw_file_url = str(raw_path)
            ci_record.text_hashed = text_hash
            ci_record.text_content = text_content
            await db.flush()
            await db.refresh(ci_record)
            print(f"[UPLOAD] CI text new record created: id_ci={ci_record.id_ci}, user={user_id}")

        safe_name = (request_body.file_name or "company_research").strip() or "company_research"

        print(f"[UPLOAD] CI text uploaded: id_ci={ci_record.id_ci}, user={user_id}, cache_preserved={cache_preserved}")

        return {
            "success": True,
            "message": "Lưu nội dung nghiên cứu công ty thành công",
            "file_name": f"{safe_name}.txt",
            "file_path": str(raw_path),
            "file_type": "txt",
            "file_size": len(text_content.encode("utf-8")),
            "id_ci": ci_record.id_ci,
            "text_hashed": text_hash,
            "cache_preserved": cache_preserved,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lưu nội dung nghiên cứu công ty: {str(e)}",
        )
