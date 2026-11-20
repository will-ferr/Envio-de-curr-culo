<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'

const props = withDefaults(defineProps<{ open: boolean; title: string; size?: 'md' | 'lg' }>(), { size: 'md' })
const emit = defineEmits<{ close: [] }>()
const panel = ref<HTMLElement | null>(null)

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.open) emit('close')
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

// Foco no primeiro campo ao abrir (acessibilidade e agilidade).
watch(
  () => props.open,
  (open) => {
    if (open) setTimeout(() => panel.value?.querySelector<HTMLElement>('input, textarea, select, button')?.focus())
  },
)
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-from-class="opacity-0"
      enter-active-class="transition-opacity duration-150"
      leave-to-class="opacity-0"
      leave-active-class="transition-opacity duration-100"
    >
      <div v-if="open" class="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4">
        <div class="absolute inset-0 bg-black/50" aria-hidden="true" @click="emit('close')" />
        <div
          ref="panel"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
          class="relative max-h-[92dvh] w-full overflow-y-auto rounded-t-2xl border border-line bg-surface shadow-xl sm:rounded-2xl"
          :class="size === 'lg' ? 'sm:max-w-3xl' : 'sm:max-w-lg'"
        >
          <header class="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-surface px-5 py-4">
            <h2 class="text-base font-semibold">{{ title }}</h2>
            <button
              type="button"
              class="rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-ink"
              aria-label="Fechar"
              @click="emit('close')"
            >
              <X class="size-5" />
            </button>
          </header>
          <div class="p-5">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="flex justify-end gap-2 border-t border-line px-5 py-4">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
