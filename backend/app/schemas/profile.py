"""Perfil profissional: a fonte da verdade de tudo que pode aparecer num currículo.

Nada que não esteja aqui pode ser afirmado pela IA (ver app/domain/validation.py).
"""

import uuid

from pydantic import BaseModel, Field, field_validator


def _id() -> str:
    return uuid.uuid4().hex[:8]


class Link(BaseModel):
    label: str = Field(max_length=40)
    url: str = Field(max_length=300)


class Contact(BaseModel):
    name: str = Field("", max_length=120)
    email: str = Field("", max_length=254)
    phone: str = Field("", max_length=40)
    location: str = Field("", max_length=120)
    links: list[Link] = []


class Experience(BaseModel):
    id: str = Field(default_factory=_id)
    role: str = Field(max_length=120)
    company: str = Field(max_length=120)
    start: str = Field("", max_length=20, description="Livre: '06/2024', '2024'")
    end: str = Field("", max_length=20, description="Vazio quando atual")
    location: str = Field("", max_length=120)
    highlights: list[str] = []


class Education(BaseModel):
    id: str = Field(default_factory=_id)
    course: str = Field(max_length=160)
    institution: str = Field(max_length=160)
    start: str = Field("", max_length=20)
    end: str = Field("", max_length=40)


class Skill(BaseModel):
    name: str = Field(max_length=80)
    category: str = Field("", max_length=60)
    level: str = Field("", max_length=30)


class Project(BaseModel):
    id: str = Field(default_factory=_id)
    name: str = Field(max_length=120)
    description: str = Field("", max_length=600)
    url: str = Field("", max_length=300)
    technologies: list[str] = []


class Language(BaseModel):
    name: str = Field(max_length=40)
    level: str = Field("", max_length=120)


class Certification(BaseModel):
    name: str = Field(max_length=160)
    issuer: str = Field("", max_length=120)
    year: str = Field("", max_length=10)


class ProfileData(BaseModel):
    contact: Contact = Contact()
    headline: str = Field("", max_length=160)
    summary: str = Field("", max_length=2000)
    availability: str = Field("", max_length=200)
    experiences: list[Experience] = []
    education: list[Education] = []
    skills: list[Skill] = []
    projects: list[Project] = []
    languages: list[Language] = []
    certifications: list[Certification] = []

    @field_validator("skills")
    @classmethod
    def _unique_skills(cls, skills: list[Skill]) -> list[Skill]:
        seen: set[str] = set()
        out = []
        for s in skills:
            key = s.name.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(s)
        return out

    def is_empty(self) -> bool:
        return not (self.contact.name or self.experiences or self.skills)
