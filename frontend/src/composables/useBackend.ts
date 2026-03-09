import axios from 'axios'
import { reactive, readonly } from 'vue'

export type BackendStatus = 'checking' | 'online' | 'offline'

const BACKEND_ORIGIN = 'http://127.0.0.1:8721'
const BACKEND_START_COMMAND = 'uv run --project backend python run_backend.py'

const state = reactive({
  status: 'checking' as BackendStatus,
  error: '',
  lastCheckedAt: 0,
})

let pendingHealthCheck: Promise<boolean> | null = null

export function isTauriRuntime() {
  return typeof window !== 'undefined' && !!((window as unknown as Record<string, unknown>).__TAURI_INTERNALS__)
}

export function getBackendOrigin() {
  return BACKEND_ORIGIN
}

export function getBackendStartCommand() {
  return BACKEND_START_COMMAND
}

export function getApiBaseUrl() {
  return isTauriRuntime() ? `${BACKEND_ORIGIN}/api` : '/api'
}

export function getWebSocketUrl(sessionId: string | number) {
  if (isTauriRuntime()) {
    return `ws://127.0.0.1:8721/ws/${sessionId}`
  }

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/ws/${sessionId}`
}

export function normalizeBackendError(error: unknown, fallback = 'Cannot reach the backend server.') {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (typeof error.message === 'string' && error.message.trim()) return error.message
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message
  }

  if (typeof error === 'string' && error.trim()) {
    return error
  }

  return fallback
}

export function isBackendOfflineError(error: unknown) {
  return axios.isAxiosError(error)
    ? !error.response
    : error instanceof TypeError
}

export function markBackendOnline() {
  state.status = 'online'
  state.error = ''
  state.lastCheckedAt = Date.now()
}

export function markBackendOffline(error: unknown, fallback?: string) {
  state.status = 'offline'
  state.error = normalizeBackendError(error, fallback)
  state.lastCheckedAt = Date.now()
}

export async function checkBackend(force = false) {
  if (pendingHealthCheck && !force) {
    return pendingHealthCheck
  }

  if (state.status !== 'online' || force) {
    state.status = 'checking'
  }
  state.error = ''

  pendingHealthCheck = fetch(`${getApiBaseUrl()}/health`, {
    method: 'GET',
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Backend responded with ${response.status}`)
      }

      markBackendOnline()
      return true
    })
    .catch((error: unknown) => {
      markBackendOffline(error)
      return false
    })
    .finally(() => {
      pendingHealthCheck = null
    })

  return pendingHealthCheck
}

export function getBackendOfflineMessage(action: string) {
  return `Backend is offline, so ${action} is unavailable. Start it with: ${BACKEND_START_COMMAND}`
}

export function useBackendState() {
  return readonly(state)
}
