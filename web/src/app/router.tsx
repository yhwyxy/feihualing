import { Navigate, RouterProvider, createBrowserRouter } from 'react-router-dom'

import { AppShell } from '../shared/ui/AppShell'
import { AuthorsPage } from '../pages/AuthorsPage'
import { CollectionsPage } from '../pages/CollectionsPage'
import { PoemsPage } from '../pages/PoemsPage'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/poems" replace /> },
      { path: 'poems', element: <PoemsPage /> },
      { path: 'authors', element: <AuthorsPage /> },
      { path: 'collections', element: <CollectionsPage /> },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
