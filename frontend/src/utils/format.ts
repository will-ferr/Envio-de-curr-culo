import type { ApplicationStatus } from '@/types/api'

const dateFmt = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short' })
const dateTimeFmt = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : dateFmt.format(d)
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : dateTimeFmt.format(d)
}

export function relativeDays(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return '—'
  const days = Math.floor((now.getTime() - new Date(iso).getTime()) / 86_400_000)
  if (days <= 0) return 'hoje'
  if (days === 1) return 'ontem'
  return `há ${days} dias`
}

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  draft: 'Rascunho',
  approved: 'Aprovada',
  sent: 'Enviada',
  interview: 'Entrevista',
  offer: 'Proposta',
  rejected: 'Recusada',
  withdrawn: 'Desistência',
}

export const ORIGIN_LABELS = { manual: 'Texto colado', url: 'Link', rss: 'RSS', email: 'E-mail' } as const

export function formatTokens(n: number): string {
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)} mi` : n >= 1000 ? `${Math.round(n / 1000)} mil` : String(n)
}
