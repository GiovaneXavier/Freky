import { useEffect, useRef, useState } from 'react'
import { ScanResult } from '../types/scan'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000'
const MAX_HISTORY = 50

export function useScans() {
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
        setTimeout(connect, 3000) // reconecta automaticamente
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
