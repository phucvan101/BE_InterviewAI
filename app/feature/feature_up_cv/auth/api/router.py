# -*- coding: utf-8 -*-
from fastapi import APIRouter

from app.feature.feature_up_cv.auth.api.endpoints.cv_profile import router as cv_profile_router
from app.feature.feature_up_cv.auth.api.endpoints.upload_cv import router as upload_cv_router
from app.feature.feature_up_cv.auth.api.endpoints.job_description import router as job_description_router
from app.feature.feature_up_cv.auth.api.endpoints.company_research import router as company_research_router
from app.feature.feature_up_cv.auth.api.endpoints.analysis import router as analysis_router
from app.feature.feature_up_cv.auth.api.endpoints.score_feedback import router as score_feedback_router

router = APIRouter()

router.include_router(cv_profile_router)
router.include_router(upload_cv_router)
router.include_router(job_description_router)
router.include_router(company_research_router)
router.include_router(analysis_router)
router.include_router(score_feedback_router)