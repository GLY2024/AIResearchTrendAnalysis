<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import Sidebar from '@/components/common/Sidebar.vue'
import { useSessionStore } from '@/stores/session'

const sessionStore = useSessionStore()

onMounted(async () => {
  await sessionStore.fetchSessions()
})
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-[var(--bg-primary)]">
    <Sidebar />
    <main class="flex-1 overflow-auto p-6">
      <RouterView />
    </main>
  </div>
</template>
