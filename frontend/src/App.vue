<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { RouterView } from 'vue-router'
import Sidebar from '@/components/common/Sidebar.vue'
import { useSessionStore } from '@/stores/session'
import { checkBackend, getBackendStartCommand, useBackendState } from '@/composables/useBackend'

const sessionStore = useSessionStore()
const backendState = useBackendState()

let healthPoller: ReturnType<typeof setInterval> | null = null

async function ensureBackendStatus(force = false) {
  console.log('[ARTA] Checking backend connection...')
  await checkBackend(force)
}

watch(
  () => backendState.status,
  async (status) => {
    if (status !== 'online') return

    try {
      await sessionStore.fetchSessions()
      console.log('[ARTA] Sessions loaded:', sessionStore.sessions.length)
    } catch (err) {
      console.error('[ARTA] Failed to load sessions:', err)
    }
  },
  { immediate: false }
)

onMounted(async () => {
  console.log('[ARTA] App mounted, initializing...')
  await ensureBackendStatus(true)
  healthPoller = setInterval(() => {
    void ensureBackendStatus(false)
  }, 15000)
})

onUnmounted(() => {
  if (healthPoller) clearInterval(healthPoller)
})
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-[var(--bg-primary)]">
    <Sidebar />
    <main class="flex-1 overflow-auto p-6" style="margin-left: var(--sidebar-width)">
      <!-- Backend connection banner -->
      <div
        v-if="backendState.status === 'offline'"
        class="mb-4 p-4 rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/10 text-sm"
      >
        <div class="flex items-center justify-between">
          <div>
            <p class="font-semibold text-[var(--error)]">Backend Not Connected</p>
            <p class="text-[var(--text-secondary)] mt-1">
              Cannot reach the backend server at port 8721.
              <span v-if="backendState.error" class="text-[var(--text-muted)]">({{ backendState.error }})</span>
            </p>
            <p class="text-[var(--text-muted)] mt-1 text-xs">
              Start the backend with: {{ getBackendStartCommand() }}
            </p>
          </div>
          <button class="glass-btn text-xs shrink-0 ml-4" @click="ensureBackendStatus(true)">
            Retry
          </button>
        </div>
      </div>
      <div
        v-if="backendState.status === 'checking'"
        class="mb-4 p-3 rounded-xl border border-[var(--info)]/30 bg-[var(--info)]/10 text-sm text-[var(--text-secondary)] flex items-center gap-2"
      >
        <span class="inline-block w-2 h-2 rounded-full bg-[var(--info)] animate-pulse" />
        Connecting to backend...
      </div>
      <RouterView />
    </main>
  </div>
</template>
