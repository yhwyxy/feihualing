import type { BatchImportPayload, ImportCollectionInput } from '../types/api'

export const SAMPLE_IMPORT_PAYLOAD: BatchImportPayload = {
  authors: [
    {
      name: '李白',
      bio: '唐代诗人，字太白，号青莲居士。',
    },
  ],
  poems: [
    {
      title: '静夜思',
      author: '李白',
      content: '床前明月光，\n疑是地上霜。\n举头望明月，\n低头思故乡。',
      collections: ['唐诗精选', '思乡诗'],
    },
  ],
  collections: [
    {
      name: '唐诗精选',
      description: '收录常见唐诗名篇。',
      poems: [
        {
          title: '静夜思',
          author: '李白',
        },
      ],
    },
  ],
}

export function parseCsv(text: string) {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let inQuotes = false

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index]
    const nextChar = text[index + 1]

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        cell += '"'
        index += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }

    if (char === ',' && !inQuotes) {
      row.push(cell)
      cell = ''
      continue
    }

    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && nextChar === '\n') index += 1
      row.push(cell)
      if (row.some((value) => value.trim())) rows.push(row)
      row = []
      cell = ''
      continue
    }

    cell += char
  }

  row.push(cell)
  if (row.some((value) => value.trim())) rows.push(row)
  return rows
}

export function parseCsvImport(text: string): BatchImportPayload {
  const rows = parseCsv(text)
  const [headers, ...dataRows] = rows
  if (!headers || dataRows.length === 0) {
    throw new Error('CSV 至少需要标题行和一行数据')
  }

  const columnIndexes = new Map(headers.map((header, index) => [header.trim(), index]))
  const getValue = (row: string[], key: string) => row[columnIndexes.get(key) ?? -1]?.trim() ?? ''
  const authorMap = new Map<string, { name: string; bio: string | null }>()
  const collectionMap = new Map<string, ImportCollectionInput>()
  const poems: NonNullable<BatchImportPayload['poems']> = []

  dataRows.forEach((row, index) => {
    const title = getValue(row, 'title')
    const author = getValue(row, 'author')
    const content = getValue(row, 'content').replace(/\\n/g, '\n')
    const authorBio = getValue(row, 'author_bio') || null
    const collectionDescription = getValue(row, 'collection_description') || null
    const collections = getValue(row, 'collections')
      .split(';')
      .map((item) => item.trim())
      .filter(Boolean)

    if (!title || !author || !content) {
      throw new Error(`CSV 第 ${index + 2} 行必须包含 title、author、content`)
    }

    if (!authorMap.has(author)) {
      authorMap.set(author, { name: author, bio: authorBio })
    }

    collections.forEach((name) => {
      if (!collectionMap.has(name)) {
        collectionMap.set(name, { name, description: collectionDescription, poems: [] })
      }
      collectionMap.get(name)?.poems?.push({ title, author })
    })

    poems.push({ title, author, content, collections })
  })

  return {
    authors: Array.from(authorMap.values()),
    poems,
    collections: Array.from(collectionMap.values()),
  }
}

export function parseImportText(text: string): BatchImportPayload {
  const value = JSON.parse(text) as BatchImportPayload
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('JSON 顶层必须是对象')
  }
  return value
}
