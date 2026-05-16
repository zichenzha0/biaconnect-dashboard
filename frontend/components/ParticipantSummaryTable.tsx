import type { DashboardParticipant } from '@/lib/types'

interface Props {
  participants: DashboardParticipant[]
  selectedId: number | null
  onSelectParticipant: (p: DashboardParticipant) => void
}

function Badge({ present }: { present: boolean }) {
  return present ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
      Yes
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
      <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />
      No
    </span>
  )
}

function DeviceBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    ios:     'bg-blue-100 text-blue-700',
    android: 'bg-green-100 text-green-700',
    unknown: 'bg-gray-100 text-gray-500',
  }
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${styles[type] ?? styles.unknown}`}>
      {type}
    </span>
  )
}

const TH = ({ children, right }: { children: React.ReactNode; right?: boolean }) => (
  <th className={`whitespace-nowrap px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider ${right ? 'text-right' : 'text-left'}`}>
    {children}
  </th>
)

function fmt(v: string | null): string { return v ? v.slice(0, 10) : '—' }
function num(v: number): string { return v > 0 ? v.toLocaleString() : '—' }

export default function ParticipantSummaryTable({ participants, selectedId, onSelectParticipant }: Props) {
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm bg-white">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <TH>Record ID</TH>
            <TH>Alias</TH>
            <TH>Health Code</TH>
            <TH>Device</TH>
            <TH>Self-Report</TH>
            <TH>Synapse</TH>
            <TH right>SR Rows</TH>
            <TH right>Syn Sessions</TH>
            <TH>SR First</TH>
            <TH>SR Last</TH>
            <TH>Syn First</TH>
            <TH>Syn Last</TH>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {participants.map(p => {
            const isSelected = selectedId === p.record_id
            return (
              <tr
                key={p.record_id ?? p.health_code}
                onClick={() => onSelectParticipant(p)}
                className={`cursor-pointer transition-colors ${
                  isSelected
                    ? 'bg-indigo-50 ring-1 ring-inset ring-indigo-300'
                    : 'hover:bg-gray-50'
                }`}
              >
                <td className="px-3 py-2 font-mono font-medium text-gray-900">{p.record_id ?? '—'}</td>
                <td className="px-3 py-2 text-gray-600 tabular-nums">{p.alias ?? '—'}</td>
                <td className="px-3 py-2 font-mono text-gray-500 text-xs">{p.health_code_masked}</td>
                <td className="px-3 py-2"><DeviceBadge type={p.device_type} /></td>
                <td className="px-3 py-2"><Badge present={p.has_self_report} /></td>
                <td className="px-3 py-2"><Badge present={p.has_synapse} /></td>
                <td className="px-3 py-2 tabular-nums text-right text-gray-700">{num(p.self_report_rows)}</td>
                <td className="px-3 py-2 tabular-nums text-right text-gray-700">{num(p.synapse_sessions)}</td>
                <td className="px-3 py-2 text-gray-500 whitespace-nowrap text-xs">{fmt(p.first_self_report_date)}</td>
                <td className="px-3 py-2 text-gray-500 whitespace-nowrap text-xs">{fmt(p.last_self_report_date)}</td>
                <td className="px-3 py-2 text-gray-500 whitespace-nowrap text-xs">{fmt(p.first_synapse_date)}</td>
                <td className="px-3 py-2 text-gray-500 whitespace-nowrap text-xs">{fmt(p.last_synapse_date)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div className="border-t border-gray-100 bg-gray-50 px-4 py-2 text-xs text-gray-400">
        {participants.length} participant{participants.length !== 1 ? 's' : ''} shown
        {' · '}Health codes masked.
        {' · '}Click a row to view details.
      </div>
    </div>
  )
}
