import type { Run } from '../types'

export function RunControl({
  run,
  error,
  running,
  onStart,
}: {
  run: Run | null
  error: string | null
  running: boolean
  onStart: () => void
}) {
  return (
    <div className="run-control">
      <button onClick={onStart} disabled={running}>
        {running ? 'Running…' : 'Run Pipeline'}
      </button>
      {running && run?.current_step && <span className="run-progress">{run.current_step}</span>}
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
