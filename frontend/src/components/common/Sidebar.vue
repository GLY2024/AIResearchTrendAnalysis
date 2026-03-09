<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'

const router = useRouter()
const sessionStore = useSessionStore()

const navLinks = [
  { label: 'Chat', path: '/chat', icon: '💬' },
  { label: 'Search Plan', path: '/plan', icon: '🔍' },
  { label: 'Library', path: '/library', icon: '📚' },
  { label: 'Analysis', path: '/analysis', icon: '📊' },
  { label: 'Report', path: '/report', icon: '📄' },
  { label: 'Settings', path: '/settings', icon: '⚙️' },
]

async function handleNewSession() {
  const session = await sessionStore.createSession('New Session')
  router.push('/chat')
}

onMounted(() => {
  sessionStore.fetchSessions()
})
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
        @click="handleNewSession"
      >
        <span class="text-lg leading-none">+</span>
        New Session
      </button>
    </div>

    <!-- Session list -->
    <div class="flex-1 overflow-y-auto px-3 pb-2">
      <div class="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider px-2 mb-2">
        Sessions
      </div>
      <ul class="space-y-0.5">
        <li v-for="session in sessionStore.sessions" :key="session.id">
          <button
            class="w-full text-left px-3 py-2 rounded-lg text-sm truncate transition-colors"
            :class="
              session.id === sessionStore.currentSessionId
                ? 'bg-[var(--glass-active)] text-[var(--text-primary)]'
                : 'text-[var(--text-secondary)] hover:bg-[var(--glass-bg)] hover:text-[var(--text-primary)]'
            "
            @click="sessionStore.setCurrentSession(session.id)"
          >
            {{ session.title }}
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
