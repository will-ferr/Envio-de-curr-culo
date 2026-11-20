<script setup lang="ts">
import { computed } from 'vue'
import { CircleAlert, OctagonX, ShieldCheck } from 'lucide-vue-next'
import type { Issue } from '@/types/api'

const props = defineProps<{ issues: Issue[] }>()
const errors = computed(() => props.issues.filter((i) => i.severity === 'error'))
const warnings = computed(() => props.issues.filter((i) => i.severity === 'warning'))
</script>

<template>
  <div v-if="!issues.length" class="flex items-center gap-2 rounded-lg bg-success-soft px-3 py-2 text-sm text-success">
    <ShieldCheck class="size-4 shrink-0" /> Tudo confere com o seu perfil.
  </div>
  <div v-else class="space-y-2">
    <div v-if="errors.length" role="alert" class="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
      <p class="flex items-center gap-2 font-medium"><OctagonX class="size-4" /> Corrija antes de aprovar</p>
      <ul class="mt-1 list-disc pl-6">
        <li v-for="i in errors" :key="i.message">{{ i.message }}</li>
      </ul>
    </div>
    <div v-if="warnings.length" class="rounded-lg bg-brand-soft px-3 py-2 text-sm text-ink">
      <p class="flex items-center gap-2 font-medium"><CircleAlert class="size-4 text-brand" /> Confira antes de enviar</p>
      <ul class="mt-1 list-disc pl-6">
        <li v-for="i in warnings" :key="i.message">{{ i.message }}</li>
      </ul>
    </div>
  </div>
</template>
