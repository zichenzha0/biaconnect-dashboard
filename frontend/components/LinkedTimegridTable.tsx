import type { LinkedTimegridRow } from '@/lib/types'
import EmptyState from './EmptyState'

interface LinkedTimegridTableProps {
  rows: LinkedTimegridRow[]
}

/** Render a small colored bar representing bin observation intensity. */
function IntensityBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(value / max, 1) : 0
  const width = Math.round(pct * 48)
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-2 rounded-sm bg-gray-100 w-12 overflow-hidden">
        <div
          className="h-full rounded-sm bg-indigo-400"
          style={{ width: `${width}px` }}
        />
      </div>
      <span className="tabular-nums text-gray-700">{value}</span>
    </div>
  )
}

const TH = ({ children, right }: { children: React.ReactNode; right?: boolean }) => (
  <th
    className={`whitespace-nowrap px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider ${
      right ? 'text-right' : 'text-left'
    }`}
  >
    {children}
  </th>
)

export default function LinkedTimegridTable({ rows }: LinkedTimegridTableProps) {
  if (rows.length === 0) {
    return (
      <EmptyState
        message="No linked timegrid rows for this participant."
        hint="Run the pipeline with --build-grid after downloading and parsing session files."
      />
    )
  }

  const maxKeylogs = Math.max(...rows.map(r => r.n_keylogs), 1)

  // Show only observed bins to keep the table manageable
  const observed = rows.filter(r => r.has_keylog_observation || r.has_accel_observation)
  const shown = observed.slice(0, 200)

  return (
    <div className="space-y-2">
      <p className="text-xs text-gray-400">
        Showing {shown.length} observed bins of {rows.length} total
        ({Math.round((rows.length / 96))} day{rows.length / 96 !== 1 ? 's' : ''} × 96 bins/day).
        Only bins with keylog or accelerometer observations are shown.
      </p>
      <div className="overflow-x-auto rounded border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <TH>Date</TH>
              <TH right>Bin</TH>
              <TH>Bin Start</TH>
              <TH right>Keylogs</TH>
              <TH right>Keystrokes/min</TH>
              <TH right>Backspace %</TH>
              <TH right>Accels</TH>
              <TH right>Suicidality (0–9)</TH>
              <TH right>Self-Harm</TH>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {shown.map((row, i) => (
              <tr key={i} className="hover:bg-gray-50">
                <td className="px-3 py-1.5 text-gray-600 whitespace-nowrap">{row.date}</td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-500">{row.bin_index}</td>
                <td className="px-3 py-1.5 font-mono text-xs text-gray-400">
                  {row.bin_start.slice(11, 16)}
                </td>
                <td className="px-3 py-1.5">
                  <IntensityBar value={row.n_keylogs} max={maxKeylogs} />
                </td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-700">
                  {row.typing_intensity > 0 ? row.typing_intensity.toFixed(1) : '—'}
                </td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-700">
                  {row.backspace_ratio != null
                    ? `${(row.backspace_ratio * 100).toFixed(1)}%`
                    : '—'}
                </td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-700">
                  {row.n_accelerations > 0 ? row.n_accelerations : '—'}
                </td>
                <td className="px-3 py-1.5 tabular-nums text-right">
                  {row.suicidality_0_9 != null ? (
                    <span
                      className={`font-medium ${
                        row.suicidality_0_9 >= 5
                          ? 'text-rose-600'
                          : row.suicidality_0_9 >= 2
                          ? 'text-amber-600'
                          : 'text-gray-700'
                      }`}
                    >
                      {row.suicidality_0_9}
                    </span>
                  ) : (
                    <span className="text-gray-300">—</span>
                  )}
                </td>
                <td className="px-3 py-1.5 tabular-nums text-right text-gray-700">
                  {row.self_harm_binary != null ? row.self_harm_binary : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="border-t border-gray-100 bg-gray-50 px-4 py-2 text-xs text-gray-400">
          {shown.length} observed bin{shown.length !== 1 ? 's' : ''} shown.
          Outcome columns populated only for the first bin of each day (daily alignment).
        </div>
      </div>
    </div>
  )
}
