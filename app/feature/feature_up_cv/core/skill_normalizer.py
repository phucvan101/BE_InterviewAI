# -*- coding: utf-8 -*-
"""
Skill normalization and post-processing utilities.
Ensures consistent skill naming across CV, JD, and Company parsers
for accurate matching downstream.
"""

import re
from typing import Dict, List, Set

# Canonical skill names → accepted aliases
SKILL_CANONICAL_MAP: Dict[str, List[str]] = {
    # Languages
    "python": ["py", "python3", "python2"],
    "javascript": ["js", "ecmascript", "es6", "es2020"],
    "typescript": ["ts", "tsx", "typescript-language"],
    "java": ["java17", "java11", "java8"],
    "csharp": ["c#", "c-sharp", "dotnet", "dot-net"],
    "cpp": ["c++", "c plus plus"],
    "go": ["golang", "go-lang"],
    "rust": ["rs"],
    "ruby": ["rb", "ruby-on-rails", "ror"],
    "php": ["php7", "php8", "laravel"],
    "scala": ["spark", "databricks"],
    "kotlin": ["kt"],
    "swift": ["ios", "swiftui"],
    "r": ["rstats", "r-programming"],
    "dart": ["flutter"],
    "shell": ["bash", "sh", "zsh", "shell-script", "powershell"],
    "sql": ["tsql", "plsql", "mysql", "postgresql", "mariadb", "sqlite", "mssql"],
    # Frameworks
    "react": ["reactjs", "react.js", "react-native", "reactjs"],
    "reactnative": ["react native", "rn"],
    "nextjs": ["next.js", "next-js"],
    "vuejs": ["vue", "vue.js", "vue3"],
    "angular": ["angularjs", "angular.js", "angular2"],
    "svelte": ["sveltejs"],
    "nodejs": ["node", "node.js", "express", "expressjs"],
    "django": ["django-rest", "djangorestframework", "drf"],
    "fastapi": ["fast.api", "starlette"],
    "flask": ["flask-api"],
    "spring": ["springboot", "spring-boot", "springboot", "spring framework"],
    "springboot": ["spring boot"],
    "nestjs": ["nest.js"],
    "laravel": ["laravel-php"],
    "rails": ["ruby on rails", "ror"],
    "servlet": ["jsp", "javax.servlet"],
    # Databases
    "postgresql": ["postgres", "psql", "postgre", "postgresql-database"],
    "mysql": ["my-sql", "mysql8", "mariadb"],
    "mongodb": ["mongo", "mongo-db", "mongodb-database"],
    "redis": ["redis-cache", "redis-db"],
    "elasticsearch": ["elastic", "elastic-search", "es-search"],
    "cassandra": ["datastax"],
    "dynamodb": ["dynamo"],
    "sqlite": ["sqlite3"],
    "neo4j": ["neo4j-graph"],
    # Data & ML
    "tensorflow": ["tf", "tf2", "keras"],
    "pytorch": ["torch", "pyTorch", "pytorch-lightning"],
    "scikit-learn": ["sklearn", "scikit", "scikitlearn"],
    "pandas": ["pandas-python", "pd"],
    "numpy": ["np", "numpy-python"],
    "spark": ["pyspark", "apache-spark", "spark-sql", "sparkml"],
    "kafka": ["apache-kafka", "msk", "confluent-kafka", "kafka-streams"],
    "airflow": ["apache-airflow", "airflow-dag"],
    "mlflow": ["mlops", "ml-flow"],
    "hadoop": ["hdfs", "mapreduce", "hive", "hbase"],
    "tableau": ["tableau-desktop", "tableau-server"],
    "powerbi": ["power-bi", "powerbi-dashboard"],
    # Cloud & DevOps
    "aws": ["amazon-web-services", "amazon-web-service", "aws-ec2", "aws-s3", "aws-lambda", "aws-eks", "aws-ecs", "aws-rds"],
    "gcp": ["google-cloud-platform", "google-cloud", "gcp-cloud", "googlecloud"],
    "azure": ["microsoft-azure", "ms-azure", "azure-devops", "azure-cloud"],
    "docker": ["docker-container", "docker-compose", "dockerfile", "docker-image"],
    "kubernetes": ["k8s", "k8", "k8s-cluster", "eks", "gke", "aks", "minikube", "helm"],
    "terraform": ["tf", "terraform-iac", "tfvars"],
    "ansible": ["ansible-playbook", "ansible-tower"],
    "jenkins": ["jenkins-ci", "jenkins-pipeline"],
    "githubactions": ["github-actions", "gh-actions", "gha"],
    "gitlabci": ["gitlab-ci", "gitlab-pipeline"],
    "ci/cd": ["cicd", "ci cd", "continuous-integration", "continuous-deployment"],
    "grafana": ["grafana-loki", "loki-monitoring"],
    "prometheus": ["prometheus-monitoring"],
    "argocd": ["argo-cd", "argo"],
    # Mobile
    "ios": ["iphone", "ipad", "swift", "objective-c"],
    "android": ["android-sdk", "android-studio", "java-android"],
    "flutter": ["dart-flutter"],
    "reactnative": ["rn"],
    # AI & CV
    "opencv": ["cv2", "open-cv", "opencv-python", "cv"],
    "computervision": ["computer-vision", "cv", "image-processing"],
    "deeplearning": ["dl", "deep-learning", "neural-network", "nn"],
    "nlp": ["natural-language-processing", "text-processing", "text-mining"],
    "llm": ["large-language-model", "language-model", "generative-ai", "genai", "gpt", "bert", "transformer"],
    "cnn": ["convolutional-neural-network"],
    "rnn": ["recurrent-neural-network", "lstm", "gru"],
    "yolo": ["yolov5", "yolov6", "yolov7", "yolov8", "yolov9", "yolo11"],
    "ocr": ["tesseract", "easyocr", "paddleocr"],
    "tracking": ["object-tracking", "multi-object-tracking", "mot"],
    "cuda": ["nvidia-cuda", "cuda-gpu"],
    "tensorrt": ["trt", "nvidia-tensorrt"],
    "onnx": ["onnx-runtime", "onnxruntime"],
    "langchain": ["langchain4j", "langsmith"],
    "huggingface": ["transformers-library", "huggingface-transformers", "hf"],
    "stablediffusion": ["stable-diffusion", "sdxl", "diffusion-model"],
    # Backend & API
    "graphql": ["gql", "graphql-api"],
    "restapi": ["rest", "rest-api", "restful", "restful-api", "restapi"],
    "grpc": ["grpc-api"],
    "webservice": ["web-service", "web-service-api"],
    "microservices": ["micro-services", "micro services", "service-mesh", "service mesh"],
    "api": ["api-design", "api-development"],
    # Tools & Others
    "git": ["github", "gitlab", "bitbucket", "git-flow", "gitops", "git-versioning"],
    "linux": ["unix", "ubuntu", "debian", "centos", "redhat"],
    "scrum": ["agile", "scrum-master", "scrum-master", "waterfall", "sdlc"],
    "testing": ["unit-testing", "integration-testing", "e2e-testing", "selenium", "jest", "pytest", "junit", "cypress"],
    "security": ["cybersecurity", "infosec", "penetration-testing", "owasp", "iso27001"],
    "figma": ["ui-design", "ui/ux", "ux-design", "user-interface"],
    "iot": ["internet-of-things", "embedded-systems", "esp32", "arduino"],
    "blockchain": ["solidity", "smart-contract", "web3", "nft"],
    "dataengineering": ["data-pipeline", "etl", "elt", "data-warehouse", "dbt"],
    "dataanalysis": ["data-analytics", "statistics", "a/b-testing"],
    "devops": ["sre", "platform-engineering", "platform-engineer"],
    "mlops": ["aicops", "ml-engineering"],
    "productmanagement": ["product-owner", "po", "pm", "product-manager"],
    "projectmanagement": ["project-manager", "pm", "prince2", "pmp"],
    "sales": ["business-development", "b2b-sales", "b2c-sales", "account-management"],
    "marketing": ["digital-marketing", "seo", "sem", "content-marketing", "email-marketing"],
    "communication": ["soft-skills", "presentation", "public-speaking"],
    "leadership": ["team-lead", "management", "mentoring", "coaching"],
    "excel": ["spreadsheet", "excel-vba", "vba"],
    "word": ["msword", "microsoft-word", "docx"],
    "powerpoint": ["mspowerpoint", "presentation-software"],
}

# Vietnamese skill phrase → canonical key (for cross-language matching)
# English JD has "Sales Prospecting", Vietnamese CV has "Tìm kiếm khách hàng"
_VI_SKILL_ALIASES: Dict[str, str] = {
    # Sales
    "bán hàng": "sales",
    "ban hang": "sales",
    "kinh doanh": "business development",
    "tìm kiếm khách hàng": "sales prospecting",
    "tim kiem khach hang": "sales prospecting",
    "phát triển kinh doanh": "business development",
    "phat trien kinh doanh": "business development",
    "quản lý quan hệ khách hàng": "crm",
    "quan ly quan he khach hang": "crm",
    "chăm sóc khách hàng": "crm",
    "cham soc khach hang": "crm",
    "phân tích nhu cầu khách hàng": "crm",
    "phan tich nhieu khach hang": "crm",
    "đàm phán": "negotiation",
    "dam phan": "negotiation",
    "thương lượng": "negotiation",
    "thuong luong": "negotiation",
    "thuyết phục": "persuasion",
    "thuyet phuc": "persuasion",
    "chốt sales": "sales",
    "chot sales": "sales",
    "lập hợp đồng": "contract closing",
    "lap hop dong": "contract closing",
    "báo giá": "sales reporting",
    "bao gia": "sales reporting",
    "theo dõi đơn hàng": "sales tracking",
    "theo doi don hang": "sales tracking",
    "tăng doanh số": "sales target achievement",
    "tang doanh so": "sales target achievement",
    "chiến lược tiếp cận khách hàng": "business development",
    " chien luoc tiep can khach hang": "business development",
    "triển khai chiến dịch": "marketing",
    "trien khai chien dich": "marketing",
    "hỗ trợ sau bán": "crm",
    "ho tro sau ban": "crm",
    "xử lý khiếu nại": "customer relationship management",
    "xu ly khieu nai": "customer relationship management",
    "lập báo cáo": "sales reporting",
    "lap bao cao": "sales reporting",
    "marketing": "marketing",
    "email marketing": "marketing",
    "tổ chức sự kiện": "project management",
    "to chuc su kien": "project management",
    "xây dựng mối quan hệ": "crm",
    "xay dung moi quan he": "crm",
    "phối hợp": "teamwork",
    "phoi hop": "teamwork",
    "giao tiếp": "communication",
    "giao tiep": "communication",
    "giải quyết vấn đề": "problem solving",
    "giai quyet van de": "problem solving",
    "làm việc nhóm": "teamwork",
    "lam viec nhom": "teamwork",
    "kpi": "sales target achievement",
    "scps chuyên viên bán hàng chuyên nghiệp": "sales",
    "scps chuyen vien ban hang chuyen nghiep": "sales",
    # Also no-space versions (after regex strips spaces in normalize_skill)
    "bánhàng": "sales",
    "bankh": "business development",
    "tìmkiếmkháchhn": "sales prospecting",
    "timkiemkhachhang": "sales prospecting",
    "pháttriểnkinhdoanh": "business development",
    "phattrienkinhdoanh": "business development",
    "quảnlýquanhệkháchhàng": "crm",
    "quanlyquanhekhachhang": "crm",
    "chămsóckháchhàng": "crm",
    "chamsockhachhang": "crm",
    "đàmphán": "negotiation",
    "damphan": "negotiation",
    "thươnglượng": "negotiation",
    "thuongluong": "negotiation",
    "kinhdoanh": "business development",
    "marketing": "marketing",
    "giao tiếp": "communication",
    "giai tiep": "communication",
    "giảiquyếtvấnđề": "problem solving",
    "giaiquyetvande": "problem solving",
    "làmviệcnhóm": "teamwork",
    "lamviecnhom": "teamwork",
}

# Build reverse lookup: alias → canonical
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for canonical, aliases in SKILL_CANONICAL_MAP.items():
    _ALIAS_TO_CANONICAL[canonical] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical
        _ALIAS_TO_CANONICAL[alias.lower().replace(" ", "")] = canonical
# Also include domain skills so normalize_skill doesn't strip them
# (added after _DOMAIN_SKILLS is defined, below)


# Domain-specific skills to keep as-is
_DOMAIN_SKILLS = {
    "sales", "crm", "marketing", "negotiation", "account management",
    "b2b", "b2c", "business development", "erp", "saas",
    "product management", "project management", "operations",
    "finance", "accounting", "hr", "recruitment", "customer success",
    "seo", "sem", "content marketing", "email marketing", "digital marketing",
    "data analysis", "data engineering", "business intelligence",
    "consulting", "advisory", "auditing", "compliance", "risk management",
    "supply chain", "logistics", "procurement", "inventory",
    "real estate", "trading", "investment", "wealth management",
    "telecommunication", "networking",
    "ux", "ui", "product design", "brand", "copywriting",
    "training", "coaching", "teaching", "research",
}

# Skills to ALWAYS keep (even short ones)
_ALWAYS_KEEP = {
    "ai", "ml", "cv", "nlp", "llm", "iot", "erp", "crm", "saas",
    "b2b", "b2c", "seo", "sem", "ux", "ui", "bi", "api", "sql", "os",
}

# Add domain skills to reverse lookup (after both are defined)
for skill in _DOMAIN_SKILLS:
    _ALIAS_TO_CANONICAL[skill] = skill
    _ALIAS_TO_CANONICAL[skill.replace(" ", "")] = skill


def normalize_skill(skill: str) -> str:
    """Normalize a single skill name to canonical form. Preserves Vietnamese characters."""
    s = skill.strip()
    # Keep: ASCII letters, digits, spaces, hyphen/plus/hash, and Vietnamese diacritics
    # Remove only control/emoji/special chars that would break downstream processing
    s = re.sub(
        r"[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩđùúụủũôồốộổỗơờớợởỡỳýỵ]",
        "",
        s,
        flags=re.UNICODE,
    )
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)

    # 1. Direct lookup in canonical map
    if s in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[s]

    # 2. Vietnamese skill alias lookup (for cross-language matching)
    # e.g. "tìm kiếm khách hàng" → "sales prospecting"
    if s in _VI_SKILL_ALIASES:
        return _VI_SKILL_ALIASES[s]
    # Also try without spaces (e.g. "timkiemkhachhang")
    s_nospace = re.sub(r"\s+", "", s)
    if s_nospace in _VI_SKILL_ALIASES:
        return _VI_SKILL_ALIASES[s_nospace]

    # Always keep important short domain skills
    if s in _ALWAYS_KEEP or s in _DOMAIN_SKILLS:
        return s

    # 3. Strip common suffixes and try canonical lookup
    s_clean = re.sub(r"[\-\+\#]?(js|py|ts|sql|api|cv|nlp|ml|dl|ai|db)$", "", s, flags=re.IGNORECASE).strip()
    if s_clean and s_clean in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[s_clean]

    # 4. Fuzzy: if close to a known canonical (edit distance ≤ 2)
    canonicals = list(SKILL_CANONICAL_MAP.keys())
    for cand in canonicals:
        if cand in s or s in cand:
            return cand
        if len(cand) > 3 and len(s) > 3 and (cand.startswith(s[:2]) or s.startswith(cand[:2])):
            if _levenshtein(cand, s) <= 2:
                return cand

    # 5. Keep multi-word skills as-is (title-cased)
    if len(s) >= 3 and " " in s and not re.match(r"^[0-9\-\+]+$", s):
        return s.title()
    return s


def _levenshtein(a: str, b: str) -> int:
    """Simple edit distance."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = range(len(b) + 1)
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]


def normalize_skills_list(skills: List[str]) -> List[str]:
    """Normalize a list of skills, deduplicate, return canonical names."""
    seen: Set[str] = set()
    result: List[str] = []

    for skill in skills:
        if not skill or not isinstance(skill, str):
            continue
        norm = normalize_skill(skill)
        # Keep skills with len >= 2 (covers "AI", "ML", "UX", "UI", "SQL", "API", "OS", etc.)
        if norm and norm not in seen and len(norm) >= 2:
            seen.add(norm)
            result.append(norm)

    return result


def extract_skills_from_text(text: str) -> List[str]:
    """Extract tech/industry keywords from raw text using regex patterns."""
    patterns = [
        # Named tech with Framework/Library/Tool/Platform keywords
        r"\b([A-Z][a-z]+(?:\s?[A-Z][a-z]+)?)\s*(?:Framework|Library|Tool|Platform|Engine|Database|Cloud)\b",
        # Named programming languages
        r"\b(Python|JavaScript|TypeScript|Java|C\+\+|C#|Go|Rust|Swift|Kotlin|Ruby|PHP|Scala|Shell)\b",
        # Named frameworks
        r"\b(React|Vue|Angular|Node\.js|Django|Flask|FastAPI|Spring|Laravel|Rails)\b",
        # ML/AI frameworks
        r"\b(TensorFlow|PyTorch|Keras|Scikit-learn|Pandas|Numpy|Spark|Hadoop|Kafka|Airflow)\b",
        # Databases
        r"\b(PostgreSQL|MySQL|MongoDB|Redis|Elasticsearch|Cassandra|Neo4j|SQLite|DynamoDB)\b",
        # DevOps/Cloud
        r"\b(Docker|Kubernetes|Terraform|Ansible|Jenkins|CircleCI|GitHubActions)\b",
        r"\b(AWS|Azure|GCP|Google\s*Cloud|Amazon\s*Web\s*Services)\b",
        # Version control
        r"\b(Git|GitHub|GitLab|Bitbucket|SVN)\b",
        # AI/CV specific
        r"\b(OpenCV|Open-CV|CUDA|TensorRT|ONNX|YOLO|OCR|LSTM|CNN|Transformer)\b",
        # API
        r"\b(REST|RESTful|GraphQL|gRPC|gRPC-API|API)\b",
        # Frontend
        r"\b(HTML5|CSS3|CSS|SASS|LESS|Bootstrap|Tailwind)\b",
        # AI/ML
        r"\b(Machine Learning|Deep Learning|NLP|Computer Vision|MLOps)\b",
        # Project management
        r"\b(A/B Testing|Agile|Scrum|Kanban|Jira|Confluence)\b",
        # Networking/Servers
        r"\b(HTTP|HTTPS|TCP|UDP|DNS|SQL|NoSQL|REST)\b",
        r"\b(Nginx|Apache|Tomcat|IIS|WebLogic)\b",
        # Mobile
        r"\b(Flutter|React Native|Ionic|Cordova|Android|iOS)\b",
        # Data platforms
        r"\b(BigQuery|Snowflake|Redshift|Dataflow|BigTable)\b",
        # LLM/HF
        r"\b(Hugging Face|llama|GPT-4|Claude|Gemini|Stable Diffusion)\b",
        # CRM/Business - case insensitive
        r"(?i)\b(CRM|ERP|SaaS|B2B|B2C|SEO|SEM|POC|MVP|KPI)\b",
        r"(?i)\b(Customer\s*Relationship\s*Management|Account\s*Management|Business\s*Development)\b",
        # Project management tools
        r"(?i)\b(Project\s*Management|Product\s*Management|HRM|HRIS)\b",
    ]

    found: Set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            skill = match.group(0).strip()
            if len(skill) >= 2:
                found.add(skill)

    return normalize_skills_list(list(found))


def post_process_cv_skills(cv_data: dict, raw_text: str = "") -> dict:
    """
    Post-process CV parsed data to normalize skills.
    1. Normalize skills list
    2. Extract additional skills from highlights/description text
    3. Extract from projects
    """
    # Normalize skills
    if "skills" in cv_data and isinstance(cv_data["skills"], list):
        cv_data["skills"] = normalize_skills_list(cv_data["skills"])

    # Extract from work experience highlights
    additional_skills: Set[str] = set()
    for exp in cv_data.get("work_experience", []):
        for key in ("highlights", "responsibilities", "description"):
            for item in exp.get(key, []):
                extracted = extract_skills_from_text(str(item))
                additional_skills.update(extracted)

    # Extract from projects
    for proj in cv_data.get("projects", []):
        for key in ("technologies", "description"):
            for item in proj.get(key, []):
                extracted = extract_skills_from_text(str(item))
                additional_skills.update(extracted)

    # Extract from raw text if provided
    if raw_text:
        extracted = extract_skills_from_text(raw_text)
        additional_skills.update(extracted)

    # Merge: keep original normalized skills + extracted ones
    existing = set(normalize_skills_list(cv_data.get("skills", [])))
    all_skills = normalize_skills_list(list(existing | additional_skills))
    cv_data["skills"] = all_skills

    # Normalize evidence skills
    if "evidence" in cv_data and isinstance(cv_data["evidence"], dict):
        if "skills" in cv_data["evidence"]:
            cv_data["evidence"]["skills"] = normalize_skills_list(
                cv_data["evidence"].get("skills", [])
            )

    return cv_data


def post_process_jd_skills(jd_data: dict, raw_text: str = "") -> dict:
    """
    Post-process JD parsed data to normalize and enhance skills.
    1. Normalize skills_required and skills_preferred
    2. Extract from responsibilities/requirements if empty
    3. Add industry-specific skills
    """
    structured = jd_data.get("structured", jd_data)

    for field in ("skills_required", "skills_preferred", "keywords"):
        if field in structured and isinstance(structured[field], list):
            structured[field] = normalize_skills_list(structured[field])

    # If skills_required is empty, extract from responsibilities/requirements
    if not structured.get("skills_required") and not structured.get("skills_preferred"):
        text_parts = []
        for field in ("responsibilities", "requirements", "benefits"):
            text_parts.extend(structured.get(field, []))
        for field in ("responsibilities", "requirements"):
            text_parts.extend(jd_data.get(field, []))
        if raw_text:
            text_parts.append(raw_text)

        extracted = extract_skills_from_text(" ".join(str(p) for p in text_parts))
        if extracted:
            structured["skills_required"] = extracted[:20]

    # Normalize evidence
    if "evidence" in structured:
        ev = structured["evidence"]
        for field in ("skills_required", "skills_preferred"):
            if field in ev and isinstance(ev[field], list):
                ev[field] = normalize_skills_list(ev[field])

    jd_data["structured"] = structured
    return jd_data


def post_process_company(company_data: dict, raw_text: str = "") -> dict:
    """Post-process company data to normalize tech stack."""
    for field in ("key_skills", "technologies"):
        if field in company_data and isinstance(company_data[field], list):
            company_data[field] = normalize_skills_list(company_data[field])

    # Extract from description/culture if empty
    if not company_data.get("technologies"):
        text = company_data.get("description", "") + " " + company_data.get("company_culture", "")
        if raw_text:
            text += " " + raw_text
        extracted = extract_skills_from_text(text)
        if extracted:
            company_data["technologies"] = extracted[:15]

    if "evidence" in company_data:
        ev = company_data["evidence"]
        for field in ("key_skills", "technologies"):
            if field in ev and isinstance(ev[field], list):
                ev[field] = normalize_skills_list(ev[field])

    return company_data
