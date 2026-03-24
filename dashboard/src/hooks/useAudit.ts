import { useCallback, useEffect, useState } from 'react'
import { Decision, ScanResult } from '../types/scan'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface AuditFilters {
  decision?: Decision | ''
  dateFrom?: string
  dateTo?: string
  page: number
}

export interface AuditStats {
  total: number
  by_decision: Partial<Record<Decision, number>>
}

export interface DailyStat {
  date: string
  LIBERADO: number
  VERIFICAR: number
  INCONCLUSIVO: number
}

export function useAudit(filters: AuditFilters) {
  const [scans, setScans] = useState<ScanResult[]>([])
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(true)

  const fetchScans = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams({ page: String(filters.page), page_size: '50' })
    if (filters.decision)  params.set('decision',   filters.decision)
    if (filters.dateFrom)  params.set('date_from',  filters.dateFrom)
    if (filters.dateTo)    params.set('date_to',    filters.dateTo)

    try {
      const res = await fetch(`${API}/audit/?${params}`)
      const data: ScanResult[] = await res.json()
      setScans(data)
      setHasMore(data.length === 50)
    } finally {
      setLoading(false)
    }
  }, [filters.page, filters.decision, filters.dateFrom, filters.dateTo])

  useEffect(() => { fetchScans() }, [fetchScans])

  return { scans, loading, hasMore, refetch: fetchScans }
}

export function useAuditStats() {
  const [stats, setStats] = useState<AuditStats | null>(null)

  useEffect(() => {
    fetch(`${API}/audit/stats`)
      .then(r => r.json())
      .then(setStats)
      .catch(() => {})
  }, [])

  return stats
}

export function useDailyStats(days: number = 14) {
  const [data, setData] = useState<DailyStat[]>([])

  useEffect(() => {
    fetch(`${API}/audit/daily?days=${days}`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
  }, [days])

  return data
}

export async function submitFeedback(
  scanId: string,
  operatorId: string,
  feedback: 'confirmed' | 'false_positive' | 'false_negative',
): Promise<void> {
  await fetch(`${API}/scans/${scanId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, feedback }),
  })
}
