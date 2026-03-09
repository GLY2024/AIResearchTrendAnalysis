import axios from 'axios'
import type { Session, ChatMessage, SearchPlan, Paper, AnalysisRun, Report, AppSetting } from '@/types'

// In Tauri mode, requests go directly to backend; in dev mode, Vite proxy handles it
const BACKEND_BASE = (window as Record<string, unknown>).__TAURI_INTERNALS__
  ? 'http://127.0.0.1:8721/api'
  : '/api'

const api = axios.create({
  baseURL: BACKEND_BASE,
  timeout: 30000,
})

// Request/response logging interceptors
api.interceptors.request.use((config) => {
  console.log(`[ARTA:API] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`, config.params || '')
  return config
})

api.interceptors.response.use(
  (response) => {
    console.log(`[ARTA:API] ${response.status} ${response.config.url}`)
    return response
  },
  (error) => {
    const status = error.response?.status ?? 'NETWORK_ERROR'
    const url = error.config?.url ?? '?'
    const msg = error.response?.data?.detail ?? error.message
    console.error(`[ARTA:API] ${status} ${url}: ${msg}`)
    return Promise.reject(error)
  }
)

// Sessions
export const sessionApi = {
  list: () => api.get<Session[]>('/sessions').then(r => r.data),
  get: (id: number) => api.get<Session>(`/sessions/${id}`).then(r => r.data),
  create: (data: { title: string; description?: string }) =>
    api.post<Session>('/sessions', data).then(r => r.data),
  update: (id: number, data: Partial<Session>) =>
    api.patch<Session>(`/sessions/${id}`, data).then(r => r.data),
  delete: (id: number) => api.delete(`/sessions/${id}`),
}

// Chat
export const chatApi = {
  getMessages: (sessionId: number) =>
    api.get<ChatMessage[]>(`/chat/${sessionId}/messages`).then(r => r.data),
  send: (data: { session_id: number; content: string }) =>
    api.post<ChatMessage>('/chat/send', data).then(r => r.data),
}

// Search
export const searchApi = {
  listPlans: (sessionId: number) =>
    api.get<SearchPlan[]>('/search/plans', { params: { session_id: sessionId } }).then(r => r.data),
  getPlan: (planId: number) =>
    api.get<SearchPlan>(`/search/plans/${planId}`).then(r => r.data),
  planAction: (planId: number, action: string) =>
    api.post<SearchPlan>(`/search/plans/${planId}/action`, { action }).then(r => r.data),
}

// Papers
export const paperApi = {
  list: (sessionId: number, params?: Record<string, unknown>) =>
    api.get<Paper[]>('/papers', { params: { session_id: sessionId, ...params } }).then(r => r.data),
  get: (id: number) => api.get<Paper>(`/papers/${id}`).then(r => r.data),
  update: (id: number, data: Partial<Paper>) =>
    api.patch<Paper>(`/papers/${id}`, data).then(r => r.data),
  delete: (id: number) => api.delete(`/papers/${id}`),
  count: (sessionId: number) =>
    api.get<{ count: number }>('/papers/count', { params: { session_id: sessionId } }).then(r => r.data),
}

// Analysis
export const analysisApi = {
  list: (sessionId: number) =>
    api.get<AnalysisRun[]>('/analysis', { params: { session_id: sessionId } }).then(r => r.data),
  create: (data: { session_id: number; analysis_type: string; params?: Record<string, unknown> }) =>
    api.post<AnalysisRun>('/analysis', data).then(r => r.data),
  get: (id: number) => api.get<AnalysisRun>(`/analysis/${id}`).then(r => r.data),
}

// Reports
export const reportApi = {
  list: (sessionId: number) =>
    api.get<Report[]>('/reports', { params: { session_id: sessionId } }).then(r => r.data),
  get: (id: number) => api.get<Report>(`/reports/${id}`).then(r => r.data),
  generate: (data: { session_id: number; parent_report_id?: number }) =>
    api.post<Report>('/reports/generate', data).then(r => r.data),
}

// Settings
export const settingsApi = {
  list: () => api.get<AppSetting[]>('/settings').then(r => r.data),
  update: (data: { key: string; value: string; is_sensitive?: boolean }) =>
    api.put('/settings', data).then(r => r.data),
  delete: (key: string) => api.delete('/settings', { params: { key } }),
}

// Export
const exportBase = (window as Record<string, unknown>).__TAURI_INTERNALS__
  ? 'http://127.0.0.1:8721/api'
  : '/api'

export const exportApi = {
  risUrl: (sessionId: number) => `${exportBase}/export/ris/${sessionId}`,
  bibtexUrl: (sessionId: number) => `${exportBase}/export/bibtex/${sessionId}`,
}

// Health
export const healthApi = {
  check: () => api.get('/health').then(r => r.data),
}
