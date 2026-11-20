<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { KeyRound } from 'lucide-vue-next'
import BaseButton from '@/components/ui/BaseButton.vue'
import FormField from '@/components/ui/FormField.vue'
import { settingsApi } from '@/services/api'
import { useToastStore } from '@/stores/toast'
import type { SettingsOut } from '@/types/api'
import { toApiError } from '@/utils/apiError'
import { formatTokens } from '@/utils/format'

const props = defineProps<{ settings: SettingsOut }>()
const emit = defineEmits<{ saved: [] }>()
const toast = useToastStore()
const form = reactive({ api_key: '', model: props.settings.ai.model, effort: props.settings.ai.effort })
const saving = ref(false)
const testing = ref(false)
const usage = ref<Awaited<ReturnType<typeof settingsApi.aiUsage>>['items']>([])

onMounted(async () => {
  usage.value = (await settingsApi.aiUsage()).items
})

const EFFORTS: Record<string, string> = { low: 'Baixo (mais rápido e barato)', medium: 'Médio (recomendado)', high: 'Alto (mais cuidadoso)' }
const OPS: Record<string, string> = {
  analyze_job: 'Análise de vagas',
  tailor_documents: 'Currículos e cartas',
  import_profile: 'Importação de PDF',
  extract_email_jobs: 'Alertas por e-mail',
}

async function save() {
  saving.value = true
  try {
    await settingsApi.saveAi({ api_key: form.api_key || null, model: form.model, effort: form.effort })
    form.api_key = ''
    toast.success('Configuração de IA salva', 'A chave foi validada com a Anthropic.')
    emit('saved')
  } catch (e) {
    toast.error('Não foi possível salvar', toApiError(e).message)
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  try {
    await settingsApi.testAi()
    toast.success('Chave funcionando')
  } catch (e) {
    toast.error('Falha no teste', toApiError(e).message)
  } finally {
    testing.value = false
  }
}

async function removeKey() {
  if (!confirm('Remover a chave? A análise volta a ser só por palavras-chave.')) return
  await settingsApi.deleteAiKey()
  toast.success('Chave removida')
  emit('saved')
}
</script>

<template>
  <div class="space-y-6">
    <div class="rounded-lg bg-surface-2 p-4 text-sm">
      <p class="font-medium">Você usa a sua própria chave da API da Anthropic (Claude).</p>
      <p class="mt-1 text-muted">
        Crie uma em <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener noreferrer" class="text-brand hover:underline">console.anthropic.com</a>.
        A chave fica criptografada nesta instância e o custo vai direto para a sua conta. Seus dados de contato nunca são enviados à IA.
      </p>
    </div>
    <form class="space-y-4" @submit.prevent="save">
      <FormField
        v-model="form.api_key"
        type="password"
        autocomplete="off"
        label="Chave de API"
        :placeholder="settings.ai.api_key.configured ? '•••••••• (cadastrada — deixe vazio para manter)' : 'sk-ant-...'"
      />
      <div class="grid gap-4 sm:grid-cols-2">
        <FormField v-model="form.model" as="select" label="Modelo">
          <option v-for="(label, id) in settings.ai.models" :key="id" :value="id">{{ label }}</option>
        </FormField>
        <FormField v-model="form.effort" as="select" label="Esforço de raciocínio">
          <option v-for="e in settings.ai.efforts" :key="e" :value="e">{{ EFFORTS[e] ?? e }}</option>
        </FormField>
      </div>
      <div class="flex flex-wrap gap-2">
        <BaseButton type="submit" :loading="saving"><KeyRound v-if="!saving" class="size-4" /> Salvar e validar</BaseButton>
        <BaseButton v-if="settings.ai.api_key.configured" variant="secondary" :loading="testing" @click="test">Testar</BaseButton>
        <BaseButton v-if="settings.ai.api_key.configured" variant="ghost" @click="removeKey">Remover chave</BaseButton>
      </div>
    </form>

    <section>
      <h3 class="text-sm font-semibold">Uso nos últimos 30 dias</h3>
      <p v-if="!usage.length" class="mt-2 text-sm text-muted">Nenhum uso registrado.</p>
      <table v-else class="mt-2 w-full text-left text-sm">
        <thead class="text-xs text-muted">
          <tr><th class="py-1 font-medium">Operação</th><th class="font-medium">Chamadas</th><th class="font-medium">Tokens (entrada / saída)</th></tr>
        </thead>
        <tbody class="divide-y divide-line">
          <tr v-for="u in usage" :key="u.operation + u.model">
            <td class="py-1.5">{{ OPS[u.operation] ?? u.operation }} <span class="text-xs text-muted">· {{ u.model }}</span></td>
            <td>{{ u.calls }}</td>
            <td>{{ formatTokens(u.input_tokens) }} / {{ formatTokens(u.output_tokens) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>
