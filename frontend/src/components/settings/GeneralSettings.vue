<script setup lang="ts">
import { reactive, ref } from 'vue'
import { Download, TriangleAlert } from 'lucide-vue-next'
import BaseButton from '@/components/ui/BaseButton.vue'
import FormField from '@/components/ui/FormField.vue'
import { authApi, settingsApi } from '@/services/api'
import { useToastStore } from '@/stores/toast'
import type { SettingsOut } from '@/types/api'
import { toApiError } from '@/utils/apiError'

const props = defineProps<{ settings: SettingsOut }>()
const emit = defineEmits<{ saved: [] }>()
const toast = useToastStore()
const prefs = reactive({
  daily_send_limit: props.settings.prefs.daily_send_limit,
  min_score_notify: props.settings.prefs.min_score_notify,
  default_template: props.settings.prefs.default_template,
})
const pwd = reactive({ current: '', next: '' })
const busy = ref('')

async function act(name: string, fn: () => Promise<unknown>, ok: string) {
  busy.value = name
  try {
    await fn()
    toast.success(ok)
    emit('saved')
  } catch (e) {
    toast.error('Não foi possível salvar', toApiError(e).message)
  } finally {
    busy.value = ''
  }
}

function wipe() {
  if (prompt('Isto apaga perfil, vagas, documentos e configurações. Digite APAGAR para confirmar.') !== 'APAGAR') return
  void act('wipe', settingsApi.wipe, 'Dados apagados')
}
</script>

<template>
  <div class="space-y-8 text-sm">
    <form class="space-y-4" @submit.prevent="act('prefs', () => settingsApi.savePrefs(prefs), 'Preferências salvas')">
      <h3 class="font-semibold">Preferências</h3>
      <div class="grid gap-4 sm:grid-cols-3">
        <FormField v-model.number="prefs.daily_send_limit" type="number" label="Limite de envios por dia" hint="Evita disparos em massa." />
        <FormField v-model.number="prefs.min_score_notify" type="number" label="Avisar a partir de (%)" hint="Compatibilidade mínima para notificar." />
        <FormField v-model="prefs.default_template" as="select" label="Modelo padrão">
          <option v-for="(label, id) in settings.prefs.templates" :key="id" :value="id">{{ label }}</option>
        </FormField>
      </div>
      <BaseButton type="submit" :loading="busy === 'prefs'">Salvar</BaseButton>
    </form>

    <form
      class="space-y-4 border-t border-line pt-6"
      @submit.prevent="act('pwd', async () => { await authApi.changePassword(pwd.current, pwd.next); pwd.current = ''; pwd.next = '' }, 'Senha alterada')"
    >
      <h3 class="font-semibold">Senha de acesso</h3>
      <div class="grid gap-4 sm:grid-cols-2">
        <FormField v-model="pwd.current" type="password" autocomplete="current-password" label="Senha atual" required />
        <FormField v-model="pwd.next" type="password" autocomplete="new-password" label="Nova senha" hint="Mínimo de 10 caracteres." required />
      </div>
      <BaseButton type="submit" :loading="busy === 'pwd'">Alterar senha</BaseButton>
    </form>

    <section class="space-y-3 border-t border-line pt-6">
      <h3 class="font-semibold">Seus dados</h3>
      <p class="text-muted">Tudo fica nesta instância. Exporte para guardar uma cópia ou levar para outro lugar.</p>
      <div class="flex flex-wrap gap-2">
        <a :href="settingsApi.exportUrl" class="inline-flex h-10 items-center gap-2 rounded-lg border border-line px-4 hover:bg-surface-2">
          <Download class="size-4" /> Exportar (JSON)
        </a>
        <BaseButton variant="danger" :loading="busy === 'wipe'" @click="wipe"><TriangleAlert class="size-4" /> Apagar todos os dados</BaseButton>
      </div>
    </section>
  </div>
</template>
