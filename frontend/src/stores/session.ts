import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Session } from '@/types'
import { sessionApi } from '@/composables/useApi'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<number | null>(null)
  const loading = ref(false)

  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value) ?? null
  )

  async function fetchSessions() {
    loading.value = true
    try {
      sessions.value = await sessionApi.list()
    } finally {
      loading.value = false
    }
  }

  async function createSession(title: string, description = '') {
    const session = await sessionApi.create({ title, description })
    sessions.value.unshift(session)
    currentSessionId.value = session.id
    return session
  }

  async function deleteSession(id: number) {
    await sessionApi.delete(id)
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (currentSessionId.value === id) {
      currentSessionId.value = sessions.value[0]?.id ?? null
    }
  }

  function setCurrentSession(id: number) {
    currentSessionId.value = id
  }

  return {
    sessions,
    currentSessionId,
    currentSession,
    loading,
    fetchSessions,
    createSession,
    deleteSession,
    setCurrentSession,
  }
})
