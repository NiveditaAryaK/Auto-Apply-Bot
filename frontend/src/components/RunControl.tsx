import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Run } from '../types'

const POLL_INTERVAL_MS = 2000

export function RunControl({ onRunFinished }: { onRunFinished: () => void }) {
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<number | null>(null)

  const stopPolling = () => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  useEffect(() => stopPolling, [])

  const poll = (runId: number) => {
    stopPolling()
    pollRef.current = window.setInterval(async () => {
      try {
        const updated = await api.getRun(runId)
        setRun(updated)
        if (updated.status !== 'running') {
          stopPolling()
          onRunFinished()
        }
      } catch (e) {
        stopPolling()
        setError((e as Error).message)
      }
    }, POLL_INTERVAL_MS)
  }

  const start = async () => {
    setError(null)
    try {
      const started = await api.triggerRun()
      setRun(started)
      poll(started.id)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const running = run?.status === 'running'

  return (
    <div className="run-control">
      <button onClick={start} disabled={running}>
        {running ? 'Running…' : 'Run Pipeline'}
      </button>
      {error && <span className="error">{error}</span>}
      {run?.status === 'completed' && (
        <span className="run-summary">
          Found {run.postings_found ?? 0}, passed {run.screened_pass ?? 0}, applied {run.applied_count ?? 0}
        </span>
      )}
      {run?.status === 'failed' && <span className="error">Run failed: {run.error}</span>}
    </div>
  )
}
