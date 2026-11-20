import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/services/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<{ name: string; email: string } | null>(null)
  const checked = ref(false)

  /** Descobre se há sessão válida (cookie httpOnly — o JS não consegue lê-lo). */
  async function load() {
    try {
      user.value = await authApi.me()
    } catch {
      user.value = null
    } finally {
      checked.value = true
    }
  }

  async function login(email: string, password: string) {
    user.value = await authApi.login(email, password)
    checked.value = true
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      user.value = null
    }
  }

  function clear() {
    user.value = null
  }

  return { user, checked, load, login, logout, clear }
})
