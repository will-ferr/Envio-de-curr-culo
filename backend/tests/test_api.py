"""API: configuração inicial, autenticação, segurança e fluxo vaga → currículo → candidatura."""

from app.ai.base import AIAuthError
from app.models import Task
from app.schemas.ai import JobAnalysisResult, TailoredCoverLetter, TailoredDocuments, TailoredExperience, TailoredResume
from app.services import settings
from app.worker.runner import Worker
from tests.conftest import JOB_TEXT, PASSWORD, sample_profile


def run_tasks(limit: int = 20) -> None:
    w = Worker()
    for _ in range(limit):
        if not w.run_once():
            break


# ---------- configuração inicial e autenticação ----------
class TestSetupAndAuth:
    def test_first_access_creates_owner_once(self, client):
        assert client.get("/api/setup/status").json() == {"needs_owner": True}
        body = {"name": "Ana", "email": "Ana@Exemplo.com", "password": PASSWORD}
        assert client.post("/api/setup/owner", json=body).status_code == 201
        assert client.get("/api/setup/status").json() == {"needs_owner": False}
        # Ninguém pode "reconfigurar" a instância depois.
        assert client.post("/api/setup/owner", json=body).json()["error"]["code"] == "ALREADY_SETUP"

    def test_login_is_case_insensitive_on_email(self, client):
        client.post("/api/setup/owner", json={"name": "Ana", "email": "Ana@Exemplo.com", "password": PASSWORD})
        assert (
            client.post("/api/auth/login", json={"email": "ana@exemplo.com", "password": PASSWORD}).status_code == 200
        )

    def test_wrong_password_same_message(self, client):
        client.post("/api/setup/owner", json={"name": "Ana", "email": "ana@exemplo.com", "password": PASSWORD})
        r1 = client.post("/api/auth/login", json={"email": "ana@exemplo.com", "password": "errada-123456"})
        r2 = client.post("/api/auth/login", json={"email": "outra@exemplo.com", "password": PASSWORD})
        assert r1.status_code == r2.status_code == 401
        assert r1.json()["error"]["message"] == r2.json()["error"]["message"]

    def test_protected_routes_require_session(self, client):
        assert client.get("/api/profile").status_code == 401

    def test_session_cookie_is_httponly_strict(self, client):
        client.post("/api/setup/owner", json={"name": "Ana", "email": "ana@exemplo.com", "password": PASSWORD})
        r = client.post("/api/auth/login", json={"email": "ana@exemplo.com", "password": PASSWORD})
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie

    def test_password_change_invalidates_old_sessions(self, auth):
        old_cookie = auth.cookies.get("candidaturas_session")
        r = auth.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "nova-senha-456"})
        assert r.status_code == 200
        auth.cookies.clear()
        auth.cookies.set("candidaturas_session", old_cookie)
        assert auth.get("/api/auth/me").status_code == 401

    def test_login_rate_limit(self, client):
        from app.api.routers import auth as auth_router

        auth_router._ATTEMPTS.clear()
        codes = [
            client.post("/api/auth/login", json={"email": "x@x.com", "password": "y"}).status_code for _ in range(6)
        ]
        assert codes[-1] == 429
        auth_router._ATTEMPTS.clear()


class TestSecurity:
    def test_csrf_header_required_for_writes(self, auth):
        r = auth.put("/api/profile", json={}, headers={"X-Requested-With": ""})
        assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF"

    def test_errors_have_request_id(self, auth):
        r = auth.get("/api/jobs/999")
        assert r.status_code == 404
        assert r.json()["error"]["request_id"] == r.headers["x-request-id"]

    def test_secrets_never_returned(self, auth, db):
        settings.set_value(db, "smtp.password", "segredo-super")
        db.commit()
        body = auth.get("/api/settings").text
        assert "segredo-super" not in body
        assert auth.get("/api/settings").json()["smtp"]["password"] == {"configured": True}

    def test_secrets_are_encrypted_at_rest(self, db):
        from app.models import AppSetting

        settings.set_value(db, "ai.api_key", "sk-ant-123")
        db.commit()
        assert "sk-ant" not in str(db.get(AppSetting, "ai.api_key").value)
        assert settings.get(db, "ai.api_key") == "sk-ant-123"

    def test_internal_urls_are_blocked(self, auth):
        r = auth.post("/api/jobs", json={"url": "http://127.0.0.1:8080/admin"})
        assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_URL"

    def test_invalid_ai_key_is_rejected_before_saving(self, auth, monkeypatch, db):
        from app.ai import anthropic_provider

        def bad_check(self):
            raise AIAuthError("Chave de API inválida ou revogada.")

        monkeypatch.setattr(anthropic_provider.AnthropicProvider, "check", bad_check)
        r = auth.put("/api/settings/ai", json={"api_key": "sk-ant-errada", "model": "claude-opus-5-5"})
        assert r.status_code == 422 and r.json()["error"]["code"] == "AI_AUTH"
        assert not settings.is_set(db, "ai.api_key")


# ---------- perfil e perfis-alvo ----------
class TestProfile:
    def test_save_and_load(self, auth):
        data = sample_profile().model_dump(mode="json")
        assert auth.put("/api/profile", json=data).status_code == 200
        assert auth.get("/api/profile").json()["skills"][0]["name"] == "Python"

    def test_duplicate_skills_are_merged(self, auth):
        data = sample_profile().model_dump(mode="json")
        data["skills"].append({"name": " python ", "category": "", "level": ""})
        names = [s["name"] for s in auth.put("/api/profile", json=data).json()["skills"]]
        assert names.count("Python") == 1 and " python " not in names

    def test_import_requires_ai(self, auth):
        r = auth.post("/api/profile/import", files={"file": ("cv.pdf", b"%PDF-1.4", "application/pdf")})
        assert r.json()["error"]["code"] == "AI_NOT_CONFIGURED"

    def test_import_rejects_non_pdf(self, auth, db):
        settings.set_value(db, "ai.api_key", "x")
        db.commit()
        r = auth.post("/api/profile/import", files={"file": ("cv.pdf", b"nao sou pdf", "application/pdf")})
        assert r.json()["error"]["code"] == "NOT_PDF"

    def test_target_roles_default_is_unique(self, auth):
        a = auth.post("/api/target-roles", json={"name": "Back-end", "headline": "Dev Back-end"}).json()
        assert a["is_default"] is True  # o primeiro vira padrão
        b = auth.post("/api/target-roles", json={"name": "Dados", "headline": "Analista", "is_default": True}).json()
        roles = {r["id"]: r["is_default"] for r in auth.get("/api/target-roles").json()}
        assert roles == {a["id"]: False, b["id"]: True}
        assert auth.post("/api/target-roles", json={"name": "dados", "headline": "Analista"}).status_code == 409


# ---------- fluxo principal ----------
def _setup_profile(auth):
    auth.put("/api/profile", json=sample_profile().model_dump(mode="json"))
    return auth.post(
        "/api/target-roles",
        json={
            "name": "Back-end Python",
            "headline": "Desenvolvedora Python",
            "keywords": ["python", "fastapi"],
            "skills_focus": ["FastAPI"],
        },
    ).json()


class TestFlowWithoutAI:
    def test_job_from_text_is_analyzed_by_keywords(self, auth):
        _setup_profile(auth)
        r = auth.post("/api/jobs", json={"title": "Dev Python", "company": "Acme", "description": JOB_TEXT})
        assert r.status_code == 201
        job_id = r.json()["job"]["id"]
        assert r.json()["job"]["contact_email"] == "vagas@empresa.com.br"
        run_tasks()
        job = auth.get(f"/api/jobs/{job_id}").json()
        assert job["status"] == "analyzed"
        assert job["analysis"]["used_ai"] is False
        assert job["analysis"]["score"] == 67
        assert "kubernetes" in job["analysis"]["missing"]

    def test_duplicate_job_returns_existing_id(self, auth):
        _setup_profile(auth)
        first = auth.post("/api/jobs", json={"title": "Dev", "description": JOB_TEXT}).json()["job"]["id"]
        r = auth.post("/api/jobs", json={"title": "Dev", "description": JOB_TEXT})
        assert r.status_code == 409 and r.json()["error"]["details"]["job_id"] == first

    def test_short_description_rejected(self, auth):
        assert auth.post("/api/jobs", json={"description": "curta"}).json()["error"]["code"] == "JOB_TOO_SHORT"

    def test_generate_requires_profile(self, auth):
        job_id = auth.post("/api/jobs", json={"title": "Dev", "description": JOB_TEXT}).json()["job"]["id"]
        auth.post(f"/api/jobs/{job_id}/documents", json={})
        run_tasks()
        assert auth.get(f"/api/jobs/{job_id}").json()["documents"] == []

    def test_full_flow_baseline_documents_approve_and_mark_sent(self, auth, db):
        role = _setup_profile(auth)
        job_id = auth.post("/api/jobs", json={"title": "Dev Python", "description": JOB_TEXT}).json()["job"]["id"]
        auth.post(f"/api/jobs/{job_id}/documents", json={"target_role_id": role["id"]})
        run_tasks()

        job = auth.get(f"/api/jobs/{job_id}").json()
        resume = next(d for d in job["documents"] if d["kind"] == "resume")
        assert resume["issues"] == [] and resume["has_pdf"] is True
        assert resume["content"]["skills"][0] == "FastAPI"  # foco do perfil-alvo primeiro

        preview = auth.get(f"/api/documents/{resume['id']}/preview")
        assert "Ana Teste" in preview.text and "default-src 'none'" in preview.headers["content-security-policy"]
        pdf = auth.get(f"/api/documents/{resume['id']}/pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

        app = auth.post("/api/applications", json={"job_id": job_id}).json()
        assert app["status"] == "approved"
        sent = auth.post(f"/api/applications/{app['id']}/status", json={"status": "sent"}).json()
        assert sent["status"] == "sent" and sent["sent_via"] == "manual"
        interview = auth.post(f"/api/applications/{app['id']}/status", json={"status": "interview"}).json()
        assert [e["to"] for e in interview["events"]] == ["draft", "approved", "sent", "interview"]

        # Transição inválida
        r = auth.post(f"/api/applications/{app['id']}/status", json={"status": "sent"})
        assert r.json()["error"]["code"] == "INVALID_TRANSITION"

        dash = auth.get("/api/dashboard").json()
        assert dash["funnel"]["interview"] == 1 and dash["response_rate"] == 100

    def test_cannot_approve_resume_with_invented_skill(self, auth):
        _setup_profile(auth)
        job_id = auth.post("/api/jobs", json={"title": "Dev", "description": JOB_TEXT}).json()["job"]["id"]
        auth.post(f"/api/jobs/{job_id}/documents", json={})
        run_tasks()
        resume = next(d for d in auth.get(f"/api/jobs/{job_id}").json()["documents"] if d["kind"] == "resume")

        content = {**resume["content"], "skills": [*resume["content"]["skills"], "Kubernetes"]}
        edited = auth.put(f"/api/documents/{resume['id']}", json={"content": content}).json()
        assert any(i["severity"] == "error" for i in edited["issues"])
        assert auth.post("/api/applications", json={"job_id": job_id}).json()["error"]["code"] == "RESUME_INVALID"

    def test_email_send_validations(self, auth, db):
        _setup_profile(auth)
        job_id = auth.post("/api/jobs", json={"title": "Dev", "description": JOB_TEXT}).json()["job"]["id"]
        auth.post(f"/api/jobs/{job_id}/documents", json={})
        run_tasks()
        app_id = auth.post("/api/applications", json={"job_id": job_id}).json()["id"]
        assert auth.post(f"/api/applications/{app_id}/send").json()["error"]["code"] == "SMTP_NOT_CONFIGURED"


class TestFlowWithAI:
    def test_ai_analysis_and_tailoring(self, auth, ai, db, monkeypatch):
        role = _setup_profile(auth)
        ai.responses[JobAnalysisResult] = JobAnalysisResult(
            title="Dev Python",
            company="Acme",
            location="Remoto",
            seniority="júnior",
            contact_email="",
            score=81,
            summary="Boa aderência.",
            matched=["Python"],
            missing=["Kubernetes"],
            target_role_id=role["id"],
        )
        ai.responses[TailoredDocuments] = TailoredDocuments(
            resume=TailoredResume(
                headline="Desenvolvedora Python",
                summary="Experiência com APIs REST em Python e FastAPI.",
                skills=["FastAPI", "Python", "PostgreSQL"],
                experiences=[
                    TailoredExperience(id="exp1", highlights=["Desenvolvimento de APIs REST com FastAPI e PostgreSQL."])
                ],
                project_ids=["prj1"],
            ),
            cover_letter=TailoredCoverLetter(
                subject="Candidatura — Dev Python",
                greeting="Olá, equipe da Acme,",
                paragraphs=["Tenho experiência com Python e FastAPI."],
                closing="Atenciosamente,\nAna Teste",
            ),
        )

        job_id = auth.post("/api/jobs", json={"title": "Dev Python", "description": JOB_TEXT}).json()["job"]["id"]
        run_tasks()
        job = auth.get(f"/api/jobs/{job_id}").json()
        assert job["analysis"]["used_ai"] is True and job["analysis"]["score"] == 81
        assert job["company"] == "Acme"  # completado pela IA

        # O contato do candidato não é enviado para a IA (minimização de dados).
        assert "ana@exemplo.com" not in ai.calls[0]["prompt"]

        auth.post(f"/api/jobs/{job_id}/documents", json={})
        run_tasks()
        docs = auth.get(f"/api/jobs/{job_id}").json()["documents"]
        assert {d["kind"]: d["issues"] for d in docs} == {"resume": [], "cover_letter": []}
        usage = auth.get("/api/ai-usage").json()["items"]
        assert {u["operation"] for u in usage} == {"analyze_job", "tailor_documents"}

    def test_ai_failure_keeps_keyword_analysis_retryable(self, auth, ai, db):
        from app.ai.base import AIRateLimited

        _setup_profile(auth)
        ai.responses[JobAnalysisResult] = AIRateLimited("limite")
        job_id = auth.post("/api/jobs", json={"title": "Dev", "description": JOB_TEXT}).json()["job"]["id"]
        Worker().run_once()
        task = db.query(Task).filter(Task.kind == "analyze_job").one()
        assert task.status == "pending" and task.attempts == 1  # reagendada com backoff
        assert "AI_RATE_LIMITED" in task.last_error
        assert auth.get(f"/api/jobs/{job_id}").json()["status"] == "new"


class TestData:
    def test_export_and_wipe(self, auth):
        _setup_profile(auth)
        exported = auth.get("/api/data/export").json()
        assert exported["profile"]["contact"]["name"] == "Ana Teste"
        assert auth.post("/api/data/wipe", json={"confirm": "nao"}).status_code == 422
        assert auth.post("/api/data/wipe", json={"confirm": "APAGAR"}).status_code == 200
        assert auth.get("/api/profile").json()["skills"] == []
        assert auth.get("/api/auth/me").status_code == 200  # a conta continua
