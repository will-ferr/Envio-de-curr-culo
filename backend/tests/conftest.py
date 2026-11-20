"""Fixtures: banco SQLite em memória, cliente HTTP autenticado e IA falsa."""

import os
import tempfile
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "t" * 48)
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite://")
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="candidaturas-test-")
os.environ["CORS_ORIGINS"] = "[]"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as db_module  # noqa: E402
from app.ai.fake import FakeProvider  # noqa: E402
from app.db import Base  # noqa: E402
from app.schemas.profile import Experience, ProfileData, Project, Skill  # noqa: E402
from app.services import ai_runtime, render  # noqa: E402

PASSWORD = "senha-forte-123"


@pytest.fixture(autouse=True)
def database():
    engine = db_module.init_engine(os.environ["DATABASE_URL"])
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    with db_module.session_factory()() as session:
        yield session


@pytest.fixture(autouse=True)
def fake_pdf(monkeypatch):
    """Evita abrir o Chromium nos testes unitários: grava um PDF mínimo."""

    def _fake(html: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"%PDF-1.4 fake\n" + html[:200].encode())
        return dest

    monkeypatch.setattr(render, "html_to_pdf", _fake)


@pytest.fixture
def ai():
    provider = FakeProvider()
    ai_runtime.set_override(provider)
    yield provider
    ai_runtime.set_override(None)


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app, headers={"X-Requested-With": "candidaturas"}) as c:
        yield c


@pytest.fixture
def auth(client):
    client.post("/api/setup/owner", json={"name": "Ana Teste", "email": "ana@exemplo.com", "password": PASSWORD})
    r = client.post("/api/auth/login", json={"email": "ana@exemplo.com", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return client


def sample_profile() -> ProfileData:
    return ProfileData.model_validate(
        {
            "contact": {
                "name": "Ana Teste",
                "email": "ana@exemplo.com",
                "phone": "",
                "location": "Belo Horizonte",
                "links": [{"label": "GitHub", "url": "https://github.com/ana"}],
            },
            "headline": "Desenvolvedora Back-end Júnior",
            "summary": "Desenvolvedora com experiência em APIs REST com Python e FastAPI.",
            "experiences": [
                Experience(
                    id="exp1",
                    role="Estagiária de Desenvolvimento",
                    company="Empresa X",
                    start="01/2024",
                    end="",
                    highlights=[
                        "Desenvolvimento de APIs REST com FastAPI e PostgreSQL.",
                        "Criação de testes automatizados com pytest.",
                    ],
                ).model_dump()
            ],
            "skills": [Skill(name=n).model_dump() for n in ("Python", "FastAPI", "PostgreSQL", "Docker", "Git")],
            "projects": [
                Project(
                    id="prj1", name="Agenda", description="API de agendamentos", technologies=["Python", "FastAPI"]
                ).model_dump()
            ],
        }
    )


JOB_TEXT = (
    "Desenvolvedor(a) Python Júnior\n"
    "Requisitos: Python, FastAPI, PostgreSQL, Docker e Kubernetes. Desejável: AWS.\n"
    "Envie seu currículo para vagas@empresa.com.br"
)
