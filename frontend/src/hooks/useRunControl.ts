import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Run } from '../types'

const POLL_INTERVAL_MS = 2000

export function useRunControl(onRunFinished?: () => void) {
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<number | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  useEffect(() => stopPolling, [stopPolling])

  const poll = useCallback(
    (runId: number) => {
      stopPolling()
      pollRef.current = window.setInterval(async () => {
        try {
          const updated = await api.getRun(runId)
          setRun(updated)
          if (updated.status !== 'running') {
            stopPolling()
            onRunFinished?.()
          }
        } catch (e) {
          stopPolling()
          setError((e as Error).message)
        }
      }, POLL_INTERVAL_MS)
    },
    [stopPolling, onRunFinished],
  )

  const start = useCallback(async () => {
    setError(null)
    try {
      const started = await api.triggerRun()
      setRun(started)
      poll(started.id)
      return started
    } catch (e) {
      setError((e as Error).message)
      return null
    }
  }, [poll])

  return { run, error, running: run?.status === 'running', start }
}
