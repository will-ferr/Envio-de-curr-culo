import { http } from './http'
import type {
  ApplicationOut,
  ApplicationStatus,
  Checklist,
  Dashboard,
  DocumentOut,
  JobDetail,
  JobSummary,
  Profile,
  SettingsOut,
  Source,
  TargetRole,
  TaskOut,
} from '@/types/api'

const data = <T>(p: Promise<{ data: T }>) => p.then((r) => r.data)

export const authApi = {
  setupStatus: () => data<{ needs_owner: boolean }>(http.get('/setup/status')),
  createOwner: (body: { name: string; email: string; password: string }) => data(http.post('/setup/owner', body)),
  login: (email: string, password: string) =>
    data<{ name: string; email: string }>(http.post('/auth/login', { email, password })),
  logout: () => data(http.post('/auth/logout')),
  me: () => data<{ name: string; email: string }>(http.get('/auth/me')),
  changePassword: (current_password: string, new_password: string) =>
    data(http.post('/auth/password', { current_password, new_password })),
}

export const profileApi = {
  get: () => data<Profile>(http.get('/profile')),
  save: (p: Profile) => data<Profile>(http.put('/profile', p)),
  importPdf: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return data<{ task_id: number }>(http.post('/profile/import', form))
  },
  roles: () => data<TargetRole[]>(http.get('/target-roles')),
  createRole: (r: Omit<TargetRole, 'id'>) => data<TargetRole>(http.post('/target-roles', r)),
  updateRole: (id: number, r: Omit<TargetRole, 'id'>) => data<TargetRole>(http.put(`/target-roles/${id}`, r)),
  deleteRole: (id: number) => data(http.delete(`/target-roles/${id}`)),
  templates: () => data<{ id: string; name: string }[]>(http.get('/templates')),
}

export const jobsApi = {
  list: (params: { status?: string; q?: string; min_score?: number } = {}) =>
    data<JobSummary[]>(http.get('/jobs', { params })),
  create: (body: { url?: string; title?: string; company?: string; description?: string }) =>
    data<{ job: JobDetail; task_id: number }>(http.post('/jobs', body)),
  get: (id: number, signal?: AbortSignal) => data<JobDetail>(http.get(`/jobs/${id}`, { signal })),
  patch: (id: number, body: Partial<Pick<JobDetail, 'title' | 'company' | 'location' | 'contact_email' | 'status'>>) =>
    data<JobDetail>(http.patch(`/jobs/${id}`, body)),
  remove: (id: number) => data(http.delete(`/jobs/${id}`)),
  analyze: (id: number) => data<{ task_id: number }>(http.post(`/jobs/${id}/analyze`)),
  generate: (id: number, body: { target_role_id?: number | null; template?: string | null }) =>
    data<{ task_id: number }>(http.post(`/jobs/${id}/documents`, body)),
}

export const documentsApi = {
  update: (id: number, content: unknown, template?: string) =>
    data<DocumentOut & { task_id: number }>(http.put(`/documents/${id}`, { content, template })),
  preview: (id: number) => data<string>(http.get(`/documents/${id}/preview`, { responseType: 'text' })),
  pdfUrl: (id: number) => `/api/documents/${id}/pdf`,
}

export const applicationsApi = {
  list: () => data<ApplicationOut[]>(http.get('/applications')),
  approve: (job_id: number) => data<ApplicationOut>(http.post('/applications', { job_id })),
  setStatus: (id: number, status: Exclude<ApplicationStatus, 'draft' | 'approved'>, note = '') =>
    data<ApplicationOut>(http.post(`/applications/${id}/status`, { status, note })),
  notes: (id: number, notes: string) => data<ApplicationOut>(http.patch(`/applications/${id}`, { notes })),
  send: (id: number) => data<{ task_id: number }>(http.post(`/applications/${id}/send`)),
}

export const settingsApi = {
  get: () => data<SettingsOut>(http.get('/settings')),
  checklist: () => data<Checklist>(http.get('/setup/checklist')),
  saveAi: (body: { api_key?: string | null; model: string; effort: string }) => data(http.put('/settings/ai', body)),
  testAi: () => data(http.post('/settings/ai/test')),
  deleteAiKey: () => data(http.delete('/settings/ai/key')),
  saveTelegram: (bot_token: string) =>
    data<{ bot_username: string; pair_code: string }>(http.put('/settings/telegram', { bot_token })),
  newPairCode: () => data<{ pair_code: string }>(http.post('/settings/telegram/pair')),
  testTelegram: () => data(http.post('/settings/telegram/test')),
  deleteTelegram: () => data(http.delete('/settings/telegram')),
  saveSmtp: (body: Record<string, unknown>) => data(http.put('/settings/smtp', body)),
  testSmtp: () => data(http.post('/settings/smtp/test')),
  saveImap: (body: Record<string, unknown>) => data(http.put('/settings/imap', body)),
  savePrefs: (body: { daily_send_limit: number; min_score_notify: number; default_template: string }) =>
    data(http.put('/settings/prefs', body)),
  sources: () => data<Source[]>(http.get('/settings/sources')),
  createSource: (body: { name: string; url: string; enabled: boolean }) =>
    data<Source>(http.post('/settings/sources', body)),
  updateSource: (id: number, body: { name: string; url: string; enabled: boolean }) =>
    data<Source>(http.put(`/settings/sources/${id}`, body)),
  deleteSource: (id: number) => data(http.delete(`/settings/sources/${id}`)),
  pollNow: () => data<{ task_id: number }>(http.post('/settings/sources/poll')),
  aiUsage: () =>
    data<{ items: { operation: string; model: string; calls: number; input_tokens: number; output_tokens: number }[] }>(
      http.get('/ai-usage'),
    ),
  exportUrl: '/api/data/export',
  wipe: () => data(http.post('/data/wipe', { confirm: 'APAGAR' })),
}

export const systemApi = {
  dashboard: () => data<Dashboard>(http.get('/dashboard')),
  task: (id: number) => data<TaskOut>(http.get(`/tasks/${id}`)),
}
