<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BrandLogo from '@/components/BrandLogo.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import FormField from '@/components/ui/FormField.vue'
import { useAuthStore } from '@/stores/auth'
import { toApiError } from '@/utils/apiError'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const form = reactive({ email: '', password: '' })
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(form.email, form.password)
    // Só caminhos internos: "//site.com" seria um redirecionamento para fora.
    const raw = typeof route.query.next === 'string' ? route.query.next : ''
    const next = raw.startsWith('/') && !raw.startsWith('//') ? raw : '/'
    router.push(next)
  } catch (e) {
    error.value = toApiError(e).message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-dvh items-center justify-center bg-sidebar px-4">
    <div class="w-full max-w-sm">
      <div class="mb-6 flex justify-center"><BrandLogo /></div>
      <form class="space-y-4 rounded-2xl border border-line bg-surface p-6 shadow-xl" @submit.prevent="submit">
        <h1 class="text-lg font-semibold">Entrar</h1>
        <FormField v-model="form.email" label="E-mail" type="email" autocomplete="email" required />
        <FormField v-model="form.password" label="Senha" type="password" autocomplete="current-password" required />
        <p v-if="error" role="alert" class="text-sm text-danger">{{ error }}</p>
        <BaseButton type="submit" class="w-full" :loading="loading">Entrar</BaseButton>
      </form>
    </div>
  </div>
</template>
