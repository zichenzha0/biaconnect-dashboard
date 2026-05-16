import type { SessionManifestRow } from '@/lib/types'
import EmptyState from './EmptyState'

interface SessionManifestTableProps {
  rows: SessionManifestRow[]
}

const TH = ({ children }: { children: React.ReactNode }) => (
  <th className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
    {children}
  </th>
)

export default function SessionManifestTable({ rows }: SessionManifestTableProps) {
  if (rows.length === 0) {
    return (
      <EmptyState
        message="No session manifest rows for this participant."
        hint="Run the pipeline with --build-manifest to generate Synapse session records."
      />
    )
  }

  return (
    <div className="overflow-x-auto rounded border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <TH>#</TH>
            <TH>recordId</TH>
            <TH>Session Date</TH>
            <TH>Source</TH>
            <TH>App Version</TH>
            <TH>Phone Info</TH>
            <TH>Upload Date (UTC)</TH>
            <TH>Day in Study</TH>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((row, i) => (
            <tr key={row.recordId ?? i} className="hover:bg-gray-50">
              <td className="px-3 py-2 text-gray-400 tabular-nums">{row.row_num_within_participant ?? i + 1}</td>
              <td className="px-3 py-2 font-mono text-xs text-gray-700">{row.recordId}</td>
              <td className="px-3 py-2 text-gray-700 whitespace-nowrap">{row.session_date}</td>
              <td className="px-3 py-2">
                <span className="inline-block rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
                  {row.source_label}
                </span>
              </td>
              <td className="px-3 py-2 text-gray-500 text-xs">{row.appVersion || '—'}</td>
              <td className="px-3 py-2 text-gray-500 text-xs">{row.phoneInfo || '—'}</td>
              <td className="px-3 py-2 text-gray-500 text-xs whitespace-nowrap">
                {row.uploadDate ? row.uploadDate.replace('T', ' ').replace('Z', '') : '—'}
              </td>
              <td className="px-3 py-2 tabular-nums text-gray-600 text-right">
                {row.dayInStudy ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t border-gray-100 bg-gray-50 px-4 py-2 text-xs text-gray-400">
        {rows.length} session row{rows.length !== 1 ? 's' : ''}
      </div>
    </div>
  )
}
