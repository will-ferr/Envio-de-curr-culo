<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { BriefcaseBusiness, Link2, Plus, Search } from 'lucide-vue-next'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import FormField from '@/components/ui/FormField.vue'
import ScoreBadge from '@/components/ui/ScoreBadge.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { useAsync } from '@/composables/useAsync'
import { jobsApi } from '@/services/api'
import { useToastStore } from '@/stores/toast'
import { ORIGIN_LABELS, STATUS_LABELS, relativeDays } from '@/utils/format'
import { toApiError } from '@/utils/apiError'

const router = useRouter()
const toast = useToastStore()
const filters = reactive({ q: '', status: 'active', minScore: '' })
const list = useAsync(() =>
  jobsApi.list({
    status: filters.status || undefined,
    q: filters.q || undefined,
    min_score: filters.minScore ? Number(filters.minScore) : undefined,
  }),
)
onMounted(() => list.execute())

// Busca com pequena espera para não disparar uma requisição por tecla.
let debounce: ReturnType<typeof setTimeout> | undefined
watch(filters, () => {
  clearTimeout(debounce)
  debounce = setTimeout(() => list.execute(), 300)
})

const modal = ref(false)
const mode = ref<'url' | 'text'>('url')
const draft = ref({ url: '', title: '', company: '', description: '' })
const formError = ref('')
const saving = ref(false)

function openModal() {
  draft.value = { url: '', title: '', company: '', description: '' }
  formError.value = ''
  modal.value = true
}

async function save() {
  formError.value = ''
  saving.value = true
  try {
    const body =
      mode.value === 'url'
        ? { url: draft.value.url.trim() }
        : { title: draft.value.title, company: draft.value.company || undefined, description: draft.value.description }
    const { job } = await jobsApi.create(body)
    modal.value = false
    toast.success('Vaga adicionada', 'A análise de compatibilidade já começou.')
    router.push(`/vagas/${job.id}`)
  } catch (e) {
    const err = toApiError(e)
    if (err.code === 'JOB_DUPLICATE' && typeof err.details.job_id === 'number') {
      modal.value = false
      toast.info('Essa vaga já estava na sua lista')
      router.push(`/vagas/${err.details.job_id}`)
      return
    }
    formError.value = err.fields[0]?.message ?? err.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-end">
      <div class="relative flex-1">
        <Search class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
        <label class="sr-only" for="busca">Buscar vagas</label>
        <input
          id="busca"
          v-model="filters.q"
          placeholder="Buscar por cargo ou empresa"
          class="h-10 w-full rounded-lg border border-line bg-surface pr-3 pl-9 text-sm focus:border-brand focus:outline-none"
        />
      </div>
      <select
        v-model="filters.status"
        aria-label="Situação"
        class="h-10 rounded-lg border border-line bg-surface px-3 text-sm"
      >
        <option value="active">Ativas</option>
        <option value="new">Aguardando análise</option>
        <option value="analyzed">Analisadas</option>
        <option value="discarded">Descartadas</option>
      </select>
      <select
        v-model="filters.minScore"
        aria-label="Compatibilidade mínima"
        class="h-10 rounded-lg border border-line bg-surface px-3 text-sm"
      >
        <option value="">Qualquer nota</option>
        <option value="50">50% ou mais</option>
        <option value="70">70% ou mais</option>
      </select>
      <BaseButton @click="openModal"><Plus class="size-4" /> Adicionar vaga</BaseButton>
    </div>

    <div v-if="!list.data.value && !list.error.value" class="space-y-2">
      <SkeletonBlock v-for="i in 5" :key="i" class="h-16" />
    </div>
    <BaseCard v-else-if="list.error.value && !list.data.value">
      <ErrorState :error="list.error.value" :retrying="list.loading.value" @retry="list.execute()" />
    </BaseCard>
    <BaseCard v-else-if="list.data.value && !list.data.value.length">
      <EmptyState
        :icon="BriefcaseBusiness"
        title="Nenhuma vaga por aqui"
        :description="filters.q || filters.minScore ? 'Nenhuma vaga com esses filtros.' : 'Cole o link ou o texto de uma vaga para começar.'"
      >
        <BaseButton v-if="!filters.q && !filters.minScore" @click="openModal"><Plus class="size-4" /> Adicionar vaga</BaseButton>
      </EmptyState>
    </BaseCard>
    <ul v-else-if="list.data.value" class="space-y-2">
      <li v-for="j in list.data.value" :key="j.id">
        <RouterLink
          :to="`/vagas/${j.id}`"
          class="flex items-center gap-4 rounded-xl border border-line bg-surface p-4 shadow-sm hover:border-brand/50"
        >
          <ScoreBadge :score="j.score" />
          <div class="min-w-0 flex-1">
            <p class="truncate font-medium">{{ j.title }}</p>
            <p class="truncate text-sm text-muted">
              {{ j.company || 'Empresa não informada' }}<span v-if="j.location"> · {{ j.location }}</span>
            </p>
          </div>
          <div class="hidden shrink-0 flex-col items-end gap-1 sm:flex">
            <StatusBadge
              v-if="j.application_status"
              tone="info"
              :label="STATUS_LABELS[j.application_status]"
            />
            <StatusBadge v-else-if="j.status === 'new'" tone="neutral" label="Analisando…" />
            <span class="text-xs text-muted">{{ ORIGIN_LABELS[j.origin] }} · {{ relativeDays(j.created_at) }}</span>
          </div>
        </RouterLink>
      </li>
    </ul>

    <BaseModal :open="modal" title="Adicionar vaga" @close="modal = false">
      <div class="mb-4 inline-flex rounded-lg border border-line p-0.5 text-sm" role="tablist">
        <button
          v-for="m in ['url', 'text'] as const"
          :key="m"
          type="button"
          role="tab"
          :aria-selected="mode === m"
          class="rounded-md px-3 py-1.5"
          :class="mode === m ? 'bg-surface-2 font-medium' : 'text-muted'"
          @click="mode = m"
        >
          {{ m === 'url' ? 'Pelo link' : 'Colar o texto' }}
        </button>
      </div>
      <form id="job-form" class="space-y-4" @submit.prevent="save">
        <template v-if="mode === 'url'">
          <FormField
            v-model="draft.url"
            label="Link da vaga"
            type="url"
            placeholder="https://..."
            required
            hint="Funciona melhor com páginas públicas. Se o site exigir login, cole o texto."
          />
        </template>
        <template v-else>
          <FormField v-model="draft.title" label="Cargo" placeholder="Desenvolvedor(a) Python Júnior" />
          <FormField v-model="draft.company" label="Empresa" />
          <FormField v-model="draft.description" as="textarea" :rows="8" label="Descrição da vaga" required />
        </template>
        <p v-if="formError" role="alert" class="text-sm text-danger">{{ formError }}</p>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="modal = false">Cancelar</BaseButton>
        <BaseButton type="submit" form="job-form" :loading="saving">
          <Link2 v-if="!saving && mode === 'url'" class="size-4" /> Adicionar
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>
