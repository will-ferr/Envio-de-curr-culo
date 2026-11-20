"""Perfil (fonte da verdade) e perfis-alvo."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Profile, TargetRole
from app.schemas.ai import ExtractedProfile
from app.schemas.profile import (
    Certification,
    Contact,
    Education,
    Experience,
    Language,
    Link,
    ProfileData,
    Project,
    Skill,
)


def get_profile(db: Session) -> ProfileData:
    row = db.get(Profile, 1)
    return ProfileData.model_validate(row.data) if row else ProfileData()


def save_profile(db: Session, data: ProfileData) -> ProfileData:
    row = db.get(Profile, 1)
    payload = data.model_dump(mode="json")
    if row is None:
        db.add(Profile(id=1, data=payload))
    else:
        row.data = payload
    db.flush()
    return data


def _label_for(url: str) -> str:
    low = url.lower()
    for key, label in (("linkedin", "LinkedIn"), ("github", "GitHub"), ("gitlab", "GitLab")):
        if key in low:
            return label
    return "Site"


def from_extracted(x: ExtractedProfile) -> ProfileData:
    """Converte a extração da IA no perfil, gerando os ids (a IA nunca escolhe ids)."""
    return ProfileData(
        contact=Contact(
            name=x.name,
            email=x.email,
            phone=x.phone,
            location=x.location,
            links=[Link(label=_label_for(u), url=u) for u in x.links if u],
        ),
        headline=x.headline,
        summary=x.summary,
        experiences=[
            Experience(
                role=e.role,
                company=e.company,
                start=e.start,
                end=e.end,
                location=e.location,
                highlights=[h for h in e.highlights if h.strip()],
            )
            for e in x.experiences
        ],
        education=[
            Education(course=e.course, institution=e.institution, start=e.start, end=e.end) for e in x.education
        ],
        skills=[Skill(name=s.name, category=s.category) for s in x.skills if s.name.strip()],
        projects=[
            Project(name=p.name, description=p.description, url=p.url, technologies=p.technologies) for p in x.projects
        ],
        languages=[Language(name=lang.name, level=lang.level) for lang in x.languages],
        certifications=[Certification(name=c) for c in x.certifications if c.strip()],
    )


def list_roles(db: Session) -> list[TargetRole]:
    return list(db.scalars(select(TargetRole).order_by(TargetRole.is_default.desc(), TargetRole.name)))


def set_default_role(db: Session, role: TargetRole) -> None:
    for r in list_roles(db):
        r.is_default = r.id == role.id
