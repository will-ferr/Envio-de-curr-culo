// Contratos da API (ver /api/docs).

export interface ApiFieldError {
  field: string
  message: string
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    request_id?: string
    fields?: ApiFieldError[]
    details?: { fields?: ApiFieldError[] } & Record<string, unknown>
  }
}

// ---------- perfil ----------
export interface Link {
  label: string
  url: string
}
export interface Experience {
  id: string
  role: string
  company: string
  start: string
  end: string
  location: string
  highlights: string[]
}
export interface Education {
  id: string
  course: string
  institution: string
  start: string
  end: string
}
export interface Skill {
  name: string
  category: string
  level: string
}
export interface Project {
  id: string
  name: string
  description: string
  url: string
  technologies: string[]
}
export interface Language {
  name: string
  level: string
}
export interface Certification {
  name: string
  issuer: string
  year: string
}
export interface Profile {
  contact: { name: string; email: string; phone: string; location: string; links: Link[] }
  headline: string
  summary: string
  availability: string
  experiences: Experience[]
  education: Education[]
  skills: Skill[]
  projects: Project[]
  languages: Language[]
  certifications: Certification[]
}

export interface TargetRole {
  id: number
  name: string
  headline: string
  summary: string
  skills_focus: string[]
  keywords: string[]
  template: string
  is_default: boolean
}

// ---------- vagas e documentos ----------
export type JobStatus = 'new' | 'analyzed' | 'discarded'
export type ApplicationStatus = 'draft' | 'approved' | 'sent' | 'interview' | 'offer' | 'rejected' | 'withdrawn'

export interface JobSummary {
  id: number
  title: string
  company: string | null
  location: string | null
  url: string | null
  origin: 'manual' | 'url' | 'rss' | 'email'
  status: JobStatus
  created_at: string
  score: number | null
  used_ai: boolean | null
  application_status: ApplicationStatus | null
}

export interface Issue {
  severity: 'error' | 'warning'
  field: string
  message: string
}

export interface ResumeContent {
  headline: string
  summary: string
  skills: string[]
  experiences: { id: string; highlights: string[] }[]
  project_ids: string[]
}

export interface LetterContent {
  subject: string
  greeting: string
  paragraphs: string[]
  closing: string
}

export interface DocumentOut {
  id: number
  kind: 'resume' | 'cover_letter'
  template: string
  content: ResumeContent | LetterContent
  issues: Issue[]
  used_ai: boolean
  has_pdf: boolean
  target_role_id: number | null
  updated_at: string
}

export interface ApplicationEventOut {
  from: ApplicationStatus | null
  to: ApplicationStatus
  actor: 'owner' | 'telegram' | 'system'
  note: string
  at: string
}

export interface ApplicationOut {
  id: number
  status: ApplicationStatus
  status_label: string
  sent_via: 'email' | 'manual' | null
  sent_at: string | null
  notes: string
  resume_document_id: number | null
  cover_document_id: number | null
  events: ApplicationEventOut[]
  job?: JobSummary
}

export interface JobDetail extends JobSummary {
  description: string
  contact_email: string | null
  analysis: {
    score: number
    keyword_score: number
    matched: string[]
    missing: string[]
    summary: string
    seniority: string | null
    target_role_id: number | null
    used_ai: boolean
    updated_at: string
  } | null
  documents: DocumentOut[]
  application: ApplicationOut | null
}

export interface TaskOut {
  id: number
  kind: string
  status: 'pending' | 'running' | 'done' | 'failed'
  attempts: number
  error: string | null
  result: Record<string, unknown> | null
}

export interface Dashboard {
  funnel: Record<ApplicationStatus, number>
  jobs_last_7_days: number
  average_score: number | null
  response_rate: number | null
  sent_today: number
  followups: { application_id: number; job_id: number; title: string; company: string | null; sent_at: string }[]
  to_review: { id: number; title: string; company: string | null; score: number }[]
  failed_tasks: number
}

export interface Checklist {
  ai: boolean
  profile: boolean
  target_roles: boolean
  telegram: boolean
  smtp: boolean
}

export interface Secret {
  configured: boolean
}

export interface SettingsOut {
  ai: { api_key: Secret; model: string; effort: string; models: Record<string, string>; efforts: string[] }
  telegram: { bot_token: Secret; linked: boolean; pair_code: string | null }
  smtp: {
    host: string | null
    port: number
    username: string | null
    password: Secret
    security: 'starttls' | 'ssl' | 'none'
    from_email: string | null
    from_name: string | null
  }
  imap: {
    host: string | null
    port: number
    username: string | null
    password: Secret
    folder: string
    enabled: boolean
    sender_filter: string
  }
  prefs: { daily_send_limit: number; min_score_notify: number; default_template: string; templates: Record<string, string> }
}

export interface Source {
  id: number
  name: string
  url: string
  enabled: boolean
  last_checked_at: string | null
  last_error: string | null
}
