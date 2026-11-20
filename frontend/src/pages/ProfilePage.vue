<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { FileUp, Plus, Save, Trash2 } from 'lucide-vue-next'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import FormField from '@/components/ui/FormField.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import TagInput from '@/components/ui/TagInput.vue'
import { useAsync } from '@/composables/useAsync'
import { useTask } from '@/composables/useTask'
import { profileApi } from '@/services/api'
import { useToastStore } from '@/stores/toast'
import type { Profile } from '@/types/api'
import { toApiError } from '@/utils/apiError'

const toast = useToastStore()
const loader = useAsync(() => profileApi.get())
const profile = ref<Profile | null>(null)
const saved = ref('')
const saving = ref(false)
const fieldErrors = ref<Record<string, string>>({})

onMounted(async () => {
  const p = await loader.execute()
  if (p) setProfile(p)
})

function setProfile(p: Profile) {
  profile.value = p
  saved.value = JSON.stringify(p)
}
const dirty = computed(() => !!profile.value && JSON.stringify(profile.value) !== saved.value)

onBeforeRouteLeave(() => !dirty.value || confirm('Há alterações não salvas no perfil. Sair mesmo assim?'))

const newId = () => Math.random().toString(16).slice(2, 10)

// Competências editadas como lista de nomes (categoria/nível ficam preservados).
const skillNames = computed({
  get: () => profile.value?.skills.map((s) => s.name) ?? [],
  set: (names: string[]) => {
    if (!profile.value) return
    const byName = new Map(profile.value.skills.map((s) => [s.name.toLowerCase(), s]))
    profile.value.skills = names.map((n) => byName.get(n.toLowerCase()) ?? { name: n, category: '', level: '' })
  },
})

async function save() {
  if (!profile.value) return
  saving.value = true
  fieldErrors.value = {}
  try {
    setProfile(await profileApi.save(profile.value))
    toast.success('Perfil salvo')
  } catch (e) {
    const err = toApiError(e)
    fieldErrors.value = Object.fromEntries(err.fields.map((f) => [f.field, f.message]))
    toast.error('Não foi possível salvar', err.fields.length ? 'Revise os campos destacados.' : err.message)
  } finally {
    saving.value = false
  }
}

// ---------- importação ----------
const fileInput = ref<HTMLInputElement | null>(null)
const importTask = useTask({ intervalMs: 2000 })
const importing = ref(false)
async function importPdf(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  ;(e.target as HTMLInputElement).value = ''
  if (dirty.value && !confirm('A importação vai substituir o que está na tela (sem salvar). Continuar?')) return
  importing.value = true
  try {
    const { task_id } = await profileApi.importPdf(file)
    const t = await importTask.wait(task_id)
    profile.value = (t.result as { profile: Profile }).profile
    toast.info('Currículo importado', 'Revise cada seção e clique em Salvar perfil.')
  } catch (err) {
    toast.error('Falha na importação', toApiError(err).message)
  } finally {
    importing.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <div v-if="!profile && !loader.error.value" class="space-y-4"><SkeletonBlock v-for="i in 3" :key="i" class="h-40" /></div>
    <BaseCard v-else-if="loader.error.value && !profile">
      <ErrorState :error="loader.error.value" :retrying="loader.loading.value" @retry="loader.execute()" />
    </BaseCard>

    <template v-else-if="profile">
      <BaseCard>
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div class="flex-1">
            <h2 class="font-semibold">Seu perfil é a fonte da verdade</h2>
            <p class="text-sm text-muted">
              Os currículos gerados só podem usar o que está aqui. Importe o currículo atual para começar mais rápido.
            </p>
          </div>
          <input ref="fileInput" type="file" accept="application/pdf" class="hidden" @change="importPdf" />
          <BaseButton variant="secondary" :loading="importing" @click="fileInput?.click()">
            <FileUp v-if="!importing" class="size-4" /> {{ importing ? 'Lendo o PDF…' : 'Importar PDF' }}
          </BaseButton>
        </div>
      </BaseCard>

      <BaseCard title="Contato e apresentação">
        <div class="grid gap-4 sm:grid-cols-2">
          <FormField v-model="profile.contact.name" label="Nome completo" :error="fieldErrors['contact.name']" />
          <FormField v-model="profile.contact.email" label="E-mail" type="email" />
          <FormField v-model="profile.contact.phone" label="Telefone" />
          <FormField v-model="profile.contact.location" label="Cidade" placeholder="Belo Horizonte, MG" />
          <FormField v-model="profile.headline" class="sm:col-span-2" label="Título profissional" placeholder="Desenvolvedor Back-end Júnior" />
          <FormField v-model="profile.summary" class="sm:col-span-2" as="textarea" :rows="4" label="Resumo" />
          <FormField v-model="profile.availability" class="sm:col-span-2" label="Disponibilidade" placeholder="CLT ou PJ · Remoto ou híbrido" />
        </div>
        <h3 class="mt-6 text-sm font-semibold">Links</h3>
        <div v-for="(l, i) in profile.contact.links" :key="i" class="mt-2 grid grid-cols-[8rem_1fr_auto] items-end gap-2">
          <FormField v-model="l.label" label="Nome" />
          <FormField v-model="l.url" label="URL" type="url" />
          <BaseButton variant="ghost" size="sm" aria-label="Remover link" @click="profile.contact.links.splice(i, 1)"><Trash2 class="size-4" /></BaseButton>
        </div>
        <button type="button" class="mt-2 inline-flex items-center gap-1 text-sm text-brand hover:underline" @click="profile.contact.links.push({ label: '', url: '' })">
          <Plus class="size-4" /> Adicionar link
        </button>
      </BaseCard>

      <BaseCard title="Competências" subtitle="Tudo que você sabe explicar numa entrevista. Só elas podem entrar no currículo.">
        <TagInput v-model="skillNames" label="Competências" placeholder="Digite e tecle Enter (ou cole separado por vírgulas)" />
      </BaseCard>

      <BaseCard title="Experiência profissional">
        <div v-for="(e, i) in profile.experiences" :key="e.id" class="mb-4 rounded-xl border border-line p-4">
          <div class="grid gap-3 sm:grid-cols-2">
            <FormField v-model="e.role" label="Cargo" />
            <FormField v-model="e.company" label="Empresa" />
            <FormField v-model="e.start" label="Início" placeholder="06/2024" />
            <FormField v-model="e.end" label="Fim" placeholder="Vazio se atual" />
          </div>
          <p class="mt-3 text-sm font-medium">Realizações</p>
          <div v-for="(_, h) in e.highlights" :key="h" class="mt-2 flex items-start gap-2">
            <textarea
              v-model="e.highlights[h]"
              rows="2"
              :aria-label="`Realização ${h + 1}`"
              class="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm focus:border-brand focus:outline-none"
            />
            <BaseButton variant="ghost" size="sm" aria-label="Remover realização" @click="e.highlights.splice(h, 1)"><Trash2 class="size-4" /></BaseButton>
          </div>
          <div class="mt-2 flex justify-between">
            <button type="button" class="inline-flex items-center gap-1 text-sm text-brand hover:underline" @click="e.highlights.push('')">
              <Plus class="size-4" /> Realização
            </button>
            <button type="button" class="text-sm text-danger hover:underline" @click="profile.experiences.splice(i, 1)">Remover experiência</button>
          </div>
        </div>
        <BaseButton
          variant="secondary"
          size="sm"
          @click="profile.experiences.push({ id: newId(), role: '', company: '', start: '', end: '', location: '', highlights: [''] })"
        >
          <Plus class="size-4" /> Adicionar experiência
        </BaseButton>
      </BaseCard>

      <BaseCard title="Projetos">
        <div v-for="(p, i) in profile.projects" :key="p.id" class="mb-4 rounded-xl border border-line p-4">
          <div class="grid gap-3 sm:grid-cols-2">
            <FormField v-model="p.name" label="Nome" />
            <FormField v-model="p.url" label="Link (GitHub, demo…)" type="url" />
            <FormField v-model="p.description" class="sm:col-span-2" as="textarea" :rows="2" label="Descrição" />
            <TagInput v-model="p.technologies" class="sm:col-span-2" label="Tecnologias" />
          </div>
          <button type="button" class="mt-2 text-sm text-danger hover:underline" @click="profile.projects.splice(i, 1)">Remover projeto</button>
        </div>
        <BaseButton
          variant="secondary"
          size="sm"
          @click="profile.projects.push({ id: newId(), name: '', description: '', url: '', technologies: [] })"
        >
          <Plus class="size-4" /> Adicionar projeto
        </BaseButton>
      </BaseCard>

      <div class="grid gap-6 lg:grid-cols-2">
        <BaseCard title="Formação">
          <div v-for="(f, i) in profile.education" :key="f.id" class="mb-3 grid grid-cols-2 gap-2 rounded-xl border border-line p-3">
            <FormField v-model="f.course" class="col-span-2" label="Curso" />
            <FormField v-model="f.institution" class="col-span-2" label="Instituição" />
            <FormField v-model="f.start" label="Início" />
            <FormField v-model="f.end" label="Conclusão" />
            <button type="button" class="col-span-2 text-left text-sm text-danger hover:underline" @click="profile.education.splice(i, 1)">Remover</button>
          </div>
          <BaseButton variant="secondary" size="sm" @click="profile.education.push({ id: newId(), course: '', institution: '', start: '', end: '' })">
            <Plus class="size-4" /> Adicionar formação
          </BaseButton>
        </BaseCard>

        <BaseCard title="Idiomas e certificações">
          <div v-for="(l, i) in profile.languages" :key="`l${i}`" class="mb-2 grid grid-cols-[1fr_1.5fr_auto] items-end gap-2">
            <FormField v-model="l.name" label="Idioma" />
            <FormField v-model="l.level" label="Nível" />
            <BaseButton variant="ghost" size="sm" aria-label="Remover idioma" @click="profile.languages.splice(i, 1)"><Trash2 class="size-4" /></BaseButton>
          </div>
          <button type="button" class="mb-4 inline-flex items-center gap-1 text-sm text-brand hover:underline" @click="profile.languages.push({ name: '', level: '' })">
            <Plus class="size-4" /> Idioma
          </button>
          <div v-for="(c, i) in profile.certifications" :key="`c${i}`" class="mb-2 grid grid-cols-[1.5fr_1fr_5rem_auto] items-end gap-2">
            <FormField v-model="c.name" label="Certificação" />
            <FormField v-model="c.issuer" label="Emissor" />
            <FormField v-model="c.year" label="Ano" />
            <BaseButton variant="ghost" size="sm" aria-label="Remover certificação" @click="profile.certifications.splice(i, 1)"><Trash2 class="size-4" /></BaseButton>
          </div>
          <button type="button" class="inline-flex items-center gap-1 text-sm text-brand hover:underline" @click="profile.certifications.push({ name: '', issuer: '', year: '' })">
            <Plus class="size-4" /> Certificação
          </button>
        </BaseCard>
      </div>

      <!-- Barra de salvar fixa: sempre visível no celular. -->
      <div class="sticky bottom-4 z-20 flex justify-end">
        <BaseButton :loading="saving" :disabled="!dirty" class="shadow-lg" @click="save">
          <Save v-if="!saving" class="size-4" /> {{ dirty ? 'Salvar perfil' : 'Perfil salvo' }}
        </BaseButton>
      </div>
    </template>
  </div>
</template>
