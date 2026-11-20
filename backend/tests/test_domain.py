"""Regras puras: comparação vaga × perfil, validação anti-alucinação, normalização."""

from app.domain import compose, matching, validation
from app.domain.text import job_fingerprint, normalize_url
from app.schemas.ai import TailoredCoverLetter, TailoredExperience, TailoredResume
from tests.conftest import JOB_TEXT, sample_profile


class TestFindTerms:
    def test_does_not_double_count_variants(self):
        # Antes, "node" e "node.js" contavam duas vezes.
        assert matching.find_terms("Experiência com Node.js e React.js", ["node", "node.js", "react", "react.js"]) == [
            "node.js",
            "react",
        ]

    def test_hyphenated_words_do_not_match(self):
        # Antes, "go-live" contava ponto para Golang.
        assert matching.find_terms("Acompanhar o go-live do projeto", ["go"]) == []
        assert matching.find_terms("Vaga para Go e Rust", ["go"]) == ["go"]

    def test_special_characters(self):
        assert matching.find_terms("Desenvolvedor C# e .NET; também C++", ["c#", ".net", "c++"]) == [
            ".net",
            "c#",
            "c++",
        ]

    def test_accented_words_are_whole_words(self):
        assert matching.find_terms("Boa expressão escrita", ["express"]) == []

    def test_synonyms_are_canonical(self):
        assert matching.find_terms("Golang e Postgres", ["golang", "postgres"]) == ["go", "postgresql"]


class TestAnalyze:
    def test_scores_matched_vs_missing(self):
        result = matching.analyze(JOB_TEXT, sample_profile(), [])
        assert set(result.matched) == {"python", "fastapi", "postgresql", "docker"}
        assert set(result.missing) == {"kubernetes", "aws"}
        assert result.score == 67

    def test_no_known_terms(self):
        assert matching.analyze("Vaga de atendimento ao cliente", sample_profile(), []).score == 0

    def test_picks_role_by_keywords_or_default(self):
        roles = [
            matching.RoleOption(1, ["java", "spring"], is_default=True),
            matching.RoleOption(2, ["python", "fastapi"]),
        ]
        assert matching.analyze(JOB_TEXT, sample_profile(), roles).target_role_id == 2
        assert matching.analyze("Vaga de suporte", sample_profile(), roles).target_role_id == 1


def _resume(**overrides) -> TailoredResume:
    base = {
        "headline": "Desenvolvedora Back-end Júnior",
        "summary": "Desenvolvedora com experiência em APIs REST com Python e FastAPI.",
        "skills": ["Python", "FastAPI"],
        "experiences": [TailoredExperience(id="exp1", highlights=["Criação de testes automatizados com pytest."])],
        "project_ids": ["prj1"],
    }
    return TailoredResume(**{**base, **overrides})


class TestValidation:
    def test_valid_resume_has_no_issues(self):
        assert validation.validate_resume(sample_profile(), _resume()) == []

    def test_invented_skill_is_an_error(self):
        issues = validation.validate_resume(sample_profile(), _resume(skills=["Python", "Kubernetes"]))
        assert [i.severity for i in issues] == ["error"]
        assert "Kubernetes" in issues[0].message

    def test_skill_comparison_ignores_case_and_spaces(self):
        assert validation.validate_resume(sample_profile(), _resume(skills=["  python ", "FASTAPI"])) == []

    def test_rewritten_highlight_is_an_error(self):
        resume = _resume(
            experiences=[TailoredExperience(id="exp1", highlights=["Liderei a migração para Kubernetes."])]
        )
        issues = validation.validate_resume(sample_profile(), resume)
        assert any(i.severity == "error" and i.field == "experiences" for i in issues)

    def test_unknown_experience_and_project(self):
        resume = _resume(experiences=[TailoredExperience(id="nope", highlights=[])], project_ids=["xxx"])
        fields = {i.field for i in validation.validate_resume(sample_profile(), resume) if i.severity == "error"}
        assert fields == {"experiences", "projects"}

    def test_unknown_technology_in_summary_is_a_warning(self):
        issues = validation.validate_resume(
            sample_profile(), _resume(summary="Tenho experiência com Python e Kubernetes.")
        )
        assert [(i.severity, "Kubernetes" in i.message) for i in issues] == [("warning", True)]

    def test_word_boundary_in_corpus(self):
        # "Java" não pode ser aceito só porque o perfil tem "JavaScript".
        profile = sample_profile()
        profile.skills.append(profile.skills[0].model_copy(update={"name": "JavaScript"}))
        issues = validation.validate_resume(profile, _resume(summary="Atuo com Java no back-end."))
        assert any("Java" in i.message for i in issues)

    def test_invented_years_of_experience(self):
        issues = validation.validate_resume(sample_profile(), _resume(summary="Desenvolvedora com 5 anos de Python."))
        assert any("5 anos" in i.message for i in issues)

    def test_cover_letter_allows_company_name(self):
        letter = TailoredCoverLetter(
            subject="Candidatura",
            greeting="Olá, equipe da Acme Tech,",
            paragraphs=["Quero contribuir com APIs em Python na Acme Tech."],
            closing="Atenciosamente,\nAna Teste",
        )
        assert (
            validation.validate_cover_letter(sample_profile(), letter, validation.allowed_job_terms("Acme Tech")) == []
        )
        assert validation.validate_cover_letter(sample_profile(), letter) != []


class TestCompose:
    def test_baseline_puts_focus_skills_first(self):
        resume = compose.baseline_resume(sample_profile(), focus=["Docker", "postgres"])
        assert resume.skills[:2] == ["Docker", "PostgreSQL"]
        assert validation.validate_resume(sample_profile(), resume) == []

    def test_render_context_drops_unknown_items(self):
        ctx = compose.render_resume_context(
            sample_profile(), _resume(skills=["Python", "Inexistente"], project_ids=["prj1", "nope"])
        )
        assert [s["name"] for s in ctx["skills"]] == ["Python"]
        assert [p["name"] for p in ctx["projects"]] == ["Agenda"]


class TestText:
    def test_normalize_url_strips_tracking(self):
        a = normalize_url("https://Site.com/vagas/123/?utm_source=x&id=9#topo")
        assert a == normalize_url("https://site.com/vagas/123?id=9&fbclid=abc")

    def test_fingerprint_same_job_different_links(self):
        assert job_fingerprint("https://s.com/v/1?utm_medium=a", "", None, "") == job_fingerprint(
            "https://s.com/v/1", "x", "y", "z"
        )


class TestCoverLetterTitle:
    def _letter(self, paragraph: str) -> TailoredCoverLetter:
        return TailoredCoverLetter(
            subject="Candidatura — Dev Kotlin",
            greeting="Olá,",
            paragraphs=[paragraph],
            closing="Atenciosamente,\nAna Teste",
        )

    def test_title_can_be_cited_when_talking_about_the_job(self):
        letter = self._letter("Gostaria de me candidatar à vaga de Dev Kotlin.")
        assert validation.validate_cover_letter(sample_profile(), letter, title_terms={"dev", "kotlin"}) == []

    def test_title_terms_still_flagged_as_claims(self):
        letter = self._letter("Tenho experiência sólida com Kotlin.")
        issues = validation.validate_cover_letter(sample_profile(), letter, title_terms={"dev", "kotlin"})
        assert any("Kotlin" in i.message for i in issues)
