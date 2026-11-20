<script setup lang="ts">
import { RouterView } from 'vue-router'
import ToastContainer from '@/components/ui/ToastContainer.vue'
import { useThemeStore } from '@/stores/theme'

useThemeStore()
</script>

<template>
  <RouterView />
  <ToastContainer />
</template>
