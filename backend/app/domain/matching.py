"""Análise de compatibilidade vaga × perfil sem IA (sempre disponível, custo zero).

Quando a IA está configurada, ela refina o resultado; esta análise continua
servindo de base e de fallback.
"""

from dataclasses import dataclass, field

from app.domain.text import find_spans
from app.schemas.profile import ProfileData

# Termos técnicos comuns reconhecidos em qualquer vaga. Não precisa ser exaustivo:
# as competências do próprio perfil e as palavras-chave dos perfis-alvo também entram.
TECH_TERMS = [
    # linguagens
    "python",
    "java",
    "javascript",
    "typescript",
    "c#",
    "c++",
    "go",
    "golang",
    "rust",
    "kotlin",
    "swift",
    "php",
    "ruby",
    "scala",
    "elixir",
    "dart",
    "r",
    "sql",
    "abap",
    # back-end
    ".net",
    "asp.net",
    "dotnet",
    "entity framework",
    "spring",
    "spring boot",
    "quarkus",
    "node.js",
    "nodejs",
    "express",
    "nestjs",
    "django",
    "fastapi",
    "flask",
    "laravel",
    "rails",
    "gin",
    "graphql",
    "grpc",
    "rest",
    "microsserviços",
    "microservices",
    "rabbitmq",
    "kafka",
    # front-end
    "react",
    "angular",
    "vue",
    "vue.js",
    "next.js",
    "nuxt",
    "svelte",
    "html",
    "css",
    "tailwind",
    "redux",
    "rxjs",
    "jquery",
    "flutter",
    "react native",
    # dados
    "postgresql",
    "postgres",
    "mysql",
    "sql server",
    "oracle",
    "mongodb",
    "redis",
    "elasticsearch",
    "power bi",
    "excel",
    "pandas",
    "spark",
    "airflow",
    "etl",
    # infra
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "terraform",
    "linux",
    "ci/cd",
    "github actions",
    "jenkins",
    "git",
    "azure devops",
    # práticas e outros
    "scrum",
    "kanban",
    "tdd",
    "clean architecture",
    "solid",
    "sap",
    "salesforce",
    "figma",
    "jira",
]

# Grafias equivalentes tratadas como a mesma competência.
SYNONYMS = {
    "golang": "go",
    "nodejs": "node.js",
    "node": "node.js",
    "dotnet": ".net",
    "asp.net core": "asp.net",
    "postgres": "postgresql",
    "vue.js": "vue",
    "vuejs": "vue",
    "reactjs": "react",
    "react.js": "react",
    "csharp": "c#",
    "ms sql": "sql server",
    "microservices": "microsserviços",
    "k8s": "kubernetes",
}


def canonical(term: str) -> str:
    t = term.strip().casefold()
    return SYNONYMS.get(t, t)


def find_terms(text: str, terms: list[str]) -> list[str]:
    """Termos presentes no texto, já canonizados e sem contagem dupla.

    Se um termo só aparece dentro de outro maior ("node" dentro de "node.js",
    "spring" dentro de "spring boot"), conta apenas o maior.
    """
    spans: dict[str, list[tuple[int, int]]] = {}
    for term in {t.strip() for t in terms if t.strip()}:
        found = find_spans(text, term)
        if found:
            spans[term] = found

    def covered(span: tuple[int, int], by: str) -> bool:
        return any(s <= span[0] and span[1] <= e and (e - s) > (span[1] - span[0]) for s, e in spans[by])

    result: list[str] = []
    for term, term_spans in spans.items():
        others = [o for o in spans if o != term]
        if any(not any(covered(sp, o) for o in others) for sp in term_spans):
            c = canonical(term)
            if c not in result:
                result.append(c)
    return sorted(result)


@dataclass
class RoleOption:
    id: int
    keywords: list[str]
    is_default: bool = False


@dataclass
class KeywordAnalysis:
    score: int
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    target_role_id: int | None = None


def profile_terms(profile: ProfileData) -> set[str]:
    terms = {canonical(s.name) for s in profile.skills}
    for p in profile.projects:
        terms.update(canonical(t) for t in p.technologies)
    return terms


def choose_role(text: str, roles: list[RoleOption]) -> int | None:
    best_id, best_hits = None, 0
    for role in roles:
        hits = len(find_terms(text, role.keywords))
        if hits > best_hits:
            best_id, best_hits = role.id, hits
    if best_id is None:
        default = next((r for r in roles if r.is_default), roles[0] if roles else None)
        best_id = default.id if default else None
    return best_id


def analyze(job_text: str, profile: ProfileData, roles: list[RoleOption]) -> KeywordAnalysis:
    vocabulary = TECH_TERMS + [s.name for s in profile.skills] + [k for r in roles for k in r.keywords]
    job_terms = find_terms(job_text, vocabulary)
    mine = profile_terms(profile)

    matched = [t for t in job_terms if t in mine]
    missing = [t for t in job_terms if t not in mine]
    score = round(100 * len(matched) / len(job_terms)) if job_terms else 0
    return KeywordAnalysis(score=score, matched=matched, missing=missing, target_role_id=choose_role(job_text, roles))
