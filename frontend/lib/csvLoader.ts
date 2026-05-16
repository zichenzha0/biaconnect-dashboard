/**
 * CSV loader for BiaConnect Dashboard.
 *
 * Reads pre-generated pipeline output files from:
 *   /dashboard_exports/<filename>
 *
 * Files must be placed in frontend/public/dashboard_exports/ by running:
 *   python src/main.py ... --copy-to-frontend
 *
 * Each loader returns null when the file is unavailable (404 or network error),
 * so the calling page can fall back to mock data and show the correct badge.
 */

import type {
  ParticipantIndexRow,
  SynapsePresenceRow,
  SessionManifestRow,
  SelfReportOutcomesRow,
  MetricBinsRow,
  LinkedTimegridRow,
} from './types'

// ─── CSV parser ───────────────────────────────────────────────────────────────
// Handles quoted fields, NA/NaN/None → null, numeric coercion.

function parseCSVLine(line: string): string[] {
  const result: string[] = []
  let cur = ''
  let inQuote = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      inQuote = !inQuote
    } else if (ch === ',' && !inQuote) {
      result.push(cur)
      cur = ''
    } else {
      cur += ch
    }
  }
  result.push(cur)
  return result
}

function parseCSV<T>(text: string): T[] {
  const lines = text.replace(/\r\n/g, '\n').trim().split('\n')
  if (lines.length < 2) return []
  const headers = parseCSVLine(lines[0]).map(h => h.trim())
  const rows: T[] = []
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue
    const values = parseCSVLine(line)
    const obj: Record<string, string | number | boolean | null> = {}
    headers.forEach((h, idx) => {
      const raw = (values[idx] ?? '').trim()
      if (raw === '' || raw === 'NA' || raw === 'NaN' || raw === 'None' || raw === 'NaT') {
        obj[h] = null
      } else if (raw === 'True' || raw === 'true') {
        obj[h] = true
      } else if (raw === 'False' || raw === 'false') {
        obj[h] = false
      } else if (!isNaN(Number(raw)) && raw !== '') {
        obj[h] = Number(raw)
      } else {
        obj[h] = raw
      }
    })
    rows.push(obj as T)
  }
  return rows
}

async function fetchCSV<T>(publicPath: string): Promise<T[] | null> {
  try {
    const res = await fetch(publicPath, { cache: 'no-store' })
    if (!res.ok) return null   // file not yet generated
    const text = await res.text()
    const rows = parseCSV<T>(text)
    return rows.length > 0 ? rows : null
  } catch {
    return null
  }
}

// ─── Public loaders ───────────────────────────────────────────────────────────
// Each returns the parsed rows or null (file unavailable → use mock data).

export async function loadParticipantIndex(): Promise<ParticipantIndexRow[] | null> {
  return fetchCSV<ParticipantIndexRow>('/dashboard_exports/participant_index_filtered.csv')
}

export async function loadSelfReportOutcomes(): Promise<SelfReportOutcomesRow[] | null> {
  return fetchCSV<SelfReportOutcomesRow>('/dashboard_exports/self_report_daily_outcomes.csv')
}

export async function loadSynapsePresence(): Promise<SynapsePresenceRow[] | null> {
  return fetchCSV<SynapsePresenceRow>('/dashboard_exports/synapse_presence_filtered.csv')
}

/** Load a per-participant detail CSV from its public path. Returns null if unavailable. */
export async function loadDetailCSV<T>(publicPath: string): Promise<T[] | null> {
  return fetchCSV<T>(publicPath)
}

/** Full session manifest — 300 MB; not auto-loaded on page start. Use loadDetailCSV instead. */
export async function loadSessionManifest(): Promise<SessionManifestRow[] | null> {
  return fetchCSV<SessionManifestRow>('/dashboard_exports/session_manifest_filtered.csv')
}

/** Metric bins are optional (require --download --parse). Always returns an array; never null. */
export async function loadMetricBins(): Promise<MetricBinsRow[]> {
  const rows = await fetchCSV<MetricBinsRow>('/dashboard_exports/biaffect_metric_bins_filtered.csv')
  return rows ?? []
}

export async function loadLinkedTimegrid(): Promise<LinkedTimegridRow[] | null> {
  return fetchCSV<LinkedTimegridRow>('/dashboard_exports/linked_timegrid_filtered.csv')
}
