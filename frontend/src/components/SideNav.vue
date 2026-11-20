<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'
import { LogOut, X } from 'lucide-vue-next'
import BrandLogo from '@/components/BrandLogo.vue'
import { navigation } from '@/router'

defineProps<{ userName?: string; closable?: boolean }>()
defineEmits<{ close: []; logout: [] }>()

const route = useRoute()
const isActive = (to: string) => (to === '/' ? route.path === '/' : route.path.startsWith(to))
</script>

<template>
  <div class="flex h-full flex-col bg-sidebar">
    <div class="flex h-16 items-center justify-between px-6">
      <BrandLogo />
      <button
        v-if="closable"
        type="button"
        class="rounded-lg p-2 text-sidebar-ink hover:bg-sidebar-active"
        aria-label="Fechar menu"
        @click="$emit('close')"
      >
        <X class="size-5" />
      </button>
    </div>
    <nav aria-label="Navegação principal" class="flex flex-1 flex-col gap-1 px-3">
      <RouterLink
        v-for="item in navigation"
        :key="item.to"
        :to="item.to"
        class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-ink transition-colors hover:bg-sidebar-active hover:text-white"
        :class="{ 'bg-sidebar-active !text-white': isActive(item.to) }"
        :aria-current="isActive(item.to) ? 'page' : undefined"
      >
        <component :is="item.icon" class="size-4.5 shrink-0" aria-hidden="true" />
        {{ item.label }}
      </RouterLink>
    </nav>
    <div class="border-t border-white/10 p-3">
      <p v-if="userName" class="truncate px-3 text-xs text-sidebar-ink">{{ userName }}</p>
      <button
        type="button"
        class="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-sidebar-ink hover:bg-sidebar-active hover:text-white"
        @click="$emit('logout')"
      >
        <LogOut class="size-4.5" aria-hidden="true" /> Sair
      </button>
    </div>
  </div>
</template>
