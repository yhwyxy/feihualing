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
