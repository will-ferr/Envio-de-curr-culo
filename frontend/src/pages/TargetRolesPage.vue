<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Pencil, Plus, Star, Target, Trash2 } from 'lucide-vue-next'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import FormField from '@/components/ui/FormField.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import TagInput from '@/components/ui/TagInput.vue'
import { useAsync } from '@/composables/useAsync'
import { profileApi } from '@/services/api'
import { useToastStore } from '@/stores/toast'
import type { TargetRole } from '@/types/api'
import { toApiError } from '@/utils/apiError'

const toast = useToastStore()
const list = useAsync(() => profileApi.roles(), { keepDataOnError: true })
const templates = ref<{ id: string; name: string }[]>([])
onMounted(async () => {
  void list.execute()
  templates.value = await profileApi.templates()
})

const empty = (): Omit<TargetRole, 'id'> => ({
  name: '',
  headline: '',
  summary: '',
  skills_focus: [],
  keywords: [],
  template: 'classico',
  is_default: false,
})
const modal = ref(false)
const editingId = ref<number | null>(null)
const form = reactive(empty())
const errors = ref<Record<string, string>>({})
const saving = ref(false)

function open(role?: TargetRole) {
  editingId.value = role?.id ?? null
  Object.assign(form, role ? JSON.parse(JSON.stringify(role)) : empty())
  errors.value = {}
  modal.value = true
}

async function save() {
  saving.value = true
  errors.value = {}
  try {
    const body = { ...form }
    if (editingId.value) await profileApi.updateRole(editingId.value, body)
    else await profileApi.createRole(body)
    modal.value = false
    toast.success('Perfil-alvo salvo')
    await list.execute()
  } catch (e) {
    const err = toApiError(e)
    errors.value = Object.fromEntries(err.fields.map((f) => [f.field, f.message]))
    if (!err.fields.length) errors.value.general = err.message
  } finally {
    saving.value = false
  }
}

async function remove(role: TargetRole) {
  if (!confirm(`Excluir o perfil-alvo “${role.name}”?`)) return
  try {
    await profileApi.deleteRole(role.id)
    toast.success('Perfil-alvo excluído')
    await list.execute()
  } catch (e) {
    toast.error('Não foi possível excluir', toApiError(e).message)
  }
}
</script>

<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
      <p class="flex-1 text-sm text-muted">
        Cada perfil-alvo é um tipo de vaga que você busca. Ele define o título, o resumo base, as competências em destaque
        e as palavras-chave usadas para reconhecer vagas desse tipo.
      </p>
      <BaseButton @click="open()"><Plus class="size-4" /> Novo perfil-alvo</BaseButton>
    </div>

    <div v-if="!list.data.value && !list.error.value" class="grid gap-4 sm:grid-cols-2"><SkeletonBlock v-for="i in 2" :key="i" class="h-36" /></div>
    <BaseCard v-else-if="list.error.value && !list.data.value">
      <ErrorState :error="list.error.value" :retrying="list.loading.value" @retry="list.execute()" />
    </BaseCard>
    <BaseCard v-else-if="list.data.value && !list.data.value.length">
      <EmptyState :icon="Target" title="Nenhum perfil-alvo" description="Exemplos: “Back-end .NET”, “Analista de Dados Júnior”, “Suporte Técnico”.">
        <BaseButton @click="open()"><Plus class="size-4" /> Criar o primeiro</BaseButton>
      </EmptyState>
    </BaseCard>
    <div v-else-if="list.data.value" class="grid gap-4 sm:grid-cols-2">
      <BaseCard v-for="r in list.data.value" :key="r.id">
        <div class="flex items-start gap-2">
          <div class="min-w-0 flex-1">
            <h3 class="flex items-center gap-1.5 font-semibold">
              {{ r.name }}
              <Star v-if="r.is_default" class="size-4 fill-brand text-brand" aria-label="Padrão" />
            </h3>
            <p class="text-sm text-muted">{{ r.headline }}</p>
          </div>
          <BaseButton variant="ghost" size="sm" :aria-label="`Editar ${r.name}`" @click="open(r)"><Pencil class="size-4" /></BaseButton>
          <BaseButton variant="ghost" size="sm" :aria-label="`Excluir ${r.name}`" @click="remove(r)"><Trash2 class="size-4" /></BaseButton>
        </div>
        <div v-if="r.keywords.length" class="mt-3 flex flex-wrap gap-1.5">
          <span v-for="k in r.keywords" :key="k" class="rounded-md bg-surface-2 px-2 py-0.5 text-xs">{{ k }}</span>
        </div>
      </BaseCard>
    </div>

    <BaseModal :open="modal" :title="editingId ? 'Editar perfil-alvo' : 'Novo perfil-alvo'" size="lg" @close="modal = false">
      <form id="role-form" class="space-y-4" @submit.prevent="save">
        <div class="grid gap-4 sm:grid-cols-2">
          <FormField v-model="form.name" label="Nome" placeholder="Back-end Python" required :error="errors.name" />
          <FormField v-model="form.headline" label="Título no currículo" placeholder="Desenvolvedor Python Júnior" required :error="errors.headline" />
        </div>
        <FormField v-model="form.summary" as="textarea" :rows="4" label="Resumo base" hint="Usado quando a IA não está configurada." />
        <TagInput v-model="form.skills_focus" label="Competências em destaque" hint="Aparecem primeiro. Use os nomes do seu perfil." />
        <TagInput v-model="form.keywords" label="Palavras-chave das vagas" hint="Ex.: python, fastapi, django. Identificam vagas deste tipo." />
        <FormField v-model="form.template" as="select" label="Modelo de currículo">
          <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
        </FormField>
        <label class="flex items-center gap-2 text-sm"><input v-model="form.is_default" type="checkbox" /> Usar como padrão</label>
        <p v-if="errors.general" role="alert" class="text-sm text-danger">{{ errors.general }}</p>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="modal = false">Cancelar</BaseButton>
        <BaseButton type="submit" form="role-form" :loading="saving">Salvar</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>
