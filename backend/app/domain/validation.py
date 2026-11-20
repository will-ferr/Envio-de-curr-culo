"""Validação anti-alucinação dos documentos gerados.

Regra central do produto: um currículo enviado em nome da pessoa não pode
afirmar nada que não esteja no perfil dela.

- error   → bloqueia a aprovação (competência, experiência ou projeto inexistente,
            item de experiência que não existe no perfil)
- warning → precisa de revisão humana (termo próprio ou número citado no texto
            livre que não aparece em nenhum lugar do perfil)
"""

import re
from dataclasses import asdict, dataclass

from app.domain.text import find_spans, normalize
from app.schemas.ai import TailoredCoverLetter, TailoredResume
from app.schemas.profile import ProfileData

# Palavras capitalizadas comuns em currículos/cartas que não são afirmações técnicas.
COMMON_WORDS = {
    "desenvolvedor",
    "desenvolvedora",
    "analista",
    "engenheiro",
    "engenheira",
    "estagiário",
    "estagiária",
    "júnior",
    "junior",
    "pleno",
    "sênior",
    "senior",
    "full",
    "stack",
    "back-end",
    "front-end",
    "backend",
    "frontend",
    "fullstack",
    "prezado",
    "prezada",
    "prezados",
    "olá",
    "atenciosamente",
    "cordialmente",
    "obrigado",
    "obrigada",
    "brasil",
    "ti",
    "rh",
    "eu",
    "minha",
    "meu",
    "com",
    "em",
    "na",
    "no",
    "para",
    "tenho",
    "sou",
    "busco",
    "atuo",
    "atuei",
    "possuo",
    "estou",
    "como",
    "também",
    "além",
    "experiência",
    "formação",
    "conhecimento",
    "conhecimentos",
    "equipe",
    "empresa",
    "vaga",
    "oportunidade",
    "carta",
    "candidatura",
    "resumo",
    "profissional",
    "ciência",
    "computação",
    "bacharelado",
    "universidade",
}

_TOKEN = re.compile(r"[A-Za-zÀ-ÿ0-9][\w.+#/-]*[\w+#]|[A-Za-zÀ-ÿ0-9]")
_YEARS = re.compile(r"\b(\d{1,2})\s*\+?\s*anos?\b", re.I)


@dataclass
class Issue:
    severity: str  # error | warning
    field: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


def profile_corpus(profile: ProfileData) -> str:
    return normalize(profile.model_dump_json())


def _is_claim_token(token: str, sentence_start: bool) -> bool:
    """Tokens que parecem nome próprio, tecnologia ou sigla."""
    if any(ch.isdigit() for ch in token) or any(ch in "#+./" for ch in token[1:]):
        return True
    if len(token) >= 2 and token.isupper():
        return True
    return token[0].isupper() and not sentence_start


def unknown_terms(text: str, corpus: str, allowed: set[str] = frozenset()) -> list[str]:
    found: list[str] = []
    for sentence in re.split(r"(?<=[.!?:])\s+|\n+", text):
        for i, m in enumerate(_TOKEN.finditer(sentence)):
            tok = m.group(0).strip(".,;:")
            if not tok or len(tok) < 2:
                continue
            low = tok.casefold()
            if low in COMMON_WORDS or low in allowed:
                continue
            # Busca por palavra inteira: "Java" não pode passar só porque o perfil tem "JavaScript".
            if _is_claim_token(tok, sentence_start=(i == 0)) and not find_spans(corpus, low) and tok not in found:
                found.append(tok)
    return found


def _check_free_text(field: str, text: str, corpus: str, allowed: set[str]) -> list[Issue]:
    issues = [
        Issue("warning", field, f"“{t}” não aparece no seu perfil. Confirme que é verdade antes de enviar.")
        for t in unknown_terms(text, corpus, allowed)
    ]
    for m in _YEARS.finditer(text):
        if m.group(0).casefold() not in corpus:
            issues.append(
                Issue("warning", field, f"“{m.group(0)}” não consta no seu perfil. Revise o tempo de experiência.")
            )
    return issues


def validate_resume(profile: ProfileData, resume: TailoredResume, allowed: set[str] = frozenset()) -> list[Issue]:
    issues: list[Issue] = []
    corpus = profile_corpus(profile)

    skill_names = {normalize(s.name) for s in profile.skills}
    for s in resume.skills:
        if normalize(s) not in skill_names:
            issues.append(Issue("error", "skills", f"Competência “{s}” não existe no seu perfil."))

    experiences = {e.id: e for e in profile.experiences}
    for exp in resume.experiences:
        original = experiences.get(exp.id)
        if original is None:
            issues.append(Issue("error", "experiences", f"Experiência “{exp.id}” não existe no seu perfil."))
            continue
        known = {normalize(h).rstrip(".;") for h in original.highlights}
        for h in exp.highlights:
            if normalize(h).rstrip(".;") not in known:
                issues.append(Issue("error", "experiences", f"Item não encontrado em “{original.role}”: “{h[:80]}”."))

    project_ids = {p.id for p in profile.projects}
    for pid in resume.project_ids:
        if pid not in project_ids:
            issues.append(Issue("error", "projects", f"Projeto “{pid}” não existe no seu perfil."))

    issues += _check_free_text("headline", resume.headline, corpus, allowed)
    issues += _check_free_text("summary", resume.summary, corpus, allowed)
    return issues


_MENTIONS_JOB = re.compile(r"\b(vaga|cargo|posição|posicao|oportunidade|candidat\w*)\b", re.I)


def validate_cover_letter(
    profile: ProfileData,
    letter: TailoredCoverLetter,
    allowed: set[str] = frozenset(),
    title_terms: set[str] = frozenset(),
) -> list[Issue]:
    """O título da vaga pode aparecer no assunto, na saudação e em frases que falam da vaga
    ("candidato-me à vaga de Dev Python"); fora disso, continua sendo verificado."""
    corpus = profile_corpus(profile)
    with_title = allowed | title_terms
    issues = _check_free_text("cover_letter", f"{letter.subject}\n{letter.greeting}", corpus, with_title)
    for paragraph in [*letter.paragraphs, letter.closing]:
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            terms = with_title if _MENTIONS_JOB.search(sentence) else allowed
            issues += _check_free_text("cover_letter", sentence, corpus, terms)
    return issues


def _words(text: str | None) -> set[str]:
    return {w.casefold().strip(".,()") for w in (text or "").split() if w.strip(".,()")}


def allowed_job_terms(company: str | None) -> set[str]:
    """O nome da empresa pode ser citado na carta sem ser uma afirmação sobre a pessoa."""
    return _words(company)


def job_title_terms(title: str | None) -> set[str]:
    return _words(title)


def has_errors(issues: list[dict] | list[Issue]) -> bool:
    return any((i.severity if isinstance(i, Issue) else i.get("severity")) == "error" for i in issues)
