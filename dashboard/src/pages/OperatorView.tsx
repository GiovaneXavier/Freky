import { useScans } from '../hooks/useScans'
import { DecisionBadge } from '../components/DecisionBadge'
import { ScanResult } from '../types/scan'

function classLabel(name: string): string {
  const map: Record<string, string> = {
    mobile_phone: 'Celular',
    tablet: 'Tablet',
    laptop: 'Notebook',
    portable_charger: 'Powerbank',
    portable_charger_1: 'Powerbank',
    portable_charger_2: 'Powerbank',
    kindle: 'Kindle',
    e_reader: 'E-Reader',
    key: 'Chave',
    coin: 'Moeda',
    wallet: 'Carteira',
  }
  return map[name] ?? name
}

function ScanCard({ scan }: { scan: ScanResult }) {
  return (
    <div className="bg-gray-800 rounded-xl p-6 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="text-gray-400 text-sm">{scan.filename}</span>
        {scan.processing_time_ms && (
          <span className="text-gray-500 text-xs">{scan.processing_time_ms.toFixed(0)}ms</span>
        )}
      </div>

      <div className="flex justify-center">
        <DecisionBadge decision={scan.decision} large />
      </div>

      {scan.detections.length > 0 && (
        <div>
          <p className="text-gray-400 text-sm mb-2">Itens detectados:</p>
          <ul className="space-y-1">
            {scan.detections.map((d, i) => (
              <li key={i} className="flex justify-between text-sm">
                <span className="text-white">{classLabel(d.class_name)}</span>
                <span className="text-gray-400">{(d.confidence * 100).toFixed(0)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function OperatorView() {
  const { latest, history, connected } = useScans()

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <header className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold tracking-wide">FREKY</h1>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-red-400'}`} />
          <span className="text-sm text-gray-400">{connected ? 'Conectado' : 'Reconectando...'}</span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Resultado atual — destaque */}
        <div className="lg:col-span-2">
          <h2 className="text-gray-400 text-sm uppercase tracking-widest mb-3">Ultimo scan</h2>
          {latest ? (
            <ScanCard scan={latest} />
          ) : (
            <div className="bg-gray-800 rounded-xl p-10 flex items-center justify-center text-gray-600">
              Aguardando proximo scan...
            </div>
          )}
        </div>

        {/* Historico */}
        <div>
          <h2 className="text-gray-400 text-sm uppercase tracking-widest mb-3">
            Historico ({history.length})
          </h2>
          <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
            {history.map((scan) => (
              <div
                key={scan.id}
                className="bg-gray-800 rounded-lg px-4 py-3 flex items-center justify-between"
              >
                <div>
                  <p className="text-sm text-white truncate max-w-[140px]">{scan.filename}</p>
                  <p className="text-xs text-gray-500">
                    {new Date(scan.created_at).toLocaleTimeString('pt-BR')}
                  </p>
                </div>
                <DecisionBadge decision={scan.decision} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
