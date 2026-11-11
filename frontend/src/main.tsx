import '@fontsource-variable/inter'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router'
import './index.css'
import { AppShell } from './components/AppShell'
import { JobPage } from './pages/JobPage'
import { JobsPage } from './pages/JobsPage'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<JobsPage />} />
          <Route path="/jobs/:jobId" element={<JobPage />} />
          <Route path="/jobs/:jobId/applicants/:applicantId" element={<JobPage />} />
          <Route path="/jobs/:jobId/setup" element={<JobPage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  </StrictMode>,
)
