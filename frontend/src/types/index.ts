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
  metadata?: Record<string, unknown>
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
  snowball_config: SnowballConfig
  inclusion_criteria: string[]
  exclusion_criteria: string[]
  notes: string
}

export interface SnowballConfig {
  enabled: boolean
  approval_required?: boolean
  approval_mode?: 'batch' | 'all'
  decision_mode?: 'manual_review' | 'all' | 'high_confidence'
  max_hops: number
  directions: string[]
  min_citation_threshold: number
  max_seed_papers?: number
  per_seed_limit?: number
  max_candidates?: number
  verification_mode?: 'none' | 'stable_identifier' | 'cross_source'
  ai_filter?: {
    enabled: boolean
    min_score: number
    auto_import_score: number
  }
}

export interface SnowballRun {
  id: number
  session_id: number
  plan_id: number
  status: 'proposed' | 'running' | 'awaiting_review' | 'completed' | 'rejected' | 'failed'
  config: SnowballConfig
  proposal_summary: {
    topic?: string
    decision_mode?: string
    approval_mode?: string
    verification_mode?: string
    estimated_candidate_budget?: number
    seed_papers?: {
      paper_id: number
      title: string
      year: number | null
      citation_count: number
    }[]
  }
  stats: {
    candidate_count?: number
    verified_count?: number
    high_confidence_count?: number
    imported_count?: number
    direction_counts?: Record<string, number>
  }
  created_at: string
  updated_at: string
}

export interface SnowballCandidate {
  id: number
  run_id: number
  seed_paper_id: number | null
  direction: string
  hop: number
  title: string
  year: number | null
  citation_count: number
  source_name: string
  relevance_score: number | null
  relevance_reason: string
  verification_status: string
  verification_sources: string[]
  status: 'pending' | 'approved' | 'rejected' | 'imported'
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

export interface PaperListPage {
  items: Paper[]
  total: number
  limit: number
  offset: number
}

export interface Author {
  name: string
  affiliation: string
  orcid: string
}

export interface AnalysisRun {
  id: number
  session_id: number
  analysis_type: 'bibliometrics' | 'topic_modeling' | 'trend' | 'network' | 'coauthor'
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
