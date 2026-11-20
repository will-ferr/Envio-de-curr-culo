<script setup lang="ts">
import { computed, useId } from 'vue'

/**
 * Campo de formulário com rótulo, ajuda e erro. `as` escolhe input, textarea ou select;
 * para select, passe as opções pelo slot padrão.
 */
const props = withDefaults(
  defineProps<{
    label: string
    as?: 'input' | 'textarea' | 'select'
    type?: string
    hint?: string
    error?: string
    rows?: number
    placeholder?: string
    autocomplete?: string
    required?: boolean
  }>(),
  { as: 'input', type: 'text', rows: 4, hint: undefined, error: undefined, placeholder: undefined, autocomplete: undefined },
)
const model = defineModel<string | number | null>()
const id = useId()
const describedBy = computed(() => (props.error ? `${id}-err` : props.hint ? `${id}-hint` : undefined))
const base =
  'mt-1 block w-full rounded-lg border bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted/70 ' +
  'focus:border-brand focus:outline-none'
</script>

<template>
  <div>
    <label :for="id" class="text-sm font-medium">
      {{ label }}<span v-if="required" class="text-danger" aria-hidden="true"> *</span>
    </label>
    <textarea
      v-if="as === 'textarea'"
      :id="id"
      v-model="model"
      :rows="rows"
      :placeholder="placeholder"
      :required="required"
      :aria-invalid="!!error"
      :aria-describedby="describedBy"
      :class="[base, error ? 'border-danger' : 'border-line']"
    />
    <select
      v-else-if="as === 'select'"
      :id="id"
      v-model="model"
      :required="required"
      :aria-describedby="describedBy"
      :class="[base, error ? 'border-danger' : 'border-line']"
    >
      <slot />
    </select>
    <input
      v-else
      :id="id"
      v-model="model"
      :type="type"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :required="required"
      :aria-invalid="!!error"
      :aria-describedby="describedBy"
      :class="[base, error ? 'border-danger' : 'border-line']"
    />
    <p v-if="error" :id="`${id}-err`" class="mt-1 text-xs text-danger">{{ error }}</p>
    <p v-else-if="hint" :id="`${id}-hint`" class="mt-1 text-xs text-muted">{{ hint }}</p>
  </div>
</template>
