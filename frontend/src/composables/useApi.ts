import axios from 'axios'
import type {
  Session,
  ChatMessage,
  SearchPlan,
  Paper,
  PaperListPage,
  AnalysisRun,
  Report,
  AppSetting,
} from '@/types'
import { getApiBaseUrl, markBackendOffline, markBackendOnline, isBackendOfflineError } from '@/composables/useBackend'

const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000,
})

// Request/response logging interceptors
api.interceptors.request.use((config) => {
  console.log(`[ARTA:API] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`, config.params || '')
  return config
})

api.interceptors.response.use(
  (response) => {
    markBackendOnline()
    console.log(`[ARTA:API] ${response.status} ${response.config.url}`)
    return response
  },
  (error) => {
    const status = error.response?.status ?? 'NETWORK_ERROR'
    const url = error.config?.url ?? '?'
    const msg = error.response?.data?.detail ?? error.message
    if (isBackendOfflineError(error)) {
      markBackendOffline(error)
    }
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
  retryMessage: (messageId: number) =>
    api.post<ChatMessage>(`/chat/messages/${messageId}/retry`).then(r => r.data),
  deleteMessage: (messageId: number) =>
    api.delete(`/chat/messages/${messageId}`),
}

// Search
export const searchApi = {
  listPlans: (sessionId: number) =>
    api.get<SearchPlan[]>('/search/plans', { params: { session_id: sessionId } }).then(r => r.data),
  getPlan: (planId: number) =>
    api.get<SearchPlan>(`/search/plans/${planId}`).then(r => r.data),
  planAction: (planId: number, action: string, planData?: Record<string, unknown>) =>
    api.post<SearchPlan>(`/search/plans/${planId}/action`, { action, plan_data: planData }).then(r => r.data),
}

// Papers
export const paperApi = {
  list: (sessionId: number, params?: Record<string, unknown>) =>
    api.get<PaperListPage | Paper[]>('/papers', { params: { session_id: sessionId, ...params } }).then((r) => {
      if (Array.isArray(r.data)) {
        const offset = Number(params?.offset ?? 0)
        const limit = Number(params?.limit ?? r.data.length)
        return {
          items: r.data,
          total: offset + r.data.length,
          limit,
          offset,
        } satisfies PaperListPage
      }

      return r.data
    }),
  get: (id: number) => api.get<Paper>(`/papers/${id}`).then(r => r.data),
  update: (id: number, data: Partial<Paper>) =>
    api.patch<Paper>(`/papers/${id}`, data).then(r => r.data),
  delete: (id: number) => api.delete(`/papers/${id}`),
  count: (sessionId: number, params?: Record<string, unknown>) =>
    api.get<{ count: number }>('/papers/count', { params: { session_id: sessionId, ...params } }).then(r => r.data),
  sources: (sessionId: number) =>
    api.get<{ sources: string[]; discovery_methods: string[] }>('/papers/sources', {
      params: { session_id: sessionId },
    }).then(r => r.data),
  batchUpdate: (paperIds: number[], isIncluded: boolean) =>
    api.post('/papers/batch-update', {
      paper_ids: paperIds,
      is_included: isIncluded,
    }),
  batchDelete: (paperIds: number[]) =>
    api.post('/papers/batch-delete', {
      paper_ids: paperIds,
    }),
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
  validate: (data: { key: string; value: string; base_url?: string }) =>
    api.post<{ valid: boolean; message: string }>('/validate-key', data).then(r => r.data),
  fetchModels: (provider: string) =>
    api.get<{ models: { id: string; name: string }[]; error: string | null }>('/settings/models', {
      params: { provider },
    }).then(r => r.data),
}

// Export
export const exportApi = {
  risUrl: (sessionId: number) => `${getApiBaseUrl()}/export/ris/${sessionId}`,
  bibtexUrl: (sessionId: number) => `${getApiBaseUrl()}/export/bibtex/${sessionId}`,
}

// Health
export const healthApi = {
  check: () => api.get('/health').then(r => r.data),
}
