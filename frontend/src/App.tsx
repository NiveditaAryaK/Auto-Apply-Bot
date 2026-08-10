import { useState } from 'react'
import './App.css'
import { DashboardPage } from './components/DashboardPage'
import { ResumesPage } from './components/ResumesPage'
import { RunControl } from './components/RunControl'
import { useRunControl } from './hooks/useRunControl'

type Tab = 'dashboard' | 'resumes'

function App() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [refreshKey, setRefreshKey] = useState(0)
  const runControl = useRunControl(() => setRefreshKey((k) => k + 1))

  const handleResumeUploaded = async () => {
    const started = await runControl.start()
    if (started) setTab('dashboard')
  }

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
        <RunControl run={runControl.run} error={runControl.error} running={runControl.running} onStart={runControl.start} />
      </header>

      <main>
        {tab === 'dashboard' ? (
          <DashboardPage refreshKey={refreshKey} />
        ) : (
          <ResumesPage runInProgress={runControl.running} onResumeUploaded={handleResumeUploaded} />
        )}
      </main>
    </div>
  )
}

export default App
