<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { RouterView } from 'vue-router'
import Sidebar from '@/components/common/Sidebar.vue'
import { useSessionStore } from '@/stores/session'
import { checkBackend, getBackendStartCommand, useBackendState } from '@/composables/useBackend'

const sessionStore = useSessionStore()
const backendState = useBackendState()
const mobileMenuOpen = ref(false)

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
    <!-- Mobile hamburger -->
    <button
      class="fixed top-3 left-3 z-50 md:hidden glass-btn !p-2 !rounded-lg"
      @click="mobileMenuOpen = !mobileMenuOpen"
    >
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
        <path v-if="!mobileMenuOpen" d="M3 5h14M3 10h14M3 15h14" />
        <path v-else d="M5 5l10 10M15 5L5 15" />
      </svg>
    </button>

    <!-- Mobile overlay -->
    <div
      v-if="mobileMenuOpen"
      class="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm md:hidden"
      @click="mobileMenuOpen = false"
    />

    <Sidebar :mobile-open="mobileMenuOpen" @close-mobile="mobileMenuOpen = false" />
    <main class="flex-1 overflow-auto p-6 max-md:p-4 max-md:pt-14" style="margin-left: var(--sidebar-width)">
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
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<style>
/* Mobile: override sidebar margin */
@media (max-width: 767px) {
  main {
    margin-left: 0 !important;
  }
}
</style>
