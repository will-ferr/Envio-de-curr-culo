"""Integrações isoladas da rede: Telegram, leitura de páginas, fila, e-mail e RSS."""

from datetime import timedelta
from pathlib import Path

import pytest

from app.db import utcnow
from app.errors import BusinessRule
from app.models import Application, Job, JobSource, Task
from app.services import fetch, mail, notify, queue, settings
from app.services import jobs as jobs_svc
from app.services import profile as profile_svc
from app.services.telegram import _keyboard, esc
from tests.conftest import JOB_TEXT, sample_profile


class FakeTelegram:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []
        self.answers: list[str] = []

    def send_message(self, chat_id, text, buttons=None):
        self.sent.append((chat_id, text))

    def answer_callback(self, callback_id, text=""):
        self.answers.append(text)


def _job(db) -> Job:
    profile_svc.save_profile(db, sample_profile())
    job = jobs_svc.create_job(db, origin="manual", title="Dev <Python> & Co", description=JOB_TEXT)
    db.commit()
    return job


class TestTelegram:
    def test_pairing_with_code_links_chat(self, db):
        settings.set_value(db, "telegram.bot_token", "123:abc")
        code = notify.new_pair_code(db)
        db.commit()
        tg = FakeTelegram()
        notify.handle_update(db, {"message": {"chat": {"id": 42}, "text": "/start 000000-errado"}}, tg)
        assert not settings.get(db, "telegram.chat_id")
        notify.handle_update(db, {"message": {"chat": {"id": 42}, "text": f"/start {code}"}}, tg)
        assert settings.get(db, "telegram.chat_id") == "42"
        assert settings.get(db, "telegram.pair_code") is None  # código de uso único

    def test_callbacks_from_other_chats_are_ignored(self, db):
        job = _job(db)
        settings.set_value(db, "telegram.chat_id", "42")
        db.commit()
        tg = FakeTelegram()
        notify.handle_update(
            db, {"callback_query": {"id": "c1", "data": f"d:{job.id}", "message": {"chat": {"id": 666}}}}, tg
        )
        db.refresh(job)
        assert job.status == "new" and tg.answers == ["Chat não autorizado."]

    def test_discard_and_generate_buttons(self, db):
        job = _job(db)
        settings.set_value(db, "telegram.chat_id", "42")
        db.commit()
        tg = FakeTelegram()
        cb = {"id": "c1", "message": {"chat": {"id": 42}}}
        notify.handle_update(db, {"callback_query": {**cb, "data": f"g:{job.id}"}}, tg)
        assert db.query(Task).filter(Task.kind == "generate_documents").count() == 1
        notify.handle_update(db, {"callback_query": {**cb, "data": f"d:{job.id}"}}, tg)
        db.refresh(job)
        assert job.status == "discarded"

    def test_approve_without_resume_reports_error(self, db):
        job = _job(db)
        settings.set_value(db, "telegram.chat_id", "42")
        db.commit()
        tg = FakeTelegram()
        notify.handle_update(
            db, {"callback_query": {"id": "c", "data": f"m:{job.id}", "message": {"chat": {"id": 42}}}}, tg
        )
        assert tg.answers == ["Gere o currículo antes de aprovar."]
        assert db.query(Application).count() == 0

    def test_html_escaping_and_keyboard(self):
        assert esc("P&D <Júnior>") == "P&amp;D &lt;Júnior&gt;"
        kb = _keyboard([[("Abrir", "https://x.com/v/1"), ("Gerar", "g:1")]])
        assert kb["inline_keyboard"][0] == [
            {"text": "Abrir", "url": "https://x.com/v/1"},
            {"text": "Gerar", "callback_data": "g:1"},
        ]


class TestFetch:
    def test_json_ld_job_posting(self):
        html = """<html><head><title>Ignorado</title>
        <script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting",
         "title":"Dev Python Pleno","hiringOrganization":{"@type":"Organization","name":"Acme"},
         "jobLocation":{"address":{"addressLocality":"Belo Horizonte","addressRegion":"MG"}},
         "description":"<p>Trabalhar com <b>FastAPI</b> e PostgreSQL.</p>"}</script></head><body>x</body></html>"""
        job = fetch.parse_job_page("https://x.com/v/1", html)
        assert (job.title, job.company, job.location) == ("Dev Python Pleno", "Acme", "Belo Horizonte, MG")
        assert "FastAPI" in job.description and "<b>" not in job.description

    def test_fallback_to_main_text_without_scripts(self):
        html = (
            "<html><head><meta property='og:title' content='Vaga Backend'></head><body><nav>menu</nav>"
            "<main><h1>Vaga</h1><p>Requisitos: Go e Docker</p></main><script>alert(1)</script></body></html>"
        )
        job = fetch.parse_job_page("https://x.com/v/2", html)
        assert job.title == "Vaga Backend"
        assert "Requisitos" in job.description and "menu" not in job.description and "alert" not in job.description

    @pytest.mark.parametrize(
        "url", ["ftp://x.com/a", "http://localhost/x", "http://10.0.0.5/", "http://169.254.169.254/"]
    )
    def test_blocks_non_public_urls(self, url):
        with pytest.raises(BusinessRule):
            fetch.assert_public_url(url)


class TestQueue:
    def test_claim_retry_backoff_and_failure(self, db):
        t = queue.enqueue(db, "x", {"a": 1}, max_attempts=2)
        db.commit()
        claimed = queue.claim(db)
        assert claimed.id == t.id and claimed.status == "running" and claimed.attempts == 1
        queue.fail(db, claimed, "boom")
        assert t.status == "pending" and t.run_after > utcnow()
        assert queue.claim(db) is None  # ainda no backoff
        t.run_after = utcnow() - timedelta(seconds=1)
        db.commit()
        queue.fail(db, queue.claim(db), "boom de novo")
        assert t.status == "failed"

    def test_dedupe(self, db):
        a = queue.enqueue(db, "poll_sources", {}, dedupe=True)
        b = queue.enqueue(db, "poll_sources", {}, dedupe=True)
        assert a.id == b.id

    def test_recover_stale(self, db):
        t = queue.enqueue(db, "x", {})
        db.commit()
        queue.claim(db)
        t.updated_at = utcnow() - timedelta(hours=1)
        db.commit()
        assert queue.recover_stale(db) == 1 and t.status == "pending"


class TestMail:
    def test_build_message_with_attachment(self, tmp_path: Path):
        pdf = tmp_path / "cv.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        cfg = mail.SMTPConfig("smtp.x.com", 587, "u", "p", "starttls", "ana@exemplo.com", "Ana Teste")
        msg = mail.build_message(cfg, "rh@acme.com", "Candidatura", "Olá", [mail.Attachment("Ana_CV.pdf", pdf)])
        assert msg["From"] == "Ana Teste <ana@exemplo.com>" and msg["To"] == "rh@acme.com"
        att = next(msg.iter_attachments())
        assert att.get_filename() == "Ana_CV.pdf" and att.get_content_type() == "application/pdf"

    def test_daily_limit(self, db, auth):
        from app.services import applications as apps_svc

        job = _job(db)
        app = Application(job_id=job.id, status="approved")
        db.add(app)
        for k, v in {
            "smtp.host": "h",
            "smtp.username": "u",
            "smtp.password": "p",
            "smtp.from_email": "a@b.com",
            "prefs.daily_send_limit": 1,
        }.items():
            settings.set_value(db, k, v)
        other = jobs_svc.create_job(db, origin="manual", title="Outra", description=JOB_TEXT + " outra")
        db.add(Application(job_id=other.id, status="sent", sent_via="email", sent_at=utcnow()))
        db.commit()
        with pytest.raises(BusinessRule) as exc:
            apps_svc.check_can_email(db, app)
        assert exc.value.code == "DAILY_LIMIT"


class TestPollSources:
    def test_rss_creates_jobs_and_records_errors(self, db, monkeypatch):
        from app.services.rss import FeedEntry
        from app.worker import handlers

        profile_svc.save_profile(db, sample_profile())
        db.add_all(
            [JobSource(name="Bom", url="https://bom.com/rss"), JobSource(name="Ruim", url="https://ruim.com/rss")]
        )
        db.commit()

        def fake_feed(url):
            if "ruim" in url:
                raise BusinessRule("feed fora do ar")
            return [
                FeedEntry("Dev Python", "https://bom.com/v/1", JOB_TEXT * 3, "Acme"),
                FeedEntry("Dev Python", "https://bom.com/v/1?utm_source=rss", JOB_TEXT * 3, "Acme"),
            ]

        monkeypatch.setattr(handlers, "read_feed", fake_feed)
        result = handlers.poll_sources(db, {})
        assert result == {"created": 1, "failed_sources": ["Ruim"]}  # a URL repetida com utm é a mesma vaga
        ruim = db.query(JobSource).filter_by(name="Ruim").one()
        assert ruim.last_error == "feed fora do ar"
        assert db.query(Task).filter(Task.kind == "analyze_job").count() == 1


class TestCli:
    def test_import_example_profile(self, db):
        from pathlib import Path

        from app import cli

        example = Path(__file__).resolve().parents[2] / "examples" / "perfil-exemplo.json"
        assert cli.main(["importar-perfil", str(example)]) == 0
        db.expire_all()
        assert profile_svc.get_profile(db).contact.name == "Maria Exemplo"
        assert [r.name for r in profile_svc.list_roles(db)] == ["Back-end Python"]

    def test_legacy_yaml_conversion(self):
        from app.cli import legacy_to_profile, skills_from_sentence

        assert skills_from_sentence("ASP.NET Core: APIs RESTful, middleware") == [
            "ASP.NET Core",
            "APIs RESTful",
            "middleware",
        ]
        assert "Ferramentas" not in skills_from_sentence("Ferramentas: VS Code, Postman")
        base = {
            "nome": "Ana",
            "experiencia": [
                {"cargo": "Estagiária", "empresa": "X", "periodo": "06/2024 – Atual", "itens": ["Fiz algo"]}
            ],
            "competencias_comuns": ["Git e GitHub"],
        }
        stacks = {
            "py": {
                "nome": "Python",
                "titulo": "Dev Python",
                "resumo": "Uso {front}.",
                "competencias": ["Python: POO"],
                "palavras_chave": ["python"],
            }
        }
        fronts = {"vue": {"nome": "Vue.js", "competencia": "Vue.js (em estudo): componentes"}, "comum": "Web: HTML5"}
        profile, roles = legacy_to_profile(base, stacks, fronts)
        assert profile.experiences[0].start == "06/2024" and profile.experiences[0].end == ""
        assert {"Git", "GitHub", "Python", "POO", "Vue.js", "HTML5"} <= {s.name for s in profile.skills}
        assert roles[0]["summary"] == "Uso Vue.js."
