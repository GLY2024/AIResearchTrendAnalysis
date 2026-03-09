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
    console.log('[ARTA:Session] Fetching sessions...')
    try {
      sessions.value = await sessionApi.list()
      console.log('[ARTA:Session] Loaded', sessions.value.length, 'sessions')
    } catch (err) {
      console.error('[ARTA:Session] Failed to fetch sessions:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createSession(title: string, description = '') {
    console.log('[ARTA:Session] Creating session:', title)
    try {
      const session = await sessionApi.create({ title, description })
      sessions.value.unshift(session)
      currentSessionId.value = session.id
      console.log('[ARTA:Session] Created session:', session.id)
      return session
    } catch (err) {
      console.error('[ARTA:Session] Failed to create session:', err)
      throw err
    }
  }

  async function deleteSession(id: number) {
    console.log('[ARTA:Session] Deleting session:', id)
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
