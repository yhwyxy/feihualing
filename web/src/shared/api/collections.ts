import { apiFetch } from './http'
import type {
  CollectionPoemRead,
  CollectionRead,
  CollectionWritePayload,
  MessageResponse,
  PageResponse,
} from '../types/api'

export function listCollections(keyword = '', limit = 20, offset = 0) {
  const search = new URLSearchParams()
  if (keyword) search.set('keyword', keyword)
  search.set('limit', String(limit))
  search.set('offset', String(offset))

  return apiFetch<PageResponse<CollectionRead>>(`/collections?${search.toString()}`)
}

export function createCollection(payload: CollectionWritePayload) {
  return apiFetch<CollectionRead>('/collections', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateCollection(collectionId: number, payload: CollectionWritePayload) {
  return apiFetch<CollectionRead>(`/collections/${collectionId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteCollection(collectionId: number) {
  return apiFetch<MessageResponse>(`/collections/${collectionId}`, {
    method: 'DELETE',
  })
}

export function addPoemToCollection(collectionId: number, poemId: number) {
  return apiFetch<MessageResponse>(`/collections/${collectionId}/poems`, {
    method: 'POST',
    body: JSON.stringify({ poem_id: poemId }),
  })
}

export function replaceCollectionPoems(collectionId: number, poemIds: number[]) {
  return apiFetch<MessageResponse>(`/collections/${collectionId}/poems`, {
    method: 'PUT',
    body: JSON.stringify({ poem_ids: poemIds }),
  })
}

export function removePoemFromCollection(collectionId: number, poemId: number) {
  return apiFetch<MessageResponse>(`/collections/${collectionId}/poems/${poemId}`, {
    method: 'DELETE',
  })
}

export function getCollectionPoems(collectionId: number, limit = 20, offset = 0) {
  return apiFetch<PageResponse<CollectionPoemRead>>(
    `/collections/${collectionId}/poems?limit=${limit}&offset=${offset}`,
  )
}
