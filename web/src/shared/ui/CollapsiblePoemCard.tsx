import type { ReactNode } from 'react'
import { useState } from 'react'

interface CollapsiblePoemCardProps {
  id: number
  title: string
  author: string
  content: string
  onEdit?: () => void
  onDelete?: () => void
  onAddToCollection?: () => void
  editLabel?: string
  deleteLabel?: string
  addToCollectionLabel?: string
  disabled?: boolean
  expandedContent?: ReactNode
}

export function CollapsiblePoemCard({
  id,
  title,
  author,
  content,
  onEdit,
  onDelete,
  onAddToCollection,
  editLabel = '编辑',
  deleteLabel = '删除',
  addToCollectionLabel = '加入合集',
  disabled,
  expandedContent,
}: CollapsiblePoemCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <article className="card-item">
      <div className="card-item-header">
        <button className="card-toggle" type="button" onClick={() => setExpanded((value) => !value)}>
          <div>
            <h3>{title}</h3>
            {expanded ? <p>{author}</p> : null}
          </div>
        </button>

        <div className="card-toggle-meta">
          <span className="badge">#{id}</span>
          {onAddToCollection || onEdit || onDelete ? (
            <div className="menu-wrap">
              <button
                className="icon-button"
                type="button"
                aria-label="更多操作"
                onClick={() => setMenuOpen((value) => !value)}
              >
                ⋯
              </button>
              {menuOpen ? (
                <div className="popup-menu">
                  {onAddToCollection ? (
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => {
                        setMenuOpen(false)
                        onAddToCollection()
                      }}
                    >
                      {addToCollectionLabel}
                    </button>
                  ) : null}
                  {onEdit ? (
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => {
                        setMenuOpen(false)
                        onEdit()
                      }}
                    >
                      {editLabel}
                    </button>
                  ) : null}
                  {onDelete ? (
                    <button
                      className="danger-text"
                      type="button"
                      disabled={disabled}
                      onClick={() => {
                        setMenuOpen(false)
                        onDelete()
                      }}
                    >
                      {deleteLabel}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
          <button
            className={expanded ? 'chevron chevron-expanded' : 'chevron'}
            type="button"
            aria-label={expanded ? '收起诗词' : '展开诗词'}
            onClick={() => setExpanded((value) => !value)}
          >
            ▾
          </button>
        </div>
      </div>

      {expanded ? <p className="poem-content">{content}</p> : null}
      {expanded ? expandedContent : null}
    </article>
  )
}
