import type { MetricBinsRow } from '@/lib/types'
import EmptyState from './EmptyState'

interface Props { rows: MetricBinsRow[] }

const TH = ({ children, right }: { children: React.ReactNode; right?: boolean }) => (
  <th className={`whitespace-nowrap px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider ${right ? 'text-right' : 'text-left'}`}>
    {children}
  </th>
)

function Bar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(value / max, 1) : 0
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-2 w-12 rounded-sm bg-gray-100 overflow-hidden">
        <div className="h-full rounded-sm bg-indigo-400" style={{ width: `${Math.round(pct * 48)}px` }} />
      </div>
      <span className="tabular-nums text-gray-700">{value}</span>
    </div>
  )
}

function pct(v: number | null) { return v != null ? `${(v * 100).toFixed(1)}%` : '—' }
function num(v: number | null) { return v != null ? v.toFixed(2) : '—' }
function cov(v: number | null) { return v != null ? `${(v * 100).toFixed(0)}%` : '—' }

export default function BiAffectMetricBinsTable({ rows }: Props) {
  if (rows.length === 0) {
    return (
      <EmptyState
        message="Metric bins are not available yet."
        hint="Run the backend with --download --parse --build-grid to generate parsed BiAffect metrics, then re-run with --copy-to-frontend."
      />
    )
  }

  const maxTyping = Math.max(...rows.map(r => r.typing_event_count ?? 0), 1)

  return (
    <div className="space-y-2">
      <p className="text-xs text-gray-400">
        {rows.length} bin{rows.length !== 1 ? 's' : ''} across{' '}
        {new Set(rows.map(r => r.date)).size} day{new Set(rows.map(r => r.date)).size !== 1 ? 's' : ''}.
        {' '}15-minute resolution. <span className="italic">mean/median IKI not available from current session data.</span>
      </p>
      <div className="overflow-x-auto rounded border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <TH>Date</TH>
              <TH right>Bin</TH>
              <TH>Start</TH>
              <TH right>Obs Min</TH>
              <TH right>KB Sessions</TH>
              <TH right>Typing Events</TH>
              <TH right>Backspaces</TH>
              <TH right>Backspace %</TH>
              <TH right>Mean IKI</TH>
              <TH right>Median IKI</TH>
              <TH right>Accel Mean</TH>
              <TH right>Accel SD</TH>
              <TH right>Coverage</TH>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row, i) => (
              <tr key={i} className="hover:bg-gray-50">
                <td className="px-3 py-1.5 text-gray-600 whitespace-nowrap">{row.date}</td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-400">{row.bin_index}</td>
                <td className="px-3 py-1.5 font-mono text-xs text-gray-400">{row.bin_start?.slice(11, 16) ?? '—'}</td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-700">{row.observed_minutes}</td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-700">{row.keyboard_session_count ?? '—'}</td>
                <td className="px-3 py-1.5">
                  <Bar value={row.typing_event_count ?? 0} max={maxTyping} />
                </td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-700">{row.backspace_count ?? '—'}</td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-700">{pct(row.backspace_ratio)}</td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-300 italic text-xs">{num(row.mean_inter_key_interval)}</td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-300 italic text-xs">{num(row.median_inter_key_interval)}</td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-700">{num(row.accelerometer_activity_mean)}</td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-700">{num(row.accelerometer_activity_sd)}</td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-700">{cov(row.data_coverage_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="border-t border-gray-100 bg-gray-50 px-4 py-2 text-xs text-gray-400">
          IKI = inter-key interval. Grayed-out IKI columns require raw keystroke timestamps (not yet extracted).
        </div>
      </div>
    </div>
  )
}
