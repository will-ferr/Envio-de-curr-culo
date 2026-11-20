<script setup lang="ts">
import { reactive } from 'vue'
import { Plus } from 'lucide-vue-next'
import FormField from '@/components/ui/FormField.vue'
import type { LetterContent } from '@/types/api'

const props = defineProps<{ content: LetterContent }>()
const draft = reactive<LetterContent>(JSON.parse(JSON.stringify(props.content)))

defineExpose({ value: () => JSON.parse(JSON.stringify(draft)) as LetterContent })
</script>

<template>
  <div class="space-y-4">
    <FormField v-model="draft.subject" label="Assunto do e-mail" />
    <FormField v-model="draft.greeting" label="Saudação" />
    <div v-for="(_, i) in draft.paragraphs" :key="i" class="relative">
      <FormField v-model="draft.paragraphs[i]" as="textarea" :rows="4" :label="`Parágrafo ${i + 1}`" />
      <button
        v-if="draft.paragraphs.length > 1"
        type="button"
        class="absolute top-0 right-0 text-xs text-danger hover:underline"
        @click="draft.paragraphs.splice(i, 1)"
      >
        Remover
      </button>
    </div>
    <button type="button" class="inline-flex items-center gap-1 text-sm text-brand hover:underline" @click="draft.paragraphs.push('')">
      <Plus class="size-4" /> Adicionar parágrafo
    </button>
    <FormField v-model="draft.closing" as="textarea" :rows="2" label="Encerramento" />
  </div>
</template>
