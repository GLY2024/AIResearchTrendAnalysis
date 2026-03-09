<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterView } from 'vue-router'
import Sidebar from '@/components/common/Sidebar.vue'
import { useSessionStore } from '@/stores/session'
import { healthApi } from '@/composables/useApi'

const sessionStore = useSessionStore()
const backendStatus = ref<'checking' | 'online' | 'offline'>('checking')
const backendError = ref('')

async function checkBackend() {
  backendStatus.value = 'checking'
  backendError.value = ''
  console.log('[ARTA] Checking backend connection...')
  try {
    const data = await healthApi.check()
    console.log('[ARTA] Backend online:', data)
    backendStatus.value = 'online'
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    console.error('[ARTA] Backend offline:', msg)
    backendStatus.value = 'offline'
    backendError.value = msg
  }
}

onMounted(async () => {
  console.log('[ARTA] App mounted, initializing...')
  await checkBackend()
  if (backendStatus.value === 'online') {
    try {
      await sessionStore.fetchSessions()
      console.log('[ARTA] Sessions loaded:', sessionStore.sessions.length)
    } catch (err) {
      console.error('[ARTA] Failed to load sessions:', err)
    }
  }
})
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-[var(--bg-primary)]">
    <Sidebar />
    <main class="flex-1 overflow-auto p-6" style="margin-left: var(--sidebar-width)">
      <!-- Backend connection banner -->
      <div
        v-if="backendStatus === 'offline'"
        class="mb-4 p-4 rounded-xl border border-[var(--error)]/30 bg-[var(--error)]/10 text-sm"
      >
        <div class="flex items-center justify-between">
          <div>
            <p class="font-semibold text-[var(--error)]">Backend Not Connected</p>
            <p class="text-[var(--text-secondary)] mt-1">
              Cannot reach the backend server at port 8721.
              <span v-if="backendError" class="text-[var(--text-muted)]">({{ backendError }})</span>
            </p>
            <p class="text-[var(--text-muted)] mt-1 text-xs">
              If running in dev mode, start the backend with: uv run uvicorn app.main:app --port 8721
            </p>
          </div>
          <button class="glass-btn text-xs shrink-0 ml-4" @click="checkBackend">
            Retry
          </button>
        </div>
      </div>
      <div
        v-if="backendStatus === 'checking'"
        class="mb-4 p-3 rounded-xl border border-[var(--info)]/30 bg-[var(--info)]/10 text-sm text-[var(--text-secondary)] flex items-center gap-2"
      >
        <span class="inline-block w-2 h-2 rounded-full bg-[var(--info)] animate-pulse" />
        Connecting to backend...
      </div>
      <RouterView />
    </main>
  </div>
</template>
