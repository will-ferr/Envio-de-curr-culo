<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ShieldCheck } from 'lucide-vue-next'
import BrandLogo from '@/components/BrandLogo.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import FormField from '@/components/ui/FormField.vue'
import { markSetupDone } from '@/router'
import { authApi } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { toApiError } from '@/utils/apiError'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ name: '', email: '', password: '', confirm: '' })
const errors = reactive<Record<string, string>>({})
const generalError = ref('')
const saving = ref(false)

async function submit() {
  Object.keys(errors).forEach((k) => delete errors[k])
  generalError.value = ''
  if (form.password.length < 10) errors.password = 'Use pelo menos 10 caracteres.'
  if (form.password !== form.confirm) errors.confirm = 'As senhas não conferem.'
  if (Object.keys(errors).length) return

  saving.value = true
  try {
    await authApi.createOwner({ name: form.name, email: form.email, password: form.password })
    markSetupDone()
    await auth.login(form.email, form.password)
    router.push({ name: 'dashboard', query: { boasVindas: '1' } })
  } catch (e) {
    const err = toApiError(e)
    for (const f of err.fields) errors[f.field] = f.message
    if (!err.fields.length) generalError.value = err.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="flex min-h-dvh items-center justify-center bg-sidebar px-4 py-10">
    <div class="w-full max-w-md">
      <div class="mb-6 flex justify-center"><BrandLogo /></div>
      <form class="space-y-4 rounded-2xl border border-line bg-surface p-6 shadow-xl" @submit.prevent="submit">
        <div>
          <h1 class="text-lg font-semibold">Bem-vindo! Vamos configurar sua instância</h1>
          <p class="mt-1 text-sm text-muted">
            Esta conta protege seus dados. Ela fica só neste computador — nada é enviado para servidores de terceiros.
          </p>
        </div>
        <FormField v-model="form.name" label="Seu nome" autocomplete="name" required :error="errors.name" />
        <FormField v-model="form.email" label="E-mail" type="email" autocomplete="email" required :error="errors.email" />
        <FormField
          v-model="form.password"
          label="Senha"
          type="password"
          autocomplete="new-password"
          hint="Mínimo de 10 caracteres."
          required
          :error="errors.password"
        />
        <FormField
          v-model="form.confirm"
          label="Confirme a senha"
          type="password"
          autocomplete="new-password"
          required
          :error="errors.confirm"
        />
        <p v-if="generalError" role="alert" class="text-sm text-danger">{{ generalError }}</p>
        <BaseButton type="submit" class="w-full" :loading="saving">
          <ShieldCheck v-if="!saving" class="size-4" /> Criar conta e continuar
        </BaseButton>
      </form>
    </div>
  </div>
</template>
