import { Navigate, RouterProvider, createBrowserRouter } from 'react-router-dom'

import { AppShell } from '../shared/ui/AppShell'
import { AuthorsPage } from '../pages/AuthorsPage'
import { CollectionsPage } from '../pages/CollectionsPage'
import { DocumentsPage } from '../pages/DocumentsPage'
import { FeihualingPage } from '../pages/FeihualingPage'
import { PoemsPage } from '../pages/PoemsPage'
import { RagPage } from '../pages/RagPage'
import { SettingsPage } from '../pages/SettingsPage'
import { WorkspacePage } from '../pages/WorkspacePage'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/feihualing" replace /> },
      { path: 'feihualing', element: <FeihualingPage /> },
      {
        path: 'workspace',
        element: <WorkspacePage />,
        children: [
          { index: true, element: <Navigate to="poems" replace /> },
          { path: 'poems', element: <PoemsPage /> },
          { path: 'authors', element: <AuthorsPage /> },
          { path: 'collections', element: <CollectionsPage /> },
          { path: 'documents', element: <DocumentsPage /> },
          { path: 'rag', element: <RagPage /> },
          { path: 'settings', element: <SettingsPage /> },
        ],
      },
      { path: 'poems', element: <Navigate to="/workspace/poems" replace /> },
      { path: 'authors', element: <Navigate to="/workspace/authors" replace /> },
      { path: 'collections', element: <Navigate to="/workspace/collections" replace /> },
      { path: 'documents', element: <Navigate to="/workspace/documents" replace /> },
      { path: 'rag', element: <Navigate to="/workspace/rag" replace /> },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
