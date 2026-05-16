import type { PresenceSummaryStats } from '@/lib/types'

interface CardProps {
  label: string
  value: number
  sublabel?: string
  variant?: 'default' | 'green' | 'blue' | 'indigo' | 'red'
}

function StatCard({ label, value, sublabel, variant = 'default' }: CardProps) {
  const accent: Record<string, string> = {
    default: 'text-gray-800',
    green:   'text-emerald-700',
    blue:    'text-sky-700',
    indigo:  'text-indigo-700',
    red:     'text-rose-600',
  }
  const border: Record<string, string> = {
    default: 'border-gray-200',
    green:   'border-emerald-200',
    blue:    'border-sky-200',
    indigo:  'border-indigo-200',
    red:     'border-rose-200',
  }
  const bg: Record<string, string> = {
    default: 'bg-white',
    green:   'bg-emerald-50',
    blue:    'bg-sky-50',
    indigo:  'bg-indigo-50',
    red:     'bg-rose-50',
  }

  return (
    <div className={`rounded-lg border ${border[variant]} ${bg[variant]} px-4 py-4 shadow-sm`}>
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider leading-none mb-1">
        {label}
      </p>
      <p className={`text-3xl font-bold tabular-nums leading-none ${accent[variant]}`}>{value}</p>
      {sublabel && (
        <p className="text-xs text-gray-400 mt-1">{sublabel}</p>
      )}
    </div>
  )
}

interface PresenceSummaryCardsProps {
  stats: PresenceSummaryStats
}

export default function PresenceSummaryCards({ stats }: PresenceSummaryCardsProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <StatCard
        label="Total participants"
        value={stats.total}
        variant="default"
      />
      <StatCard
        label="REDCap data"
        value={stats.withRedcap}
        sublabel="self-report available"
        variant="blue"
      />
      <StatCard
        label="Synapse data"
        value={stats.withSynapse}
        sublabel="BiAffect matched"
        variant="indigo"
      />
      <StatCard
        label="Both sources"
        value={stats.withBoth}
        sublabel="fully linked"
        variant="green"
      />
      <StatCard
        label="Missing linkage"
        value={stats.missingLinkage}
        sublabel="no data source"
        variant={stats.missingLinkage > 0 ? 'red' : 'default'}
      />
    </div>
  )
}
