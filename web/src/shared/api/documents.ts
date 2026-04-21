import { apiFetch } from './http'
import type {
  DocumentDetail,
  DocumentListResponse,
  DocumentRead,
  DocumentUploadPayload,
  MessageResponse,
} from '../types/api'

export function listDocuments(params: { limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams()
  if (params.limit !== undefined) search.set('limit', String(params.limit))
  if (params.offset !== undefined) search.set('offset', String(params.offset))
  const suffix = search.toString() ? `?${search.toString()}` : ''
  return apiFetch<DocumentListResponse>(`/documents${suffix}`)
}

export function getDocument(id: number) {
  return apiFetch<DocumentDetail>(`/documents/${id}`)
}

export function uploadDocument(payload: DocumentUploadPayload) {
  return apiFetch<DocumentRead>('/documents', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteDocument(id: number) {
  return apiFetch<MessageResponse>(`/documents/${id}`, {
    method: 'DELETE',
  })
}
