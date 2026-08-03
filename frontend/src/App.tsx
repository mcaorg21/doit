import { Route, Routes } from 'react-router-dom'
import ProjectListPage from './pages/ProjectListPage'
import WorkflowListPage from './pages/WorkflowListPage'
import EditorPage from './pages/EditorPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<ProjectListPage />} />
      <Route path="/projects/:projectId" element={<WorkflowListPage />} />
      <Route path="/projects/:projectId/workflows/:workflowId" element={<EditorPage />} />
    </Routes>
  )
}

export default App
