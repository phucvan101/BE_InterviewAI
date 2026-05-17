"""
Interactive terminal script that tests Conversation via FastAPI HTTP API.

Prereqs:
  - Run the API server first (e.g. `uvicorn app.main:app --reload`)
  - Ensure `.env` points to the same DB the server uses.

Run:
  PYTHONPATH=. .venv/bin/python app/scripts/interactive_conversation_api_cli.py

Flags:
  --base-url http://localhost:8000
  --email test@example.com --password test123456
"""

import argparse
import asyncio
import json
from typing import Any, Optional

import httpx


SAMPLE_JOB_DESCRIPTION = """
Senior Python Backend Engineer

Requirements:
- 5+ years experience with Python
- FastAPI or Django experience
- PostgreSQL and async programming
- AWS/Cloud services
- RESTful API design
- System design and scalability

Responsibilities:
- Design and build scalable backend services
- Mentor junior developers
- Code review and architecture decisions
""".strip()

SAMPLE_CV_PROFILE = """
Name: Nguyen Van A
Email: nguyenvana@example.com
Phone: +84 123 456 789

Experience:
- Backend Developer at TechCorp (2021-2024, 3 years)
  * Built APIs using FastAPI
  * PostgreSQL database design
  * AWS deployment and DevOps

- Junior Developer at StartupXYZ (2019-2021, 2 years)
  * Django development
  * REST API development
  * MySQL database

Skills:
- Languages: Python, JavaScript, SQL
- Frameworks: FastAPI, Django, Flask
- Databases: PostgreSQL, MySQL, MongoDB
- Cloud: AWS, Google Cloud
- Tools: Docker, Git, CI/CD
""".strip()


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


async def _start_conversation(client: httpx.AsyncClient, api_prefix: str, *, job_description: str, cv_profile: str) -> dict[str, Any]:
    resp = await client.post(
        f"{api_prefix}/conversations/",
        json={"job_description": job_description, "cv_profile": cv_profile},
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


async def _end_interview(client: httpx.AsyncClient, api_prefix: str, *, session_id: str) -> dict[str, Any]:
    resp = await client.post(f"{api_prefix}/conversations/{session_id}/end")
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
    use_sample: bool,
) -> int:
    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        await _maybe_register(client, api_prefix, email=email, username=username, password=password)
        token = await _login(client, api_prefix, email=email, password=password)
        client.headers.update({"Authorization": f"Bearer {token}"})

        print("\n=== START INTERVIEW (API) ===")
        if use_sample:
            job_description = SAMPLE_JOB_DESCRIPTION
            cv_profile = SAMPLE_CV_PROFILE
            print("(using SAMPLE_JOB_DESCRIPTION + SAMPLE_CV_PROFILE)")
        else:
            job_description = await _ainput("Paste Job Description (single line):\n> ")
            cv_profile = await _ainput("Paste CV profile (single line):\n> ")

        conv = await _start_conversation(
            client,
            api_prefix,
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

        result = await _end_interview(client, api_prefix, session_id=session_id)
        print("\n=== RESULT ===")
        print(f"Session ID: {result.get('session_id')}")
        print(f"Status: {result.get('status')}")
        print(f"Score: {result.get('score')}")
        print(f"Total messages: {result.get('total_messages')}")
        print("Result JSON:")
        print(json.dumps(result.get("result"), ensure_ascii=False, indent=2))
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive Conversation API CLI test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-prefix", default="/api/v1")
    parser.add_argument("--email", default="test@example.com")
    parser.add_argument("--username", default="testuser")
    parser.add_argument("--password", default="test123456")
    parser.add_argument("--max-rounds", type=int, default=6)
    parser.add_argument("--no-sample", action="store_true", help="Do not use sample JD/CV; prompt for input")
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
                use_sample=not args.no_sample,
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
