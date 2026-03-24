import { useState } from 'react'
import { ScanResult } from '../types/scan'
import { DecisionBadge } from './DecisionBadge'
import { submitFeedback } from '../hooks/useAudit'

const CLASS_PT: Record<string, string> = {
  mobile_phone: 'Celular',
  tablet: 'Tablet',
  laptop: 'Notebook',
  portable_charger_1: 'Powerbank',
  portable_charger_2: 'Powerbank',
  cosmetic: 'Cosmético',
  water: 'Água',
  nonmetallic_lighter: 'Isqueiro',
}

interface Props {
  scan: ScanResult
  onClose: () => void
  onFeedbackSent?: () => void
}

export function ScanDetailModal({ scan, onClose, onFeedbackSent }: Props) {
  const [operatorId, setOperatorId] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(!!scan.operator_feedback)

  const handleFeedback = async (type: 'confirmed' | 'false_positive' | 'false_negative') => {
    if (!operatorId.trim()) return
    setSending(true)
    try {
      await submitFeedback(scan.id, operatorId.trim(), type)
      setSent(true)
      onFeedbackSent?.()
    } finally {
      setSending(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-800 rounded-2xl w-full max-w-lg p-6 flex flex-col gap-5"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <p className="text-gray-400 text-xs mb-1">{scan.filename}</p>
            <p className="text-gray-500 text-xs">
              {new Date(scan.created_at).toLocaleString('pt-BR')}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">✕</button>
        </div>

        {/* Decisao */}
        <div className="flex justify-center">
          <DecisionBadge decision={scan.decision} large />
        </div>

        {/* Deteccoes */}
        {scan.detections.length > 0 ? (
          <div>
            <p className="text-gray-400 text-sm mb-2 uppercase tracking-wide">Itens detectados</p>
            <div className="space-y-2">
              {scan.detections.map((d, i) => (
                <div key={i} className="flex items-center justify-between bg-gray-700 rounded-lg px-4 py-2">
                  <span className="text-white text-sm">{CLASS_PT[d.class_name] ?? d.class_name}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 bg-gray-600 rounded-full h-1.5">
                      <div
                        className="bg-blue-400 h-1.5 rounded-full"
                        style={{ width: `${d.confidence * 100}%` }}
                      />
                    </div>
                    <span className="text-gray-400 text-xs w-10 text-right">
                      {(d.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-gray-500 text-sm text-center">Nenhum item detectado</p>
        )}

        {/* Feedback */}
        <div className="border-t border-gray-700 pt-4">
          <p className="text-gray-400 text-sm mb-3 uppercase tracking-wide">Feedback do operador</p>
          {sent ? (
            <p className="text-green-400 text-sm text-center">
              ✓ Feedback registrado: <strong>{scan.operator_feedback ?? 'confirmado'}</strong>
            </p>
          ) : (
            <>
              <input
                type="text"
                placeholder="ID do operador"
                value={operatorId}
                onChange={e => setOperatorId(e.target.value)}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 mb-3 focus:outline-none focus:border-blue-500"
              />
              <div className="grid grid-cols-3 gap-2">
                <button
                  disabled={!operatorId || sending}
                  onClick={() => handleFeedback('confirmed')}
                  className="bg-green-600 hover:bg-green-500 disabled:opacity-40 text-white text-xs font-medium py-2 rounded-lg transition-colors"
                >
                  Confirmar
                </button>
                <button
                  disabled={!operatorId || sending}
                  onClick={() => handleFeedback('false_positive')}
                  className="bg-yellow-600 hover:bg-yellow-500 disabled:opacity-40 text-white text-xs font-medium py-2 rounded-lg transition-colors"
                >
                  Falso positivo
                </button>
                <button
                  disabled={!operatorId || sending}
                  onClick={() => handleFeedback('false_negative')}
                  className="bg-red-700 hover:bg-red-600 disabled:opacity-40 text-white text-xs font-medium py-2 rounded-lg transition-colors"
                >
                  Falso negativo
                </button>
              </div>
            </>
          )}
        </div>

        {/* Metricas */}
        {scan.processing_time_ms && (
          <p className="text-center text-gray-600 text-xs">
            Processado em {scan.processing_time_ms.toFixed(0)} ms
          </p>
        )}
      </div>
    </div>
  )
}
