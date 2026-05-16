'use client'

import { useState } from 'react'
import type { FilterState } from '@/lib/types'

interface ParticipantFilterPanelProps {
  onApply: (filters: FilterState) => void
  defaultFilters: FilterState
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-xs font-medium text-gray-600 mb-1">{children}</label>
  )
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full rounded border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-900 placeholder-gray-400 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
    />
  )
}

function exportFilterConfig(filters: FilterState) {
  const json = JSON.stringify(filters, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'biaconnect_filter_config.json'
  a.click()
  URL.revokeObjectURL(url)
}

export default function ParticipantFilterPanel({
  onApply,
  defaultFilters,
}: ParticipantFilterPanelProps) {
  const [form, setForm] = useState<FilterState>(defaultFilters)

  function set<K extends keyof FilterState>(key: K, value: FilterState[K]) {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  function handleApply() {
    onApply(form)
  }

  function handleReset() {
    setForm(defaultFilters)
    onApply(defaultFilters)
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">
          Filters
        </h2>

        {/* record_id */}
        <div className="mb-3">
          <Label>Record ID(s)</Label>
          <Input
            type="text"
            placeholder="e.g. 127084, 091811"
            value={form.record_id}
            onChange={e => set('record_id', e.target.value)}
          />
          <p className="text-xs text-gray-400 mt-0.5">Comma-separated REDCap IDs</p>
        </div>

        {/* alias */}
        <div className="mb-3">
          <Label>Alias(es)</Label>
          <Input
            type="text"
            placeholder="e.g. 1001, 1002"
            value={form.alias}
            onChange={e => set('alias', e.target.value)}
          />
        </div>

        {/* health_code */}
        <div className="mb-3">
          <Label>Health Code(s)</Label>
          <Input
            type="text"
            placeholder="e.g. abc123"
            value={form.health_code}
            onChange={e => set('health_code', e.target.value)}
          />
          <p className="text-xs text-gray-400 mt-0.5">Comma-separated Synapse health_codes</p>
        </div>

        {/* device_type */}
        <div className="mb-3">
          <Label>Device type</Label>
          <select
            value={form.device_type}
            onChange={e => set('device_type', e.target.value as FilterState['device_type'])}
            className="w-full rounded border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="all">All devices</option>
            <option value="ios">iOS</option>
            <option value="android">Android</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>

        {/* require checkboxes */}
        <div className="mb-3 space-y-2">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={form.require_redcap}
              onChange={e => set('require_redcap', e.target.checked)}
              className="h-3.5 w-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span className="text-sm text-gray-700">Require REDCap data</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={form.require_synapse}
              onChange={e => set('require_synapse', e.target.checked)}
              className="h-3.5 w-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span className="text-sm text-gray-700">Require Synapse data</span>
          </label>
        </div>

        {/* date range */}
        <div className="mb-3">
          <Label>Start date</Label>
          <Input
            type="date"
            value={form.start_date}
            onChange={e => set('start_date', e.target.value)}
          />
        </div>
        <div className="mb-3">
          <Label>End date</Label>
          <Input
            type="date"
            value={form.end_date}
            onChange={e => set('end_date', e.target.value)}
          />
        </div>

        {/* max rows */}
        <div className="mb-4">
          <Label>Max rows per participant</Label>
          <Input
            type="number"
            min={0}
            placeholder="0 = no cap"
            value={form.max_rows || ''}
            onChange={e =>
              set('max_rows', e.target.value === '' ? 0 : parseInt(e.target.value, 10))
            }
          />
          <p className="text-xs text-gray-400 mt-0.5">0 means no cap</p>
        </div>
      </div>

      {/* Action buttons */}
      <div className="space-y-2 pt-1 border-t border-gray-100">
        <button
          onClick={handleApply}
          className="w-full rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 transition-colors"
        >
          Apply Filters
        </button>
        <button
          onClick={handleReset}
          className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-600 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-1 transition-colors"
        >
          Reset
        </button>
        <button
          onClick={() => exportFilterConfig(form)}
          className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-600 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-1 transition-colors"
        >
          Export Filter Config
        </button>
      </div>

      <div className="rounded bg-amber-50 border border-amber-200 p-2.5">
        <p className="text-xs text-amber-700 leading-snug">
          <span className="font-semibold">MVP mode:</span> Filters apply to mock data locally.
          Connect to Python pipeline outputs in{' '}
          <code className="font-mono">lib/csvLoader.ts</code>.
        </p>
      </div>
    </div>
  )
}
