<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  Archive,
  ArchiveRestore,
  Download,
  ExternalLink,
  FileText,
  Mail,
  Pencil,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
} from 'lucide-vue-next'
import IssueList from '@/components/jobs/IssueList.vue'
import LetterEditor from '@/components/jobs/LetterEditor.vue'
import ResumeEditor from '@/components/jobs/ResumeEditor.vue'
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
import { useTask } from '@/composables/useTask'
import { applicationsApi, documentsApi, jobsApi, profileApi } from '@/services/api'
import { useToastStore } from '@/stores/toast'
import type { DocumentOut, LetterContent, Profile, ResumeContent, TargetRole } from '@/types/api'
import { toApiError } from '@/utils/apiError'
import { STATUS_LABELS, formatDateTime } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()
const jobId = computed(() => Number(route.params.id))

const job = useAsync((signal) => jobsApi.get(jobId.value, signal), { keepDataOnError: true })
const roles = ref<TargetRole[]>([])
const templates = ref<{ id: string; name: string }[]>([])
const task = useTask()
const busy = ref('')

async function load() {
  await job.execute()
}
onMounted(async () => {
  await load()
  ;[roles.value, templates.value] = await Promise.all([profileApi.roles(), profileApi.templates()])
  genRole.value = job.data.value?.analysis?.target_role_id ?? roles.value.find((r) => r.is_default)?.id ?? null
})
watch(jobId, load)

/** Executa uma ação que cria tarefa no worker, espera terminar e recarrega a vaga. */
async function runTask(label: string, start: () => Promise<{ task_id: number }>, ok?: string) {
  busy.value = label
  try {
    const { task_id } = await start()
    await task.wait(task_id)
    if (ok) toast.success(ok)
  } catch (e) {
    toast.error('Não foi possível concluir', toApiError(e).message)
  } finally {
    busy.value = ''
    await load()
  }
}

// Vaga recém-criada: recarrega até a análise automática terminar (no máximo ~2 min).
let polls = 0
let pollTimer: ReturnType<typeof setTimeout> | undefined
watch(
  () => job.data.value?.status,
  (status) => {
    clearTimeout(pollTimer)
    if (status === 'new' && polls++ < 50) pollTimer = setTimeout(load, 2500)
  },
)
onBeforeUnmount(() => clearTimeout(pollTimer))

const resume = computed(() => latest('resume'))
const letter = computed(() => latest('cover_letter'))
function latest(kind: DocumentOut['kind']) {
  return [...(job.data.value?.documents ?? [])].reverse().find((d) => d.kind === kind)
}
const resumeBlocked = computed(() => !!resume.value?.issues.some((i) => i.severity === 'error'))

const tab = ref<'resume' | 'cover_letter'>('resume')
const shownDoc = computed(() => (tab.value === 'resume' ? resume.value : letter.value))
// A pré-visualização é buscada pela API (com a sessão) e exibida via srcdoc num iframe sandbox:
// sem scripts e sem depender de o navegador enviar cookies a um iframe isolado.
const previewHtml = ref('')
watch(
  () => `${shownDoc.value?.id}-${shownDoc.value?.updated_at}`,
  async () => {
    const doc = shownDoc.value
    previewHtml.value = ''
    if (!doc) return
    try {
      previewHtml.value = await documentsApi.preview(doc.id)
    } catch (e) {
      toast.error('Não foi possível carregar a pré-visualização', toApiError(e).message)
    }
  },
  { immediate: true },
)

// ---------- geração ----------
const genRole = ref<number | null>(null)
const genTemplate = ref<string>('')
function generate() {
  return runTask(
    'generate',
    () => jobsApi.generate(jobId.value, { target_role_id: genRole.value, template: genTemplate.value || null }),
    'Currículo e carta gerados',
  )
}

// ---------- edição ----------
const editing = ref(false)
const profile = ref<Profile | null>(null)
const resumeEditor = ref<InstanceType<typeof ResumeEditor> | null>(null)
const letterEditor = ref<InstanceType<typeof LetterEditor> | null>(null)
const editTemplate = ref('')
async function openEditor() {
  profile.value ??= await profileApi.get()
  editTemplate.value = resume.value?.template ?? 'classico'
  editing.value = true
}
async function saveEdit() {
  const doc = shownDoc.value
  if (!doc) return
  const content = tab.value === 'resume' ? resumeEditor.value?.value() : letterEditor.value?.value()
  editing.value = false
  await runTask(
    'edit',
    () => documentsApi.update(doc.id, content, tab.value === 'resume' ? editTemplate.value : undefined),
    'Documento atualizado',
  )
}

// ---------- vaga ----------
async function patch(body: Parameters<typeof jobsApi.patch>[1], msg: string) {
  try {
    job.data.value = await jobsApi.patch(jobId.value, body)
    toast.success(msg)
  } catch (e) {
    toast.error('Não foi possível salvar', toApiError(e).message)
  }
}
const contactEmail = ref('')
watch(
  () => job.data.value?.contact_email,
  (v) => (contactEmail.value = v ?? ''),
)

async function remove() {
  if (!confirm('Excluir esta vaga, os documentos gerados e a candidatura?')) return
  await jobsApi.remove(jobId.value)
  toast.success('Vaga excluída')
  router.push('/vagas')
}

// ---------- candidatura ----------
const app = computed(() => job.data.value?.application ?? null)
async function approve() {
  busy.value = 'approve'
  try {
    await applicationsApi.approve(jobId.value)
    toast.success('Candidatura aprovada')
  } catch (e) {
    toast.error('Não foi possível aprovar', toApiError(e).message)
  } finally {
    busy.value = ''
    await load()
  }
}
function sendEmail() {
  if (!app.value) return
  const id = app.value.id
  return runTask('send', () => applicationsApi.send(id), 'E-mail enviado')
}
async function markSent() {
  if (!app.value) return
  busy.value = 'mark'
  try {
    await applicationsApi.setStatus(app.value.id, 'sent')
    toast.success('Marcada como enviada')
    if (job.data.value?.url) window.open(job.data.value.url, '_blank', 'noopener')
  } catch (e) {
    toast.error('Não foi possível atualizar', toApiError(e).message)
  } finally {
    busy.value = ''
    await load()
  }
}
</script>

<template>
  <div class="space-y-6">
    <div v-if="!job.data.value && !job.error.value" class="space-y-4">
      <SkeletonBlock class="h-24" /><SkeletonBlock class="h-64" />
    </div>
    <BaseCard v-else-if="job.error.value && !job.data.value">
      <ErrorState :error="job.error.value" :retrying="job.loading.value" @retry="load" />
    </BaseCard>

    <template v-else-if="job.data.value">
      <!-- Cabeçalho -->
      <BaseCard>
        <div class="flex flex-col gap-4 sm:flex-row sm:items-start">
          <ScoreBadge :score="job.data.value.analysis?.score ?? null" size="lg" />
          <div class="min-w-0 flex-1">
            <h2 class="text-lg font-semibold">{{ job.data.value.title }}</h2>
            <p class="text-sm text-muted">
              {{ job.data.value.company || 'Empresa não informada' }}
              <span v-if="job.data.value.location"> · {{ job.data.value.location }}</span>
            </p>
            <a
              v-if="job.data.value.url"
              :href="job.data.value.url"
              target="_blank"
              rel="noopener noreferrer"
              class="mt-1 inline-flex items-center gap-1 text-sm text-brand hover:underline"
            >
              Abrir anúncio <ExternalLink class="size-3.5" />
            </a>
          </div>
          <div class="flex flex-wrap gap-2">
            <BaseButton variant="secondary" size="sm" :loading="busy === 'analyze'" @click="runTask('analyze', () => jobsApi.analyze(jobId), 'Análise atualizada')">
              <RefreshCw v-if="busy !== 'analyze'" class="size-4" /> Reanalisar
            </BaseButton>
            <BaseButton
              v-if="job.data.value.status !== 'discarded'"
              variant="ghost"
              size="sm"
              @click="patch({ status: 'discarded' }, 'Vaga descartada')"
            >
              <Archive class="size-4" /> Descartar
            </BaseButton>
            <BaseButton v-else variant="ghost" size="sm" @click="patch({ status: 'analyzed' }, 'Vaga restaurada')">
              <ArchiveRestore class="size-4" /> Restaurar
            </BaseButton>
            <BaseButton variant="ghost" size="sm" aria-label="Excluir vaga" @click="remove"><Trash2 class="size-4" /></BaseButton>
          </div>
        </div>
      </BaseCard>

      <div class="grid gap-6 lg:grid-cols-5">
        <!-- Análise -->
        <div class="space-y-6 lg:col-span-2">
          <BaseCard title="Compatibilidade">
            <div v-if="!job.data.value.analysis" class="flex items-center gap-2 text-sm text-muted">
              <RefreshCw class="size-4 animate-spin" /> Analisando a vaga…
            </div>
            <div v-else class="space-y-4 text-sm">
              <p>{{ job.data.value.analysis.summary }}</p>
              <p class="text-xs text-muted">
                {{ job.data.value.analysis.used_ai ? 'Análise por IA' : 'Análise por palavras-chave (sem IA)' }}
                <span v-if="job.data.value.analysis.seniority"> · Nível: {{ job.data.value.analysis.seniority }}</span>
              </p>
              <div v-if="job.data.value.analysis.matched.length">
                <p class="font-medium">Você atende</p>
                <div class="mt-1 flex flex-wrap gap-1.5">
                  <span v-for="m in job.data.value.analysis.matched" :key="m" class="rounded-md bg-success-soft px-2 py-0.5 text-success">{{ m }}</span>
                </div>
              </div>
              <div v-if="job.data.value.analysis.missing.length">
                <p class="font-medium">Faltando</p>
                <div class="mt-1 flex flex-wrap gap-1.5">
                  <span v-for="m in job.data.value.analysis.missing" :key="m" class="rounded-md bg-danger-soft px-2 py-0.5 text-danger">{{ m }}</span>
                </div>
              </div>
            </div>
          </BaseCard>

          <BaseCard title="Contato para envio">
            <form class="flex items-end gap-2" @submit.prevent="patch({ contact_email: contactEmail }, 'E-mail salvo')">
              <FormField v-model="contactEmail" class="flex-1" label="E-mail da vaga" type="email" placeholder="rh@empresa.com" />
              <BaseButton type="submit" variant="secondary">Salvar</BaseButton>
            </form>
          </BaseCard>

          <BaseCard title="Descrição da vaga">
            <p class="max-h-96 overflow-y-auto text-sm whitespace-pre-line text-muted">{{ job.data.value.description }}</p>
          </BaseCard>
        </div>

        <!-- Documentos e candidatura -->
        <div class="space-y-6 lg:col-span-3">
          <BaseCard title="Currículo e carta">
            <template #actions>
              <span v-if="resume?.used_ai" class="inline-flex items-center gap-1 text-xs text-muted"><Sparkles class="size-3.5" /> Adaptado por IA</span>
            </template>

            <div class="mb-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
              <FormField v-model="genRole" as="select" label="Perfil-alvo">
                <option :value="null">Automático</option>
                <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
              </FormField>
              <FormField v-model="genTemplate" as="select" label="Modelo">
                <option value="">Padrão do perfil-alvo</option>
                <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
              </FormField>
              <BaseButton :loading="busy === 'generate'" @click="generate">
                <FileText v-if="busy !== 'generate'" class="size-4" /> {{ resume ? 'Gerar de novo' : 'Gerar' }}
              </BaseButton>
            </div>

            <EmptyState
              v-if="!resume"
              :icon="FileText"
              title="Nenhum documento gerado"
              description="Gere um currículo adaptado e uma carta para esta vaga. Nada é enviado sem a sua aprovação."
            />
            <template v-else>
              <div class="mb-3 flex items-center gap-1 border-b border-line" role="tablist">
                <button
                  v-for="t in [{ id: 'resume', label: 'Currículo' }, { id: 'cover_letter', label: 'Carta' }] as const"
                  :key="t.id"
                  type="button"
                  role="tab"
                  :aria-selected="tab === t.id"
                  class="-mb-px border-b-2 px-3 py-2 text-sm"
                  :class="tab === t.id ? 'border-brand font-medium' : 'border-transparent text-muted'"
                  @click="tab = t.id"
                >
                  {{ t.label }}
                  <span v-if="(t.id === 'resume' ? resume : letter)?.issues.length" class="ml-1 text-xs text-brand">●</span>
                </button>
              </div>
              <template v-if="shownDoc">
                <IssueList :issues="shownDoc.issues" />
                <SkeletonBlock v-if="!previewHtml" class="mt-3 h-[34rem] w-full" />
                <iframe
                  v-else
                  :srcdoc="previewHtml"
                  :title="`Pré-visualização: ${tab === 'resume' ? 'currículo' : 'carta'}`"
                  sandbox=""
                  class="mt-3 h-[34rem] w-full rounded-lg border border-line bg-white"
                />
                <div class="mt-3 flex flex-wrap gap-2">
                  <BaseButton variant="secondary" size="sm" :loading="busy === 'edit'" @click="openEditor">
                    <Pencil v-if="busy !== 'edit'" class="size-4" /> Editar
                  </BaseButton>
                  <a
                    :href="documentsApi.pdfUrl(shownDoc.id)"
                    class="inline-flex h-8 items-center gap-2 rounded-lg border border-line px-3 text-sm hover:bg-surface-2"
                  >
                    <Download class="size-4" /> Baixar PDF
                  </a>
                </div>
              </template>
            </template>
          </BaseCard>

          <BaseCard title="Candidatura">
            <div v-if="!app || app.status === 'draft'" class="space-y-3 text-sm">
              <p class="text-muted">Revise o currículo. Ao aprovar, você escolhe como se candidatar.</p>
              <BaseButton :disabled="!resume || resumeBlocked" :loading="busy === 'approve'" @click="approve">Aprovar candidatura</BaseButton>
              <p v-if="resumeBlocked" class="text-xs text-danger">Corrija os erros do currículo para aprovar.</p>
            </div>
            <div v-else class="space-y-4">
              <div class="flex items-center gap-2">
                <StatusBadge tone="info" :label="STATUS_LABELS[app.status]" />
                <span v-if="app.sent_at" class="text-xs text-muted">
                  {{ app.sent_via === 'email' ? 'por e-mail' : 'pelo site' }} em {{ formatDateTime(app.sent_at) }}
                </span>
              </div>
              <div v-if="app.status === 'approved'" class="flex flex-wrap gap-2">
                <BaseButton v-if="job.data.value.contact_email" :loading="busy === 'send'" @click="sendEmail">
                  <Mail v-if="busy !== 'send'" class="size-4" /> Enviar para {{ job.data.value.contact_email }}
                </BaseButton>
                <BaseButton variant="secondary" :loading="busy === 'mark'" @click="markSent">
                  <Send v-if="busy !== 'mark'" class="size-4" /> Já me candidatei pelo site
                </BaseButton>
              </div>
              <ol class="space-y-2 border-l border-line pl-4 text-sm">
                <li v-for="(e, i) in app.events" :key="i">
                  <p class="font-medium">{{ STATUS_LABELS[e.to] }}</p>
                  <p class="text-xs text-muted">
                    {{ formatDateTime(e.at) }} · {{ e.actor === 'telegram' ? 'pelo Telegram' : e.actor === 'owner' ? 'por você' : 'automático' }}
                    <span v-if="e.note"> · {{ e.note }}</span>
                  </p>
                </li>
              </ol>
              <RouterLink to="/candidaturas" class="text-sm text-brand hover:underline">Atualizar o status no funil →</RouterLink>
            </div>
          </BaseCard>
        </div>
      </div>

      <BaseModal :open="editing" :title="tab === 'resume' ? 'Editar currículo' : 'Editar carta'" size="lg" @close="editing = false">
        <template v-if="tab === 'resume' && resume && profile">
          <FormField v-model="editTemplate" as="select" label="Modelo" class="mb-6">
            <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
          </FormField>
          <ResumeEditor ref="resumeEditor" :content="resume.content as ResumeContent" :profile="profile" />
        </template>
        <LetterEditor v-else-if="letter" ref="letterEditor" :content="letter.content as LetterContent" />
        <template #footer>
          <BaseButton variant="secondary" @click="editing = false">Cancelar</BaseButton>
          <BaseButton @click="saveEdit">Salvar e revalidar</BaseButton>
        </template>
      </BaseModal>
    </template>
  </div>
</template>
