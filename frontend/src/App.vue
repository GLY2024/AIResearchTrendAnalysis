<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import Sidebar from '@/components/common/Sidebar.vue'
import { useSessionStore } from '@/stores/session'
import { checkBackend, getBackendStartCommand, useBackendState } from '@/composables/useBackend'

const route = useRoute()
const sessionStore = useSessionStore()
const backendState = useBackendState()
const mobileMenuOpen = ref(false)

let healthPoller: ReturnType<typeof setInterval> | null = null

const pageMeta = computed(() => {
  const name = route.name as string | undefined
  const map: Record<string, { eyebrow: string; title: string }> = {
    chat: { eyebrow: 'Conversation', title: 'Research cockpit' },
    plan: { eyebrow: 'Search design', title: 'Acquisition pipeline' },
    library: { eyebrow: 'Corpus', title: 'Paper collection' },
    analysis: { eyebrow: 'Insight engine', title: 'Analysis studio' },
    report: { eyebrow: 'Publishing', title: 'Report room' },
    settings: { eyebrow: 'Configuration', title: 'Model control panel' },
  }
  return map[name ?? ''] ?? { eyebrow: 'Workspace', title: 'ARTA workbench' }
})

const backendBadgeClass = computed(() => {
  if (backendState.status === 'online') return 'capsule capsule--success'
  if (backendState.status === 'checking') return 'capsule capsule--warning'
  return 'capsule capsule--error'
})

const backendLabel = computed(() => {
  if (backendState.status === 'online') return 'Backend online'
  if (backendState.status === 'checking') return 'Checking backend'
  return 'Backend offline'
})

async function ensureBackendStatus(force = false) {
  await checkBackend(force)
}

watch(
  () => backendState.status,
  async (status) => {
    if (status !== 'online') return

    try {
      await sessionStore.fetchSessions()
    } catch (err) {
      console.error('[ARTA] Failed to load sessions:', err)
    }
  },
  { immediate: false },
)

watch(
  () => route.fullPath,
  () => {
    mobileMenuOpen.value = false
  },
)

onMounted(async () => {
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
  <div class="app-shell">
    <button
      class="fixed left-4 top-4 z-50 md:hidden glass-btn !h-11 !w-11 !rounded-2xl !p-0"
      @click="mobileMenuOpen = !mobileMenuOpen"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linecap="round"
      >
        <path v-if="!mobileMenuOpen" d="M3 5h14M3 10h14M3 15h14" />
        <path v-else d="M5 5l10 10M15 5L5 15" />
      </svg>
    </button>

    <div
      v-if="mobileMenuOpen"
      class="fixed inset-0 z-30 bg-black/55 backdrop-blur-sm md:hidden"
      @click="mobileMenuOpen = false"
    />

    <Sidebar :mobile-open="mobileMenuOpen" @close-mobile="mobileMenuOpen = false" />

    <main class="app-main" style="margin-left: var(--sidebar-width)">
      <div class="content-shell">
        <div class="app-topbar">
          <div>
            <p class="app-topbar__eyebrow">{{ pageMeta.eyebrow }}</p>
            <h1 class="app-topbar__title">{{ pageMeta.title }}</h1>
            <p class="mt-2 text-sm text-[var(--text-secondary)]">
              {{ sessionStore.currentSession?.title ?? 'Select or create a session to stage a live research workflow.' }}
            </p>
          </div>

          <div class="app-topbar__meta">
            <span :class="backendBadgeClass">
              <span class="inline-block h-2 w-2 rounded-full bg-current" />
              {{ backendLabel }}
            </span>
            <span class="capsule">
              Sessions
              <strong class="text-[var(--text-primary)]">{{ sessionStore.sessions.length }}</strong>
            </span>
            <span v-if="sessionStore.currentSession" class="capsule">
              Papers
              <strong class="text-[var(--text-primary)]">{{ sessionStore.currentSession.paper_count ?? 0 }}</strong>
            </span>
          </div>
        </div>

        <div
          v-if="backendState.status === 'offline'"
          class="callout callout--warm mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"
        >
          <div>
            <div class="text-sm font-semibold text-[var(--text-primary)]">Backend connection required</div>
            <div class="mt-1 text-sm text-[var(--text-secondary)]">
              ARTA cannot reach the local service on port 8721.
              <span v-if="backendState.error" class="text-[var(--text-muted)]">({{ backendState.error }})</span>
            </div>
            <div class="mt-2 text-xs text-[var(--text-muted)]">
              Start command: {{ getBackendStartCommand() }}
            </div>
          </div>
          <button class="glass-btn glass-btn-primary shrink-0" @click="ensureBackendStatus(true)">
            Retry connection
          </button>
        </div>

        <div
          v-else-if="backendState.status === 'checking'"
          class="callout callout--accent mb-5 flex items-center gap-3 text-sm text-[var(--text-secondary)]"
        >
          <span class="inline-block h-2.5 w-2.5 rounded-full bg-[var(--accent-primary)] animate-pulse" />
          Checking local backend availability...
        </div>

        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </div>
    </main>
  </div>
</template>

<style scoped>
.app-main {
  min-height: 100vh;
  overflow: auto;
  padding: 14px 24px 32px;
}

@media (max-width: 767px) {
  .app-main {
    margin-left: 0 !important;
    padding: 64px 14px 24px;
  }
}
</style>
