<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'

defineOptions({ name: 'AppSidebar' })

const router = useRouter()
const sessionStore = useSessionStore()
const backendState = useBackendState()
const hoveredSession = ref<number | null>(null)
const confirmDeleteId = ref<number | null>(null)
const actionError = ref('')

defineProps<{
  mobileOpen?: boolean
}>()

const emit = defineEmits<{
  closeMobile: []
}>()

const navLinks = [
  { label: 'Chat', hint: 'Discuss and steer the topic', path: '/chat', icon: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z' },
  { label: 'Search Plan', hint: 'Approve collection strategy', path: '/plan', icon: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.35-4.35' },
  { label: 'Library', hint: 'Inspect the paper corpus', path: '/library', icon: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z' },
  { label: 'Analysis', hint: 'Generate charts and insights', path: '/analysis', icon: 'M18 20V10M12 20V4M6 20v-6' },
  { label: 'Report', hint: 'Assemble the final story', path: '/report', icon: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8' },
  { label: 'Settings', hint: 'Configure providers and models', path: '/settings', icon: 'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z' },
] as const

const backendCapsuleClass = computed(() => {
  if (backendState.status === 'online') return 'capsule capsule--success'
  if (backendState.status === 'checking') return 'capsule capsule--warning'
  return 'capsule capsule--error'
})

const backendLabel = computed(() => {
  if (backendState.status === 'online') return 'Ready'
  if (backendState.status === 'checking') return 'Checking'
  return 'Offline'
})

async function handleNewSession() {
  actionError.value = ''
  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('creating a session')
    return
  }

  try {
    await sessionStore.createSession('Research Session')
    router.push('/chat')
    emit('closeMobile')
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to create session.'
    await checkBackend(true)
  }
}

async function handleDeleteSession(id: number) {
  actionError.value = ''
  if (confirmDeleteId.value === id) {
    try {
      await sessionStore.deleteSession(id)
      confirmDeleteId.value = null
    } catch (err) {
      actionError.value = err instanceof Error ? err.message : 'Failed to delete session.'
      await checkBackend(true)
    }
    return
  }

  confirmDeleteId.value = id
  setTimeout(() => {
    if (confirmDeleteId.value === id) confirmDeleteId.value = null
  }, 3000)
}

function handleNavClick() {
  emit('closeMobile')
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)

  if (diffMin < 60) return `${Math.max(diffMin, 1)}m ago`

  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`

  return date.toLocaleDateString()
}
</script>

<template>
  <aside
    class="sidebar fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-white/8 transition-transform duration-200"
    :class="[
      'max-md:-translate-x-full',
      mobileOpen ? 'max-md:translate-x-0' : '',
    ]"
    style="width: var(--sidebar-width)"
  >
    <div class="px-4 pt-4">
      <div class="rounded-[28px] border border-white/10 bg-white/[0.03] p-4">
        <div class="flex items-start justify-between gap-3">
          <div class="flex items-center gap-3">
            <div class="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--accent-primary),#257dff)] text-sm font-bold text-white shadow-[0_10px_24px_rgba(77,184,255,0.25)]">
              AR
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.22em] text-[var(--text-muted)]">ARTA</div>
              <div class="mt-1 text-base font-semibold text-[var(--text-primary)]">Research Workbench</div>
            </div>
          </div>
          <span :class="backendCapsuleClass">{{ backendLabel }}</span>
        </div>

        <p class="mt-4 text-sm leading-6 text-[var(--text-secondary)]">
          Build the full literature workflow from topic framing to final report in one place.
        </p>

        <div class="mt-4 grid grid-cols-2 gap-3">
          <div class="rounded-2xl bg-white/[0.04] p-3">
            <div class="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Sessions</div>
            <div class="mt-1 text-xl font-semibold text-[var(--text-primary)]">{{ sessionStore.sessions.length }}</div>
          </div>
          <div class="rounded-2xl bg-white/[0.04] p-3">
            <div class="text-[10px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Corpus</div>
            <div class="mt-1 text-xl font-semibold text-[var(--text-primary)]">
              {{ sessionStore.currentSession?.paper_count ?? 0 }}
            </div>
          </div>
        </div>

        <button
          class="glass-btn glass-btn-primary mt-4 w-full"
          :disabled="backendState.status !== 'online'"
          @click="handleNewSession"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M8 3v10M3 8h10" />
          </svg>
          New session
        </button>
        <p v-if="actionError" class="mt-2 text-xs text-[var(--error)]">
          {{ actionError }}
        </p>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto px-4 pb-4 pt-4">
      <div class="mb-3 flex items-center justify-between px-1">
        <div class="text-[10px] uppercase tracking-[0.18em] text-[var(--text-muted)]">Active sessions</div>
        <div class="text-[11px] text-[var(--text-muted)]">{{ sessionStore.sessions.length }}</div>
      </div>

      <div class="space-y-2">
        <button
          v-for="session in sessionStore.sessions"
          :key="session.id"
          class="session-card group w-full text-left"
          :class="session.id === sessionStore.currentSessionId ? 'session-card--active' : ''"
          @click="sessionStore.setCurrentSession(session.id); handleNavClick()"
          @mouseenter="hoveredSession = session.id"
          @mouseleave="hoveredSession = null"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm font-semibold text-[var(--text-primary)]">
                {{ session.title }}
              </div>
              <div class="mt-1 flex flex-wrap gap-2 text-[11px] text-[var(--text-muted)]">
                <span>{{ session.paper_count ?? 0 }} papers</span>
                <span>{{ formatDate(session.updated_at || session.created_at) }}</span>
              </div>
            </div>

            <button
              v-show="hoveredSession === session.id || confirmDeleteId === session.id"
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-colors"
              :class="confirmDeleteId === session.id
                ? 'bg-[var(--error)] text-white'
                : 'bg-white/[0.04] text-[var(--text-muted)] hover:bg-[var(--error)]/12 hover:text-[var(--error)]'"
              :title="confirmDeleteId === session.id ? 'Click again to confirm' : 'Delete session'"
              @click.stop="handleDeleteSession(session.id)"
            >
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M4 4l8 8M12 4l-8 8" />
              </svg>
            </button>
          </div>
        </button>

        <div
          v-if="!sessionStore.loading && sessionStore.sessions.length === 0"
          class="rounded-2xl border border-dashed border-white/10 px-4 py-6 text-center text-sm text-[var(--text-muted)]"
        >
          No sessions yet. Create one to start the demo flow.
        </div>
      </div>
    </div>

    <nav class="border-t border-white/8 px-4 pb-4 pt-4">
      <div class="mb-3 px-1 text-[10px] uppercase tracking-[0.18em] text-[var(--text-muted)]">Pipeline</div>
      <ul class="space-y-2">
        <li v-for="link in navLinks" :key="link.path">
          <router-link
            :to="link.path"
            class="nav-link"
            active-class="nav-link--active"
            @click="handleNavClick"
          >
            <div class="nav-link__icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <path :d="link.icon" />
              </svg>
            </div>
            <div class="min-w-0">
              <div class="truncate text-sm font-semibold">{{ link.label }}</div>
              <div class="truncate text-[11px] text-[var(--text-muted)]">{{ link.hint }}</div>
            </div>
          </router-link>
        </li>
      </ul>
    </nav>
  </aside>
</template>

<style scoped>
.sidebar {
  background:
    linear-gradient(180deg, rgba(7, 16, 31, 0.96), rgba(6, 14, 27, 0.92));
  backdrop-filter: blur(18px);
}

.session-card {
  position: relative;
  padding: 14px;
  border-radius: 20px;
  border: 1px solid rgba(171, 202, 239, 0.08);
  background: rgba(255, 255, 255, 0.03);
  transition:
    border-color 180ms ease,
    transform 180ms ease,
    background 180ms ease;
}

.session-card:hover {
  transform: translateY(-1px);
  border-color: rgba(171, 202, 239, 0.16);
  background: rgba(255, 255, 255, 0.05);
}

.session-card--active {
  border-color: rgba(77, 184, 255, 0.24);
  background: rgba(77, 184, 255, 0.1);
  box-shadow: inset 0 0 0 1px rgba(77, 184, 255, 0.08);
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 18px;
  border: 1px solid transparent;
  color: var(--text-secondary);
  transition:
    border-color 180ms ease,
    background 180ms ease,
    color 180ms ease,
    transform 180ms ease;
}

.nav-link:hover {
  transform: translateY(-1px);
  border-color: rgba(171, 202, 239, 0.14);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
}

.nav-link--active {
  border-color: rgba(77, 184, 255, 0.22);
  background: rgba(77, 184, 255, 0.1);
  color: var(--text-primary);
}

.nav-link__icon {
  display: flex;
  height: 38px;
  width: 38px;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.05);
}
</style>
