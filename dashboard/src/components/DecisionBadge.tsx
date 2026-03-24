import { Decision } from '../types/scan'

interface Props {
  decision: Decision
  large?: boolean
}

const CONFIG: Record<Decision, { label: string; bg: string; text: string }> = {
  LIBERADO:     { label: 'LIBERADO',     bg: 'bg-green-500',  text: 'text-white' },
  VERIFICAR:    { label: 'VERIFICAR',    bg: 'bg-red-500',    text: 'text-white' },
  INCONCLUSIVO: { label: 'INCONCLUSIVO', bg: 'bg-yellow-400', text: 'text-black' },
}

export function DecisionBadge({ decision, large = false }: Props) {
  const { label, bg, text } = CONFIG[decision]
  return (
    <span className={`
      ${bg} ${text} font-bold rounded-lg
      ${large ? 'text-5xl px-10 py-6' : 'text-sm px-3 py-1'}
    `}>
      {label}
    </span>
  )
}
