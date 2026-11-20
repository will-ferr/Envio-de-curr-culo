<script setup lang="ts">
import { computed, reactive } from 'vue'
import { ArrowDown, ArrowUp } from 'lucide-vue-next'
import FormField from '@/components/ui/FormField.vue'
import type { Profile, ResumeContent } from '@/types/api'

/**
 * Editor do currículo adaptado. Competências, itens de experiência e projetos só podem
 * ser ESCOLHIDOS e REORDENADOS a partir do perfil — não há campo livre para inventar.
 * Texto livre existe apenas em título e resumo (validados no servidor).
 */
const props = defineProps<{ content: ResumeContent; profile: Profile }>()
const draft = reactive<ResumeContent>(JSON.parse(JSON.stringify(props.content)))

function move<T>(list: T[], i: number, dir: -1 | 1) {
  const j = i + dir
  if (j < 0 || j >= list.length) return
  ;[list[i], list[j]] = [list[j] as T, list[i] as T]
}

function toggle(list: string[], value: string) {
  const i = list.indexOf(value)
  if (i >= 0) list.splice(i, 1)
  else list.push(value)
}

const unusedSkills = computed(() => props.profile.skills.map((s) => s.name).filter((n) => !draft.skills.includes(n)))
const unusedProjects = computed(() => props.profile.projects.filter((p) => !draft.project_ids.includes(p.id)))
const projectName = (id: string) => props.profile.projects.find((p) => p.id === id)?.name ?? id

function expEntry(id: string) {
  return draft.experiences.find((e) => e.id === id)
}
function toggleExperience(id: string) {
  const i = draft.experiences.findIndex((e) => e.id === id)
  if (i >= 0) draft.experiences.splice(i, 1)
  else {
    const original = props.profile.experiences.find((e) => e.id === id)
    draft.experiences.push({ id, highlights: [...(original?.highlights ?? [])] })
  }
}

defineExpose({ value: () => JSON.parse(JSON.stringify(draft)) as ResumeContent })
</script>

<template>
  <div class="space-y-6">
    <FormField v-model="draft.headline" label="Título profissional" />
    <FormField v-model="draft.summary" as="textarea" :rows="5" label="Resumo" hint="Cite apenas fatos que estão no seu perfil." />

    <section>
      <h3 class="text-sm font-semibold">Competências (na ordem em que aparecem)</h3>
      <ol class="mt-2 space-y-1">
        <li v-for="(s, i) in draft.skills" :key="s" class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-1.5 text-sm">
          <span class="flex-1">{{ s }}</span>
          <button type="button" :aria-label="`Subir ${s}`" class="text-muted hover:text-ink" @click="move(draft.skills, i, -1)"><ArrowUp class="size-4" /></button>
          <button type="button" :aria-label="`Descer ${s}`" class="text-muted hover:text-ink" @click="move(draft.skills, i, 1)"><ArrowDown class="size-4" /></button>
          <button type="button" class="text-xs text-danger hover:underline" @click="toggle(draft.skills, s)">Remover</button>
        </li>
      </ol>
      <div v-if="unusedSkills.length" class="mt-2 flex flex-wrap gap-1.5">
        <span class="text-xs text-muted">Adicionar do perfil:</span>
        <button
          v-for="s in unusedSkills"
          :key="s"
          type="button"
          class="rounded-md border border-dashed border-line px-2 py-0.5 text-xs hover:border-brand"
          @click="draft.skills.push(s)"
        >
          + {{ s }}
        </button>
      </div>
    </section>

    <section>
      <h3 class="text-sm font-semibold">Experiências</h3>
      <div v-for="e in profile.experiences" :key="e.id" class="mt-2 rounded-lg border border-line p-3">
        <label class="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" :checked="!!expEntry(e.id)" @change="toggleExperience(e.id)" />
          {{ e.role }} — {{ e.company }}
        </label>
        <ul v-if="expEntry(e.id)" class="mt-2 space-y-1 pl-6">
          <li v-for="h in e.highlights" :key="h" class="flex items-start gap-2 text-sm">
            <input
              :id="`${e.id}-${h.slice(0, 20)}`"
              type="checkbox"
              class="mt-1"
              :checked="expEntry(e.id)!.highlights.includes(h)"
              @change="toggle(expEntry(e.id)!.highlights, h)"
            />
            <label :for="`${e.id}-${h.slice(0, 20)}`">{{ h }}</label>
          </li>
        </ul>
      </div>
    </section>

    <section v-if="profile.projects.length">
      <h3 class="text-sm font-semibold">Projetos</h3>
      <ol class="mt-2 space-y-1">
        <li v-for="(id, i) in draft.project_ids" :key="id" class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-1.5 text-sm">
          <span class="flex-1">{{ projectName(id) }}</span>
          <button type="button" :aria-label="`Subir ${projectName(id)}`" class="text-muted hover:text-ink" @click="move(draft.project_ids, i, -1)"><ArrowUp class="size-4" /></button>
          <button type="button" :aria-label="`Descer ${projectName(id)}`" class="text-muted hover:text-ink" @click="move(draft.project_ids, i, 1)"><ArrowDown class="size-4" /></button>
          <button type="button" class="text-xs text-danger hover:underline" @click="toggle(draft.project_ids, id)">Remover</button>
        </li>
      </ol>
      <div v-if="unusedProjects.length" class="mt-2 flex flex-wrap gap-1.5">
        <button
          v-for="p in unusedProjects"
          :key="p.id"
          type="button"
          class="rounded-md border border-dashed border-line px-2 py-0.5 text-xs hover:border-brand"
          @click="draft.project_ids.push(p.id)"
        >
          + {{ p.name }}
        </button>
      </div>
    </section>
  </div>
</template>
