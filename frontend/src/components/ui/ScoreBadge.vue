<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ score: number | null; size?: 'sm' | 'lg' }>()

const tone = computed(() => {
  if (props.score === null) return 'bg-surface-2 text-muted'
  if (props.score >= 70) return 'bg-success-soft text-success'
  if (props.score >= 45) return 'bg-brand-soft text-brand'
  return 'bg-danger-soft text-danger'
})
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center justify-center rounded-full font-semibold tabular-nums"
    :class="[tone, size === 'lg' ? 'size-16 text-xl' : 'h-7 min-w-12 px-2 text-xs']"
    :aria-label="score === null ? 'Ainda não analisada' : `Compatibilidade ${score}%`"
  >
    {{ score === null ? '—' : `${score}%` }}
  </span>
</template>
