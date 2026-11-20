<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Plus, RefreshCw, Rss, Trash2 } from 'lucide-vue-next'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import FormField from '@/components/ui/FormField.vue'
import { useTask } from '@/composables/useTask'
import { settingsApi } from '@/services/api'
import { useToastStore } from '@/stores/toast'
import type { Source } from '@/types/api'
import { toApiError } from '@/utils/apiError'
import { formatDateTime } from '@/utils/format'

const toast = useToastStore()
const sources = ref<Source[]>([])
const newSource = ref({ name: '', url: '' })
const adding = ref(false)
const { running: polling, wait: waitTask } = useTask({ intervalMs: 2500 })

const load = async () => (sources.value = await settingsApi.sources())
onMounted(load)

async function add() {
  adding.value = true
  try {
    await settingsApi.createSource({ ...newSource.value, enabled: true })
    newSource.value = { name: '', url: '' }
    await load()
  } catch (e) {
    const err = toApiError(e)
    toast.error('Não foi possível adicionar', err.fields[0]?.message ?? err.message)
  } finally {
    adding.value = false
  }
}

async function toggle(s: Source) {
  await settingsApi.updateSource(s.id, { name: s.name, url: s.url, enabled: !s.enabled })
  await load()
}

async function remove(s: Source) {
  if (!confirm(`Remover a fonte “${s.name}”?`)) return
  await settingsApi.deleteSource(s.id)
  await load()
}

async function pollNow() {
  try {
    const { task_id } = await settingsApi.pollNow()
    const t = await waitTask(task_id)
    const created = (t.result as { created?: number } | null)?.created ?? 0
    toast.success(created ? `${created} vaga(s) nova(s)` : 'Nenhuma vaga nova')
    await load()
  } catch (e) {
    toast.error('Falha na verificação', toApiError(e).message)
  }
}
</script>

<template>
  <div class="space-y-6 text-sm">
    <p class="text-muted">
      Feeds RSS de sites de vagas são verificados a cada hora. Vagas novas são analisadas e, se forem compatíveis,
      avisadas no Telegram.
    </p>
    <form class="grid gap-2 sm:grid-cols-[12rem_1fr_auto] sm:items-end" @submit.prevent="add">
      <FormField v-model="newSource.name" label="Nome" placeholder="Vagas Python" required />
      <FormField v-model="newSource.url" type="url" label="URL do feed" placeholder="https://.../rss" required />
      <BaseButton type="submit" :loading="adding"><Plus class="size-4" /> Adicionar</BaseButton>
    </form>

    <EmptyState v-if="!sources.length" :icon="Rss" title="Nenhuma fonte cadastrada" />
    <ul v-else class="divide-y divide-line">
      <li v-for="s in sources" :key="s.id" class="flex items-center gap-3 py-3">
        <input type="checkbox" :checked="s.enabled" :aria-label="`Ativar ${s.name}`" @change="toggle(s)" />
        <div class="min-w-0 flex-1">
          <p class="font-medium">{{ s.name }}</p>
          <p class="truncate text-xs text-muted">{{ s.url }}</p>
          <p class="text-xs" :class="s.last_error ? 'text-danger' : 'text-muted'">
            {{ s.last_error ? `Erro: ${s.last_error}` : s.last_checked_at ? `Verificada em ${formatDateTime(s.last_checked_at)}` : 'Ainda não verificada' }}
          </p>
        </div>
        <BaseButton variant="ghost" size="sm" :aria-label="`Remover ${s.name}`" @click="remove(s)"><Trash2 class="size-4" /></BaseButton>
      </li>
    </ul>
    <BaseButton variant="secondary" :loading="polling" @click="pollNow">
      <RefreshCw v-if="!polling" class="size-4" /> Verificar agora (RSS e e-mail)
    </BaseButton>
  </div>
</template>
