<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { KanbanSquare } from 'lucide-vue-next'
import BaseCard from '@/components/ui/BaseCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useAsync } from '@/composables/useAsync'
import { applicationsApi } from '@/services/api'
import { useToastStore } from '@/stores/toast'
import type { ApplicationOut, ApplicationStatus } from '@/types/api'
import { toApiError } from '@/utils/apiError'
import { STATUS_LABELS, relativeDays } from '@/utils/format'

const toast = useToastStore()
const list = useAsync(() => applicationsApi.list(), { keepDataOnError: true })
onMounted(() => list.execute())

const columns: { status: ApplicationStatus; hint: string }[] = [
  { status: 'approved', hint: 'Prontas para enviar' },
  { status: 'sent', hint: 'Aguardando resposta' },
  { status: 'interview', hint: 'Em processo' },
  { status: 'offer', hint: 'Proposta recebida' },
  { status: 'rejected', hint: 'Encerradas' },
]

/** Próximos passos válidos a partir de cada status (espelha as regras do servidor). */
const NEXT: Partial<Record<ApplicationStatus, Exclude<ApplicationStatus, 'draft' | 'approved'>[]>> = {
  approved: ['sent', 'withdrawn'],
  sent: ['interview', 'rejected', 'withdrawn'],
  interview: ['offer', 'rejected', 'withdrawn'],
  offer: ['withdrawn'],
}

const byStatus = computed(() => {
  const groups: Record<string, ApplicationOut[]> = {}
  for (const a of list.data.value ?? []) (groups[a.status] ??= []).push(a)
  return groups
})
const withdrawn = computed(() => byStatus.value.withdrawn ?? [])

async function move(a: ApplicationOut, status: Exclude<ApplicationStatus, 'draft' | 'approved'>) {
  try {
    await applicationsApi.setStatus(a.id, status)
    toast.success(`Movida para “${STATUS_LABELS[status]}”`)
    await list.execute()
  } catch (e) {
    toast.error('Não foi possível mover', toApiError(e).message)
  }
}
</script>

<template>
  <div class="space-y-4">
    <div v-if="!list.data.value && !list.error.value" class="grid gap-4 lg:grid-cols-5">
      <SkeletonBlock v-for="i in 5" :key="i" class="h-48" />
    </div>
    <BaseCard v-else-if="list.error.value && !list.data.value">
      <ErrorState :error="list.error.value" :retrying="list.loading.value" @retry="list.execute()" />
    </BaseCard>
    <BaseCard v-else-if="list.data.value && !list.data.value.length">
      <EmptyState
        :icon="KanbanSquare"
        title="Nenhuma candidatura ainda"
        description="Gere o currículo de uma vaga e aprove para ela aparecer aqui."
      >
        <RouterLink to="/vagas" class="text-sm font-medium text-brand hover:underline">Ver vagas</RouterLink>
      </EmptyState>
    </BaseCard>

    <template v-else>
      <!-- No celular, as colunas viram uma rolagem horizontal. -->
      <div class="-mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-2 lg:mx-0 lg:grid lg:grid-cols-5 lg:overflow-visible lg:px-0">
        <section
          v-for="col in columns"
          :key="col.status"
          class="w-72 shrink-0 snap-start rounded-xl border border-line bg-surface-2/50 p-3 lg:w-auto"
          :aria-label="STATUS_LABELS[col.status]"
        >
          <header class="mb-3 flex items-baseline justify-between">
            <h2 class="text-sm font-semibold">{{ STATUS_LABELS[col.status] }}</h2>
            <span class="text-xs text-muted">{{ byStatus[col.status]?.length ?? 0 }}</span>
          </header>
          <p v-if="!byStatus[col.status]?.length" class="py-6 text-center text-xs text-muted">{{ col.hint }}</p>
          <ul class="space-y-2">
            <li v-for="a in byStatus[col.status] ?? []" :key="a.id" class="rounded-lg border border-line bg-surface p-3 shadow-sm">
              <RouterLink :to="`/vagas/${a.job?.id}`" class="block hover:opacity-80">
                <p class="text-sm font-medium">{{ a.job?.title }}</p>
                <p class="text-xs text-muted">{{ a.job?.company || '—' }}</p>
              </RouterLink>
              <p v-if="a.sent_at" class="mt-1 text-xs text-muted">Enviada {{ relativeDays(a.sent_at) }}</p>
              <label v-if="NEXT[a.status]" class="mt-2 block">
                <span class="sr-only">Mover candidatura</span>
                <select
                  class="w-full rounded-md border border-line bg-surface px-2 py-1 text-xs"
                  @change="move(a, ($event.target as HTMLSelectElement).value as never)"
                >
                  <option value="" selected disabled>Mover para…</option>
                  <option v-for="s in NEXT[a.status]" :key="s" :value="s">{{ STATUS_LABELS[s] }}</option>
                </select>
              </label>
            </li>
          </ul>
        </section>
      </div>
      <p v-if="withdrawn.length" class="text-xs text-muted">{{ withdrawn.length }} candidatura(s) com desistência.</p>
    </template>
  </div>
</template>
