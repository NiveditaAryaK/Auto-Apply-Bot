import { useState } from 'react'
import './App.css'
import { DashboardPage } from './components/DashboardPage'
import { ResumesPage } from './components/ResumesPage'
import { RunControl } from './components/RunControl'

type Tab = 'dashboard' | 'resumes'

function App() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [refreshKey, setRefreshKey] = useState(0)

  return (
    <div className="app">
      <header className="app-header">
        <h1>job_agent</h1>
        <nav>
          <button className={tab === 'dashboard' ? 'active' : ''} onClick={() => setTab('dashboard')}>
            Dashboard
          </button>
          <button className={tab === 'resumes' ? 'active' : ''} onClick={() => setTab('resumes')}>
            Resumes
          </button>
        </nav>
        <RunControl onRunFinished={() => setRefreshKey((k) => k + 1)} />
      </header>

      <main>{tab === 'dashboard' ? <DashboardPage refreshKey={refreshKey} /> : <ResumesPage />}</main>
    </div>
  )
}

export default App
