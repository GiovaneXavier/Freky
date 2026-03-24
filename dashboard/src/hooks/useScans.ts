import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { ScanResult } from '../types/scan'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000'
const MAX_HISTORY = 50
const RECONNECT_BASE_MS = 1000
const RECONNECT_MAX_MS = 30000

interface ScansContextValue {
  latest: ScanResult | null
  history: ScanResult[]
  connected: boolean
}

export const ScansContext = createContext<ScansContextValue>({
  latest: null,
  history: [],
  connected: false,
})

export function useScans() {
  return useContext(ScansContext)
}

export function useScansState(): ScansContextValue {
  const [latest, setLatest] = useState<ScanResult | null>(null)
  const [history, setHistory] = useState<ScanResult[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptRef = useRef(0)
  const unmountedRef = useRef(false)

  useEffect(() => {
    unmountedRef.current = false

    function connect() {
      if (unmountedRef.current) return

      const token = localStorage.getItem('freky_token') ?? ''
      const ws = new WebSocket(`${WS_URL}/ws?token=${encodeURIComponent(token)}`)
      wsRef.current = ws

      ws.onopen = () => {
        if (unmountedRef.current) { ws.close(); return }
        attemptRef.current = 0
        setConnected(true)
      }

      ws.onclose = () => {
        if (unmountedRef.current) return
        setConnected(false)
        const delay = Math.min(
          RECONNECT_BASE_MS * Math.pow(2, attemptRef.current),
          RECONNECT_MAX_MS,
        )
        attemptRef.current += 1
        retryRef.current = setTimeout(connect, delay)
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'scan_result') {
            const scan: ScanResult = msg.data
            setLatest(scan)
            setHistory((prev) => [scan, ...prev].slice(0, MAX_HISTORY))
          }
        } catch {
          // mensagem malformada — ignora
        }
      }
    }

    connect()

    return () => {
      unmountedRef.current = true
      if (retryRef.current) clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [])

  return { latest, history, connected }
}
