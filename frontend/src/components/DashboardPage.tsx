import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Application } from '../types'

const STATUS_LABEL: Record<string, string> = {
  screened_pass: 'Screened (pass)',
  screened_reject: 'Screened (reject)',
  applied: 'Applied',
  apply_failed: 'Apply failed',
  rate_limited: 'Rate limited',
}

export function DashboardPage({ refreshKey }: { refreshKey: number }) {
  const [applications, setApplications] = useState<Application[]>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setApplications(await api.listApplications())
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh, refreshKey])

  return (
    <div className="page">
      <h2>Applications</h2>
      {error && <p className="error">{error}</p>}
      <table className="applications-table">
        <thead>
          <tr>
            <th>Company</th>
            <th>Title</th>
            <th>Status</th>
            <th>Score</th>
            <th>Recorded</th>
          </tr>
        </thead>
        <tbody>
          {applications.map((a) => (
            <tr key={a.id}>
              <td>{a.company}</td>
              <td>
                <a href={a.url} target="_blank" rel="noreferrer">
                  {a.title}
                </a>
              </td>
              <td>
                <span className={`status status-${a.status}`}>{STATUS_LABEL[a.status] ?? a.status}</span>
              </td>
              <td>{a.match_score ?? '—'}</td>
              <td>{a.applied_at ? new Date(a.applied_at).toLocaleString() : '—'}</td>
            </tr>
          ))}
          {applications.length === 0 && (
            <tr>
              <td colSpan={5} className="empty">
                No applications recorded yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
