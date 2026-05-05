import { apiFetch } from './http'
import type { MessageResponse, PageResponse, PoemQueryParams, PoemRead, PoemWritePayload } from '../types/api'

export function listPoems(params: PoemQueryParams = {}) {
  const search = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  })

  const suffix = search.toString() ? `?${search.toString()}` : ''
  return apiFetch<PageResponse<PoemRead>>(`/poems${suffix}`)
}

export function getPoem(poemId: number) {
  return apiFetch<PoemRead>(`/poems/${poemId}`)
}

export function createPoem(payload: PoemWritePayload) {
  return apiFetch<PoemRead>('/poems', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updatePoem(poemId: number, payload: PoemWritePayload) {
  return apiFetch<PoemRead>(`/poems/${poemId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deletePoem(poemId: number) {
  return apiFetch<MessageResponse>(`/poems/${poemId}`, {
    method: 'DELETE',
  })
}
