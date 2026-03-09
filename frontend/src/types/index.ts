// Core types for ARTA frontend

export interface Session {
  id: number
  title: string
  description: string
  status: 'active' | 'archived' | 'completed'
  created_at: string
  updated_at: string
  paper_count: number
}

export interface ChatMessage {
  id: number
  session_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
}

export interface SearchPlan {
  id: number
  session_id: number
  plan_data: SearchPlanData
  status: 'draft' | 'approved' | 'executing' | 'completed' | 'failed' | 'rejected'
  created_at: string
}

export interface SearchPlanData {
  topic: string
  description: string
  queries: SearchQuery[]
  year_range: { from: number | null; to: number | null }
  max_results_per_query: number
  snowball_config: {
    enabled: boolean
    max_hops: number
    directions: string[]
    min_citation_threshold: number
  }
  inclusion_criteria: string[]
  exclusion_criteria: string[]
  notes: string
}

export interface SearchQuery {
  query: string
  source: string
  rationale: string
}

export interface Paper {
  id: number
  session_id: number
  doi: string | null
  arxiv_id: string | null
  openalex_id: string | null
  title: string
  abstract: string
  authors: Author[]
  journal: string
  year: number | null
  citation_count: number
  keywords: string[]
  fields: string[]
  source: string | null
  discovery_method: string | null
  relevance_score: number | null
  is_included: boolean
  notes: string
  created_at: string
}

export interface Author {
  name: string
  affiliation: string
  orcid: string
}

export interface AnalysisRun {
  id: number
  session_id: number
  analysis_type: 'bibliometrics' | 'topic_modeling' | 'trend' | 'network'
  params: Record<string, unknown>
  results: Record<string, unknown>
  chart_configs: ChartConfig[]
  ai_interpretation: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
}

export interface ChartConfig {
  id: string
  title: string
  type: string
  option: Record<string, unknown>
}

export interface Report {
  id: number
  session_id: number
  parent_report_id: number | null
  title: string
  content_markdown: string
  chart_configs: ChartConfig[][]
  version: number
  status: 'draft' | 'generating' | 'completed' | 'failed'
  created_at: string
}

export interface AppSetting {
  key: string
  value: string
  is_encrypted: boolean
}

// WebSocket event types
export interface WSEvent {
  event: string
  data: Record<string, unknown>
  session_id?: string
}
