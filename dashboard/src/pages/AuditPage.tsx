import { useState } from 'react'
import { Decision, ScanResult } from '../types/scan'
import { useAudit, AuditFilters } from '../hooks/useAudit'
import { DecisionBadge } from '../components/DecisionBadge'
import { ScanDetailModal } from '../components/ScanDetailModal'

const DECISIONS: { value: Decision | ''; label: string }[] = [
  { value: '',             label: 'Todos' },
  { value: 'LIBERADO',     label: 'Liberado' },
  { value: 'VERIFICAR',    label: 'Verificar' },
  { value: 'INCONCLUSIVO', label: 'Inconclusivo' },
]

const FEEDBACK_LABEL: Record<string, string> = {
  confirmed:       'Confirmado',
  false_positive:  'Falso positivo',
  false_negative:  'Falso negativo',
}

export function AuditPage() {
  const [filters, setFilters] = useState<AuditFilters>({ page: 1 })
  const [selected, setSelected] = useState<ScanResult | null>(null)

  const { scans, loading, hasMore, refetch } = useAudit(filters)

  const set = (patch: Partial<AuditFilters>) =>
    setFilters(prev => ({ ...prev, ...patch, page: 1 }))

  return (
    <div className="p-6 text-white">
      <h1 className="text-xl font-bold mb-5">Auditoria de Scans</h1>

      {/* Filtros */}
      <div className="flex flex-wrap gap-3 mb-6">
        <select
          value={filters.decision ?? ''}
          onChange={e => set({ decision: e.target.value as Decision | '' })}
          className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
        >
          {DECISIONS.map(d => (
            <option key={d.value} value={d.value}>{d.label}</option>
          ))}
        </select>

        <div className="flex items-center gap-2">
          <input
            type="date"
            value={filters.dateFrom ?? ''}
            onChange={e => set({ dateFrom: e.target.value })}
            className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
          />
          <span className="text-gray-500 text-sm">até</span>
          <input
            type="date"
            value={filters.dateTo ?? ''}
            onChange={e => set({ dateTo: e.target.value })}
            className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
          />
        </div>

        <button
          onClick={() => setFilters({ page: 1 })}
          className="px-4 py-2 text-sm text-gray-400 hover:text-white bg-gray-800 border border-gray-600 rounded-lg transition-colors"
        >
          Limpar filtros
        </button>
      </div>

      {/* Tabela */}
      <div className="bg-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400 text-left">
              <th className="px-4 py-3 font-medium">Data/Hora</th>
              <th className="px-4 py-3 font-medium">Arquivo</th>
              <th className="px-4 py-3 font-medium">Decisão</th>
              <th className="px-4 py-3 font-medium">Itens</th>
              <th className="px-4 py-3 font-medium">Feedback</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                  Carregando...
                </td>
              </tr>
            )}
            {!loading && scans.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                  Nenhum scan encontrado
                </td>
              </tr>
            )}
            {scans.map(scan => (
              <tr
                key={scan.id}
                className="border-b border-gray-700/50 hover:bg-gray-700/40 transition-colors"
              >
                <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                  {new Date(scan.created_at).toLocaleString('pt-BR')}
                </td>
                <td className="px-4 py-3 text-gray-300 max-w-[180px] truncate">
                  {scan.filename}
                </td>
                <td className="px-4 py-3">
                  <DecisionBadge decision={scan.decision} />
                </td>
                <td className="px-4 py-3 text-gray-400">
                  {scan.detections.length}
                </td>
                <td className="px-4 py-3">
                  {scan.operator_feedback ? (
                    <span className="text-xs text-gray-400">
                      {FEEDBACK_LABEL[scan.operator_feedback] ?? scan.operator_feedback}
                    </span>
                  ) : (
                    <span className="text-xs text-gray-600">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => setSelected(scan)}
                    className="text-blue-400 hover:text-blue-300 text-xs underline"
                  >
                    Detalhes
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Paginacao */}
      <div className="flex justify-between items-center mt-4">
        <button
          disabled={filters.page <= 1}
          onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}
          className="px-4 py-2 text-sm bg-gray-800 border border-gray-700 rounded-lg disabled:opacity-40 hover:bg-gray-700 transition-colors"
        >
          ← Anterior
        </button>
        <span className="text-gray-500 text-sm">Página {filters.page}</span>
        <button
          disabled={!hasMore}
          onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}
          className="px-4 py-2 text-sm bg-gray-800 border border-gray-700 rounded-lg disabled:opacity-40 hover:bg-gray-700 transition-colors"
        >
          Próxima →
        </button>
      </div>

      {/* Modal */}
      {selected && (
        <ScanDetailModal
          scan={selected}
          onClose={() => setSelected(null)}
          onFeedbackSent={refetch}
        />
      )}
    </div>
  )
}
