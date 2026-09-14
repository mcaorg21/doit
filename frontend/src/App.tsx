import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import ProjectListPage from './pages/ProjectListPage'
import WorkflowListPage from './pages/WorkflowListPage'
import EditorPage from './pages/EditorPage'
import BackupPage from './pages/BackupPage'
import ExecutionsPage from './pages/ExecutionsPage'
import LanguageToggle from './i18n/LanguageToggle'

// The "data router" (createBrowserRouter + RouterProvider), not the plain
// <BrowserRouter>/<Routes> pair this app used before — required for the
// `viewTransition` prop on <Link>/setSearchParams to actually do anything: React
// Router only wires document.startViewTransition() through its data-router state
// machine, so the declarative router silently ignored the prop. See index.css for
// the actual transition styling (::view-transition-old/new(root)).
const router = createBrowserRouter([
  { path: '/', Component: ProjectListPage },
  { path: '/projects/:projectId', Component: WorkflowListPage },
  { path: '/projects/:projectId/backup', Component: BackupPage },
  { path: '/projects/:projectId/executions', Component: ExecutionsPage },
  { path: '/projects/:projectId/workflows/:workflowId', Component: EditorPage },
])

function App() {
  return (
    <>
      <LanguageToggle />
      <RouterProvider router={router} />
    </>
  )
}

export default App
