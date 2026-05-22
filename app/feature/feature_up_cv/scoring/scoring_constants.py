# -*- coding: utf-8 -*-
"""Large constant definitions used by hybrid scoring.

This module holds static mappings so `hybrid_scoring.py` stays lightweight.
"""
from typing import Dict, List, Set


# Soft skill keys — không tính vào technical skill score chính
_SOFT_SKILL_KEYS: Set[str] = {
    "communication", "problemsolving", "projectmanagement", "agile",
    "teamwork", "leadership", "creativity", "adaptability",
}


# Domain anchor descriptions — mô tả semantic cho mỗi domain
_DOMAIN_ANCHORS: Dict[str, str] = {
    "tech_ai": "AI Machine Learning Deep Learning Computer Vision NLP Neural Network Model Training MLOps",
    "tech_software": "Software Engineer Backend Frontend Fullstack DevOps Software Development API Database Microservice",
    "tech_data": "Data Engineer Data Analyst ETL Data Pipeline Analytics Business Intelligence SQL Data Warehouse",
    "sales": "Sales Business Development Account Management CRM Negotiation Lead Generation Revenue Customer Relationship B2B B2C",
    "marketing": "Digital Marketing SEO SEM Content Marketing Social Media Brand Campaign Advertising Growth",
    "finance": "Finance Accounting Financial Analysis Investment Banking Audit Tax Budgeting CFA Risk Management",
    "hr": "Human Resources Recruitment Talent Acquisition HRBP Training Employee Relations Payroll L&D",
    "operations": "Operations Supply Chain Logistics Procurement Process Improvement Lean Six Sigma Project Management",
}


# Seniority anchor descriptions
_SENIORITY_ANCHORS: Dict[int, str] = {
    0: "Internship Fresher entry level no experience trainee beginner intern junior trainee",
    1: "Junior Developer Junior Engineer Entry level with 1-2 years experience junior software engineer",
    2: "Mid-level Developer Software Engineer with 2-5 years experience mid senior independent contributor",
    3: "Senior Developer Senior Engineer Lead with 5+ years experience senior specialist expert technical lead",
    4: "Principal Lead Manager Director Head Chief with 7+ years experience principal architect manager director chief",
}


# Project tech → JD skill equivalence mapping
_PROJECT_TECH_EQUIVALENTS: Dict[str, List[str]] = {
    # Vision frameworks → specific CV concept
    "yolov8": ["yolo"],
    "yolov7": ["yolo"],
    "yolov5": ["yolo"],
    "ultralytics": ["yolo"],  # treat ultralytics as YOLO-related when present
    # Vision libraries → image processing
    "opencv": ["opencv"],
    # Annotation tools → data annotation (in combination with CV context)
    "roboflow": ["roboflow"],
    "labelme": [],
    "cvat": [],
    "labelbox": [],
    # Deep learning frameworks → deep learning
    "pytorch": ["pytorch"],
    "tensorflow": ["tensorflow"],
    "keras": ["keras"],
    "mxnet": [],
    # ML libraries → machine learning
    "scikit-learn": ["scikit-learn", "sklearn"],
    "sklearn": ["scikit-learn", "sklearn"],
    "xgboost": [],
    "lightgbm": [],
    # Data tools
    "pandas": [],
    "numpy": [],
    "matplotlib": [],
    "seaborn": [],
    "kaggle": [],
    # NLP / LLM related quick mappings
    "huggingface": ["huggingface", "transformers"],
    "transformers": ["transformers", "transformer"],
    "fastapi": ["fastapi"],
    "flask": ["flask"],
    "docker": ["docker"],
    "openai": ["openai"],
    "langchain": ["langchain"],
}


__all__ = [
    "_SOFT_SKILL_KEYS",
    "_DOMAIN_ANCHORS",
    "_SENIORITY_ANCHORS",
    "_PROJECT_TECH_EQUIVALENTS",
]
