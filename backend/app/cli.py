"""Comandos de manutenção.

    python -m app.cli importar-perfil caminho/perfil.json
    python -m app.cli importar-legado caminho/da/pasta   (base.yaml + stacks.yaml + frontends.yaml)

Dentro do Docker:
    docker compose run --rm -v "$PWD/dados:/importar:ro" api python -m app.cli importar-legado /importar
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from app.db import session_factory
from app.models import TargetRole
from app.schemas.profile import Contact, Education, Experience, Language, Link, ProfileData, Project, Skill
from app.services import profile as profile_svc

GENERIC_LABELS = {
    "ferramentas",
    "web",
    "banco de dados",
    "controle de versão",
    "sistemas corporativos",
    "inglês técnico",
}


def skills_from_sentence(sentence: str) -> list[str]:
    """'ASP.NET Core: APIs RESTful, middleware' → ['ASP.NET Core', 'APIs RESTful', 'middleware']."""
    label, _, rest = sentence.partition(":")
    out = []
    if rest and label.strip().lower() not in GENERIC_LABELS and len(label) <= 30:
        out.append(label.strip())
    for part in re.split(r",|;|\be\b", rest or sentence):
        part = part.strip(" .")
        if 1 < len(part) <= 40:
            out.append(part)
    return out


def legacy_to_profile(base: dict, stacks: dict, fronts: dict) -> tuple[ProfileData, list[dict]]:
    skills: list[str] = []
    for c in base.get("competencias_comuns", []):
        skills += skills_from_sentence(c)
    for s in stacks.values():
        for c in s.get("competencias", []):
            skills += skills_from_sentence(c)
    for key, f in fronts.items():
        if key != "comum" and isinstance(f, dict):
            skills += skills_from_sentence(f.get("competencia", "").replace("(em estudo)", ""))
    if isinstance(fronts.get("comum"), str):
        skills += skills_from_sentence(fronts["comum"])

    links = [
        Link(label=label, url=base[k]) for k, label in (("linkedin", "LinkedIn"), ("github", "GitHub")) if base.get(k)
    ]
    profile = ProfileData(
        contact=Contact(
            name=base.get("nome", ""),
            email=base.get("email", ""),
            phone=str(base.get("telefone", "")),
            location=base.get("cidade", ""),
            links=links,
        ),
        availability=base.get("disponibilidade", ""),
        experiences=[
            Experience(
                role=e["cargo"],
                company=e["empresa"],
                start=str(e.get("periodo", "")).split("–")[0].strip(),
                end=""
                if "atual" in str(e.get("periodo", "")).lower()
                else str(e.get("periodo", "")).split("–")[-1].strip(),
                highlights=e.get("itens", []),
            )
            for e in base.get("experiencia", [])
        ],
        education=[
            Education(course=f["curso"], institution=f["instituicao"], end=str(f.get("periodo", "")))
            for f in base.get("formacao", [])
        ],
        projects=[
            Project(name=p["titulo"], description=p.get("descricao", ""), technologies=p.get("tags", []))
            for p in base.get("projetos", [])
        ],
        skills=[Skill(name=s) for s in skills],
        languages=[Language(name=i["idioma"], level=i.get("nivel", "")) for i in base.get("idiomas", [])],
    )
    default_front = next((f["nome"] for k, f in fronts.items() if k != "comum" and isinstance(f, dict)), "front-end")
    roles = [
        {
            "name": f"Full Stack {s.get('nome', key)}",
            "headline": s.get("titulo", ""),
            "summary": " ".join(str(s.get("resumo", "")).replace("{front}", default_front).split()),
            "skills_focus": [x for c in s.get("competencias", []) for x in skills_from_sentence(c)][:8],
            "keywords": s.get("palavras_chave", []),
        }
        for key, s in stacks.items()
    ]
    return profile, roles


def _save(profile: ProfileData, roles: list[dict]) -> None:
    with session_factory()() as db:
        profile_svc.save_profile(db, profile)
        existing = {r.name.casefold() for r in profile_svc.list_roles(db)}
        for i, r in enumerate(roles):
            if r["name"].casefold() not in existing:
                db.add(TargetRole(**r, is_default=(i == 0 and not existing)))
        db.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("importar-perfil", help="Importa um perfil em JSON (formato do export ou do exemplo)")
    p1.add_argument("arquivo", type=Path)
    p2 = sub.add_parser("importar-legado", help="Importa base.yaml/stacks.yaml/frontends.yaml do gerador antigo")
    p2.add_argument("pasta", type=Path)
    args = parser.parse_args(argv)

    if args.cmd == "importar-perfil":
        data = json.loads(args.arquivo.read_text(encoding="utf-8"))
        profile = ProfileData.model_validate(data.get("profile", data))
        roles = data.get("target_roles", [])
    else:
        read = lambda n: yaml.safe_load((args.pasta / n).read_text(encoding="utf-8")) or {}  # noqa: E731
        profile, roles = legacy_to_profile(read("base.yaml"), read("stacks.yaml"), read("frontends.yaml"))

    _save(profile, roles)
    print(
        f"Perfil importado: {len(profile.experiences)} experiências, {len(profile.skills)} competências, "
        f"{len(roles)} perfis-alvo. Revise tudo em Perfil antes de gerar currículos."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
