# -*- coding: utf-8 -*-
"""
30 JD-CV benchmark pairs — fully synthetic, no reliance on existing files.

Covers 12 industry domains × multiple seniority levels.
"""
from typing import Dict, List

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 1: Software Engineering / Backend
# ══════════════════════════════════════════════════════════════════════════════

CV_SOFTWARE_SENIOR: Dict = {
    "personal_info": {"name": "Trần Đình Minh", "email": "minhtran.dev@gmail.com", "phone": "0901234567", "address": "TP.HCM"},
    "domain": "tech_software",
    "is_student": False,
    "career_objectives": "Principal Software Engineer với 8 năm kinh nghiệm trong hệ thống phân tán và cloud architecture. Mong muốn dẫn dắt team xây dựng nền tảng fintech quy mô lớn.",
    "education": [{"school": "ĐH Bách Khoa TP.HCM", "degree": "Thạc sĩ", "major": "Kỹ thuật Phần mềm", "start": "2014", "end": "2016"}],
    "work_experience": [
        {"company": "Techcombank", "title": "Principal Engineer", "start": "2020", "end": "Nay", "highlights": [
            "Thiết kế và xây dựng microservices cho hệ thống Core Banking xử lý 1M+ giao dịch/ngày.",
            "Dẫn dắt team 12 engineers, giảm system downtime từ 4% xuống 0.1%.",
            "Migration từ monolith sang Kubernetes trên AWS, tiết kiệm 40% chi phí infra."
        ]},
        {"company": "VNG Corporation", "title": "Senior Backend Engineer", "start": "2017", "end": "2020", "highlights": [
            "Xây dựng real-time notification service cho 50M+ người dùng Zalo.",
            "Optimize PostgreSQL queries giảm latency từ 800ms xuống 50ms.",
        ]},
    ],
    "projects": [
        {"name": "Distributed Payment Gateway", "role": "Tech Lead", "description": "Thiết kế payment gateway xử lý 10k TPS với Kafka, Redis, và PostgreSQL. Đạt 99.99% uptime.", "technologies": ["Java", "Spring Boot", "Kafka", "Redis", "PostgreSQL", "Docker", "Kubernetes"]}
    ],
    "skills": ["Java", "Spring Boot", "Python", "Go", "PostgreSQL", "Redis", "Kafka", "Docker", "Kubernetes", "AWS", "Microservices", "API Design", "System Design", "Git", "CI/CD", "Terraform"],
    "technical_skills": ["Java", "Spring Boot", "Go", "Python", "PostgreSQL", "Redis", "Kafka", "Docker", "Kubernetes", "AWS"],
    "domain_skills": ["Backend Development", "Distributed Systems", "Microservices", "Cloud Architecture", "System Design", "Performance Optimization"],
    "soft_skills": ["Team Leadership", "Technical Strategy", "Mentoring"],
    "certifications": ["AWS Solutions Architect Professional", "Google Cloud Professional Architect"],
}

CV_SOFTWARE_MID: Dict = {
    "personal_info": {"name": "Lê Thị Hương", "email": "huongle.backend@gmail.com", "phone": "0912345678", "address": "Hà Nội"},
    "domain": "tech_software",
    "is_student": False,
    "career_objectives": "Backend Engineer với 3 năm kinh nghiệm, chuyên về Python và API development. Tìm kiếm cơ hội phát triển trong môi trường product-driven startup.",
    "education": [{"school": "ĐH Công nghệ - ĐHQG HN", "degree": "Cử nhân", "major": "Công nghệ Thông tin", "start": "2016", "end": "2020"}],
    "work_experience": [
        {"company": " startup e-commerce", "title": "Backend Engineer", "start": "2021", "end": "Nay", "highlights": [
            "Xây dựng product catalog API phục vụ 100k người dùng với FastAPI và PostgreSQL.",
            "Triển khai caching layer với Redis, giảm DB load 60%.",
            "Viết automated tests đạt 85% code coverage."
        ]},
    ],
    "projects": [
        {"name": "Inventory Management System", "role": "Full-stack Developer", "description": "REST API cho hệ thống quản lý kho với FastAPI, PostgreSQL, và Vue.js frontend.", "technologies": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "Vue.js"]}
    ],
    "skills": ["Python", "FastAPI", "Django", "PostgreSQL", "Redis", "Docker", "Git", "REST API", "SQL", "AWS Basics"],
    "technical_skills": ["Python", "FastAPI", "Django", "PostgreSQL", "Redis", "Docker"],
    "domain_skills": ["Backend Development", "API Design", "Database Optimization", "Caching"],
    "soft_skills": ["Communication", "Problem Solving"],
    "certifications": [],
}

CV_SOFTWARE_FRESHER: Dict = {
    "personal_info": {"name": "Nguyễn Văn Phong", "email": "phongnv.cs@gmail.com", "phone": "0923456789", "address": "Đà Nẵng"},
    "domain": "tech_software",
    "is_student": True,
    "career_objectives": "Sinh viên năm cuối ngành CNTT, đam mê backend development. Tìm kiếm vị trí fresher để bắt đầu sự nghiệp.",
    "education": [{"school": "ĐH Bách Khoa Đà Nẵng", "degree": "Cử nhân", "major": "Công nghệ Thông tin", "start": "2022", "end": "2026"}],
    "work_experience": [],
    "projects": [
        {"name": "Student Management System", "role": "Course Project", "description": "Ứng dụng quản lý sinh viên với Flask và SQLite trong khuôn khổ bài tập lớn môn Cơ sở dữ liệu.", "technologies": ["Python", "Flask", "SQLite", "HTML", "CSS"]}
    ],
    "skills": ["Python", "Java", "C", "SQL", "Git", "Flask", "HTML", "CSS"],
    "technical_skills": ["Python", "Java", "C", "SQL", "Git"],
    "domain_skills": ["Basic Programming", "Database Fundamentals"],
    "soft_skills": ["Eager to Learn", "Teamwork"],
    "certifications": [],
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 2: AI / ML / Data Science
# ══════════════════════════════════════════════════════════════════════════════

CV_AI_SENIOR: Dict = {
    "personal_info": {"name": "Phạm Minh Tuấn", "email": "tuanpham.ai@gmail.com", "phone": "0934567890", "address": "Hà Nội"},
    "domain": "tech_ai",
    "is_student": False,
    "career_objectives": "Lead AI Engineer với 6 năm kinh nghiệm trong Computer Vision và Deep Learning. Mong muốn xây dựng AI platform quy mô production.",
    "education": [{"school": "ĐH Bách Khoa Hà Nội", "degree": "Thạc sĩ", "major": "Khoa học Máy tính", "start": "2016", "end": "2018"}],
    "work_experience": [
        {"company": "Viettel AI", "title": "Lead AI Engineer", "start": "2021", "end": "Nay", "highlights": [
            "Dẫn dắt team 8 AI engineers phát triển hệ thống face recognition cho 10M+ users.",
            "Deploy YOLOv8 + ArcFace trên edge devices với TensorRT, latency 25ms.",
            "Xây dựng AutoML pipeline giảm 50% thời gian model development."
        ]},
        {"company": "FPT Software", "title": "Senior AI Engineer", "start": "2018", "end": "2021", "highlights": [
            "Phát triển OCR engine cho hóa đơn Việt Nam đạt 97% accuracy.",
            "Implement object detection pipeline với Detectron2 cho retail analytics."
        ]},
    ],
    "projects": [
        {"name": "Smart Surveillance System", "role": "Tech Lead", "description": "Hệ thống giám sát thông minh với real-time face recognition và anomaly detection. Deploy trên NVIDIA Jetson với TensorRT.", "technologies": ["PyTorch", "TensorRT", "ONNX", "OpenCV", "YOLO", "Docker", "FastAPI"]}
    ],
    "skills": ["Python", "PyTorch", "TensorFlow", "OpenCV", "YOLO", "TensorRT", "ONNX", "Detectron2", "Docker", "FastAPI", "AWS", "Deep Learning", "Computer Vision", "CNN", "MLOps", "Model Optimization", "Model Deployment"],
    "technical_skills": ["Python", "PyTorch", "TensorFlow", "OpenCV", "YOLO", "TensorRT", "ONNX", "Docker", "FastAPI"],
    "domain_skills": ["Computer Vision", "Deep Learning", "Object Detection", "Face Recognition", "OCR", "MLOps", "Edge AI", "Model Optimization"],
    "soft_skills": ["Team Leadership", "Research", "Mentoring"],
    "certifications": ["NVIDIA Deep Learning Certification", "AWS ML Specialty"],
}

CV_AI_MID: Dict = {
    "personal_info": {"name": "Trần Thị Lan", "email": "lantran.ml@gmail.com", "phone": "0945678901", "address": "TP.HCM"},
    "domain": "tech_ai",
    "is_student": False,
    "career_objectives": "AI Engineer với 2 năm kinh nghiệm chuyên về NLP và LLM applications. Tìm kiếm cơ hội phát triển chuyên sâu trong generative AI.",
    "education": [{"school": "ĐH KHTN TP.HCM", "degree": "Cử nhân", "major": "Khoa học Dữ liệu", "start": "2016", "end": "2020"}],
    "work_experience": [
        {"company": "CMC Corporation", "title": "AI Engineer", "start": "2022", "end": "Nay", "highlights": [
            "Xây dựng RAG chatbot cho ngân hàng với LangChain + FAISS + GPT-4, phục vụ 5k người dùng/ngày.",
            "Fine-tune Vietnamese BERT cho sentiment classification, F1 cải thiện từ 0.78 lên 0.89.",
            "Deploy FastAPI endpoint cho LLM inference với Redis caching và load balancing."
        ]},
    ],
    "projects": [
        {"name": "Vietnamese Legal Document Q&A", "role": "Lead Developer", "description": "RAG system cho tra cứu văn bản pháp luật sử dụng LangChain, ChromaDB, và GPT-3.5. Đạt 85% answer accuracy trên benchmark 500 câu hỏi.", "technologies": ["Python", "LangChain", "ChromaDB", "OpenAI API", "FastAPI", "Docker", "Hugging Face"]}
    ],
    "skills": ["Python", "PyTorch", "Hugging Face", "LangChain", "LlamaIndex", "FastAPI", "FAISS", "ChromaDB", "OpenAI API", "BERT", "RAG", "LLM", "NLP", "Fine-tuning", "Text Classification", "Docker"],
    "technical_skills": ["Python", "PyTorch", "Hugging Face", "LangChain", "FastAPI", "FAISS", "OpenAI API"],
    "domain_skills": ["NLP", "LLM", "RAG", "Chatbot", "Fine-tuning", "Vietnamese NLP", "Vector Search", "Prompt Engineering"],
    "soft_skills": ["Problem Solving", "Research"],
    "certifications": ["Deep Learning Specialization (Coursera)"],
}

CV_DATA_SCIENTIST: Dict = {
    "personal_info": {"name": "Hoàng Thị Mai", "email": "maihoang.ds@gmail.com", "phone": "0956789012", "address": "Hà Nội"},
    "domain": "tech_data",
    "is_student": False,
    "career_objectives": "Data Scientist với 3 năm kinh nghiệm trong predictive analytics và A/B testing. Mong muốn đóng góp vào data-driven decision making.",
    "education": [{"school": "ĐH Kinh tế Quốc dân", "degree": "Cử nhân", "major": "Thống kê Kinh tế", "start": "2015", "end": "2019"}],
    "work_experience": [
        {"company": "Lazada Vietnam", "title": "Data Scientist", "start": "2021", "end": "Nay", "highlights": [
            "Xây dựng churn prediction model giảm churn rate 18% với XGBoost và feature engineering.",
            "Design A/B testing framework phân tích 20+ experiments mỗi tháng.",
            "Tạo automated dashboards theo dõi 50+ KPIs với Tableau và Python."
        ]},
    ],
    "projects": [
        {"name": "Customer Lifetime Value Prediction", "role": "Data Scientist", "description": "CLV prediction model với LightGBM và SHAP values cho customer segmentation. Revenue impact: +12% từ targeted campaigns.", "technologies": ["Python", "XGBoost", "LightGBM", "Scikit-learn", "SQL", "Tableau", "AWS"]}
    ],
    "skills": ["Python", "SQL", "R", "XGBoost", "LightGBM", "Scikit-learn", "TensorFlow", "Pandas", "Tableau", "Power BI", "A/B Testing", "Statistical Analysis", "Feature Engineering", "Data Visualization"],
    "technical_skills": ["Python", "SQL", "R", "XGBoost", "LightGBM", "Tableau", "Power BI"],
    "domain_skills": ["Predictive Analytics", "A/B Testing", "Customer Analytics", "Data Visualization", "Statistical Modeling"],
    "soft_skills": ["Business Communication", "Critical Thinking"],
    "certifications": ["Google Data Analytics Certificate"],
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 3: DevOps / Cloud
# ══════════════════════════════════════════════════════════════════════════════

CV_DEVOPS_SENIOR: Dict = {
    "personal_info": {"name": "Đặng Văn Hùng", "email": "hungdang.devops@gmail.com", "phone": "0967890123", "address": "Hà Nội"},
    "domain": "tech_devops",
    "is_student": False,
    "career_objectives": "DevOps/SRE Lead với 5 năm kinh nghiệm trong cloud infrastructure và CI/CD. Mong muốn xây dựng nền tảng platform engineering.",
    "education": [{"school": "Học viện Kỹ thuật Quân sự", "degree": "Cử nhân", "major": "Công nghệ Thông tin", "start": "2013", "end": "2017"}],
    "work_experience": [
        {"company": "VNG Cloud", "title": "SRE Lead", "start": "2021", "end": "Nay", "highlights": [
            "Quản lý Kubernetes clusters phục vụ 500+ microservices với 99.99% SLA.",
            "Xây dựng CI/CD pipeline với GitLab CI giảm deployment time từ 2 giờ xuống 10 phút.",
            "Implement observability stack (Prometheus, Grafana, Loki, Jaeger) cho toàn bộ hệ thống."
        ]},
        {"company": "FPT Software", "title": "DevOps Engineer", "start": "2019", "end": "2021", "highlights": [
            "Tự động hóa infrastructure provisioning với Terraform và Ansible.",
            "Setup và quản lý CI/CD pipeline cho 30+ projects."
        ]},
    ],
    "projects": [
        {"name": "Zero-Downtime Migration to Kubernetes", "role": "SRE Lead", "description": "Migration thành công 200+ VMs sang Kubernetes trên AWS EKS với zero-downtime blue-green deployment.", "technologies": ["Kubernetes", "AWS EKS", "Terraform", "Ansible", "GitLab CI", "Prometheus", "Grafana"]}
    ],
    "skills": ["Kubernetes", "Docker", "AWS", "GCP", "Terraform", "Ansible", "GitLab CI", "Jenkins", "Prometheus", "Grafana", "Linux", "Python", "Bash", "Networking", "Security"],
    "technical_skills": ["Kubernetes", "Docker", "AWS", "Terraform", "Ansible", "GitLab CI", "Prometheus", "Grafana"],
    "domain_skills": ["Platform Engineering", "SRE", "CI/CD", "Infrastructure as Code", "Cloud Architecture", "Observability"],
    "soft_skills": ["Incident Management", "Cross-team Collaboration"],
    "certifications": ["CKA (Certified Kubernetes Administrator)", "AWS Solutions Architect"],
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 4: Sales / Business Development
# ══════════════════════════════════════════════════════════════════════════════

CV_SALES_SENIOR: Dict = {
    "personal_info": {"name": "Nguyễn Thị Hồng", "email": "hongnguyen.sales@gmail.com", "phone": "0978901234", "address": "TP.HCM"},
    "domain": "sales",
    "is_student": False,
    "career_objectives": "Regional Sales Director với 8 năm kinh nghiệm trong enterprise SaaS sales. Mong muốn dẫn dắt đội ngũ sales khu vực miền Nam.",
    "education": [{"school": "ĐH Kinh tế TP.HCM", "degree": "Cử nhân", "major": "Quản trị Kinh doanh", "start": "2012", "end": "2016"}],
    "work_experience": [
        {"company": "Salesforce Vietnam", "title": "Regional Sales Director", "start": "2022", "end": "Nay", "highlights": [
            "Quản lý đội ngũ 15 AEs và SDAs, đạt 140% quota với $5M ARR.",
            "Xây dựng enterprise sales playbook giảm sales cycle 30%.",
            "Phát triển 50+ Fortune 500 accounts tại Việt Nam và Đông Dương."
        ]},
        {"company": "SAP Vietnam", "title": "Senior Account Executive", "start": "2018", "end": "2022", "highlights": [
            "Closed $2M enterprise deal với VNPT — biggest deal in SEA region năm đó.",
            "Negotiate multi-year contracts với các tập đoàn nhà nước."
        ]},
    ],
    "projects": [],
    "skills": ["Enterprise Sales", "Solution Selling", "Salesforce", "HubSpot", "Negotiation", "Contract Management", "Account Planning", "Team Leadership", "B2B Sales", "Sales Forecasting", "CRM", "Business Development"],
    "technical_skills": ["Salesforce", "HubSpot", "Microsoft Office 365", "Power BI"],
    "domain_skills": ["Enterprise SaaS", "B2B Sales", "Solution Selling", "Account Management", "Channel Sales"],
    "soft_skills": ["Executive Presence", "Strategic Thinking", "Negotiation", "Leadership"],
    "certifications": ["Challenger Sale Certified", "MEDDIC Framework Certified", "HubSpot Sales Pro"],
}

CV_SALES_FRESHER: Dict = {
    "personal_info": {"name": "Lê Hoàng Nam", "email": "namle.sales@gmail.com", "phone": "0989012345", "address": "Hà Nội"},
    "domain": "sales",
    "is_student": True,
    "career_objectives": "Sinh viên năm cuối ngành Marketing, mong muốn bắt đầu sự nghiệp trong lĩnh vực sales và business development.",
    "education": [{"school": "ĐH Thương mại", "degree": "Cử nhân", "major": "Marketing", "start": "2022", "end": "2026"}],
    "work_experience": [
        {"company": "Shopee", "title": "Part-time Sales Support", "start": "2024", "end": "Nay", "highlights": ["Hỗ trợ team sales xử lý 20+ khách hàng/ngày qua chat và điện thoại.", "Thực hiện cold outreach cho 100+ potential customers."]}
    ],
    "projects": [
        {"name": "Marketing Plan for Local Brand", "role": "Team Leader", "description": "Kế hoạch marketing tích hợp cho thương hiệu cà phê địa phương — đạt giải nhất cuộc thi kinh doanh cấp trường.", "technologies": ["Canva", "Google Analytics", "Social Media Strategy"]}
    ],
    "skills": ["Customer Service", "Communication", "Microsoft Office", "Canva", "Social Media", "Teamwork", "Active Listening"],
    "technical_skills": ["Microsoft Office", "Canva", "Google Analytics"],
    "domain_skills": ["Basic Sales", "Customer Service", "Marketing Fundamentals"],
    "soft_skills": ["Enthusiasm", "Eager to Learn", "Teamwork"],
    "certifications": ["Google Digital Marketing Certificate"],
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 5: Marketing / Digital Marketing
# ══════════════════════════════════════════════════════════════════════════════

CV_MARKETING_MID: Dict = {
    "personal_info": {"name": "Phạm Thị Thu", "email": "thupham.mkt@gmail.com", "phone": "0990123456", "address": "TP.HCM"},
    "domain": "marketing",
    "is_student": False,
    "career_objectives": "Digital Marketing Manager với 4 năm kinh nghiệm trong performance marketing và content strategy. Mong muốn dẫn dắt marketing cho startup tech.",
    "education": [{"school": "ĐH Khoa học Xã hội và Nhân văn", "degree": "Cử nhân", "major": "Truyền thông Marketing", "start": "2014", "end": "2018"}],
    "work_experience": [
        {"company": "Misa Vietnam", "title": "Digital Marketing Manager", "start": "2022", "end": "Nay", "highlights": [
            "Quản lý ngân sách marketing $500k/tháng, ROAS đạt 4.2x trên Google Ads và Meta Ads.",
            "Xây dựng content strategy tăng organic traffic 200% trong 12 tháng.",
            "Dẫn dắt team 5 content creators và performance marketers."
        ]},
        {"company": "Vietnamworks", "title": "Marketing Executive", "start": "2020", "end": "2022", "highlights": [
            "Chạy các chiến dịch SEO và SEM tăng 50% leads cho product B2B."
        ]},
    ],
    "projects": [
        {"name": "Omnichannel Marketing Campaign", "role": "Campaign Manager", "description": "Chiến dịch marketing đa kênh cho product launch mới, đạt 10k pre-orders trong tuần đầu.", "technologies": ["Google Ads", "Meta Ads", "Email Marketing", "HubSpot", "Analytics"]}
    ],
    "skills": ["Google Ads", "Meta Ads", "SEO", "Content Marketing", "Email Marketing", "HubSpot", "Google Analytics", "A/B Testing", "Marketing Strategy", "Social Media", "Copywriting"],
    "technical_skills": ["Google Ads", "Meta Ads", "HubSpot", "Google Analytics", "SEO Tools"],
    "domain_skills": ["Performance Marketing", "Content Strategy", "SEO/SEM", "Marketing Analytics", "Brand Management"],
    "soft_skills": ["Creative Thinking", "Data-driven", "Leadership"],
    "certifications": ["Google Ads Certification", "Meta Blueprint Certification"],
}

CV_MARKETING_FRESHER: Dict = {
    "personal_info": {"name": "Vũ Thị Lan", "email": "lanvu.mkt@gmail.com", "phone": "0901234560", "address": "Đà Nẵng"},
    "domain": "marketing",
    "is_student": True,
    "career_objectives": "Sinh viên năm cuối đam mê digital marketing và social media. Tìm kiếm vị trí marketing intern để học hỏi thực tế.",
    "education": [{"school": "ĐH Kinh tế Đà Nẵng", "degree": "Cử nhân", "major": "Marketing", "start": "2022", "end": "2026"}],
    "work_experience": [],
    "projects": [
        {"name": "Social Media Strategy Portfolio", "role": "Personal Project", "description": "Quản lý fanpage Instagram cá nhân với 5k followers, tạo content plan và thực hiện 50+ posts trong 3 tháng.", "technologies": ["Canva", "Instagram Insights", "Buffer"]}
    ],
    "skills": ["Social Media", "Content Creation", "Canva", "Copywriting", "Microsoft Office", "Basic SEO"],
    "technical_skills": ["Canva", "Buffer", "Instagram Insights", "Google Analytics"],
    "domain_skills": ["Social Media Marketing", "Content Creation"],
    "soft_skills": ["Creativity", "Eager to Learn"],
    "certifications": [],
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 6: Finance / Accounting
# ══════════════════════════════════════════════════════════════════════════════

CV_FINANCE_MID: Dict = {
    "personal_info": {"name": "Trần Văn Long", "email": "longtran.finance@gmail.com", "phone": "0912345670", "address": "Hà Nội"},
    "domain": "finance",
    "is_student": False,
    "career_objectives": "Finance Manager với 5 năm kinh nghiệm trong FP&A và financial modeling. Mong muốn phát triển trong môi trường fintech.",
    "education": [{"school": "ĐH Kinh tế Quốc dân", "degree": "Thạc sĩ", "major": "Tài chính - Ngân hàng", "start": "2016", "end": "2018"}],
    "work_experience": [
        {"company": "VPBank", "title": "Finance Manager", "start": "2021", "end": "Nay", "highlights": [
            "Quản lý báo cáo tài chính cho chi nhánh với tổng tài sản 5T VND.",
            "Xây dựng financial models phục vụ M&A deal trị giá $20M.",
            "Automate reporting pipeline với Python và Power BI giảm 60% thời gian close books."
        ]},
        {"company": "Big4 Audit Firm", "title": "Senior Auditor", "start": "2019", "end": "2021", "highlights": ["Audit báo cáo tài chính cho 15+ doanh nghiệp niêm yết."]},
    ],
    "projects": [
        {"name": "Financial Dashboard for CFO", "role": "Finance Manager", "description": "Xây dựng real-time financial dashboard với Power BI và Python automation, theo dõi 50+ financial KPIs.", "technologies": ["Python", "Power BI", "Excel", "SAP", "SQL"]}
    ],
    "skills": ["Financial Modeling", "FP&A", "Power BI", "Excel", "Python", "SQL", "SAP", "IFRS", "Corporate Finance", "Budgeting", "Financial Analysis"],
    "technical_skills": ["Python", "Power BI", "Excel Advanced", "SQL", "SAP"],
    "domain_skills": ["Financial Analysis", "FP&A", "Financial Modeling", "Corporate Finance", "Audit"],
    "soft_skills": ["Attention to Detail", "Analytical Thinking"],
    "certifications": ["CPA", "CFA Level 1"],
}

CV_FINANCE_FRESHER: Dict = {
    "personal_info": {"name": "Nguyễn Thị Phương", "email": "phuongngan.finance@gmail.com", "phone": "0923456780", "address": "TP.HCM"},
    "domain": "finance",
    "is_student": True,
    "career_objectives": "Sinh viên năm cuối ngành Tài chính, tìm kiếm vị trí finance intern để áp dụng kiến thức vào thực tế.",
    "education": [{"school": "ĐH Tài chính - Marketing", "degree": "Cử nhân", "major": "Tài chính", "start": "2022", "end": "2026"}],
    "work_experience": [
        {"company": "Accounting Firm", "title": "Part-time Accounting Assistant", "start": "2024", "end": "Nay", "highlights": ["Hỗ trợ nhập liệu và đối chiếu báo cáo tài chính cho 5 doanh nghiệp nhỏ."]}
    ],
    "projects": [
        {"name": "Financial Ratio Analysis Project", "role": "Course Project", "description": "Phân tích tỷ số tài chính của 10 doanh nghiệp ngành bán lẻ Việt Nam trong khuôn khổ bài tập môn Tài chính Doanh nghiệp.", "technologies": ["Excel", "PowerPoint"]}
    ],
    "skills": ["Excel", "PowerPoint", "Basic Accounting", "Financial Analysis"],
    "technical_skills": ["Excel", "PowerPoint"],
    "domain_skills": ["Basic Accounting", "Financial Ratios"],
    "soft_skills": ["Detail-oriented", "Eager to Learn"],
    "certifications": [],
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 7: HR / Human Resources
# ══════════════════════════════════════════════════════════════════════════════

CV_HR_MID: Dict = {
    "personal_info": {"name": "Lê Thị Hà", "email": "hale.hr@gmail.com", "phone": "0934567891", "address": "Hà Nội"},
    "domain": "hr",
    "is_student": False,
    "career_objectives": "HR Business Partner với 4 năm kinh nghiệm trong talent acquisition và employee engagement. Mong muốn đóng góp vào culture building.",
    "education": [{"school": "ĐH Lao động Xã hội", "degree": "Cử nhân", "major": "Quản trị Nhân sự", "start": "2014", "end": "2018"}],
    "work_experience": [
        {"company": "Shopee Vietnam", "title": "HR Business Partner", "start": "2022", "end": "Nay", "highlights": [
            "Partner với 8 heads of department, hỗ trợ tuyển 200+ positions/năm.",
            "Xây dựng onboarding program giảm 30% early attrition trong 90 ngày đầu.",
            "Dẫn dắt employee engagement survey đạt 78% participation rate."
        ]},
        {"company": "Navigos Group", "title": "Recruitment Consultant", "start": "2020", "end": "2022", "highlights": ["Headhunt 50+ candidates cho các vị trí senior tại clients Fortune 500."]},
    ],
    "projects": [
        {"name": "Employer Branding Campaign", "role": "HRBP Lead", "description": "Chiến dịch employer branding trên LinkedIn và Facebook, tăng 150% application volume và giảm time-to-hire 20%.", "technologies": ["LinkedIn", "Facebook Ads", "HRIS", "Greenhouse"]}
    ],
    "skills": ["Talent Acquisition", "Employer Branding", "Employee Engagement", "HRIS", "Greenhouse", "Interviewing", "HR Analytics", "Labor Law", "Performance Management", "Succession Planning"],
    "technical_skills": ["Greenhouse", "HRIS", "LinkedIn Recruiter", "Microsoft Office"],
    "domain_skills": ["Talent Acquisition", "HRBP", "Employee Relations", "HR Analytics", "Culture Building"],
    "soft_skills": ["Empathy", "Communication", "Stakeholder Management"],
    "certifications": ["SPHRi", "SHL Assessment Certified"],
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 8: Healthcare / Medical
# ══════════════════════════════════════════════════════════════════════════════

CV_HEALTHCARE_MID: Dict = {
    "personal_info": {"name": "Hoàng Văn Minh", "email": "minhhoang.health@gmail.com", "phone": "0945678902", "address": "TP.HCM"},
    "domain": "healthcare",
    "is_student": False,
    "career_objectives": "Healthcare Administrator với 3 năm kinh nghiệm trong hospital operations và healthcare IT. Tìm kiếm cơ hội phát triển trong healthtech.",
    "education": [{"school": "ĐH Y dược TP.HCM", "degree": "Cử nhân", "major": "Y tế Công cộng", "start": "2014", "end": "2018"}],
    "work_experience": [
        {"company": "FV Hospital", "title": "Healthcare Administrator", "start": "2021", "end": "Nay", "highlights": [
            "Quản lý vận hành phòng khám đa khoa với 500+ bệnh nhân/ngày.",
            "Implement HIS (Hospital Information System) cải thiện patient wait time 35%.",
            "Quản lý ngân sách vận hành 2T VND/năm và đạt 95% budget adherence."
        ]},
    ],
    "projects": [
        {"name": "Telemedicine Platform Setup", "role": "Project Lead", "description": "Thiết lập telemedicine platform cho 20k+ telehealth consultations trong năm đầu tiên.", "technologies": ["Telemedicine Platform", "HIS", "Microsoft Teams", "Patient Management System"]}
    ],
    "skills": ["Hospital Operations", "Healthcare IT", "Patient Management", "Healthcare Regulations", "Budget Management", "HIS", "Project Management", "HIPAA Compliance", "Stakeholder Management"],
    "technical_skills": ["HIS", "Healthcare IT Systems", "Microsoft Office", "Project Management Tools"],
    "domain_skills": ["Hospital Administration", "Healthcare IT", "Patient Experience", "Medical Records Management"],
    "soft_skills": ["Patient Care Mindset", "Cross-functional Collaboration"],
    "certifications": ["Healthcare Administration Certificate", "HIPAA Training"],
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 9: Education / Teaching
# ══════════════════════════════════════════════════════════════════════════════

CV_EDUCATION_MID: Dict = {
    "personal_info": {"name": "Trần Thị Hương", "email": "huongtran.edu@gmail.com", "phone": "0956789013", "address": "Hà Nội"},
    "domain": "education",
    "is_student": False,
    "career_objectives": "Education Manager với 5 năm kinh nghiệm trong edtech và curriculum development. Mong muốn xây dựng scalable learning programs.",
    "education": [{"school": "ĐH Sư phạm Hà Nội", "degree": "Thạc sĩ", "major": "Quản lý Giáo dục", "start": "2016", "end": "2018"}],
    "work_experience": [
        {"company": "Apollo Education", "title": "Education Manager", "start": "2021", "end": "Nay", "highlights": [
            "Quản lý 30+ giáo viên và 2,000+ học viên tại 3 chi nhánh.",
            "Phát triển curriculum mới cho chương trình IELTS và SAT tăng 25% pass rate.",
            "Implement LMS (Moodle) và training modules giảm teacher prep time 40%."
        ]},
        {"company": "VUS", "title": "Senior Teacher", "start": "2019", "end": "2021", "highlights": ["Giảng dạy 15 classes/tuần, được đánh giá 4.8/5.0 bởi học viên."]},
    ],
    "projects": [
        {"name": "Blended Learning Program", "role": "Program Designer", "description": "Thiết kế chương trình học kết hợp online-offline cho 500+ students, duy trì 90% student retention rate.", "technologies": ["Moodle", "Zoom", "Google Classroom", "Google Analytics"]}
    ],
    "skills": ["Curriculum Development", "LMS Management", "Teacher Training", "EdTech Tools", "Moodle", "Microsoft Teams", "Data Analysis", "Educational Assessment", "Student Advising", "CELTA"],
    "technical_skills": ["Moodle", "Microsoft Teams", "Zoom", "Google Analytics"],
    "domain_skills": ["EdTech", "Curriculum Design", "Teacher Development", "Learning Analytics"],
    "soft_skills": ["Patience", "Communication", "Mentoring"],
    "certifications": ["CELTA", "Google Certified Educator"],
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 10: UX/UI Design
# ══════════════════════════════════════════════════════════════════════════════

CV_DESIGN_MID: Dict = {
    "personal_info": {"name": "Phạm Thị Linh", "email": "linhpham.design@gmail.com", "phone": "0967890124", "address": "TP.HCM"},
    "domain": "design",
    "is_student": False,
    "career_objectives": "Senior UX Designer với 4 năm kinh nghiệm trong product design và design systems. Mong muốn đóng góp vào product-led organization.",
    "education": [{"school": "ĐH Bách khoa TP.HCM", "degree": "Cử nhân", "major": "Thiết kế Công nghiệp", "start": "2014", "end": "2018"}],
    "work_experience": [
        {"company": "Tiki", "title": "Senior UX Designer", "start": "2022", "end": "Nay", "highlights": [
            "Dẫn dắt redesign checkout flow tăng conversion rate từ 60% lên 78%.",
            "Xây dựng design system với 200+ components phục vụ 8 product teams.",
            "Conduct 50+ user interviews và usability tests để validate design decisions."
        ]},
        {"company": "Freelance", "title": "UI/UX Designer", "start": "2019", "end": "2022", "highlights": ["Design UI cho 20+ mobile apps và websites cho các startups Đông Nam Á."]},
    ],
    "projects": [
        {"name": "E-commerce Design System", "role": "Lead Designer", "description": "Xây dựng design system cho Tiki bao gồm 200+ components, token system, và documentation site.", "technologies": ["Figma", "Storybook", "Zeplin", "Principle"]}
    ],
    "skills": ["Figma", "Sketch", "Adobe XD", "Prototyping", "User Research", "Usability Testing", "Design Systems", "Wireframing", "Information Architecture", "CSS Basics", "HTML Basics", "Design Thinking"],
    "technical_skills": ["Figma", "Sketch", "Adobe XD", "Principle", "Storybook"],
    "domain_skills": ["Product Design", "UX Research", "Design Systems", "Mobile Design", "Web Design", "Accessibility"],
    "soft_skills": ["Empathy", "Collaboration", "Presentation"],
    "certifications": ["Google UX Design Certificate", "Interaction Design Foundation"],
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 11: Project Management / Operations
# ══════════════════════════════════════════════════════════════════════════════

CV_PM_MID: Dict = {
    "personal_info": {"name": "Nguyễn Văn Đức", "email": "ducnguyen.pm@gmail.com", "phone": "0978901235", "address": "Hà Nội"},
    "domain": "operations",
    "is_student": False,
    "career_objectives": "Senior Project Manager với 5 năm kinh nghiệm trong software project delivery. Mong muốn dẫn dắt các dự án transformation lớn.",
    "education": [{"school": "ĐH Bách Khoa Hà Nội", "degree": "Cử nhân", "major": "Kỹ thuật Phần mềm", "start": "2013", "end": "2017"}],
    "work_experience": [
        {"company": "Viettel Solutions", "title": "Senior Project Manager", "start": "2021", "end": "Nay", "highlights": [
            "Quản lý 3 software projects đồng thời với tổng budget $3M, tất cả delivery đúng deadline và trong budget.",
            "Implement Agile/Scrum framework cho team 40+ engineers.",
            "Reduce project risk incidents 60% thông qua structured risk management process."
        ]},
        {"company": "Vingroup", "title": "Project Coordinator", "start": "2018", "end": "2021", "highlights": ["Coordinate software development projects với 10+ stakeholders."]},
    ],
    "projects": [
        {"name": "Digital Transformation Program", "role": "Program Manager", "description": "Quản lý chương trình transformation 3 dự án cho Viettel Solutions, tổng giá trị $2M, hoàn thành sớm 2 tuần.", "technologies": ["Jira", "Confluence", "MS Project", "Miro", "Agile/Scrum"]}
    ],
    "skills": ["Project Management", "Agile", "Scrum", "Jira", "Confluence", "Risk Management", "Stakeholder Management", "Budget Management", "Vendor Management", "PMP", "Communication", "MS Project"],
    "technical_skills": ["Jira", "Confluence", "MS Project", "Miro"],
    "domain_skills": ["Software Project Management", "Agile Delivery", "Program Management", "Stakeholder Management"],
    "soft_skills": ["Leadership", "Communication", "Conflict Resolution"],
    "certifications": ["PMP", "Scrum Master Certified", "PRINCE2"],
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN 12: Cybersecurity
# ══════════════════════════════════════════════════════════════════════════════

CV_CYBERSECURITY_MID: Dict = {
    "personal_info": {"name": "Đặng Minh Tuấn", "email": "tuangdang.sec@gmail.com", "phone": "0989012346", "address": "Hà Nội"},
    "domain": "tech_security",
    "is_student": False,
    "career_objectives": "Security Engineer với 3 năm kinh nghiệm trong application security và SOC operations. Mong muốn phát triển chuyên sâu trong cybersecurity.",
    "education": [{"school": "Học viện Kỹ thuật Mật mã", "degree": "Cử nhân", "major": "An toàn Thông tin", "start": "2014", "end": "2018"}],
    "work_experience": [
        {"company": "BKAV", "title": "Security Engineer", "start": "2022", "end": "Nay", "highlights": [
            "Conduct penetration testing cho 20+ enterprise applications, phát hiện 100+ vulnerabilities.",
            "Setup và vận hành SIEM platform (Splunk) cho 5 enterprise clients.",
            "Xây dựng security awareness training program giảm phishing click rate từ 25% xuống 5%."
        ]},
    ],
    "projects": [
        {"name": "SOC Automation Framework", "role": "Security Engineer", "description": "Xây dựng SOAR playbook tự động hóa 70% incident response workflow, giảm MTTR từ 4 giờ xuống 45 phút.", "technologies": ["Splunk", "Python", "CrowdStrike", "Qualys", "Burp Suite"]}
    ],
    "skills": ["Penetration Testing", "SIEM", "SOC", "Incident Response", "Vulnerability Assessment", "Python", "Splunk", "CrowdStrike", "Qualys", "Burp Suite", "OWASP", "Network Security", "Cloud Security", "Linux", "Networking"],
    "technical_skills": ["Splunk", "Python", "CrowdStrike", "Qualys", "Burp Suite", "Nmap"],
    "domain_skills": ["Application Security", "SOC Operations", "Incident Response", "Vulnerability Management", "SIEM"],
    "soft_skills": ["Analytical Thinking", "Under Pressure", "Communication"],
    "certifications": ["CEH", "CompTIA Security+", "Splunk Core Certified User"],
}

# ══════════════════════════════════════════════════════════════════════════════
# SYNTHETIC JOB DESCRIPTIONS (15 diverse JDs)
# ══════════════════════════════════════════════════════════════════════════════

JD_SENIOR_SOFTWARE_ENG = {
    "job_title": "Senior Software Engineer (Backend/Platform)",
    "structured": {
        "job_title": "Senior Software Engineer (Backend/Platform)",
        "location": "Hà Nội / Remote",
        "domain": "tech_software",
        "is_entry_level": False,
        "seniority": "Senior",
        "years_of_experience": "5-8 years",
        "skills_required": ["Java", "Python", "Go", "Microservices", "PostgreSQL", "Redis", "Kafka", "Docker", "Kubernetes", "AWS", "API Design", "System Design", "CI/CD", "Git"],
        "skills_preferred": ["Terraform", "gRPC", "GraphQL", "MongoDB", "C++"],
        "responsibilities": [
            "Thiết kế và phát triển scalable backend systems cho nền tảng fintech.",
            "Dẫn dắt technical architecture decisions cho các tính năng mới.",
            "Mentor junior engineers và review code.",
            "Optimize system performance và reliability.",
            "Collaborate với cross-functional teams để deliver product."
        ],
        "requirements": [
            "5+ năm kinh nghiệm trong backend development.",
            "Thành thạo Java hoặc Go hoặc Python.",
            "Kinh nghiệm với distributed systems và microservices architecture.",
            "Thành thạo PostgreSQL, Redis, Kafka.",
            "Có kinh nghiệm với Docker, Kubernetes, và cloud (AWS/GCP).",
            "Có kinh nghiệm thiết kế API và system design."
        ],
        "benefits": ["Equity", "Remote work", "Learning budget", "Health insurance"],
        "industry": "Fintech / SaaS",
        "skill_importance": {
            "Java": "CRITICAL", "Python": "CRITICAL", "Go": "CRITICAL",
            "Microservices": "CRITICAL", "PostgreSQL": "CRITICAL",
            "Kubernetes": "IMPORTANT", "AWS": "IMPORTANT",
            "Kafka": "IMPORTANT", "API Design": "CRITICAL",
        },
    }
}

JD_MID_BACKEND = {
    "job_title": "Backend Engineer",
    "structured": {
        "job_title": "Backend Engineer",
        "location": "TP.HCM / Hybrid",
        "domain": "tech_software",
        "is_entry_level": False,
        "seniority": "Mid",
        "years_of_experience": "2-4 years",
        "skills_required": ["Python", "FastAPI", "Django", "PostgreSQL", "Redis", "Docker", "Git", "REST API", "SQL"],
        "skills_preferred": ["AWS", "GraphQL", "Celery", "MongoDB"],
        "responsibilities": [
            "Phát triển REST APIs cho các sản phẩm nội bộ và khách hàng.",
            "Thiết kế và quản lý database schemas.",
            "Viết automated tests và maintain documentation.",
            "Collaborate với frontend team để integrate APIs."
        ],
        "requirements": [
            "2+ năm kinh nghiệm backend development.",
            "Thành thạo Python và một framework (FastAPI/Django).",
            "Kinh nghiệm với PostgreSQL và Redis.",
            "Hiểu biết về RESTful API design.",
            "Sử dụng được Git và CI/CD cơ bản."
        ],
        "benefits": ["Hybrid work", "Learning budget", "Tech talks"],
        "industry": "SaaS / Tech",
        "skill_importance": {
            "Python": "CRITICAL", "FastAPI": "CRITICAL",
            "PostgreSQL": "CRITICAL", "REST API": "CRITICAL",
            "Docker": "IMPORTANT", "Redis": "IMPORTANT",
        },
    }
}

JD_FRESHER_SOFTWARE = {
    "job_title": "Software Engineer Fresher",
    "structured": {
        "job_title": "Software Engineer Fresher",
        "location": "Hà Nội / Onsite",
        "domain": "tech_software",
        "is_entry_level": True,
        "seniority": "Fresher",
        "years_of_experience": "0-1 year",
        "skills_required": ["Python", "Java", "C", "SQL", "Git", "Data Structures", "Algorithms"],
        "skills_preferred": ["JavaScript", "React", "Docker"],
        "responsibilities": [
            "Phát triển tính năng mới dưới sự hướng dẫn của senior engineer.",
            "Fix bugs và viết unit tests.",
            "Tham gia code reviews và team discussions."
        ],
        "requirements": [
            "Sinh viên năm cuối hoặc mới tốt nghiệp ngành CNTT.",
            "Nắm vững ít nhất một ngôn ngữ: Python, Java, hoặc C.",
            "Hiểu basic data structures và algorithms.",
            "Sử dụng được Git cơ bản.",
            "Eager to learn và teamwork."
        ],
        "benefits": ["Mentorship", "Training program", "Flexible hours"],
        "industry": "Tech",
        "skill_importance": {
            "Python": "CRITICAL", "Java": "CRITICAL", "Data Structures": "CRITICAL",
            "Algorithms": "CRITICAL", "Git": "IMPORTANT",
        },
    }
}

JD_SENIOR_AI = {
    "job_title": "Senior AI Engineer (Computer Vision)",
    "structured": {
        "job_title": "Senior AI Engineer (Computer Vision)",
        "location": "Hà Nội / Remote OK",
        "domain": "tech_ai",
        "is_entry_level": False,
        "seniority": "Senior",
        "years_of_experience": "4-7 years",
        "skills_required": ["Python", "PyTorch", "TensorFlow", "OpenCV", "Computer Vision", "Deep Learning", "YOLO", "CNN", "TensorRT", "ONNX", "Model Deployment", "Docker", "Git"],
        "skills_preferred": ["C++", "CUDA", "Jetson", "MLOps", "Kubernetes"],
        "responsibilities": [
            "Dẫn dắt CV R&D initiatives cho các sản phẩm AI production.",
            "Phát triển và optimize computer vision models (face recognition, OCR, object detection).",
            "Deploy models lên edge và cloud với TensorRT/ONNX.",
            "Xây dựng ML pipelines và automation.",
            "Mentor junior AI engineers."
        ],
        "requirements": [
            "4+ năm kinh nghiệm trong Computer Vision.",
            "Thành thạo PyTorch và OpenCV.",
            "Kinh nghiệm với model optimization (TensorRT, quantization, pruning).",
            "Đã deploy CV models vào production.",
            "Hiểu biết về CNN architectures, YOLO, Faster R-CNN."
        ],
        "benefits": ["Competitive salary", "Stock options", "Remote work", "Research budget"],
        "industry": "AI / Computer Vision",
        "skill_importance": {
            "Python": "CRITICAL", "PyTorch": "CRITICAL",
            "Computer Vision": "CRITICAL", "Deep Learning": "CRITICAL",
            "TensorRT": "IMPORTANT", "Model Deployment": "CRITICAL",
            "Docker": "IMPORTANT",
        },
    }
}

JD_MID_AI_NLP = {
    "job_title": "AI Engineer (NLP / LLM)",
    "structured": {
        "job_title": "AI Engineer (NLP / LLM)",
        "location": "TP.HCM / Hybrid",
        "domain": "tech_ai",
        "is_entry_level": False,
        "seniority": "Mid",
        "years_of_experience": "2-4 years",
        "skills_required": ["Python", "NLP", "LLM", "LangChain", "Hugging Face", "PyTorch", "RAG", "FastAPI", "BERT", "Text Classification", "Git", "Docker"],
        "skills_preferred": ["Fine-tuning", "Prompt Engineering", "Vector DB", "LlamaIndex", "AWS"],
        "responsibilities": [
            "Xây dựng RAG và LLM-powered applications.",
            "Fine-tune và evaluate NLP models cho Vietnamese language tasks.",
            "Deploy NLP APIs với FastAPI.",
            "Collaborate với product team để thiết kế AI features."
        ],
        "requirements": [
            "2+ năm kinh nghiệm trong NLP hoặc LLM application development.",
            "Hands-on experience với LangChain, Hugging Face, hoặc tương đương.",
            "Thành thạo Python và FastAPI.",
            "Hiểu transformer architectures (BERT, GPT)."
        ],
        "benefits": ["Learning budget", "Hybrid work", "Conference attendance"],
        "industry": "AI / Generative AI",
        "skill_importance": {
            "Python": "CRITICAL", "NLP": "CRITICAL", "LLM": "CRITICAL",
            "LangChain": "CRITICAL", "Hugging Face": "CRITICAL",
            "RAG": "IMPORTANT", "FastAPI": "IMPORTANT",
        },
    }
}

JD_DATA_SCIENTIST = {
    "job_title": "Data Scientist",
    "structured": {
        "job_title": "Data Scientist",
        "location": "Hà Nội / Remote OK",
        "domain": "tech_data",
        "is_entry_level": False,
        "seniority": "Mid",
        "years_of_experience": "2-4 years",
        "skills_required": ["Python", "SQL", "Machine Learning", "XGBoost", "LightGBM", "Scikit-learn", "Pandas", "Data Analysis", "Feature Engineering", "A/B Testing"],
        "skills_preferred": ["Deep Learning", "NLP", "Spark", "dbt", "Tableau", "Power BI"],
        "responsibilities": [
            "Build và deploy ML models cho business use cases (churn, LTV, recommendation).",
            "Design và analyze A/B experiments.",
            "Create data pipelines và automated ML workflows.",
            "Present insights to business stakeholders."
        ],
        "requirements": [
            "2+ năm kinh nghiệm trong Data Science.",
            "Thành thạo Python, SQL, và ML libraries (XGBoost, Scikit-learn).",
            "Kinh nghiệm với feature engineering và model evaluation.",
            "Hiểu biết về statistical analysis và A/B testing.",
            "Có portfolio với các ML projects."
        ],
        "benefits": ["Learning budget", "Conference attendance", "Remote work"],
        "industry": "E-commerce / Tech",
        "skill_importance": {
            "Python": "CRITICAL", "Machine Learning": "CRITICAL",
            "SQL": "CRITICAL", "XGBoost": "CRITICAL",
            "A/B Testing": "IMPORTANT", "Data Analysis": "CRITICAL",
        },
    }
}

JD_DEVOPS_SENIOR = {
    "job_title": "Senior DevOps / SRE",
    "structured": {
        "job_title": "Senior DevOps / SRE",
        "location": "Hà Nội",
        "domain": "tech_devops",
        "is_entry_level": False,
        "seniority": "Senior",
        "years_of_experience": "4-7 years",
        "skills_required": ["Kubernetes", "Docker", "AWS", "Terraform", "Ansible", "CI/CD", "GitLab CI", "Linux", "Prometheus", "Grafana", "Python", "Networking"],
        "skills_preferred": ["GCP", "Azure", "Helm", "Istio", "Vault"],
        "responsibilities": [
            "Quản lý và vận hành Kubernetes clusters cho production environment.",
            "Xây dựng và maintain CI/CD pipelines.",
            "Implement observability stack (metrics, logging, tracing).",
            "Drive SRE practices: SLOs, error budgets, incident management.",
            "Automate infrastructure provisioning với IaC."
        ],
        "requirements": [
            "4+ năm kinh nghiệm trong DevOps/SRE.",
            "Thành thạo Kubernetes và Docker.",
            "Kinh nghiệm với AWS hoặc GCP.",
            "Thành thạo Terraform và Ansible.",
            "Hiểu biết về monitoring và observability."
        ],
        "benefits": ["Competitive salary", "Remote work options", "Certification budget"],
        "industry": "Cloud / SaaS",
        "skill_importance": {
            "Kubernetes": "CRITICAL", "Docker": "CRITICAL",
            "AWS": "CRITICAL", "Terraform": "CRITICAL",
            "CI/CD": "CRITICAL", "Linux": "CRITICAL",
            "Prometheus": "IMPORTANT", "Python": "IMPORTANT",
        },
    }
}

JD_SALES_DIRECTOR = {
    "job_title": "Regional Sales Director",
    "structured": {
        "job_title": "Regional Sales Director",
        "location": "TP.HCM",
        "domain": "sales",
        "is_entry_level": False,
        "seniority": "Director",
        "years_of_experience": "7-10 years",
        "skills_required": ["Enterprise Sales", "B2B Sales", "Salesforce", "Negotiation", "Contract Management", "Team Leadership", "Account Management", "Sales Strategy", "Business Development", "Revenue Growth"],
        "skills_preferred": ["Solution Selling", "MEDDIC", "Channel Sales"],
        "responsibilities": [
            "Dẫn dắt đội ngũ sales 15-20 AEs đạt $10M+ ARR quota.",
            "Phát triển và execute sales strategy cho khu vực miền Nam.",
            "Build relationships với C-level executives tại enterprise accounts.",
            "Collaborate với marketing và product teams để drive GTM strategy."
        ],
        "requirements": [
            "7+ năm kinh nghiệm trong enterprise B2B sales, 3+ năm in leadership.",
            "Track record đạt và vượt quota $3M+ ARR.",
            "Thành thạo Salesforce và enterprise sales methodology.",
            "Kinh nghiệm với solution selling và consultative selling.",
            "MBA là lợi thế."
        ],
        "benefits": ["Competitive base + commission", "Stock options", "Company car", "Executive benefits"],
        "industry": "SaaS / Enterprise Software",
        "skill_importance": {
            "Enterprise Sales": "CRITICAL", "B2B Sales": "CRITICAL",
            "Team Leadership": "CRITICAL", "Negotiation": "CRITICAL",
            "Salesforce": "IMPORTANT", "Sales Strategy": "CRITICAL",
        },
    }
}

JD_SALES_BDR = {
    "job_title": "Business Development Representative",
    "structured": {
        "job_title": "Business Development Representative",
        "location": "Hà Nội / Hybrid",
        "domain": "sales",
        "is_entry_level": True,
        "seniority": "Entry",
        "years_of_experience": "0-2 years",
        "skills_required": ["Sales", "Communication", "CRM", "Cold Calling", "Lead Generation", "Microsoft Office"],
        "skills_preferred": ["Salesforce", "LinkedIn Sales Navigator", "Presentation Skills"],
        "responsibilities": [
            "Identify và qualify sales leads qua cold outreach.",
            "Schedule demos và meetings cho Account Executives.",
            "Maintain CRM records và pipeline data.",
            "Research target accounts và prepare account plans."
        ],
        "requirements": [
            "0-2 năm kinh nghiệm trong sales hoặc customer-facing roles.",
            "Kỹ năng giao tiếp tốt bằng tiếng Việt và tiếng Anh.",
            "Sử dụng được CRM (Salesforce là lợi thế).",
            "Eager to learn sales và business development."
        ],
        "benefits": ["Base + uncapped commission", "Sales training program", "Career path to AE"],
        "industry": "SaaS / Tech",
        "skill_importance": {
            "Communication": "CRITICAL", "Sales": "CRITICAL",
            "CRM": "IMPORTANT", "Lead Generation": "CRITICAL",
        },
    }
}

JD_DIGITAL_MARKETING = {
    "job_title": "Digital Marketing Manager",
    "structured": {
        "job_title": "Digital Marketing Manager",
        "location": "TP.HCM",
        "domain": "marketing",
        "is_entry_level": False,
        "seniority": "Mid",
        "years_of_experience": "3-5 years",
        "skills_required": ["Google Ads", "Meta Ads", "SEO", "Content Marketing", "Email Marketing", "Marketing Analytics", "A/B Testing", "Marketing Strategy", "Social Media", "Copywriting"],
        "skills_preferred": ["HubSpot", "Marketing Automation", "Video Marketing"],
        "responsibilities": [
            "Plan và execute digital marketing campaigns (Google, Meta, email).",
            "Quản lý marketing budget với ROAS target.",
            "Xây dựng content strategy và manage content calendar.",
            "Report marketing performance và recommend optimizations.",
            "Lead team of 2-3 content creators."
        ],
        "requirements": [
            "3+ năm kinh nghiệm trong digital marketing.",
            "Hands-on experience với Google Ads và Meta Ads.",
            "Kinh nghiệm với SEO và content marketing.",
            "Thành thạo Google Analytics và marketing attribution.",
            "Có track record với các successful campaigns."
        ],
        "benefits": ["Performance bonus", "Learning budget", "Creative freedom"],
        "industry": "E-commerce / Tech",
        "skill_importance": {
            "Google Ads": "CRITICAL", "Meta Ads": "CRITICAL",
            "Marketing Analytics": "CRITICAL", "SEO": "IMPORTANT",
            "Content Marketing": "IMPORTANT",
        },
    }
}

JD_FINANCE_MANAGER = {
    "job_title": "Finance Manager",
    "structured": {
        "job_title": "Finance Manager",
        "location": "Hà Nội",
        "domain": "finance",
        "is_entry_level": False,
        "seniority": "Manager",
        "years_of_experience": "5-8 years",
        "skills_required": ["Financial Modeling", "FP&A", "Power BI", "Excel", "Python", "SQL", "Budgeting", "Financial Analysis", "IFRS", "Corporate Finance"],
        "skills_preferred": ["SAP", " treasury management", "M&A"],
        "responsibilities": [
            "Quản lý FP&A process cho toàn bộ công ty.",
            "Xây dựng financial models cho strategic decisions.",
            "Prepare board-level financial reports và business cases.",
            "Drive budget planning và variance analysis.",
            "Implement financial systems và automation."
        ],
        "requirements": [
            "5+ năm kinh nghiệm trong finance, 2+ năm in FP&A.",
            "Thành thạo financial modeling và Excel.",
            "Kinh nghiệm với Power BI hoặc Tableau.",
            "Python/SQL skills là lợi thế.",
            "CPA, CFA là lợi thế."
        ],
        "benefits": ["Performance bonus", "Health insurance", "Learning budget"],
        "industry": "Fintech / Banking",
        "skill_importance": {
            "Financial Modeling": "CRITICAL", "FP&A": "CRITICAL",
            "Excel": "CRITICAL", "Power BI": "IMPORTANT",
            "Python": "BONUS", "IFRS": "CRITICAL",
        },
    }
}

JD_HR_BP = {
    "job_title": "HR Business Partner",
    "structured": {
        "job_title": "HR Business Partner",
        "location": "TP.HCM",
        "domain": "hr",
        "is_entry_level": False,
        "seniority": "Mid",
        "years_of_experience": "3-5 years",
        "skills_required": ["Talent Acquisition", "Employee Relations", "HR Analytics", "HRIS", "Performance Management", "HR Policies", "Labor Law", "Interviewing", "Succession Planning"],
        "skills_preferred": ["Greenhouse", "Workday", "Coaching"],
        "responsibilities": [
            "Partner với business leaders để drive HR strategy.",
            "Lead talent acquisition cho các vị trí tech và business.",
            "Manage employee relations và employee lifecycle.",
            "Drive performance management cycle và talent review.",
            "Analyze HR metrics và recommend interventions."
        ],
        "requirements": [
            "3+ năm kinh nghiệm trong HR, preferred HRBP role.",
            "Kinh nghiệm trong tech industry hoặc fast-paced environment.",
            "Thành thạo HRIS và HR analytics.",
            "Hiểu biết về Vietnamese labor law.",
            "Strong communication và stakeholder management skills."
        ],
        "benefits": ["Hybrid work", "Health insurance", "Training budget"],
        "industry": "Tech / SaaS",
        "skill_importance": {
            "Talent Acquisition": "CRITICAL", "HR Analytics": "CRITICAL",
            "Employee Relations": "CRITICAL", "Performance Management": "CRITICAL",
            "Labor Law": "IMPORTANT",
        },
    }
}

JD_HEALTHCARE_ADMIN = {
    "job_title": "Healthcare Administrator",
    "structured": {
        "job_title": "Healthcare Administrator",
        "location": "TP.HCM",
        "domain": "healthcare",
        "is_entry_level": False,
        "seniority": "Mid",
        "years_of_experience": "3-5 years",
        "skills_required": ["Hospital Operations", "Healthcare IT", "Patient Management", "Healthcare Regulations", "Budget Management", "Project Management", "HIPAA Compliance", "Stakeholder Management"],
        "skills_preferred": ["HIS", "Telemedicine", "Quality Management"],
        "responsibilities": [
            "Quản lý vận hành bệnh viện/phòng khám.",
            "Implement healthcare IT systems và telemedicine.",
            "Quản lý patient experience và service quality.",
            "Oversee budget và resource allocation.",
            "Ensure compliance với healthcare regulations."
        ],
        "requirements": [
            "3+ năm kinh nghiệm trong healthcare administration.",
            "Hiểu biết về healthcare IT và hospital information systems.",
            "Knowledge of Vietnamese healthcare regulations.",
            "Kinh nghiệm với budget management.",
            "MBA hoặc healthcare management degree là lợi thế."
        ],
        "benefits": ["Health insurance", "Professional development", "Stable environment"],
        "industry": "Healthcare",
        "skill_importance": {
            "Hospital Operations": "CRITICAL", "Healthcare IT": "CRITICAL",
            "Patient Management": "CRITICAL", "Healthcare Regulations": "IMPORTANT",
        },
    }
}

JD_EDUCATION_MGR = {
    "job_title": "Education Manager",
    "structured": {
        "job_title": "Education Manager",
        "location": "Hà Nội",
        "domain": "education",
        "is_entry_level": False,
        "seniority": "Manager",
        "years_of_experience": "4-6 years",
        "skills_required": ["Curriculum Development", "LMS Management", "Teacher Training", "EdTech Tools", "Data Analysis", "Educational Assessment", "Student Advising", "Program Management"],
        "skills_preferred": ["Moodle", "Microsoft Teams", "CELTA", "Data Literacy"],
        "responsibilities": [
            "Quản lý team giáo viên và learning operations.",
            "Phát triển và cải tiến curriculum.",
            "Implement LMS và technology-enhanced learning.",
            "Monitor student outcomes và program effectiveness.",
            "Collaborate với marketing để drive enrollment."
        ],
        "requirements": [
            "4+ năm kinh nghiệm trong education management, preferred edtech.",
            "Kinh nghiệm với LMS và edtech tools.",
            "Background in curriculum development và teacher training.",
            "Data-driven approach to education quality.",
            "CELTA hoặc teaching certification là lợi thế."
        ],
        "benefits": ["Education discounts", "Professional development", "Creative work"],
        "industry": "EdTech / Education",
        "skill_importance": {
            "Curriculum Development": "CRITICAL", "LMS Management": "CRITICAL",
            "Teacher Training": "IMPORTANT", "EdTech Tools": "CRITICAL",
            "Data Analysis": "IMPORTANT",
        },
    }
}

JD_SENIOR_UX = {
    "job_title": "Senior UX Designer",
    "structured": {
        "job_title": "Senior UX Designer",
        "location": "TP.HCM / Remote",
        "domain": "design",
        "is_entry_level": False,
        "seniority": "Senior",
        "years_of_experience": "4-7 years",
        "skills_required": ["Figma", "User Research", "Prototyping", "Design Systems", "Wireframing", "Information Architecture", "Usability Testing", "Design Thinking", "Interaction Design"],
        "skills_preferred": ["HTML/CSS", "Motion Design", "Front-end Basics"],
        "responsibilities": [
            "Dẫn dắt UX strategy cho product team.",
            "Conduct user research và usability testing.",
            "Xây dựng và maintain design system.",
            "Collaborate với product managers và engineers.",
            "Mentor junior designers."
        ],
        "requirements": [
            "4+ năm kinh nghiệm trong UX/product design.",
            "Strong portfolio với shipped digital products.",
            "Thành thạo Figma và prototyping tools.",
            "Kinh nghiệm với design systems và component libraries.",
            "Có portfolio showing user research process."
        ],
        "benefits": ["Remote work", "Design tools budget", "Conference attendance"],
        "industry": "Tech / Product",
        "skill_importance": {
            "Figma": "CRITICAL", "User Research": "CRITICAL",
            "Design Systems": "CRITICAL", "Prototyping": "CRITICAL",
            "Design Thinking": "IMPORTANT",
        },
    }
}

JD_SENIOR_PM = {
    "job_title": "Senior Project Manager (Software)",
    "structured": {
        "job_title": "Senior Project Manager (Software)",
        "location": "Hà Nội",
        "domain": "operations",
        "is_entry_level": False,
        "seniority": "Senior",
        "years_of_experience": "5-8 years",
        "skills_required": ["Project Management", "Agile", "Scrum", "Jira", "Risk Management", "Stakeholder Management", "Budget Management", "PMP", "Communication"],
        "skills_preferred": ["PRINCE2", "MS Project", "SAFe"],
        "responsibilities": [
            "Quản lý multiple software projects đồng thời với tổng budget $2M+.",
            "Drive Agile/Scrum practices across engineering teams.",
            "Manage stakeholder expectations và communication.",
            "Identify và mitigate project risks.",
            "Report project status to executive level."
        ],
        "requirements": [
            "5+ năm kinh nghiệm trong project management, prefer software/tech.",
            "PMP certification là bắt buộc.",
            "Kinh nghiệm với Agile/Scrum framework.",
            "Thành thạo Jira và project management tools.",
            "Track record deliver projects on time và within budget."
        ],
        "benefits": ["Competitive salary", "Certification budget", "Remote options"],
        "industry": "Tech / Software",
        "skill_importance": {
            "Project Management": "CRITICAL", "Agile": "CRITICAL",
            "Scrum": "CRITICAL", "Jira": "CRITICAL",
            "Risk Management": "CRITICAL", "PMP": "CRITICAL",
        },
    }
}

JD_CYBERSECURITY = {
    "job_title": "Security Engineer",
    "structured": {
        "job_title": "Security Engineer",
        "location": "Hà Nội",
        "domain": "tech_security",
        "is_entry_level": False,
        "seniority": "Mid",
        "years_of_experience": "2-4 years",
        "skills_required": ["Penetration Testing", "SIEM", "Incident Response", "Vulnerability Assessment", "Python", "Network Security", "Linux", "OWASP", "Cloud Security"],
        "skills_preferred": ["Splunk", "CrowdStrike", "CEH", "SOC Operations"],
        "responsibilities": [
            "Conduct penetration testing và vulnerability assessments.",
            "Vận hành SIEM platform và monitor security events.",
            "Respond to security incidents và conduct forensics.",
            "Xây dựng security awareness program.",
            "Implement security controls và compliance frameworks."
        ],
        "requirements": [
            "2+ năm kinh nghiệm trong cybersecurity.",
            "Hands-on experience với penetration testing tools (Burp Suite, Nmap).",
            "Kinh nghiệm với SIEM (Splunk preferred).",
            "Thành thạo Python cho security automation.",
            "CEH hoặc CompTIA Security+ certification là lợi thế."
        ],
        "benefits": ["Certification budget", "Conference attendance", "Cutting-edge work"],
        "industry": "Cybersecurity / Tech",
        "skill_importance": {
            "Penetration Testing": "CRITICAL", "Incident Response": "CRITICAL",
            "SIEM": "IMPORTANT", "Python": "CRITICAL",
            "Network Security": "CRITICAL", "OWASP": "IMPORTANT",
        },
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# 30 PAIRS — diverse across all 12 domains × multiple levels
# ══════════════════════════════════════════════════════════════════════════════

ALL_PAIRS = [
    # ── P1: Perfect match — same domain + level ───────────────────────────────
    {"pair_id": 1,  "cv": CV_SOFTWARE_SENIOR,    "jd": JD_SENIOR_SOFTWARE_ENG,  "case_type": "MATCH_HIGH",           "note": "Senior Software Engineer × Senior Backend JD. Perfect level match."},
    {"pair_id": 2,  "cv": CV_AI_MID,               "jd": JD_MID_AI_NLP,            "case_type": "MATCH_HIGH",           "note": "AI Engineer (NLP, 2y) × Mid NLP JD. Same domain, level match."},
    {"pair_id": 3,  "cv": CV_SALES_SENIOR,          "jd": JD_SALES_DIRECTOR,         "case_type": "MATCH_HIGH",           "note": "Regional Sales Director (8y) × Regional Sales Director JD. Perfect match."},

    # ── P4-6: Same domain, slightly off level ────────────────────────────────
    {"pair_id": 4,  "cv": CV_SOFTWARE_SENIOR,      "jd": JD_MID_BACKEND,           "case_type": "MATCH_MEDIUM",          "note": "Senior SE × Mid Backend JD. Overqualified but relevant domain."},
    {"pair_id": 5,  "cv": CV_DATA_SCIENTIST,       "jd": JD_DATA_SCIENTIST,         "case_type": "MATCH_MEDIUM",          "note": "Data Scientist (3y) × DS JD. Good match but role is slightly broader."},
    {"pair_id": 6,  "cv": CV_AI_SENIOR,            "jd": JD_SENIOR_AI,             "case_type": "MATCH_MEDIUM",          "note": "Senior AI/CV Engineer × Senior AI CV JD. Strong match but sub-specialty variance."},

    # ── P7-9: Partial overlap, different focus ────────────────────────────────
    {"pair_id": 7,  "cv": CV_SOFTWARE_MID,         "jd": JD_MID_AI_NLP,            "case_type": "MATCH_MEDIUM",          "note": "Backend Engineer (Python/FastAPI) × AI NLP JD. Some Python overlap but different focus."},
    {"pair_id": 8,  "cv": CV_DATA_SCIENTIST,       "jd": JD_MID_AI_NLP,            "case_type": "MATCH_MEDIUM",          "note": "Data Scientist × AI NLP JD. Overlap in ML/PyTorch, but different primary domain."},
    {"pair_id": 9,  "cv": CV_DEVOPS_SENIOR,        "jd": JD_SENIOR_SOFTWARE_ENG,   "case_type": "MATCH_MEDIUM",          "note": "Senior DevOps/SRE × Senior Backend JD. Both backend-heavy, some overlap in infra."},

    # ── P10-12: Weak match — entry-level with senior JD ─────────────────────
    {"pair_id": 10, "cv": CV_SOFTWARE_FRESHER,     "jd": JD_SENIOR_SOFTWARE_ENG,   "case_type": "MATCH_LOW",             "note": "CS fresher (no work exp) × Senior Backend JD. Deeply underqualified."},
    {"pair_id": 11, "cv": CV_SOFTWARE_FRESHER,     "jd": JD_MID_BACKEND,           "case_type": "MATCH_LOW",             "note": "CS fresher × Mid Backend JD. Underqualified but some Python/Java overlap."},
    {"pair_id": 12, "cv": CV_AI_MID,               "jd": JD_SENIOR_AI,             "case_type": "MATCH_LOW",             "note": "AI Engineer (NLP, 2y) × Senior AI CV JD. Underqualified + wrong sub-specialty."},

    # ── P13-15: Domain mismatch ──────────────────────────────────────────────
    {"pair_id": 13, "cv": CV_SALES_SENIOR,          "jd": JD_SENIOR_SOFTWARE_ENG,   "case_type": "MISMATCH_DOMAIN",       "note": "Regional Sales Director × Senior Backend JD. Complete domain mismatch."},
    {"pair_id": 14, "cv": CV_MARKETING_MID,         "jd": JD_SENIOR_AI,             "case_type": "MISMATCH_DOMAIN",       "note": "Digital Marketing Manager × Senior AI JD. Wrong domain entirely."},
    {"pair_id": 15, "cv": CV_FINANCE_MID,          "jd": JD_DEVOPS_SENIOR,         "case_type": "MISMATCH_DOMAIN",       "note": "Finance Manager × Senior DevOps JD. Completely different domains."},

    # ── P16-18: More domain mismatches ───────────────────────────────────────
    {"pair_id": 16, "cv": CV_HR_MID,               "jd": JD_SENIOR_UX,             "case_type": "MISMATCH_DOMAIN",       "note": "HR BP × Senior UX JD. Different domains entirely."},
    {"pair_id": 17, "cv": CV_HEALTHCARE_MID,        "jd": JD_DATA_SCIENTIST,        "case_type": "MISMATCH_DOMAIN",       "note": "Healthcare Administrator × Data Scientist JD. Mismatch despite some analytics overlap."},
    {"pair_id": 18, "cv": CV_EDUCATION_MID,        "jd": JD_DIGITAL_MARKETING,     "case_type": "MISMATCH_DOMAIN",       "note": "Education Manager × Digital Marketing JD. Different domains."},

    # ── P19-21: Cross-domain with some transferable skills ────────────────────
    {"pair_id": 19, "cv": CV_PM_MID,               "jd": JD_SENIOR_PM,             "case_type": "MATCH_MEDIUM",          "note": "Senior PM (5y, PMP) × Senior PM JD. Good match, PMP certified."},
    {"pair_id": 20, "cv": CV_DEVOPS_SENIOR,        "jd": JD_MID_BACKEND,           "case_type": "MATCH_MEDIUM",          "note": "Senior DevOps × Mid Backend JD. Overlap in Python/Docker but different primary focus."},
    {"pair_id": 21, "cv": CV_DESIGN_MID,           "jd": JD_SENIOR_UX,             "case_type": "MATCH_HIGH",            "note": "Senior UX Designer (4y) × Senior UX JD. Perfect match in design domain."},

    # ── P22-24: More mixed cases ─────────────────────────────────────────────
    {"pair_id": 22, "cv": CV_CYBERSECURITY_MID,    "jd": JD_SENIOR_SOFTWARE_ENG,   "case_type": "MATCH_MEDIUM",          "note": "Security Engineer × Senior Backend JD. Some overlap in Linux/Python/networking."},
    {"pair_id": 23, "cv": CV_CYBERSECURITY_MID,    "jd": JD_CYBERSECURITY,        "case_type": "MATCH_HIGH",           "note": "Security Engineer × Security Engineer JD. Perfect domain match, slight level gap."},
    {"pair_id": 24, "cv": CV_SOFTWARE_MID,         "jd": JD_SENIOR_PM,             "case_type": "MATCH_LOW",             "note": "Backend Engineer × Senior PM JD. Relevant domain but wrong role."},

    # ── P25-27: More mismatches ─────────────────────────────────────────────
    {"pair_id": 25, "cv": CV_SALES_FRESHER,         "jd": JD_SALES_BDR,             "case_type": "MATCH_HIGH",           "note": "Sales fresher × BDR JD. Same domain, reasonable level match."},
    {"pair_id": 26, "cv": CV_MARKETING_FRESHER,     "jd": JD_DIGITAL_MARKETING,     "case_type": "MATCH_MEDIUM",          "note": "Marketing fresher × Digital Marketing Manager JD. Same domain but experience gap."},
    {"pair_id": 27, "cv": CV_FINANCE_FRESHER,       "jd": JD_FINANCE_MANAGER,       "case_type": "MATCH_LOW",             "note": "Finance intern × Finance Manager JD. Same domain but severe experience gap."},

    # ── P28-30: Edge cases ───────────────────────────────────────────────────
    {"pair_id": 28, "cv": CV_HR_MID,               "jd": JD_SALES_BDR,             "case_type": "MISMATCH_DOMAIN",       "note": "HR BP × BDR JD. Both business roles but different functions."},
    {"pair_id": 29, "cv": CV_HEALTHCARE_MID,       "jd": JD_HR_BP,                 "case_type": "MISMATCH_DOMAIN",       "note": "Healthcare Admin × HR BP JD. Completely different domains."},
    {"pair_id": 30, "cv": CV_EDUCATION_MID,        "jd": JD_SENIOR_PM,             "case_type": "MISMATCH_DOMAIN",       "note": "Education Manager × Senior PM JD. Different domain despite some overlap in program management."},
]


def get_all_pairs() -> List[Dict]:
    return ALL_PAIRS


def get_pair_by_id(pair_id: int) -> Dict:
    for p in ALL_PAIRS:
        if p["pair_id"] == pair_id:
            return p
    return None
