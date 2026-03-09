<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { checkBackend, getBackendOfflineMessage, useBackendState } from '@/composables/useBackend'

const router = useRouter()
const sessionStore = useSessionStore()
const backendState = useBackendState()
const hoveredSession = ref<number | null>(null)
const confirmDeleteId = ref<number | null>(null)
const actionError = ref('')

const navLinks = [
  { label: 'Chat', path: '/chat', icon: '💬' },
  { label: 'Search Plan', path: '/plan', icon: '🔍' },
  { label: 'Library', path: '/library', icon: '📚' },
  { label: 'Analysis', path: '/analysis', icon: '📊' },
  { label: 'Report', path: '/report', icon: '📄' },
  { label: 'Settings', path: '/settings', icon: '⚙️' },
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
    // Auto-reset after 3s
    setTimeout(() => { if (confirmDeleteId.value === id) confirmDeleteId.value = null }, 3000)
  }
}
</script>

<template>
  <aside
    class="fixed top-0 left-0 h-screen flex flex-col bg-[var(--bg-secondary)] border-r border-white/10 z-40"
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
        <span class="text-lg leading-none">+</span>
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
            @click="sessionStore.setCurrentSession(session.id)"
          >
            {{ session.title }}
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
            ✕
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
          >
            <span class="text-base leading-none">{{ link.icon }}</span>
            {{ link.label }}
          </router-link>
        </li>
      </ul>
    </nav>
  </aside>
</template>
