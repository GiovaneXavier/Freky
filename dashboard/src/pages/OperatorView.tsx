import { useState } from 'react'
import { useScans } from '../hooks/useScans'
import { DecisionBadge } from '../components/DecisionBadge'
import { ScanDetailModal } from '../components/ScanDetailModal'
import { ScanResult } from '../types/scan'

const CLASS_PT: Record<string, string> = {
  mobile_phone: 'Celular',
  tablet: 'Tablet',
  laptop: 'Notebook',
  portable_charger_1: 'Powerbank',
  portable_charger_2: 'Powerbank',
  cosmetic: 'Cosmético',
  water: 'Água',
  nonmetallic_lighter: 'Isqueiro',
  key: 'Chave',
  coin: 'Moeda',
  wallet: 'Carteira',
}

function ScanCard({ scan }: { scan: ScanResult }) {
  return (
    <div className="bg-gray-800 rounded-xl p-6 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="text-gray-400 text-sm truncate max-w-[240px]">{scan.filename}</span>
        {scan.processing_time_ms != null && (
          <span className="text-gray-500 text-xs">{scan.processing_time_ms.toFixed(0)} ms</span>
        )}
      </div>

      <div className="flex justify-center">
        <DecisionBadge decision={scan.decision} large />
      </div>

      {scan.detections.length > 0 && (
        <div>
          <p className="text-gray-400 text-sm mb-2">Itens detectados</p>
          <ul className="space-y-1">
            {scan.detections.map((d, i) => (
              <li key={i} className="flex justify-between text-sm">
                <span className="text-white">{CLASS_PT[d.class_name] ?? d.class_name}</span>
                <span className="text-gray-400">{(d.confidence * 100).toFixed(0)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {scan.detections.length === 0 && (
        <p className="text-gray-600 text-sm text-center">Nenhum item detectado</p>
      )}
    </div>
  )
}

export function OperatorView() {
  const { latest, history } = useScans()
  const [selected, setSelected] = useState<ScanResult | null>(null)

  return (
    <div className="p-6 text-white">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Resultado atual — destaque */}
        <div className="lg:col-span-2">
          <h2 className="text-gray-400 text-sm uppercase tracking-widest mb-3">Último scan</h2>
          {latest ? (
            <ScanCard scan={latest} />
          ) : (
            <div className="bg-gray-800 rounded-xl p-10 flex items-center justify-center text-gray-600 text-sm">
              Aguardando próximo scan...
            </div>
          )}
        </div>

        {/* Histórico */}
        <div>
          <h2 className="text-gray-400 text-sm uppercase tracking-widest mb-3">
            Histórico ({history.length})
          </h2>
          <div className="space-y-2 max-h-[72vh] overflow-y-auto pr-1">
            {history.map(scan => (
              <button
                key={scan.id}
                onClick={() => setSelected(scan)}
                className="w-full bg-gray-800 rounded-lg px-4 py-3 flex items-center justify-between hover:bg-gray-700 transition-colors text-left"
              >
                <div className="min-w-0">
                  <p className="text-sm text-white truncate">{scan.filename}</p>
                  <p className="text-xs text-gray-500">
                    {new Date(scan.created_at).toLocaleTimeString('pt-BR')}
                  </p>
                </div>
                <DecisionBadge decision={scan.decision} />
              </button>
            ))}
          </div>
        </div>
      </div>

      {selected && (
        <ScanDetailModal
          scan={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}
