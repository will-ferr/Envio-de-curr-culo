<script setup lang="ts">
import { reactive, ref } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import FormField from '@/components/ui/FormField.vue'
import { settingsApi } from '@/services/api'
import { useToastStore } from '@/stores/toast'
import type { SettingsOut } from '@/types/api'
import { toApiError } from '@/utils/apiError'

const props = defineProps<{ settings: SettingsOut }>()
const emit = defineEmits<{ saved: [] }>()
const toast = useToastStore()
const s = props.settings

const smtp = reactive({
  host: s.smtp.host ?? '',
  port: s.smtp.port,
  username: s.smtp.username ?? '',
  password: '',
  security: s.smtp.security,
  from_email: s.smtp.from_email ?? '',
  from_name: s.smtp.from_name ?? '',
})
const imap = reactive({
  host: s.imap.host ?? '',
  port: s.imap.port,
  username: s.imap.username ?? '',
  password: '',
  folder: s.imap.folder,
  enabled: s.imap.enabled,
  sender_filter: s.imap.sender_filter ?? '',
})
const busy = ref('')

async function act(name: string, fn: () => Promise<unknown>, ok: string) {
  busy.value = name
  try {
    await fn()
    toast.success(ok)
    emit('saved')
  } catch (e) {
    const err = toApiError(e)
    toast.error('E-mail', err.fields[0] ? `${err.fields[0].field}: ${err.fields[0].message}` : err.message)
  } finally {
    busy.value = ''
  }
}

/** Preenche servidores conhecidos para poupar a pessoa de procurar. */
function preset(kind: 'gmail' | 'outlook') {
  const p = kind === 'gmail'
    ? { smtp: 'smtp.gmail.com', imap: 'imap.gmail.com' }
    : { smtp: 'smtp.office365.com', imap: 'outlook.office365.com' }
  Object.assign(smtp, { host: p.smtp, port: 587, security: 'starttls' })
  Object.assign(imap, { host: p.imap, port: 993 })
}
</script>

<template>
  <div class="space-y-8 text-sm">
    <div class="rounded-lg bg-surface-2 p-4">
      <p class="font-medium">Envio pela sua própria conta de e-mail.</p>
      <p class="mt-1 text-muted">
        No Gmail, ative a verificação em duas etapas e gere uma <b>senha de app</b> — a senha normal não funciona.
        Atalhos:
        <button type="button" class="text-brand hover:underline" @click="preset('gmail')">Gmail</button> ·
        <button type="button" class="text-brand hover:underline" @click="preset('outlook')">Outlook</button>
      </p>
    </div>

    <form class="space-y-4" @submit.prevent="act('smtp', () => settingsApi.saveSmtp({ ...smtp, password: smtp.password || null }), 'SMTP salvo')">
      <h3 class="font-semibold">Envio (SMTP)</h3>
      <div class="grid gap-4 sm:grid-cols-[1fr_7rem_10rem]">
        <FormField v-model="smtp.host" label="Servidor" placeholder="smtp.gmail.com" required />
        <FormField v-model.number="smtp.port" type="number" label="Porta" />
        <FormField v-model="smtp.security" as="select" label="Segurança">
          <option value="starttls">STARTTLS</option><option value="ssl">SSL/TLS</option><option value="none">Nenhuma</option>
        </FormField>
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <FormField v-model="smtp.username" label="Usuário" autocomplete="off" required />
        <FormField
          v-model="smtp.password"
          type="password"
          autocomplete="new-password"
          label="Senha (de app)"
          :placeholder="s.smtp.password.configured ? '•••••••• (mantida se vazio)' : ''"
        />
        <FormField v-model="smtp.from_email" type="email" label="E-mail do remetente" required />
        <FormField v-model="smtp.from_name" label="Nome do remetente" />
      </div>
      <div class="flex gap-2">
        <BaseButton type="submit" :loading="busy === 'smtp'">Salvar</BaseButton>
        <BaseButton variant="secondary" :loading="busy === 'test'" @click="act('test', settingsApi.testSmtp, 'Conexão SMTP funcionando')">Testar conexão</BaseButton>
      </div>
    </form>

    <form class="space-y-4 border-t border-line pt-6" @submit.prevent="act('imap', () => settingsApi.saveImap({ ...imap, password: imap.password || null }), 'IMAP salvo')">
      <h3 class="font-semibold">Alertas de vaga por e-mail (IMAP)</h3>
      <p class="text-muted">
        Lê e-mails recentes (sem marcar como lidos) e a IA extrai as vagas. Use o filtro de remetente para olhar só
        os alertas (ex.: <code>jobs-noreply@linkedin.com</code>).
      </p>
      <label class="flex items-center gap-2"><input v-model="imap.enabled" type="checkbox" /> Ativar leitura de alertas</label>
      <div class="grid gap-4 sm:grid-cols-[1fr_7rem]">
        <FormField v-model="imap.host" label="Servidor" placeholder="imap.gmail.com" />
        <FormField v-model.number="imap.port" type="number" label="Porta" />
        <FormField v-model="imap.username" label="Usuário" autocomplete="off" />
        <FormField
          v-model="imap.password"
          type="password"
          autocomplete="new-password"
          label="Senha (de app)"
          :placeholder="s.imap.password.configured ? '•••••••• (mantida se vazio)' : ''"
        />
        <FormField v-model="imap.folder" label="Pasta" />
        <FormField v-model="imap.sender_filter" label="Somente do remetente" />
      </div>
      <BaseButton type="submit" :loading="busy === 'imap'">Salvar</BaseButton>
    </form>
  </div>
</template>
