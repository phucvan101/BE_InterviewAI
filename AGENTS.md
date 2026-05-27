# AGENTS.md

Huong dan cho cac coding agent lam viec trong repository nay.

## Tong quan du an

Day la backend REST API cho InterviewAI, xay dung bang FastAPI, SQLAlchemy async, JWT auth, Google OAuth va Alembic migration.

Stack chinh:

- Python 3.x
- FastAPI + Uvicorn
- SQLAlchemy async + asyncpg/PostgreSQL
- Pydantic v2 + pydantic-settings
- Alembic
- pytest + pytest-asyncio

## Cau truc quan trong

- `app/main.py`: FastAPI app, lifespan va dang ky router.
- `app/core/`: cau hinh, database, security va dependencies dung chung.
- `app/feature/<module>/`: module nghiep vu theo feature.
- `app/scripts/`: script van hanh/kiem thu thu cong.
- `tests/`: test pytest.
- `alembic/`: migration database.
- `run.py`: entrypoint chay Uvicorn.
- `requirements.txt`: dependency Python.

Khi them module moi, giu pattern:

1. `app/feature/<module>/models/`
2. `app/feature/<module>/schemas/`
3. `app/feature/<module>/services/`
4. `app/feature/<module>/api/endpoints/`
5. `app/feature/<module>/api/router.py`

## Lenh phat trien

Tao moi truong va cai dependency:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Chay server local:

```bash
python run.py
```

Hoac:

```bash
uvicorn app.main:app --reload
```

Chay test:

```bash
pytest
```

Tao migration Alembic:

```bash
alembic revision --autogenerate -m "message"
```

Ap dung migration:

```bash
alembic upgrade head
```

Tao hoac cap nhat admin tu `.env`:

```bash
python -m app.scripts.ensure_admin
```

## Bien moi truong

Du an can file `.env` khi chay local. Cac bien quan trong gom:

- `DATABASE_URL`
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `ALLOWED_ORIGINS`
- `FRONTEND_URL`
- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_USERNAME`
- `DEFAULT_ADMIN_PASSWORD`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`

Khong commit secret thuc te. Neu can them bien moi, cap nhat ca `README.md` va config lien quan trong `app/core/config.py`.

## Quy uoc code

- Giu code theo style hien co cua du an.
- Dat logic nghiep vu trong service, khong day qua nhieu logic vao endpoint.
- Endpoint chi nen xu ly request/response, dependency injection va ma loi HTTP.
- Schema request/response dat trong `schemas/`, model database dat trong `models/`.
- Dung async SQLAlchemy session theo pattern hien co trong `app/core/database.py`.
- Khi thay doi model database, tao migration Alembic tuong ung.
- Khong them dependency moi neu co the giai quyet bang thu vien dang co.
- Khong sua file generated/cache nhu `__pycache__`, `.DS_Store`, log runtime.

## Kiem thu

- Them hoac cap nhat test khi thay doi endpoint, service, auth, database model hoac migration co anh huong hanh vi.
- Uu tien test service cho logic nghiep vu va test API cho contract HTTP.
- Truoc khi ket thuc thay doi code, chay:

```bash
pytest
```

Neu khong chay duoc test do thieu database, dependency hoac bien moi truong, ghi ro ly do va lenh da thu.

## Luu y bao mat

- Khong log password, refresh token, access token, OAuth code, secret key hoac credential.
- Password duoc hash bang bcrypt; ton trong gioi han 72 bytes UTF-8 cua bcrypt.
- Kiem tra quyen admin/superuser o dependency hoac service theo pattern hien co.
- Khi them endpoint moi, xac dinh ro endpoint public hay can auth.
- Validate input bang Pydantic schema thay vi xu ly chuoi tuy tien trong endpoint.

## Migration va database

- `DATABASE_URL` mac dinh huong toi PostgreSQL async.
- Khong dua thay doi schema vao code ma bo qua Alembic migration.
- Migration nen nho, co ten mo ta ro nghia.
- Kiem tra `alembic upgrade head` sau khi tao migration neu moi truong database san sang.

## Khi lam viec voi repository nay

- Doc file lien quan truoc khi sua.
- Giu thay doi gon trong pham vi yeu cau.
- Khong revert thay doi cua nguoi khac neu khong duoc yeu cau ro rang.
- Neu phat hien worktree da co thay doi khong lien quan, bo qua chung.
- Neu thay doi anh huong API contract, cap nhat `README.md` neu can.
