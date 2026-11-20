"""Monta o conteúdo dos documentos a partir do perfil.

`baseline_*` gera a versão sem IA (a partir do perfil-alvo); `render_context`
transforma o conteúdo (gerado por IA ou editado) no contexto do template.
"""

from app.domain.matching import canonical
from app.schemas.ai import TailoredCoverLetter, TailoredExperience, TailoredResume
from app.schemas.profile import ProfileData


def baseline_resume(
    profile: ProfileData, headline: str = "", summary: str = "", focus: list[str] | None = None
) -> TailoredResume:
    """Currículo sem IA: competências do foco do perfil-alvo primeiro, tudo do perfil incluído."""
    focus_keys = [canonical(f) for f in (focus or [])]

    def rank(name: str) -> int:
        c = canonical(name)
        return focus_keys.index(c) if c in focus_keys else len(focus_keys)

    skills = sorted((s.name for s in profile.skills), key=rank)
    projects = sorted(
        profile.projects,
        key=lambda p: 0 if {canonical(t) for t in p.technologies} & set(focus_keys) else 1,
    )
    return TailoredResume(
        headline=headline or profile.headline,
        summary=summary or profile.summary,
        skills=skills,
        experiences=[TailoredExperience(id=e.id, highlights=list(e.highlights)) for e in profile.experiences],
        project_ids=[p.id for p in projects],
    )


def baseline_cover_letter(profile: ProfileData, job_title: str, company: str | None) -> TailoredCoverLetter:
    where = f" na {company}" if company else ""
    return TailoredCoverLetter(
        subject=f"Candidatura — {job_title} — {profile.contact.name}".strip(" —"),
        greeting="Olá, equipe de recrutamento,",
        paragraphs=[
            f"Gostaria de me candidatar à vaga de {job_title}{where}.",
            profile.summary or profile.headline,
            "Envio meu currículo em anexo e fico à disposição para conversarmos.",
        ],
        closing=f"Atenciosamente,\n{profile.contact.name}",
    )


def render_resume_context(profile: ProfileData, resume: TailoredResume) -> dict:
    by_skill = {s.name.casefold(): s for s in profile.skills}
    by_exp = {e.id: e for e in profile.experiences}
    by_proj = {p.id: p for p in profile.projects}

    experiences = []
    for te in resume.experiences:
        e = by_exp.get(te.id)
        if e:
            experiences.append({**e.model_dump(), "highlights": te.highlights})

    return {
        "contact": profile.contact.model_dump(),
        "headline": resume.headline,
        "summary": resume.summary,
        "availability": profile.availability,
        "skills": [by_skill[s.casefold()].model_dump() for s in resume.skills if s.casefold() in by_skill],
        "experiences": experiences,
        "projects": [by_proj[p].model_dump() for p in resume.project_ids if p in by_proj],
        "education": [e.model_dump() for e in profile.education],
        "languages": [lang.model_dump() for lang in profile.languages],
        "certifications": [c.model_dump() for c in profile.certifications],
    }


def render_letter_context(profile: ProfileData, letter: TailoredCoverLetter) -> dict:
    return {"contact": profile.contact.model_dump(), **letter.model_dump()}


def letter_as_text(letter: TailoredCoverLetter) -> str:
    return "\n\n".join([letter.greeting, *letter.paragraphs, letter.closing])
