<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { Menu, Moon, Sun } from 'lucide-vue-next'
import SideNav from '@/components/SideNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const drawerOpen = ref(false)

watch(
  () => route.fullPath,
  () => (drawerOpen.value = false),
)

async function logout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="min-h-dvh lg:pl-64">
    <aside class="fixed inset-y-0 left-0 hidden w-64 lg:block">
      <SideNav :user-name="auth.user?.name" @logout="logout" />
    </aside>

    <Transition
      enter-from-class="opacity-0"
      enter-active-class="transition-opacity duration-200"
      leave-to-class="opacity-0"
      leave-active-class="transition-opacity duration-150"
    >
      <div v-if="drawerOpen" class="fixed inset-0 z-40 lg:hidden">
        <div class="absolute inset-0 bg-black/50" aria-hidden="true" @click="drawerOpen = false" />
        <aside id="mobile-nav" class="relative h-full w-72 max-w-[85vw]" aria-label="Menu">
          <SideNav :user-name="auth.user?.name" closable @close="drawerOpen = false" @logout="logout" />
        </aside>
      </div>
    </Transition>

    <header
      class="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-surface/90 px-4 backdrop-blur sm:px-6"
    >
      <button
        type="button"
        class="rounded-lg p-2 text-muted hover:bg-surface-2 lg:hidden"
        aria-label="Abrir menu"
        aria-controls="mobile-nav"
        :aria-expanded="drawerOpen"
        @click="drawerOpen = true"
      >
        <Menu class="size-5" />
      </button>
      <h1 class="truncate text-base font-semibold">{{ route.meta.title }}</h1>
      <button
        type="button"
        class="ml-auto rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-ink"
        :aria-label="theme.theme === 'dark' ? 'Usar tema claro' : 'Usar tema escuro'"
        @click="theme.toggle()"
      >
        <Sun v-if="theme.theme === 'dark'" class="size-5" />
        <Moon v-else class="size-5" />
      </button>
    </header>

    <main class="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
      <RouterView />
    </main>
  </div>
</template>
