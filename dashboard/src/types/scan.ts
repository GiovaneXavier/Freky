export type Decision = 'LIBERADO' | 'VERIFICAR' | 'INCONCLUSIVO'

export interface Detection {
  class_name: string
  confidence: number
  bbox: [number, number, number, number]
}

export interface ScanResult {
  id: string
  created_at: string
  filename: string
  decision: Decision
  detections: Detection[]
  processing_time_ms: number | null
}
