import { useCallback, useEffect, useState, type DragEvent } from 'react'
import { api } from '../api'
import type { Resume } from '../types'

export function ResumesPage() {
  const [resumes, setResumes] = useState<Resume[]>([])
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setResumes(await api.listResumes())
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const upload = async (file: File) => {
    setUploading(true)
    setError(null)
    try {
      await api.uploadResume(file, false)
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setUploading(false)
    }
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) upload(file)
  }

  const setPrimary = async (id: number) => {
    setError(null)
    try {
      await api.setPrimaryResume(id)
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const remove = async (id: number) => {
    setError(null)
    try {
      await api.deleteResume(id)
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="page">
      <h2>Resumes</h2>

      <div
        className={`dropzone${dragOver ? ' dropzone-active' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <p>{uploading ? 'Uploading…' : 'Drag & drop a resume (.pdf or .docx), or'}</p>
        <label className="file-picker">
          Browse files
          <input
            type="file"
            accept=".pdf,.docx"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) upload(file)
              e.target.value = ''
            }}
          />
        </label>
      </div>

      {error && <p className="error">{error}</p>}

      <ul className="resume-list">
        {resumes.map((r) => (
          <li key={r.id} className="resume-row">
            <span className="resume-name">{r.filename}</span>
            {r.is_primary ? (
              <span className="badge badge-primary">Primary</span>
            ) : (
              <button onClick={() => setPrimary(r.id)}>Set primary</button>
            )}
            <button
              className="danger"
              disabled={r.is_primary}
              title={r.is_primary ? 'Set a different resume as primary first' : undefined}
              onClick={() => remove(r.id)}
            >
              Delete
            </button>
          </li>
        ))}
        {resumes.length === 0 && <li className="empty">No resumes uploaded yet.</li>}
      </ul>
    </div>
  )
}
