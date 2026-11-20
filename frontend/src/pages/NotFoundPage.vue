<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { FileQuestion } from 'lucide-vue-next'
</script>

<template>
  <div class="flex min-h-dvh flex-col items-center justify-center px-6 text-center">
    <div class="mb-6 flex size-14 items-center justify-center rounded-full bg-brand-soft text-brand">
      <FileQuestion class="size-7" aria-hidden="true" />
    </div>
    <h1 class="text-2xl font-semibold tracking-tight">Página não encontrada</h1>
    <p class="mt-2 max-w-sm text-sm text-muted">O endereço acessado não existe.</p>
    <RouterLink
      to="/"
      class="mt-6 inline-flex h-10 items-center rounded-lg bg-brand px-4 text-sm font-medium text-brand-ink hover:brightness-110"
    >
      Voltar ao painel
    </RouterLink>
  </div>
</template>
