"""
Interactive terminal script that tests Conversation via FastAPI HTTP API.

Prereqs:
  - Run the API server first (e.g. `uvicorn app.main:app --reload`)
  - Ensure `.env` points to the same DB the server uses.
  - Have an analysis_sessions record with id=2 (or specify --analysis-session-id)

Run:
  PYTHONPATH=. .venv/bin/python app/scripts/interactive_conversation_api_cli.py

Flags:
  --base-url http://localhost:8000
  --email test@example.com --password test123456
  --analysis-session-id 2 (default: fetch JD/CV from analysis_sessions table)
"""

import argparse
import asyncio
import json
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.feature.feature_up_cv.auth.models.analysis_session import AnalysisSession
<<<<<<< HEAD
from app.feature.feature_up_cv.file_storage import load_result_analysis
from app.core.config import settings


async def _get_analysis_session_data(session_id: int) -> dict[str, Any]:
=======
from app.core.config import settings


async def _get_analysis_session_data(session_id: int) -> dict[str, str]:
>>>>>>> c2202c1 (rebase main)
    """Fetch CV and JD data from analysis_sessions table."""
    database_url = settings.DATABASE_URL
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        result = await db.execute(
            select(AnalysisSession).where(AnalysisSession.id_session == session_id)
        )
        analysis_session = result.scalar_one_or_none()
        await engine.dispose()
        
        if not analysis_session:
            raise ValueError(f"AnalysisSession with id {session_id} not found")
        
        if not analysis_session.cv_raw_text or not analysis_session.jd_raw_text:
            raise ValueError(
                f"AnalysisSession {session_id} missing cv_raw_text or jd_raw_text"
            )
<<<<<<< HEAD

        analysis_result = load_result_analysis(analysis_session.result_analysis_file_url) or {}
        company_match = analysis_result.get("company_match")
        company_name = company_match.get("company_name") if isinstance(company_match, dict) else None
=======
>>>>>>> c2202c1 (rebase main)
        
        return {
            "job_description": analysis_session.jd_raw_text,
            "cv_profile": analysis_session.cv_raw_text,
<<<<<<< HEAD
            "job_position": analysis_result.get("job_position") or "N/A",
            "company_name": company_name,
=======
>>>>>>> c2202c1 (rebase main)
        }


async def _ainput(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def _maybe_register(client: httpx.AsyncClient, api_prefix: str, *, email: str, username: str, password: str):
    payload = {
        "email": email,
        "username": username,
        "password": password,
        "full_name": "Test User",
    }
    resp = await client.post(f"{api_prefix}/users/register", json=payload)
    # 201 created is OK; 400/409 means already exists depending on implementation
    if resp.status_code in (200, 201):
        return
    if resp.status_code in (400, 409, 422):
        return
    resp.raise_for_status()


async def _login(client: httpx.AsyncClient, api_prefix: str, *, email: str, password: str) -> str:
    resp = await client.post(f"{api_prefix}/users/login", json={"email": email, "password": password})
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"Login response missing access_token: {data}")
    return token


<<<<<<< HEAD
async def _start_conversation(
    client: httpx.AsyncClient,
    api_prefix: str,
    *,
    job_position: str,
    company_name: str | None,
    job_description: str,
    cv_profile: str,
) -> dict[str, Any]:
    resp = await client.post(
        f"{api_prefix}/conversations/",
        json={
            "job_position": job_position,
            "company_name": company_name,
            "job_description": job_description,
            "cv_profile": cv_profile,
        },
=======
async def _start_conversation(client: httpx.AsyncClient, api_prefix: str, *, job_description: str, cv_profile: str) -> dict[str, Any]:
    resp = await client.post(
        f"{api_prefix}/conversations/",
        json={"job_description": job_description, "cv_profile": cv_profile},
>>>>>>> c2202c1 (rebase main)
    )
    resp.raise_for_status()
    return resp.json()


async def _next_question(client: httpx.AsyncClient, api_prefix: str, *, session_id: str) -> dict[str, Any]:
    resp = await client.post(f"{api_prefix}/conversations/{session_id}/next-question")
    resp.raise_for_status()
    return resp.json()


async def _send_answer(client: httpx.AsyncClient, api_prefix: str, *, session_id: str, answer: str) -> dict[str, Any]:
    resp = await client.post(f"{api_prefix}/conversations/{session_id}/answer", json={"answer": answer})
    resp.raise_for_status()
    return resp.json()


<<<<<<< HEAD
async def _create_analysis_report(client: httpx.AsyncClient, api_prefix: str, *, session_id: str) -> dict[str, Any]:
    resp = await client.post(f"{api_prefix}/conversations/{session_id}/analysis-report")
=======
async def _end_interview(client: httpx.AsyncClient, api_prefix: str, *, session_id: str) -> dict[str, Any]:
    resp = await client.post(f"{api_prefix}/conversations/{session_id}/end")
>>>>>>> c2202c1 (rebase main)
    resp.raise_for_status()
    return resp.json()


async def run_interactive(
    *,
    base_url: str,
    api_prefix: str,
    email: str,
    username: str,
    password: str,
    max_rounds: int,
    analysis_session_id: int,
) -> int:
    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        await _maybe_register(client, api_prefix, email=email, username=username, password=password)
        token = await _login(client, api_prefix, email=email, password=password)
        client.headers.update({"Authorization": f"Bearer {token}"})

        print("\n=== START INTERVIEW (API) ===")
        # Fetch data from analysis_sessions table
        print(f"Fetching data from analysis_sessions (id={analysis_session_id})...")
        session_data = await _get_analysis_session_data(analysis_session_id)
        job_description = session_data["job_description"]
        cv_profile = session_data["cv_profile"]
<<<<<<< HEAD
        job_position = session_data["job_position"]
        company_name = session_data["company_name"]
=======
>>>>>>> c2202c1 (rebase main)
        print(f"✓ Loaded JD and CV from analysis_sessions table")

        conv = await _start_conversation(
            client,
            api_prefix,
<<<<<<< HEAD
            job_position=job_position,
            company_name=company_name,
=======
>>>>>>> c2202c1 (rebase main)
            job_description=job_description.strip() or "N/A",
            cv_profile=cv_profile.strip() or "N/A",
        )
        session_id = conv["session_id"]
        print(f"\nSession ID: {session_id}")
        print("Commands: /end to finish, /quit to exit.\n")

        # First question
        q = await _next_question(client, api_prefix, session_id=session_id)
        print(f"[AI] {q['question']}")

        rounds = 0
        while rounds < max_rounds:
            answer = (await _ainput("[YOU] ")).strip()
            if answer.lower() in {"/quit", "/exit"}:
                print("Exit.")
                return 0
            if answer.lower() == "/end":
                break
            if not answer:
                continue

            nxt = await _send_answer(client, api_prefix, session_id=session_id, answer=answer)
            print(f"[AI] {nxt['question']}")
            rounds += 1

<<<<<<< HEAD
        result = await _create_analysis_report(client, api_prefix, session_id=session_id)
        print("\n=== RESULT ===")
        print(f"Session ID: {result.get('session_id')}")
        print(f"Status: {result.get('status')}")
        print(f"Score: {result.get('overall_score')} ({result.get('overall_grade')})")
        print(f"Total messages: {result.get('total_messages')}")
        print(f"Summary: {result.get('summary')}")
        print("Report JSON:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
=======
        result = await _end_interview(client, api_prefix, session_id=session_id)
        print("\n=== RESULT ===")
        print(f"Session ID: {result.get('session_id')}")
        print(f"Status: {result.get('status')}")
        print(f"Score: {result.get('score')}")
        print(f"Total messages: {result.get('total_messages')}")
        print("Result JSON:")
        print(json.dumps(result.get("result"), ensure_ascii=False, indent=2))
>>>>>>> c2202c1 (rebase main)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive Conversation API CLI test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-prefix", default="/api/v1")
    parser.add_argument("--email", default="test@example.com")
    parser.add_argument("--username", default="testuser")
    parser.add_argument("--password", default="test123456")
    parser.add_argument("--max-rounds", type=int, default=6)
    parser.add_argument(
        "--analysis-session-id", 
        type=int, 
        default=2, 
        help="Analysis session ID to fetch JD/CV from (default: 2)"
    )
    args = parser.parse_args()

    try:
        return asyncio.run(
            run_interactive(
                base_url=args.base_url,
                api_prefix=args.api_prefix,
                email=args.email,
                username=args.username,
                password=args.password,
                max_rounds=args.max_rounds,
                analysis_session_id=args.analysis_session_id,
            )
        )
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except httpx.ConnectError:
        print(f"Cannot connect to API at {args.base_url}. Start server first.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
