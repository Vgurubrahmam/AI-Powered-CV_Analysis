#!/usr/bin/env python
"""Seed script — populate the database with sample data for development/demo.

Usage:
    python scripts/seed_data.py [--reset]

Options:
    --reset   Drop all seeded data first (based on seed_marker email prefix)
"""

from __future__ import annotations

import asyncio
import sys
import uuid

sys.path.insert(0, ".")  # run from Backend/


async def main(reset: bool = False) -> None:
    from app.dependencies import get_session_factory
    from app.core.security import hash_password
    from app.models.user import User
    from app.models.job import JobDescription
    from app.models.resume import Resume
    from sqlalchemy import delete, select

    factory = get_session_factory()
    async with factory() as db:

        if reset:
            print("🗑  Resetting seed data...")
            await db.execute(delete(User).where(User.email.like("seed+%@ats-demo.local")))
            await db.commit()
            print("   Done.")

        # ── Users ──────────────────────────────────────────────────────────────
        users_data = [
            {"email": "seed+admin@ats-demo.local", "role": "system_admin", "plan_tier": "enterprise"},
            {"email": "seed+recruiter@ats-demo.local", "role": "recruiter", "plan_tier": "pro"},
            {"email": "seed+candidate1@ats-demo.local", "role": "candidate", "plan_tier": "free"},
            {"email": "seed+candidate2@ats-demo.local", "role": "candidate", "plan_tier": "pro"},
        ]

        created_users = []
        for ud in users_data:
            existing = (await db.execute(select(User).where(User.email == ud["email"]))).scalar_one_or_none()
            if existing:
                print(f"   ⏭  User {ud['email']} already exists, skipping.")
                created_users.append(existing)
                continue
            user = User(
                id=uuid.uuid4(),
                email=ud["email"],
                password_hash=hash_password("Password123!"),
                role=ud["role"],
                plan_tier=ud["plan_tier"],
                is_active=True,
            )
            db.add(user)
            created_users.append(user)
            print(f"   ✅ Created user: {ud['email']} ({ud['role']})")

        await db.commit()

        # ── Sample Job Descriptions ────────────────────────────────────────────
        recruiter = next((u for u in created_users if "recruiter" in u.email), None)
        if recruiter:
            jds_data = [
                {
                    "title": "Senior Software Engineer — Backend",
                    "company": "Acme Corp",
                    "raw_text": (
                        "We are looking for a Senior Backend Engineer with 5+ years of experience.\n"
                        "Required skills: Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes.\n"
                        "Nice to have: AWS, Celery, pgvector, Machine Learning.\n"
                        "BS/MS in Computer Science or related field preferred.\n"
                        "Responsibilities: Design and build scalable REST APIs, "
                        "mentor junior engineers, lead architecture decisions."
                    ),
                    "parsed_data": {
                        "required_skills": ["python", "fastapi", "postgresql", "redis", "docker", "kubernetes"],
                        "preferred_skills": ["aws", "celery", "pgvector", "machine learning"],
                        "required_yoe_min": 5,
                        "required_degree": "bachelor",
                        "seniority_level": "senior",
                    },
                    "parse_status": "SUCCESS",
                },
                {
                    "title": "ML Engineer",
                    "company": "DataFlow AI",
                    "raw_text": (
                        "Seeking an ML Engineer to build production AI systems.\n"
                        "Required: Python, PyTorch, scikit-learn, SQL, MLflow.\n"
                        "Nice to have: Kubernetes, Airflow, dbt, Spark.\n"
                        "3+ years experience required. PhD or MS preferred."
                    ),
                    "parsed_data": {
                        "required_skills": ["python", "pytorch", "scikit-learn", "sql", "mlflow"],
                        "preferred_skills": ["kubernetes", "airflow", "dbt", "spark"],
                        "required_yoe_min": 3,
                        "required_degree": "master",
                        "seniority_level": "mid",
                    },
                    "parse_status": "SUCCESS",
                },
            ]

            for jd_data in jds_data:
                existing_jd = (
                    await db.execute(
                        select(JobDescription)
                        .where(JobDescription.user_id == recruiter.id, JobDescription.title == jd_data["title"])
                    )
                ).scalar_one_or_none()

                if existing_jd:
                    print(f"   ⏭  JD '{jd_data['title']}' already exists.")
                    continue

                jd = JobDescription(
                    id=uuid.uuid4(),
                    user_id=recruiter.id,
                    title=jd_data["title"],
                    company=jd_data["company"],
                    raw_text=jd_data["raw_text"],
                    parsed_data=jd_data["parsed_data"],
                    parse_status=jd_data["parse_status"],
                )
                db.add(jd)
                print(f"   ✅ Created JD: {jd_data['title']}")

            await db.commit()

        print("\n✅ Seeding complete.")
        print("\nSeed credentials (password: Password123!):")
        for u in users_data:
            print(f"   {u['email']:45s} role={u['role']}")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    asyncio.run(main(reset=reset))
