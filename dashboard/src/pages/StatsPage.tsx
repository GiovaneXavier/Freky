import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { useAuditStats, useDailyStats } from '../hooks/useAudit'
import { Decision } from '../types/scan'

const DECISION_COLORS: Record<Decision, string> = {
  LIBERADO:     '#22c55e',
  VERIFICAR:    '#ef4444',
  INCONCLUSIVO: '#eab308',
}

const DECISION_PT: Record<Decision, string> = {
  LIBERADO:     'Liberado',
  VERIFICAR:    'Verificar',
  INCONCLUSIVO: 'Inconclusivo',
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-gray-800 rounded-xl p-5 flex flex-col gap-1">
      <p className="text-gray-400 text-xs uppercase tracking-wide">{label}</p>
      <p className="text-white text-3xl font-bold">{value}</p>
      {sub && <p className="text-gray-500 text-xs">{sub}</p>}
    </div>
  )
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs">
      <p className="text-gray-300 mb-1">{label}</p>
      {payload.map((entry: any) => (
        <p key={entry.dataKey} style={{ color: entry.fill }}>
          {DECISION_PT[entry.dataKey as Decision] ?? entry.dataKey}: {entry.value}
        </p>
      ))}
    </div>
  )
}

export function StatsPage() {
  const stats = useAuditStats()
  const daily = useDailyStats(14)

  const total = stats?.total ?? 0
  const verificar = stats?.by_decision['VERIFICAR'] ?? 0
  const liberado  = stats?.by_decision['LIBERADO']  ?? 0
  const taxaVerif = total > 0 ? ((verificar / total) * 100).toFixed(1) : '—'

  const pieData = Object.entries(stats?.by_decision ?? {}).map(([key, value]) => ({
    name: DECISION_PT[key as Decision] ?? key,
    value,
    color: DECISION_COLORS[key as Decision] ?? '#6b7280',
  }))

  const formatDate = (d: string) =>
    new Date(d + 'T00:00:00').toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })

  return (
    <div className="p-6 text-white">
      <h1 className="text-xl font-bold mb-5">Estatísticas</h1>

      {/* Cards resumo */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total de scans" value={total} />
        <StatCard label="Liberados" value={liberado}
          sub={total > 0 ? `${((liberado / total) * 100).toFixed(1)}%` : undefined} />
        <StatCard label="Para verificar" value={verificar}
          sub={total > 0 ? `${taxaVerif}%` : undefined} />
        <StatCard
          label="Taxa de detecção"
          value={`${taxaVerif}%`}
          sub="scans com item restrito"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Grafico de barras diario */}
        <div className="lg:col-span-2 bg-gray-800 rounded-xl p-5">
          <h2 className="text-gray-400 text-sm uppercase tracking-wide mb-4">
            Scans por dia — últimas 2 semanas
          </h2>
          {daily.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={daily} barCategoryGap="25%">
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDate}
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                <Bar dataKey="LIBERADO"     stackId="a" fill={DECISION_COLORS.LIBERADO}     radius={[0,0,0,0]} />
                <Bar dataKey="VERIFICAR"    stackId="a" fill={DECISION_COLORS.VERIFICAR}    radius={[0,0,0,0]} />
                <Bar dataKey="INCONCLUSIVO" stackId="a" fill={DECISION_COLORS.INCONCLUSIVO} radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[260px] flex items-center justify-center text-gray-600">
              Sem dados ainda
            </div>
          )}
        </div>

        {/* Pizza */}
        <div className="bg-gray-800 rounded-xl p-5">
          <h2 className="text-gray-400 text-sm uppercase tracking-wide mb-4">
            Distribuição geral
          </h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="45%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={3}
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Legend
                  iconType="circle"
                  iconSize={8}
                  formatter={(value) => (
                    <span style={{ color: '#d1d5db', fontSize: 12 }}>{value}</span>
                  )}
                />
                <Tooltip
                  formatter={(value: number) => [value, 'Scans']}
                  contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                  labelStyle={{ color: '#d1d5db' }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[260px] flex items-center justify-center text-gray-600">
              Sem dados ainda
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
