
import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { UploadPage } from './pages/UploadPage'
import { MatchPage } from './pages/MatchPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        {/* Redirect root to upload */}
        <Route index element={<Navigate to="/upload" replace />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="match" element={<MatchPage />} />
      </Route>
    </Routes>
  )
}

export default App

