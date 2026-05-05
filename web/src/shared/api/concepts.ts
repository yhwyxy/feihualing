import { apiFetch } from './http'
import type {
  ConceptAliasListResponse,
  ConceptAliasRead,
  ConceptGraphParams,
  ConceptGraphResponse,
  ConceptQueryParams,
  ConceptRead,
  ManualLineConceptPayload,
  MessageResponse,
  PageResponse,
  ParseJobDetailResponse,
  ParseJobRead,
  ParseJobScheduledResponse,
  PoemConceptsResponse,
} from '../types/api'

function buildSearch(
  params: Record<string, string | number | boolean | undefined> | object,
) {
  const search = new URLSearchParams()

  Object.entries(params as Record<string, string | number | boolean | undefined>).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  })

  return search.toString() ? `?${search.toString()}` : ''
}

export function listConcepts(params: ConceptQueryParams = {}) {
  return apiFetch<PageResponse<ConceptRead>>(`/concepts${buildSearch(params)}`)
}

export function getConceptGraph(conceptId: number, params: ConceptGraphParams = {}) {
  return apiFetch<ConceptGraphResponse>(`/concepts/${conceptId}/graph${buildSearch(params)}`)
}

export function listConceptAliases(conceptId: number) {
  return apiFetch<ConceptAliasListResponse>(`/concepts/${conceptId}/aliases`)
}

export function createConceptAlias(conceptId: number, alias: string) {
  return apiFetch<ConceptAliasRead>(`/concepts/${conceptId}/aliases`, {
    method: 'POST',
    body: JSON.stringify({ alias }),
  })
}

export function deleteConceptAlias(conceptId: number, aliasId: number) {
  return apiFetch<MessageResponse>(`/concepts/${conceptId}/aliases/${aliasId}`, {
    method: 'DELETE',
  })
}

export function getPoemConcepts(
  poemId: number,
  params: { include_lines?: boolean; source?: string } = {},
) {
  return apiFetch<PoemConceptsResponse>(`/poems/${poemId}/concepts${buildSearch(params)}`)
}

export function reparsePoem(poemId: number) {
  return apiFetch<ParseJobScheduledResponse>(`/poems/${poemId}/reparse`, {
    method: 'POST',
  })
}

export function listParseJobs(params: { status?: string; poem_id?: number; limit?: number; offset?: number } = {}) {
  return apiFetch<PageResponse<ParseJobRead>>(`/concepts/parse-jobs${buildSearch(params)}`)
}

export function getParseJob(jobId: number) {
  return apiFetch<ParseJobDetailResponse>(`/concepts/parse-jobs/${jobId}`)
}

export function createManualLineConcept(poemId: number, payload: ManualLineConceptPayload) {
  return apiFetch<MessageResponse>(`/poems/${poemId}/concepts/manual`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteManualLineConcept(
  poemId: number,
  params: {
    concept_id: number
    line_index: number
    matched_text: string
    start_offset: number
  },
) {
  return apiFetch<MessageResponse>(`/poems/${poemId}/concepts/manual${buildSearch(params)}`, {
    method: 'DELETE',
  })
}
