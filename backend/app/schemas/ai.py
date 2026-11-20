"""Formatos de saída exigidos da IA (structured outputs).

Os modelos de extração de perfil não têm `id`: a IA não escolhe identificadores,
eles são gerados ao converter para ProfileData.
"""

from pydantic import BaseModel, Field


# ---------- importação de currículo ----------
class ExtractedExperience(BaseModel):
    role: str
    company: str
    start: str
    end: str
    location: str
    highlights: list[str]


class ExtractedEducation(BaseModel):
    course: str
    institution: str
    start: str
    end: str


class ExtractedProject(BaseModel):
    name: str
    description: str
    url: str
    technologies: list[str]


class ExtractedSkill(BaseModel):
    name: str
    category: str


class ExtractedLanguage(BaseModel):
    name: str
    level: str


class ExtractedProfile(BaseModel):
    name: str
    email: str
    phone: str
    location: str
    links: list[str]
    headline: str
    summary: str
    experiences: list[ExtractedExperience]
    education: list[ExtractedEducation]
    skills: list[ExtractedSkill]
    projects: list[ExtractedProject]
    languages: list[ExtractedLanguage]
    certifications: list[str]


# ---------- análise de vaga ----------
class JobAnalysisResult(BaseModel):
    title: str = Field(description="Título da vaga")
    company: str = Field(description="Empresa, ou vazio se não informada")
    location: str
    seniority: str = Field(description="estágio, júnior, pleno, sênior ou vazio")
    contact_email: str = Field(description="E-mail para envio de currículo, se a vaga pedir; senão vazio")
    score: int = Field(description="Compatibilidade de 0 a 100 entre o perfil e a vaga")
    summary: str = Field(description="2 a 3 frases sobre a compatibilidade, em português")
    matched: list[str] = Field(description="Requisitos da vaga que o perfil atende")
    missing: list[str] = Field(description="Requisitos da vaga que o perfil não atende")
    target_role_id: int = Field(description="id do perfil-alvo mais adequado, ou 0")


# ---------- adaptação de documentos ----------
class TailoredExperience(BaseModel):
    id: str = Field(description="id de uma experiência existente no perfil")
    highlights: list[str] = Field(description="Itens copiados literalmente do perfil, reordenados")


class TailoredResume(BaseModel):
    headline: str
    summary: str
    skills: list[str] = Field(description="Nomes de competências existentes no perfil, mais relevantes primeiro")
    experiences: list[TailoredExperience]
    project_ids: list[str]


class TailoredCoverLetter(BaseModel):
    subject: str
    greeting: str
    paragraphs: list[str]
    closing: str


class TailoredDocuments(BaseModel):
    resume: TailoredResume
    cover_letter: TailoredCoverLetter


# ---------- alertas por e-mail ----------
class ExtractedJobLink(BaseModel):
    title: str
    company: str
    location: str
    url: str
    snippet: str


class ExtractedJobList(BaseModel):
    jobs: list[ExtractedJobLink]
