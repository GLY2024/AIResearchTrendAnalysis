<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'

const router = useRouter()
const route = useRoute()
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
  { label: 'Chat', path: '/chat', icon: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z' },
  { label: 'Search Plan', path: '/plan', icon: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.35-4.35' },
  { label: 'Library', path: '/library', icon: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z' },
  { label: 'Analysis', path: '/analysis', icon: 'M18 20V10M12 20V4M6 20v-6' },
  { label: 'Report', path: '/report', icon: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8' },
  { label: 'Settings', path: '/settings', icon: 'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z' },
]

async function handleNewSession() {
  actionError.value = ''
  if (backendState.status !== 'online') {
    actionError.value = getBackendOfflineMessage('creating a session')
    return
  }

  try {
    await sessionStore.createSession('New Session')
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
  } else {
    confirmDeleteId.value = id
    setTimeout(() => { if (confirmDeleteId.value === id) confirmDeleteId.value = null }, 3000)
  }
}

function handleNavClick() {
  emit('closeMobile')
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  return d.toLocaleDateString()
}
</script>

<template>
  <aside
    class="fixed top-0 left-0 h-screen flex flex-col bg-[var(--bg-secondary)] border-r border-white/10 z-40 transition-transform duration-200"
    :class="[
      'max-md:-translate-x-full',
      mobileOpen ? 'max-md:translate-x-0' : '',
    ]"
    style="width: var(--sidebar-width)"
  >
    <!-- Logo -->
    <div class="flex items-center gap-2.5 px-5 h-14 border-b border-white/10 shrink-0">
      <div class="w-8 h-8 rounded-lg bg-[var(--accent-primary)] flex items-center justify-center font-bold text-sm text-white">
        A
      </div>
      <span class="text-base font-semibold text-[var(--text-primary)] tracking-wide">ARTA</span>
    </div>

    <!-- New session button -->
    <div class="px-3 py-3 shrink-0">
      <button
        class="glass-btn glass-btn-primary w-full flex items-center justify-center gap-2 text-sm"
        :disabled="backendState.status !== 'online'"
        @click="handleNewSession"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M8 3v10M3 8h10" />
        </svg>
        New Session
      </button>
      <p v-if="actionError" class="mt-2 text-xs text-[var(--error)]">
        {{ actionError }}
      </p>
    </div>

    <!-- Session list -->
    <div class="flex-1 overflow-y-auto px-3 pb-2">
      <div class="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider px-2 mb-2">
        Sessions
      </div>
      <ul class="space-y-0.5">
        <li
          v-for="session in sessionStore.sessions"
          :key="session.id"
          class="relative group"
          @mouseenter="hoveredSession = session.id"
          @mouseleave="hoveredSession = null"
        >
          <button
            class="w-full text-left px-3 py-2 rounded-lg text-sm truncate transition-colors pr-8"
            :class="
              session.id === sessionStore.currentSessionId
                ? 'bg-[var(--glass-active)] text-[var(--text-primary)]'
                : 'text-[var(--text-secondary)] hover:bg-[var(--glass-bg)] hover:text-[var(--text-primary)]'
            "
            @click="sessionStore.setCurrentSession(session.id); handleNavClick()"
          >
            <div class="truncate">{{ session.title }}</div>
            <div class="text-[10px] text-[var(--text-muted)] mt-0.5 flex items-center gap-2">
              <span v-if="(session as any).paper_count != null">{{ (session as any).paper_count }} papers</span>
              <span>{{ formatDate(session.updated_at || session.created_at) }}</span>
            </div>
          </button>
          <!-- Delete button -->
          <button
            v-show="hoveredSession === session.id || confirmDeleteId === session.id"
            class="absolute right-1 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded text-xs transition-colors"
            :class="confirmDeleteId === session.id
              ? 'bg-[var(--error)] text-white'
              : 'text-[var(--text-muted)] hover:text-[var(--error)] hover:bg-[var(--error)]/10'"
            :title="confirmDeleteId === session.id ? 'Click again to confirm' : 'Delete session'"
            @click.stop="handleDeleteSession(session.id)"
          >
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M4 4l8 8M12 4l-8 8" />
            </svg>
          </button>
        </li>
      </ul>
      <div
        v-if="!sessionStore.loading && sessionStore.sessions.length === 0"
        class="text-xs text-[var(--text-muted)] px-2 py-4 text-center"
      >
        No sessions yet
      </div>
    </div>

    <!-- Navigation -->
    <nav class="border-t border-white/10 px-3 py-3 shrink-0">
      <ul class="space-y-0.5">
        <li v-for="link in navLinks" :key="link.path">
          <router-link
            :to="link.path"
            class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors text-[var(--text-secondary)] hover:bg-[var(--glass-bg)] hover:text-[var(--text-primary)]"
            active-class="!bg-[var(--glass-active)] !text-[var(--text-primary)]"
            @click="handleNavClick"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="shrink-0">
              <path :d="link.icon" />
            </svg>
            {{ link.label }}
          </router-link>
        </li>
      </ul>
    </nav>
  </aside>
</template>
