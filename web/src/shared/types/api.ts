export interface PageResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface MessageResponse {
  message: string
}

export interface AuthorRead {
  id: number
  name: string
  bio: string | null
  created_at: string
}

export interface AuthorDynastyRead {
  author_id: number
  concept_id: number | null
  name: string | null
}

export interface AuthorWritePayload {
  name: string
  bio: string | null
}

export interface AuthorOption {
  id: number
  name: string
}

export interface PoemRead {
  id: number
  title: string
  content: string
  author_id: number
  author: string
  created_at: string
}

export interface PoemWritePayload {
  title: string
  content: string
  author_id: number
}

export interface CollectionRead {
  id: number
  name: string
  description: string | null
  created_at: string
}

export interface CollectionWritePayload {
  name: string
  description: string | null
}

export interface CollectionPoemRead {
  collection_id: number
  poem: PoemRead
  created_at: string
}

export type ConceptType = 'char' | 'phrase' | 'place' | 'image' | 'theme' | 'dynasty'

export type ConceptSource = 'parser' | 'manual' | 'import' | 'llm'

export interface ConceptRead {
  id: number
  name: string
  normalized_name: string
  type: ConceptType
  description: string | null
  is_active: boolean
  poem_count: number | null
  line_count: number | null
  created_at: string
}

export interface ConceptAliasRead {
  id: number
  concept_id: number
  alias: string
  normalized_alias: string
  created_at: string
}

export interface ConceptAliasListResponse {
  concept_id: number
  aliases: ConceptAliasRead[]
}

export interface ConceptQueryParams {
  keyword?: string
  type?: ConceptType
  include_counts?: boolean
  limit?: number
  offset?: number
}

export interface ConceptGraphNode {
  id: string
  type: string
  label: string
  meta: Record<string, unknown>
}

export interface ConceptGraphEdge {
  id: string
  source: string
  target: string
  type: string
  meta: Record<string, unknown>
}

export interface ConceptGraphResponse {
  center: ConceptGraphNode
  nodes: ConceptGraphNode[]
  edges: ConceptGraphEdge[]
  limits: {
    limit_poems: number
    limit_lines: number
  }
  truncated: boolean
}

export interface ConceptGraphParams {
  depth?: number
  limit_poems?: number
  limit_lines?: number
  author_id?: number
  dynasty?: string
  node_types?: string
  source?: ConceptSource
  min_popularity?: number
  min_matched_count?: number
}

export interface LineConceptRead {
  line_index: number
  line_text: string
  matched_text: string
  start_offset: number
  source: ConceptSource
}

export interface PoemConceptRead {
  id: number
  name: string
  type: ConceptType
  confidence: string
  source: ConceptSource
  matched_count: number
  matched_texts: string[]
  lines: LineConceptRead[]
}

export interface PoemConceptsResponse {
  poem_id: number
  concepts: PoemConceptRead[]
}

export interface ParseJobScheduledResponse {
  message: string
  job_id: number
  poem_id: number
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped'
}

export interface ParseJobRead {
  id: number
  poem_id: number | null
  job_type: 'initial_parse' | 'reparse' | 'delete_cleanup' | 'batch_backfill'
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped'
  trigger_source: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface ParseLogRead {
  id: number
  job_id: number
  level: 'info' | 'warning' | 'error'
  message: string
  payload: Record<string, unknown> | null
  created_at: string
}

export interface ParseJobDetailResponse {
  job: ParseJobRead
  logs: ParseLogRead[]
}

export interface ManualLineConceptPayload {
  concept_id: number
  line_index: number
  matched_text?: string | null
  start_offset?: number
}

export interface FeihualingQueryItem {
  line: string
  line_index: number
  matched_text: string
  poem: {
    id: number
    title: string
  }
  author: {
    id: number | null
    name: string
  }
  concepts: Array<{
    id: number
    name: string
    type: ConceptType
  }>
}

export interface FeihualingQueryResponse {
  keyword: string
  position: 'any' | 'start' | 'end'
  items: FeihualingQueryItem[]
  total: number
  limit: number
  offset: number
}

export interface PoemQueryParams {
  keyword?: string
  author_name?: string
  collection_id?: number
  author_id?: number
  limit?: number
  offset?: number
}

export interface ImportAuthorInput {
  name: string
  bio?: string | null
}

export interface ImportPoemRefInput {
  title: string
  author: string
}

export interface ImportPoemInput extends ImportPoemRefInput {
  content: string
  collections?: string[]
}

export interface ImportCollectionInput {
  name: string
  description?: string | null
  poems?: ImportPoemRefInput[]
}

export interface BatchImportPayload {
  authors?: ImportAuthorInput[]
  poems?: ImportPoemInput[]
  collections?: ImportCollectionInput[]
}

export interface BatchImportCount {
  created: number
  matched: number
  skipped: number
}

export interface BatchImportSummary {
  authors: BatchImportCount
  poems: BatchImportCount
  collections: BatchImportCount
  collection_poems: BatchImportCount
}

export interface BatchImportWarning {
  code: string
  path: string
  message: string
}

export interface BatchImportResponse {
  summary: BatchImportSummary
  warnings: BatchImportWarning[]
}

export interface UnifiedImportPayload {
  title: string
  content: string
  source_filename?: string | null
  batch_payload?: BatchImportPayload | null
  extract_poems?: boolean
  max_extracted_poems?: number
}

export interface UnifiedImportExtractionResult {
  attempted: boolean
  source: 'batch_payload' | 'llm' | 'skipped' | 'unavailable' | 'failed'
  extracted_poem_count: number
  imported: BatchImportResponse | null
  warnings: BatchImportWarning[]
}

export interface UnifiedImportResponse {
  document: DocumentRead
  extraction: UnifiedImportExtractionResult
}


export interface RagSearchRequest {
  query: string
  top_k?: number
}

export interface RagPoemHit {
  id: number
  title: string
  content: string
  author_id: number | null
  author_name: string | null
  score: number
  sem_score: number
  kw_score: number
}

export interface RagAuthorHit {
  id: number
  name: string
  bio: string | null
  score: number
  sem_score: number
  kw_score: number
}

export interface RagCollectionHit {
  id: number
  name: string
  description: string | null
  score: number
  sem_score: number
  kw_score: number
}

export interface RagDocumentChunkHit {
  chunk_id: number
  document_id: number
  document_title: string
  chunk_index: number
  content: string
  score: number
  sem_score: number
  kw_score: number
}

export interface RagSearchResponse {
  query: string
  poems: RagPoemHit[]
  authors: RagAuthorHit[]
  collections: RagCollectionHit[]
  document_chunks: RagDocumentChunkHit[]
}


export interface RagAskPoemSource {
  id: number
  title: string
  author: string | null
  content: string
}

export interface RagAskDocChunkSource {
  document_id: number
  chunk_index: number
  document_title: string
  content: string
}

export interface RagAskSources {
  poems: RagAskPoemSource[]
  document_chunks: RagAskDocChunkSource[]
}

export type RagAskEvent =
  | { type: 'sources'; sources: RagAskSources }
  | { type: 'delta'; text: string }
  | { type: 'done' }
  | { type: 'error'; message: string }


export interface DocumentRead {
  id: number
  title: string
  source_filename: string | null
  chunk_count: number
  embedded_count: number
  created_at: string
}

export interface DocumentDetail extends DocumentRead {
  content: string
}

export interface DocumentListResponse {
  items: DocumentRead[]
  total: number
}

export interface DocumentUploadPayload {
  title: string
  content: string
  source_filename?: string | null
}


export type FeihualingDifficulty = 'easy' | 'medium' | 'hard' | 'expert'

export type FeihualingSessionStatus =
  | 'in_progress'
  | 'user_won'
  | 'agent_won'
  | 'abandoned'

export type FeihualingSpeaker = 'user' | 'agent'

export interface TurnRead {
  turn_index: number
  speaker: FeihualingSpeaker
  line: string
  poem_id: number | null
  title: string | null
  author: string | null
  is_valid: boolean
  reject_reason: string | null
  latency_ms: number | null
  llm_title: string | null
  llm_author: string | null
}

export interface SessionRead {
  session_id: number
  target_char: string
  difficulty: FeihualingDifficulty
  status: FeihualingSessionStatus
  winner_reason: string | null
  started_at: string
  ended_at: string | null
  turns: TurnRead[]
}

export interface PlayResponse {
  status: FeihualingSessionStatus
  winner_reason: string | null
  user_turn: TurnRead | null
  agent_turn: TurnRead | null
}

export interface SessionSummary {
  session_id: number
  target_char: string
  difficulty: FeihualingDifficulty
  status: FeihualingSessionStatus
  winner_reason: string | null
  turn_count: number
  started_at: string
  ended_at: string | null
}

export interface SessionListResponse {
  items: SessionSummary[]
  total: number
}


export type FeihualingStreamEvent =
  | {
      type: 'session_created'
      session_id: number
      target_char: string
      difficulty: FeihualingDifficulty
    }
  | { type: 'user_validating' }
  | { type: 'user_result'; turn: TurnRead }
  | { type: 'agent_thinking' }
  | { type: 'agent_tool_call'; name: string; args: Record<string, unknown> }
  | { type: 'agent_tool_result'; count: number; sample_lines: string[] }
  | { type: 'agent_result'; turn: TurnRead; source?: 'agent' | 'fallback' | null }
  | { type: 'agent_surrender'; reason: string }
  | { type: 'agent_error'; message: string }
  | { type: 'agent_fallback_started'; reason: string }
  | { type: 'error'; message: string }
  | {
      type: 'done'
      session_id: number
      status: FeihualingSessionStatus
      winner_reason: string | null
    }
