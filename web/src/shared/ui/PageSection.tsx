import type { PropsWithChildren, ReactNode } from 'react'

interface PageSectionProps extends PropsWithChildren {
  title: string
  subtitle: string
  actions?: ReactNode
}

export function PageSection({ title, subtitle, actions, children }: PageSectionProps) {
  return (
    <section className="page-section">
      <div className="page-section-header">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        {actions ? <div>{actions}</div> : null}
      </div>
      {children}
    </section>
  )
}
