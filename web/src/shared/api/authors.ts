import { apiFetch } from './http'
import type { AuthorDynastyRead, AuthorRead, AuthorWritePayload, PageResponse, PoemRead } from '../types/api'

export function listAuthors(keyword = '', limit = 20, offset = 0) {
  const search = new URLSearchParams()
  if (keyword) search.set('keyword', keyword)
  search.set('limit', String(limit))
  search.set('offset', String(offset))

  return apiFetch<PageResponse<AuthorRead>>(`/authors?${search.toString()}`)
}

export function createAuthor(payload: AuthorWritePayload) {
  return apiFetch<AuthorRead>('/authors', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateAuthor(authorId: number, payload: AuthorWritePayload) {
  return apiFetch<AuthorRead>(`/authors/${authorId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteAuthor(authorId: number) {
  return apiFetch<{ message: string }>(`/authors/${authorId}`, {
    method: 'DELETE',
  })
}

export function getAuthorPoems(authorId: number, limit = 20, offset = 0) {
  return apiFetch<PageResponse<PoemRead>>(
    `/authors/${authorId}/poems?limit=${limit}&offset=${offset}`,
  )
}

export function getAuthorDynasty(authorId: number) {
  return apiFetch<AuthorDynastyRead>(`/authors/${authorId}/dynasty`)
}

export function setAuthorDynasty(authorId: number, conceptId: number) {
  return apiFetch<AuthorDynastyRead>(`/authors/${authorId}/dynasty`, {
    method: 'PUT',
    body: JSON.stringify({ concept_id: conceptId }),
  })
}

export function deleteAuthorDynasty(authorId: number) {
  return apiFetch<{ message: string }>(`/authors/${authorId}/dynasty`, {
    method: 'DELETE',
  })
}
