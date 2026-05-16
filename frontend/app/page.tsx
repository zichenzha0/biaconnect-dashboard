'use client'

import { useState, useMemo, useEffect } from 'react'
import ParticipantFilterPanel from '@/components/ParticipantFilterPanel'
import PresenceSummaryCards from '@/components/PresenceSummaryCards'
import ParticipantSummaryTable from '@/components/ParticipantSummaryTable'
import SessionManifestTable from '@/components/SessionManifestTable'
import LinkedTimegridTable from '@/components/LinkedTimegridTable'
import BiAffectMetricBinsTable from '@/components/BiAffectMetricBinsTable'
import EmptyState from '@/components/EmptyState'
import {
  loadParticipantIndex,
  loadSelfReportOutcomes,
  loadMetricBins,
  loadDetailCSV,
} from '@/lib/csvLoader'
import {
  mockParticipants,
  mockSelfReportOutcomes,
  mockSessionManifest,
  mockMetricBins,
  mockLinkedTimegrid,
} from '@/lib/mockData'
import {
  participantFromRow,
  maskHealthCode,
} from '@/lib/types'
import type {
  DashboardParticipant,
  FilterState,
  SelfReportOutcomesRow,
  SessionManifestRow,
  MetricBinsRow,
  LinkedTimegridRow,
} from '@/lib/types'

type DetailState<T> = null | 'loading' | 'not_generated' | 'error' | T[]

// ─── Defaults ────────────────────────────────────────────────────────────────

const DEFAULT_FILTERS: FilterState = {
  record_id: '',
  alias: '',
  health_code: '',
  device_type: 'all',
  require_self_report: false,
  require_synapse: false,
  start_date: '',
  end_date: '',
  max_rows: 0,
}

// ─── Client-side filter logic ─────────────────────────────────────────────────

function applyFilters(participants: DashboardParticipant[], filters: FilterState): DashboardParticipant[] {
  let r = [...participants]
  if (filters.record_id.trim()) {
    const ids = filters.record_id.split(',').map(s => s.trim()).filter(Boolean)
    r = r.filter(p => p.record_id != null && ids.includes(String(p.record_id)))
  }
  if (filters.alias.trim()) {
    const aliases = filters.alias.split(',').map(s => s.trim()).filter(Boolean)
    r = r.filter(p => p.alias != null && aliases.includes(String(p.alias)))
  }
  if (filters.health_code.trim()) {
    const hcs = filters.health_code.split(',').map(s => s.trim()).filter(Boolean)
    r = r.filter(p => hcs.includes(p.health_code))
  }
  if (filters.device_type !== 'all') r = r.filter(p => p.device_type === filters.device_type)
  if (filters.require_self_report) r = r.filter(p => p.has_self_report)
  if (filters.require_synapse)     r = r.filter(p => p.has_synapse)
  if (filters.start_date) {
    r = r.filter(p =>
      (p.last_self_report_date && p.last_self_report_date >= filters.start_date) ||
      (p.last_synapse_date && p.last_synapse_date >= filters.start_date)
    )
  }
  if (filters.end_date) {
    r = r.filter(p =>
      (p.first_self_report_date && p.first_self_report_date <= filters.end_date) ||
      (p.first_synapse_date && p.first_synapse_date <= filters.end_date)
    )
  }
  if (filters.max_rows > 0) r = r.slice(0, filters.max_rows)
  return r
}

// ─── Data source badge ────────────────────────────────────────────────────────

type DataSource = 'loading' | 'csv' | 'mock'

function DataSourceBadge({ source }: { source: DataSource }) {
  if (source === 'loading') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded border border-gray-300 bg-white px-2 py-0.5 text-xs font-medium text-gray-500">
        <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-pulse" />
        Loading…
      </span>
    )
  }
  if (source === 'csv') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
        Local real CSV data loaded
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
      Mock demo data
    </span>
  )
}

// ─── Tab types ────────────────────────────────────────────────────────────────

type DetailTab = 'overview' | 'self-report' | 'biaffect-bins' | 'sessions' | 'timegrid'
const TAB_LABELS: Record<DetailTab, string> = {
  overview:       'Overview',
  'self-report':  'Self-Report Outcomes',
  'biaffect-bins':'BiAffect Metric Bins',
  sessions:       'Sessions',
  timegrid:       'Linked Timegrid',
}

// ─── Overview tab ─────────────────────────────────────────────────────────────

function OverviewTab({ p }: { p: DashboardParticipant }) {
  const rows: [string, string][] = [
    ['Record ID',              String(p.record_id ?? '—')],
    ['Alias',                  String(p.alias ?? '—')],
    ['Health Code (masked)',   p.health_code_masked],
    ['Device Type',            p.device_type],
    ['Self-report data',       p.has_self_report ? '✓ Present' : '✗ Absent'],
    ['Synapse data',           p.has_synapse ? '✓ Present' : '✗ Absent'],
    ['Self-report rows',       String(p.self_report_rows)],
    ['Self-report days',       String(p.self_report_days)],
    ['Synapse sessions',       String(p.synapse_sessions)],
    ['SR first date',          p.first_self_report_date ?? '—'],
    ['SR last date',           p.last_self_report_date ?? '—'],
    ['Synapse first date',     p.first_synapse_date ?? '—'],
    ['Synapse last date',      p.last_synapse_date ?? '—'],
  ]
  return (
    <div className="max-w-xl">
      <dl className="divide-y divide-gray-100 rounded border border-gray-200 overflow-hidden text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-baseline gap-4 px-4 py-2.5 even:bg-gray-50">
            <dt className="w-52 shrink-0 text-xs font-medium text-gray-500">{label}</dt>
            <dd className="text-gray-900">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-xs text-gray-400">
        Full health_code is never rendered in the UI. Linkage is health_code-based only.
      </p>
    </div>
  )
}

// ─── Self-report outcomes tab ─────────────────────────────────────────────────

function SelfReportOutcomesTab({ rows }: { rows: SelfReportOutcomesRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        message="No self-report outcomes for this participant."
        hint="Ensure health_code is matched in report.csv and run: python src/main.py --copy-to-frontend"
      />
    )
  }
  const TH = ({ children }: { children: React.ReactNode }) => (
    <th className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{children}</th>
  )
  return (
    <div className="overflow-x-auto rounded border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <TH>Date</TH>
            <TH>Survey Timestamp</TH>
            <TH>Suicidality Binary</TH>
            <TH>Suicidality 0–9</TH>
            <TH>Self-Harm Binary</TH>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="px-3 py-2 text-gray-700 whitespace-nowrap">{row.date}</td>
              <td className="px-3 py-2 text-gray-500 text-xs whitespace-nowrap">{row.survey_timestamp || '—'}</td>
              <td className="px-3 py-2 text-center">
                {row.daily_suicidality_binary != null ? (
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${row.daily_suicidality_binary === 1 ? 'bg-rose-100 text-rose-700' : 'bg-gray-100 text-gray-500'}`}>
                    {row.daily_suicidality_binary}
                  </span>
                ) : <span className="text-gray-300">—</span>}
              </td>
              <td className="px-3 py-2 text-center">
                {row.suicidality_0_9 != null ? (
                  <span className={`font-medium tabular-nums ${row.suicidality_0_9 >= 5 ? 'text-rose-600' : row.suicidality_0_9 >= 2 ? 'text-amber-600' : 'text-gray-700'}`}>
                    {row.suicidality_0_9}
                  </span>
                ) : <span className="text-gray-300">—</span>}
              </td>
              <td className="px-3 py-2 text-center tabular-nums text-gray-700">{row.self_harm_binary ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t border-gray-100 bg-gray-50 px-4 py-2 text-xs text-gray-400">
        {rows.length} row{rows.length !== 1 ? 's' : ''} — linked by health_code
      </div>
    </div>
  )
}

// ─── On-demand detail loader wrapper ─────────────────────────────────────────

function OnDemandDetail<T>({
  state,
  onLoad,
  loadLabel,
  countHint,
  children,
}: {
  state: DetailState<T>
  onLoad: () => void
  loadLabel: string
  countHint?: string
  children: (rows: T[]) => React.ReactNode
}) {
  if (state === null) {
    return (
      <div className="py-8 flex flex-col items-center gap-3">
        <button
          onClick={onLoad}
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
        >
          {loadLabel}
        </button>
        {countHint && <p className="text-xs text-gray-400">{countHint}</p>}
      </div>
    )
  }
  if (state === 'loading') {
    return <div className="py-8 text-center text-sm text-gray-400">Loading…</div>
  }
  if (state === 'not_generated' || state === 'error') {
    return (
      <EmptyState
        message="Participant-level detail export is not available yet."
        hint="Re-run the backend with --copy-to-frontend to generate per-participant detail files."
      />
    )
  }
  if (Array.isArray(state) && state.length === 0) {
    return <EmptyState message="No rows found for this participant." />
  }
  return <>{children(state as T[])}</>
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  // ── Data loading state ──
  const [dataSource, setDataSource] = useState<DataSource>('loading')
  const [allParticipants, setAllParticipants] = useState<DashboardParticipant[]>([])
  const [selfReportRows, setSelfReportRows]   = useState<SelfReportOutcomesRow[]>([])
  const [metricBinRows, setMetricBinRows]     = useState<MetricBinsRow[]>([])

  // ── UI state ──
  const [appliedFilters, setAppliedFilters]   = useState<FilterState>(DEFAULT_FILTERS)
  const [selectedParticipant, setSelected]    = useState<DashboardParticipant | null>(null)
  const [activeTab, setActiveTab]             = useState<DetailTab>('overview')

  // ── Per-participant on-demand detail state ──
  const [detailSessions, setDetailSessions]   = useState<DetailState<SessionManifestRow>>(null)
  const [detailTimegrid, setDetailTimegrid]   = useState<DetailState<LinkedTimegridRow>>(null)

  // ── Try loading core CSV data on mount; sessions/timegrid loaded on demand ──
  useEffect(() => {
    let cancelled = false
    Promise.all([
      loadParticipantIndex(),
      loadSelfReportOutcomes(),
      loadMetricBins(),  // optional — never triggers mock fallback
    ]).then(([pIdx, sr, mb]) => {
      if (cancelled) return
      if (pIdx && pIdx.length > 0 && sr && sr.length > 0) {
        setAllParticipants(pIdx.map(participantFromRow))
        setSelfReportRows(sr)
        setMetricBinRows(mb)
        setDataSource('csv')
      } else {
        setAllParticipants(mockParticipants)
        setSelfReportRows(mockSelfReportOutcomes)
        setMetricBinRows(mockMetricBins)
        setDataSource('mock')
      }
    }).catch(() => {
      if (cancelled) return
      setAllParticipants(mockParticipants)
      setSelfReportRows(mockSelfReportOutcomes)
      setMetricBinRows(mockMetricBins)
      setDataSource('mock')
    })
    return () => { cancelled = true }
  }, [])

  const filteredParticipants = useMemo(
    () => applyFilters(allParticipants, appliedFilters),
    [allParticipants, appliedFilters],
  )

  const summaryStats = useMemo(() => ({
    total:          filteredParticipants.length,
    withSelfReport: filteredParticipants.filter(p => p.has_self_report).length,
    withSynapse:    filteredParticipants.filter(p => p.has_synapse).length,
    withBoth:       filteredParticipants.filter(p => p.has_self_report && p.has_synapse).length,
    missingLinkage: filteredParticipants.filter(p => !p.has_self_report && !p.has_synapse).length,
  }), [filteredParticipants])

  // Per-participant self-report — loaded eagerly (small file)
  const pSelfReport = useMemo(() =>
    selectedParticipant
      ? selfReportRows.filter(r => r.health_code === selectedParticipant.health_code)
      : [],
    [selectedParticipant, selfReportRows])

  // Per-participant metric bins — loaded eagerly if available
  const pMetricBins = useMemo(() =>
    selectedParticipant
      ? metricBinRows.filter(r => r.health_code === selectedParticipant.health_code)
      : [],
    [selectedParticipant, metricBinRows])

  // Reset detail state whenever the selected participant changes
  useEffect(() => {
    setDetailSessions(null)
    setDetailTimegrid(null)
  }, [selectedParticipant?.health_code])

  async function handleLoadSessions() {
    if (!selectedParticipant) return
    setDetailSessions('loading')
    if (dataSource === 'mock') {
      const rows = mockSessionManifest.filter(
        r => r.health_code === selectedParticipant.health_code
      )
      setDetailSessions(rows.length > 0 ? rows : [])
      return
    }
    const path = selectedParticipant.session_manifest_detail_path
    if (!path) { setDetailSessions('not_generated'); return }
    const rows = await loadDetailCSV<SessionManifestRow>(path)
    setDetailSessions(rows ?? 'error')
  }

  async function handleLoadTimegrid() {
    if (!selectedParticipant) return
    setDetailTimegrid('loading')
    if (dataSource === 'mock') {
      const rows = mockLinkedTimegrid.filter(
        r => r.health_code === selectedParticipant.health_code
      )
      setDetailTimegrid(rows.length > 0 ? rows : [])
      return
    }
    const path = selectedParticipant.linked_timegrid_detail_path
    if (!path) { setDetailTimegrid('not_generated'); return }
    const rows = await loadDetailCSV<LinkedTimegridRow>(path)
    setDetailTimegrid(rows ?? 'error')
  }

  function handleSelect(p: DashboardParticipant) {
    setSelected(prev => prev?.health_code === p.health_code ? null : p)
    setActiveTab('overview')
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">

      {/* ── Header ── */}
      <header className="bg-slate-800 text-white px-6 py-4 shadow-md shrink-0">
        <div className="max-w-screen-2xl mx-auto flex items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight leading-none">BiaConnect Dashboard</h1>
            <p className="text-slate-400 text-xs mt-1 max-w-xl">
              Participant-level linkage — BiAffect/Synapse and self-report data linked by health_code.
              Internal research use only.
            </p>
          </div>
          <div className="shrink-0 pt-0.5">
            <DataSourceBadge source={dataSource} />
          </div>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="flex flex-1 overflow-hidden max-w-screen-2xl w-full mx-auto">

        {/* ── Sidebar ── */}
        <aside className="w-64 xl:w-72 shrink-0 bg-white border-r border-gray-200 overflow-y-auto p-4">
          <ParticipantFilterPanel
            onApply={filters => { setAppliedFilters(filters); setSelected(null) }}
            defaultFilters={DEFAULT_FILTERS}
            dataSource={dataSource}
          />
        </aside>

        {/* ── Main content ── */}
        <main className="flex-1 overflow-y-auto p-5 space-y-5">

          {/* Cohort summary cards */}
          <section>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">Cohort Overview</p>
            <PresenceSummaryCards stats={summaryStats} />
          </section>

          {/* Participant table */}
          <section>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">Participant Summary</p>
            {dataSource === 'loading' ? (
              <div className="py-10 text-center text-sm text-gray-400">Loading data…</div>
            ) : filteredParticipants.length === 0 ? (
              <EmptyState message="No participants match the current filters." hint="Try relaxing criteria or clicking Reset." />
            ) : (
              <ParticipantSummaryTable
                participants={filteredParticipants}
                selectedId={selectedParticipant?.record_id ?? null}
                onSelectParticipant={handleSelect}
              />
            )}
          </section>

          {/* Detail panel */}
          {selectedParticipant && (
            <section className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">

              {/* Tab bar */}
              <div className="border-b border-gray-200 bg-gray-50 px-4 flex items-center justify-between">
                <nav className="flex" aria-label="Detail tabs">
                  {(Object.keys(TAB_LABELS) as DetailTab[]).map(tab => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                        activeTab === tab
                          ? 'border-indigo-600 text-indigo-600'
                          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                      }`}
                    >
                      {TAB_LABELS[tab]}
                    </button>
                  ))}
                </nav>
                <button
                  onClick={() => setSelected(null)}
                  className="ml-4 text-xs text-gray-400 hover:text-gray-600 transition-colors py-2 px-1"
                >
                  ✕ Close
                </button>
              </div>

              {/* Participant identity bar */}
              <div className="px-4 pt-3 pb-1 border-b border-gray-100 flex items-center gap-3 text-xs">
                <span className="font-medium text-gray-500">Participant</span>
                <span className="font-mono font-semibold text-gray-900">{selectedParticipant.record_id ?? '—'}</span>
                <span className="text-gray-300">·</span>
                <span className="font-mono text-gray-500">{selectedParticipant.health_code_masked}</span>
                <span className="text-gray-300">·</span>
                <span className="capitalize text-gray-500">{selectedParticipant.device_type}</span>
                {selectedParticipant.has_self_report && (
                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-blue-700 font-medium">Self-Report</span>
                )}
                {selectedParticipant.has_synapse && (
                  <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-indigo-700 font-medium">Synapse</span>
                )}
              </div>

              {/* Tab body */}
              <div className="p-4">
                {activeTab === 'overview'      && <OverviewTab p={selectedParticipant} />}
                {activeTab === 'self-report'   && <SelfReportOutcomesTab rows={pSelfReport} />}
                {activeTab === 'biaffect-bins' && <BiAffectMetricBinsTable rows={pMetricBins} />}
                {activeTab === 'sessions'      && (
                  <OnDemandDetail
                    state={detailSessions}
                    onLoad={handleLoadSessions}
                    loadLabel="Load Session Manifest"
                    countHint={selectedParticipant.synapse_sessions > 0
                      ? `${selectedParticipant.synapse_sessions.toLocaleString()} Synapse sessions available`
                      : undefined}
                  >
                    {(rows) => <SessionManifestTable rows={rows as SessionManifestRow[]} />}
                  </OnDemandDetail>
                )}
                {activeTab === 'timegrid'      && (
                  <OnDemandDetail
                    state={detailTimegrid}
                    onLoad={handleLoadTimegrid}
                    loadLabel="Load Linked Timegrid"
                    countHint={selectedParticipant.self_report_rows > 0
                      ? `${selectedParticipant.self_report_rows.toLocaleString()} self-report rows available`
                      : undefined}
                  >
                    {(rows) => <LinkedTimegridTable rows={rows as LinkedTimegridRow[]} />}
                  </OnDemandDetail>
                )}
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  )
}
