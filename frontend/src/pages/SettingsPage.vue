<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AiSettings from '@/components/settings/AiSettings.vue'
import EmailSettings from '@/components/settings/EmailSettings.vue'
import GeneralSettings from '@/components/settings/GeneralSettings.vue'
import SourcesSettings from '@/components/settings/SourcesSettings.vue'
import TelegramSettings from '@/components/settings/TelegramSettings.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useAsync } from '@/composables/useAsync'
import { settingsApi } from '@/services/api'

const route = useRoute()
const router = useRouter()
const settings = useAsync(() => settingsApi.get(), { keepDataOnError: true })
onMounted(() => settings.execute())

const tabs = [
  { id: 'ia', label: 'IA', component: AiSettings },
  { id: 'telegram', label: 'Telegram', component: TelegramSettings },
  { id: 'email', label: 'E-mail', component: EmailSettings },
  { id: 'fontes', label: 'Fontes de vagas', component: SourcesSettings },
  { id: 'geral', label: 'Geral e dados', component: GeneralSettings },
] as const

// A aba fica na URL: links do painel abrem direto a aba certa.
const active = computed(() => tabs.find((t) => t.id === route.query.aba) ?? tabs[0])
const select = (id: string) => router.replace({ query: { aba: id } })
</script>

<template>
  <div class="space-y-5">
    <div class="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <div class="flex gap-1 border-b border-line" role="tablist">
        <button
          v-for="t in tabs"
          :key="t.id"
          type="button"
          role="tab"
          :aria-selected="active.id === t.id"
          class="-mb-px shrink-0 border-b-2 px-3 py-2 text-sm"
          :class="active.id === t.id ? 'border-brand font-medium' : 'border-transparent text-muted hover:text-ink'"
          @click="select(t.id)"
        >
          {{ t.label }}
        </button>
      </div>
    </div>

    <SkeletonBlock v-if="!settings.data.value && !settings.error.value" class="h-72" />
    <BaseCard v-else-if="settings.error.value && !settings.data.value">
      <ErrorState :error="settings.error.value" :retrying="settings.loading.value" @retry="settings.execute()" />
    </BaseCard>
    <BaseCard v-else-if="settings.data.value">
      <!-- key: recria o formulário com os valores salvos após cada alteração -->
      <component :is="active.component" :key="active.id" :settings="settings.data.value" @saved="settings.execute()" />
    </BaseCard>
  </div>
</template>
