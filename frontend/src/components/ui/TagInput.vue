<script setup lang="ts">
import { ref, useId } from 'vue'
import { X } from 'lucide-vue-next'

defineProps<{ label: string; hint?: string; placeholder?: string }>()
const tags = defineModel<string[]>({ required: true })
const draft = ref('')
const id = useId()

function add() {
  // Aceita vários itens colados de uma vez, separados por vírgula.
  for (const part of draft.value.split(',')) {
    const value = part.trim()
    if (value && !tags.value.some((t) => t.toLowerCase() === value.toLowerCase())) {
      tags.value = [...tags.value, value]
    }
  }
  draft.value = ''
}

function remove(i: number) {
  tags.value = tags.value.filter((_, idx) => idx !== i)
}

function onBackspace() {
  if (!draft.value && tags.value.length) remove(tags.value.length - 1)
}
</script>

<template>
  <div>
    <label :for="id" class="text-sm font-medium">{{ label }}</label>
    <div
      class="mt-1 flex flex-wrap items-center gap-1.5 rounded-lg border border-line bg-surface px-2 py-1.5 focus-within:border-brand"
    >
      <span
        v-for="(tag, i) in tags"
        :key="tag"
        class="inline-flex items-center gap-1 rounded-md bg-surface-2 px-2 py-0.5 text-sm"
      >
        {{ tag }}
        <button type="button" class="text-muted hover:text-danger" :aria-label="`Remover ${tag}`" @click="remove(i)">
          <X class="size-3.5" />
        </button>
      </span>
      <input
        :id="id"
        v-model="draft"
        :placeholder="tags.length ? '' : placeholder"
        class="min-w-32 flex-1 bg-transparent px-1 py-0.5 text-sm outline-none"
        @keydown.enter.prevent="add"
        @keydown.backspace="onBackspace"
        @blur="add"
      />
    </div>
    <p v-if="hint" class="mt-1 text-xs text-muted">{{ hint }}</p>
  </div>
</template>
