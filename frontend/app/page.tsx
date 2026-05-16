'use client'

import { useState, useMemo } from 'react'
import ParticipantFilterPanel from '@/components/ParticipantFilterPanel'
import PresenceSummaryCards from '@/components/PresenceSummaryCards'
import ParticipantSummaryTable from '@/components/ParticipantSummaryTable'
import SessionManifestTable from '@/components/SessionManifestTable'
import LinkedTimegridTable from '@/components/LinkedTimegridTable'
import EmptyState from '@/components/EmptyState'
import {
  mockParticipants,
  mockSessionManifest,
  mockRedcapOutcomes,
  mockLinkedTimegrid,
} from '@/lib/mockData'
import type {
  DashboardParticipant,
  FilterState,
  RedcapOutcomesRow,
} from '@/lib/types'

// ─── Default filter state ─────────────────────────────────────────────────────

const DEFAULT_FILTERS: FilterState = {
  record_id: '',
  alias: '',
  health_code: '',
  device_type: 'all',
  require_redcap: false,
  require_synapse: false,
  start_date: '',
  end_date: '',
  max_rows: 0,
}

// ─── Client-side filtering logic ─────────────────────────────────────────────

function applyFilters(
  participants: DashboardParticipant[],
  filters: FilterState,
): DashboardParticipant[] {
  let result = [...participants]

  if (filters.record_id.trim()) {
    const ids = filters.record_id
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
    result = result.filter(p => p.record_id != null && ids.includes(String(p.record_id)))
  }

  if (filters.alias.trim()) {
    const aliases = filters.alias
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
    result = result.filter(p => p.alias != null && aliases.includes(String(p.alias)))
  }

  if (filters.health_code.trim()) {
    const hcs = filters.health_code
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
    result = result.filter(p => hcs.includes(p.health_code))
  }

  if (filters.device_type !== 'all') {
    result = result.filter(p => p.device_type === filters.device_type)
  }

  if (filters.require_redcap) {
    result = result.filter(p => p.has_redcap)
  }

  if (filters.require_synapse) {
    result = result.filter(p => p.has_synapse)
  }

  if (filters.start_date) {
    result = result.filter(
      p => p.last_observed_date != null && p.last_observed_date >= filters.start_date,
    )
  }

  if (filters.end_date) {
    result = result.filter(
      p => p.first_observed_date != null && p.first_observed_date <= filters.end_date,
    )
  }

  if (filters.max_rows && filters.max_rows > 0) {
    result = result.slice(0, filters.max_rows)
  }

  return result
}

// ─── Detail tab types ─────────────────────────────────────────────────────────

type DetailTab = 'overview' | 'self-report' | 'sessions' | 'timegrid'

const TAB_LABELS: Record<DetailTab, string> = {
  overview:      'Overview',
  'self-report': 'Self-Report Outcomes',
  sessions:      'BiAffect Sessions',
  timegrid:      'Linked Timegrid',
}

// ─── Overview tab ─────────────────────────────────────────────────────────────

function OverviewTab({ participant }: { participant: DashboardParticipant }) {
  const rows: { label: string; value: string | number }[] = [
    { label: 'Record ID',          value: participant.record_id ?? '—' },
    { label: 'Alias',              value: participant.alias ?? '—' },
    { label: 'Health Code',        value: participant.health_code_masked },
    { label: 'Device Type',        value: participant.device_type },
    { label: 'REDCap data',        value: participant.has_redcap ? '✓ Present' : '✗ Absent' },
    { label: 'Synapse data',       value: participant.has_synapse ? '✓ Present' : '✗ Absent' },
    { label: 'Self-Report Days',   value: participant.self_report_days },
    { label: 'Synapse Sessions',   value: participant.synapse_sessions },
    { label: 'First Observed',     value: participant.first_observed_date ?? '—' },
    { label: 'Last Observed',      value: participant.last_observed_date ?? '—' },
  ]

  return (
    <div className="max-w-xl">
      <dl className="divide-y divide-gray-100 rounded border border-gray-200 overflow-hidden">
        {rows.map(({ label, value }) => (
          <div key={label} className="flex items-baseline gap-4 px-4 py-2.5 even:bg-gray-50">
            <dt className="w-44 shrink-0 text-xs font-medium text-gray-500">{label}</dt>
            <dd className="text-sm text-gray-900">{String(value)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-gray-400">
        Health code is masked for display. Full value is never rendered in the UI.
      </p>
    </div>
  )
}

// ─── Self-report outcomes tab ─────────────────────────────────────────────────

function RedcapOutcomesTab({ rows }: { rows: RedcapOutcomesRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        message="No REDCap outcomes for this participant."
        hint="Ensure the participant has a matching record_id in report.csv and run the pipeline."
      />
    )
  }

  return (
    <div className="overflow-x-auto rounded border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            {[
              'Date',
              'Survey Timestamp (UTC)',
              'Suicidality Binary',
              'Suicidality 0–9',
              'Self-Harm Binary',
            ].map(h => (
              <th
                key={h}
                className="whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="px-3 py-2 text-gray-700 whitespace-nowrap">{row.date}</td>
              <td className="px-3 py-2 text-gray-500 text-xs whitespace-nowrap">
                {row.survey_timestamp || '—'}
              </td>
              <td className="px-3 py-2 text-center">
                {row.daily_suicidality_binary != null ? (
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                      row.daily_suicidality_binary === 1
                        ? 'bg-rose-100 text-rose-700'
                        : 'bg-gray-100 text-gray-500'
                    }`}
                  >
                    {row.daily_suicidality_binary}
                  </span>
                ) : (
                  <span className="text-gray-300">—</span>
                )}
              </td>
              <td className="px-3 py-2 text-center">
                {row.suicidality_0_9 != null ? (
                  <span
                    className={`font-medium tabular-nums ${
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
              <td className="px-3 py-2 text-center tabular-nums text-gray-700">
                {row.self_harm_binary ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t border-gray-100 bg-gray-50 px-4 py-2 text-xs text-gray-400">
        {rows.length} outcome row{rows.length !== 1 ? 's' : ''} for this participant
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [appliedFilters, setAppliedFilters] = useState<FilterState>(DEFAULT_FILTERS)
  const [selectedParticipant, setSelectedParticipant] = useState<DashboardParticipant | null>(null)
  const [activeTab, setActiveTab] = useState<DetailTab>('overview')

  const filteredParticipants = useMemo(
    () => applyFilters(mockParticipants, appliedFilters),
    [appliedFilters],
  )

  const summaryStats = useMemo(
    () => ({
      total:          filteredParticipants.length,
      withRedcap:     filteredParticipants.filter(p => p.has_redcap).length,
      withSynapse:    filteredParticipants.filter(p => p.has_synapse).length,
      withBoth:       filteredParticipants.filter(p => p.has_redcap && p.has_synapse).length,
      missingLinkage: filteredParticipants.filter(p => !p.has_redcap && !p.has_synapse).length,
    }),
    [filteredParticipants],
  )

  const participantSessions = useMemo(
    () =>
      selectedParticipant
        ? mockSessionManifest.filter(s => s.record_id === selectedParticipant.record_id)
        : [],
    [selectedParticipant],
  )

  const participantOutcomes = useMemo(
    () =>
      selectedParticipant
        ? mockRedcapOutcomes.filter(o => o.health_code === selectedParticipant.health_code)
        : [],
    [selectedParticipant],
  )

  const participantTimegrid = useMemo(
    () =>
      selectedParticipant
        ? mockLinkedTimegrid.filter(t => t.health_code === selectedParticipant.health_code)
        : [],
    [selectedParticipant],
  )

  function handleSelectParticipant(p: DashboardParticipant) {
    setSelectedParticipant(prev =>
      prev?.record_id === p.record_id ? null : p,
    )
    setActiveTab('overview')
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">

      {/* ── Header ── */}
      <header className="bg-slate-800 text-white px-6 py-4 shadow-md shrink-0">
        <div className="max-w-screen-2xl mx-auto flex items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight leading-none">
              BiaConnect Dashboard
            </h1>
            <p className="text-slate-400 text-xs mt-1 max-w-xl">
              Participant-level linkage dashboard for BiAffect/Synapse and REDCap-style self-report
              data. Internal research use only.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400 shrink-0">
            <span className="inline-block rounded bg-amber-600/20 border border-amber-500/30 px-2 py-0.5 text-amber-300 font-medium">
              MVP — Mock Data
            </span>
          </div>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="flex flex-1 overflow-hidden max-w-screen-2xl w-full mx-auto">

        {/* ── Filter sidebar ── */}
        <aside className="w-64 xl:w-72 shrink-0 bg-white border-r border-gray-200 overflow-y-auto p-4">
          <ParticipantFilterPanel
            onApply={filters => {
              setAppliedFilters(filters)
              setSelectedParticipant(null)
            }}
            defaultFilters={DEFAULT_FILTERS}
          />
        </aside>

        {/* ── Main content ── */}
        <main className="flex-1 overflow-y-auto p-5 space-y-5">

          {/* Presence summary */}
          <section>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
              Cohort Overview
            </p>
            <PresenceSummaryCards stats={summaryStats} />
          </section>

          {/* Participant table */}
          <section>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
              Participant Summary
            </p>
            {filteredParticipants.length === 0 ? (
              <EmptyState
                message="No participants match the current filters."
                hint="Try relaxing the filter criteria or clicking Reset."
              />
            ) : (
              <ParticipantSummaryTable
                participants={filteredParticipants}
                selectedId={selectedParticipant?.record_id ?? null}
                onSelectParticipant={handleSelectParticipant}
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
                  onClick={() => setSelectedParticipant(null)}
                  className="ml-4 text-xs text-gray-400 hover:text-gray-600 transition-colors py-2 px-1"
                  aria-label="Close detail panel"
                >
                  ✕ Close
                </button>
              </div>

              {/* Tab label */}
              <div className="px-4 pt-3 pb-1 border-b border-gray-100 bg-white flex items-center gap-3">
                <span className="text-xs font-medium text-gray-500">Participant</span>
                <span className="font-mono text-sm font-semibold text-gray-900">
                  {selectedParticipant.record_id ?? '—'}
                </span>
                <span className="text-gray-300">·</span>
                <span className="font-mono text-xs text-gray-500">
                  {selectedParticipant.health_code_masked}
                </span>
                <span className="text-gray-300">·</span>
                <span className="text-xs text-gray-500 capitalize">
                  {selectedParticipant.device_type}
                </span>
              </div>

              {/* Tab body */}
              <div className="p-4">
                {activeTab === 'overview' && (
                  <OverviewTab participant={selectedParticipant} />
                )}
                {activeTab === 'self-report' && (
                  <RedcapOutcomesTab rows={participantOutcomes} />
                )}
                {activeTab === 'sessions' && (
                  <SessionManifestTable rows={participantSessions} />
                )}
                {activeTab === 'timegrid' && (
                  <LinkedTimegridTable rows={participantTimegrid} />
                )}
              </div>
            </section>
          )}

        </main>
      </div>
    </div>
  )
}
