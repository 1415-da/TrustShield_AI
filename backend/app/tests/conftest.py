"""Shared fixtures. Tests run against an in-memory SQLite database seeded once per session with the
synthetic NovaCorp reference data (no back-filled history), using the offline mock LLM."""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["JWT_SECRET"] = "test-secret-not-for-production-use-0123456789"
os.environ["DEMO_USER_PASSWORD"] = "test-password-123"

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.guardrails.pipeline import Actor  # noqa: E402
from app.seed.loader import seed_reference  # noqa: E402
from app.services.llm import LLMProvider, LLMResponse, MockProvider, set_provider_override  # noqa: E402

PASSWORD = "test-password-123"
EMPLOYEE = "ananya.rao@novacorp.test"
HR = "neha.kapoor@novacorp.test"
FINANCE = "rahul.verma@novacorp.test"
REVIEWER = "kavya.menon@novacorp.test"
AUDITOR = "sanjay.gupta@novacorp.test"
ADMIN = "rohan.das@novacorp.test"


class SpyProvider(LLMProvider):
    """Wraps the mock provider and records every call, to prove what reached the model."""

    name = "spy"
    model = "spy-1"

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self.inner = MockProvider()

    def generate(self, prompt: str, context: list[str]) -> LLMResponse:
        self.calls.append((prompt, context))
        r = self.inner.generate(prompt, context)
        r.provider, r.model = self.name, self.model
        return r


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_reference(db, PASSWORD)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def spy() -> Iterator[SpyProvider]:
    provider = SpyProvider()
    set_provider_override(provider)
    yield provider
    set_provider_override(None)


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def login(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def headers(client: TestClient) -> dict[str, dict[str, str]]:
    return {k: login(client, v) for k, v in
            {"employee": EMPLOYEE, "hr": HR, "finance": FINANCE, "reviewer": REVIEWER, "auditor": AUDITOR, "admin": ADMIN}.items()}


def actor(role: str, perms: set[str] | None = None) -> Actor:
    defaults = {"employee": {"assistant:use"}, "hr_manager": {"assistant:use", "data:compensation"},
                "finance_analyst": {"assistant:use", "data:financial"}}
    return Actor(None, f"{role}@test", {role}, perms if perms is not None else defaults.get(role, set()), role)
