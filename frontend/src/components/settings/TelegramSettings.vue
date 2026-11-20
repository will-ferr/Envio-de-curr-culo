<script setup lang="ts">
import { ref } from 'vue'
import { BellRing, CheckCircle2 } from 'lucide-vue-next'
import BaseButton from '@/components/ui/BaseButton.vue'
import FormField from '@/components/ui/FormField.vue'
import { settingsApi } from '@/services/api'
import { useToastStore } from '@/stores/toast'
import type { SettingsOut } from '@/types/api'
import { toApiError } from '@/utils/apiError'

const props = defineProps<{ settings: SettingsOut }>()
const emit = defineEmits<{ saved: [] }>()
const toast = useToastStore()
const token = ref('')
const botName = ref('')
const code = ref(props.settings.telegram.pair_code)
const busy = ref('')

async function act(name: string, fn: () => Promise<void>) {
  busy.value = name
  try {
    await fn()
  } catch (e) {
    toast.error('Telegram', toApiError(e).message)
  } finally {
    busy.value = ''
  }
}

const save = () =>
  act('save', async () => {
    const r = await settingsApi.saveTelegram(token.value.trim())
    botName.value = r.bot_username
    code.value = r.pair_code
    token.value = ''
    toast.success(`Bot @${r.bot_username} conectado`, 'Agora vincule seu chat.')
    emit('saved')
  })
const newCode = () => act('code', async () => void (code.value = (await settingsApi.newPairCode()).pair_code))
const test = () => act('test', async () => {
  await settingsApi.testTelegram()
  toast.success('Mensagem de teste enviada')
})
const disconnect = () =>
  act('remove', async () => {
    if (!confirm('Desconectar o Telegram?')) return
    await settingsApi.deleteTelegram()
    code.value = null
    emit('saved')
  })
</script>

<template>
  <div class="space-y-6 text-sm">
    <ol class="list-decimal space-y-1 pl-5 text-muted">
      <li>No Telegram, abra <b>@BotFather</b>, envie <code>/newbot</code> e siga as instruções.</li>
      <li>Copie o token que ele devolver e cole abaixo.</li>
      <li>Abra o seu bot e envie <code>/start</code> seguido do código de pareamento.</li>
    </ol>

    <div v-if="settings.telegram.linked" class="flex items-center gap-2 rounded-lg bg-success-soft px-3 py-2 text-success">
      <CheckCircle2 class="size-4" /> Chat vinculado. Você recebe vagas compatíveis e pode aprovar pelo celular.
    </div>

    <form class="flex flex-col gap-2 sm:flex-row sm:items-end" @submit.prevent="save">
      <FormField
        v-model="token"
        class="flex-1"
        type="password"
        autocomplete="off"
        label="Token do bot"
        :placeholder="settings.telegram.bot_token.configured ? '•••••••• (cadastrado)' : '123456:ABC...'"
      />
      <BaseButton type="submit" :disabled="token.length < 20" :loading="busy === 'save'"><BellRing class="size-4" /> Conectar</BaseButton>
    </form>

    <div v-if="code && !settings.telegram.linked" class="rounded-xl border border-dashed border-brand p-4 text-center">
      <p class="text-muted">Envie para {{ botName ? `@${botName}` : 'o seu bot' }}:</p>
      <p class="mt-1 font-mono text-2xl font-semibold tracking-widest">/start {{ code }}</p>
      <p class="mt-2 text-xs text-muted">Depois de enviar, recarregue esta página.</p>
    </div>

    <div v-if="settings.telegram.bot_token.configured" class="flex flex-wrap gap-2">
      <BaseButton v-if="settings.telegram.linked" variant="secondary" :loading="busy === 'test'" @click="test">Enviar teste</BaseButton>
      <BaseButton variant="secondary" :loading="busy === 'code'" @click="newCode">Gerar novo código</BaseButton>
      <BaseButton variant="ghost" :loading="busy === 'remove'" @click="disconnect">Desconectar</BaseButton>
    </div>
  </div>
</template>
