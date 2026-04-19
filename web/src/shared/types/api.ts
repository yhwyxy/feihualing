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
