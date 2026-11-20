<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { BellRing, Check, CircleDashed, KeyRound, Mail, Target, UserRound } from 'lucide-vue-next'
import BaseCard from '@/components/ui/BaseCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import ScoreBadge from '@/components/ui/ScoreBadge.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useAsync } from '@/composables/useAsync'
import { settingsApi, systemApi } from '@/services/api'
import { STATUS_LABELS, relativeDays } from '@/utils/format'
import type { ApplicationStatus } from '@/types/api'

const dash = useAsync(() => systemApi.dashboard())
const check = useAsync(() => settingsApi.checklist())
onMounted(() => {
  void dash.execute()
  void check.execute()
})

const steps = computed(() => {
  const c = check.data.value
  if (!c) return []
  return [
    { done: c.ai, label: 'Cadastrar a chave de IA', hint: 'Necessária para importar o currículo e adaptar documentos.', to: '/configuracoes?aba=ia', icon: KeyRound },
    { done: c.profile, label: 'Preencher ou importar seu perfil', hint: 'É a fonte da verdade de tudo que vai no currículo.', to: '/perfil', icon: UserRound },
    { done: c.target_roles, label: 'Criar um perfil-alvo', hint: 'O tipo de vaga que você procura (ex.: Back-end Python).', to: '/perfis-alvo', icon: Target },
    { done: c.telegram, label: 'Conectar o Telegram (opcional)', hint: 'Receba vagas compatíveis e aprove pelo celular.', to: '/configuracoes?aba=telegram', icon: BellRing },
    { done: c.smtp, label: 'Configurar e-mail (opcional)', hint: 'Para enviar candidaturas quando a vaga pede e-mail.', to: '/configuracoes?aba=email', icon: Mail },
  ]
})
const pending = computed(() => steps.value.filter((s) => !s.done).length)

const funnelOrder: ApplicationStatus[] = ['approved', 'sent', 'interview', 'offer', 'rejected']
</script>

<template>
  <div class="space-y-6">
    <BaseCard v-if="check.data.value && pending > 0" title="Primeiros passos" :subtitle="`${steps.length - pending} de ${steps.length} concluídos`">
      <ul class="-my-2 divide-y divide-line">
        <li v-for="s in steps" :key="s.label">
          <RouterLink :to="s.to" class="flex items-center gap-3 py-3 hover:opacity-80">
            <Check v-if="s.done" class="size-5 shrink-0 text-success" aria-label="Concluído" />
            <CircleDashed v-else class="size-5 shrink-0 text-muted" aria-label="Pendente" />
            <div class="min-w-0">
              <p class="text-sm font-medium" :class="{ 'text-muted line-through': s.done }">{{ s.label }}</p>
              <p v-if="!s.done" class="text-xs text-muted">{{ s.hint }}</p>
            </div>
            <component :is="s.icon" class="ml-auto size-4 shrink-0 text-muted" aria-hidden="true" />
          </RouterLink>
        </li>
      </ul>
    </BaseCard>

    <div v-if="!dash.data.value && !dash.error.value" class="grid gap-4 sm:grid-cols-3">
      <SkeletonBlock v-for="i in 3" :key="i" class="h-24" />
    </div>
    <BaseCard v-else-if="dash.error.value && !dash.data.value">
      <ErrorState :error="dash.error.value" :retrying="dash.loading.value" @retry="dash.execute()" />
    </BaseCard>

    <template v-else-if="dash.data.value">
      <div class="grid gap-4 sm:grid-cols-3">
        <BaseCard>
          <p class="text-sm text-muted">Vagas na última semana</p>
          <p class="mt-1 text-3xl font-semibold">{{ dash.data.value.jobs_last_7_days }}</p>
        </BaseCard>
        <BaseCard>
          <p class="text-sm text-muted">Compatibilidade média</p>
          <p class="mt-1 text-3xl font-semibold">
            {{ dash.data.value.average_score === null ? '—' : `${dash.data.value.average_score}%` }}
          </p>
        </BaseCard>
        <BaseCard>
          <p class="text-sm text-muted">Taxa de resposta</p>
          <p class="mt-1 text-3xl font-semibold">
            {{ dash.data.value.response_rate === null ? '—' : `${dash.data.value.response_rate}%` }}
          </p>
          <p class="mt-1 text-xs text-muted">Entrevista, proposta ou recusa ÷ enviadas</p>
        </BaseCard>
      </div>

      <BaseCard title="Funil de candidaturas">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <RouterLink
            v-for="s in funnelOrder"
            :key="s"
            to="/candidaturas"
            class="rounded-xl border border-line p-3 text-center hover:bg-surface-2"
          >
            <p class="text-2xl font-semibold">{{ dash.data.value.funnel[s] }}</p>
            <p class="text-xs text-muted">{{ STATUS_LABELS[s] }}</p>
          </RouterLink>
        </div>
      </BaseCard>

      <div class="grid gap-6 lg:grid-cols-2">
        <BaseCard title="Para revisar" subtitle="Vagas analisadas, mais compatíveis primeiro">
          <EmptyState
            v-if="!dash.data.value.to_review.length"
            title="Nenhuma vaga para revisar"
            description="Adicione vagas por link, texto ou fontes RSS."
          >
            <RouterLink to="/vagas" class="text-sm font-medium text-brand hover:underline">Ir para vagas</RouterLink>
          </EmptyState>
          <ul v-else class="-my-2 divide-y divide-line">
            <li v-for="j in dash.data.value.to_review" :key="j.id">
              <RouterLink :to="`/vagas/${j.id}`" class="flex items-center gap-3 py-2.5 hover:opacity-80">
                <ScoreBadge :score="j.score" />
                <div class="min-w-0">
                  <p class="truncate text-sm font-medium">{{ j.title }}</p>
                  <p class="truncate text-xs text-muted">{{ j.company || 'Empresa não informada' }}</p>
                </div>
              </RouterLink>
            </li>
          </ul>
        </BaseCard>

        <BaseCard title="Sem resposta há mais de 10 dias" subtitle="Bom momento para um follow-up">
          <EmptyState v-if="!dash.data.value.followups.length" title="Nenhum follow-up pendente" />
          <ul v-else class="-my-2 divide-y divide-line">
            <li v-for="f in dash.data.value.followups" :key="f.application_id">
              <RouterLink :to="`/vagas/${f.job_id}`" class="flex items-center justify-between gap-3 py-2.5 hover:opacity-80">
                <div class="min-w-0">
                  <p class="truncate text-sm font-medium">{{ f.title }}</p>
                  <p class="truncate text-xs text-muted">{{ f.company || '—' }}</p>
                </div>
                <span class="shrink-0 text-xs text-muted">{{ relativeDays(f.sent_at) }}</span>
              </RouterLink>
            </li>
          </ul>
        </BaseCard>
      </div>

      <p v-if="dash.data.value.failed_tasks" class="text-sm text-danger">
        {{ dash.data.value.failed_tasks }} tarefa(s) falharam nos últimos 7 dias. Veja os logs do worker
        (<code>docker compose logs worker</code>).
      </p>
    </template>
  </div>
</template>
