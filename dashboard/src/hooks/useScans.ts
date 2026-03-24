import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { ScanResult } from '../types/scan'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000'
const MAX_HISTORY = 50

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

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(`${WS_URL}/ws`)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        setTimeout(connect, 3000)
      }
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)
        if (msg.type === 'scan_result') {
          const scan: ScanResult = msg.data
          setLatest(scan)
          setHistory((prev) => [scan, ...prev].slice(0, MAX_HISTORY))
        }
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  return { latest, history, connected }
}
