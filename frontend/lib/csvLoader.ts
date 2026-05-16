/**
 * CSV loader utilities for BiaConnect Dashboard.
 *
 * TODO: Connect these functions to the real output files produced by
 *       `python src/main.py ...` once they have been generated.
 *
 * Planned file paths (relative to project root):
 *   outputs/dashboard_exports/participant_index_filtered.csv
 *   outputs/dashboard_exports/synapse_presence_filtered.csv
 *   outputs/dashboard_exports/session_manifest_filtered.csv
 *   outputs/dashboard_exports/redcap_daily_outcomes.csv
 *   outputs/dashboard_exports/metric_bins_observed_filtered.csv
 *   outputs/dashboard_exports/linked_timegrid_filtered.csv
 *
 * For Next.js on Vercel, these files need to be served as static assets
 * placed under `frontend/public/dashboard_exports/` and fetched via
 * `fetch('/dashboard_exports/<filename>')`.
 *
 * For a local research setup, a simple Express/Flask API endpoint could
 * serve them from the filesystem outside the Next.js public dir.
 */

import type {
  ParticipantIndexRow,
  SynapsePresenceRow,
  SessionManifestRow,
  RedcapOutcomesRow,
  MetricBinsRow,
  LinkedTimegridRow,
} from './types'

// ─── Minimal CSV parser ──────────────────────────────────────────────────────

function parseCSV<T>(text: string): T[] {
  const lines = text.trim().split('\n')
  if (lines.length < 2) return []
  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))
  return lines.slice(1).map(line => {
    const values = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''))
    const obj: Record<string, string | number | null> = {}
    headers.forEach((h, i) => {
      const raw = values[i] ?? ''
      if (raw === '' || raw === 'NA' || raw === 'NaN' || raw === 'None') {
        obj[h] = null
      } else if (!isNaN(Number(raw))) {
        obj[h] = Number(raw)
      } else {
        obj[h] = raw
      }
    })
    return obj as T
  })
}

async function fetchCSV<T>(publicPath: string): Promise<T[]> {
  const res = await fetch(publicPath)
  if (!res.ok) throw new Error(`Failed to load ${publicPath}: ${res.status}`)
  const text = await res.text()
  return parseCSV<T>(text)
}

// ─── Public loader functions ──────────────────────────────────────────────────
// Place generated CSV files under frontend/public/dashboard_exports/ and
// un-comment the fetch call below. While no files exist yet, each function
// falls back gracefully and returns an empty array.

export async function loadParticipantIndex(): Promise<ParticipantIndexRow[]> {
  // TODO: return fetchCSV<ParticipantIndexRow>('/dashboard_exports/participant_index_filtered.csv')
  return []
}

export async function loadSynapsePresence(): Promise<SynapsePresenceRow[]> {
  // TODO: return fetchCSV<SynapsePresenceRow>('/dashboard_exports/synapse_presence_filtered.csv')
  return []
}

export async function loadSessionManifest(): Promise<SessionManifestRow[]> {
  // TODO: return fetchCSV<SessionManifestRow>('/dashboard_exports/session_manifest_filtered.csv')
  return []
}

export async function loadRedcapOutcomes(): Promise<RedcapOutcomesRow[]> {
  // TODO: return fetchCSV<RedcapOutcomesRow>('/dashboard_exports/redcap_daily_outcomes.csv')
  return []
}

export async function loadMetricBins(): Promise<MetricBinsRow[]> {
  // TODO: return fetchCSV<MetricBinsRow>('/dashboard_exports/metric_bins_observed_filtered.csv')
  return []
}

export async function loadLinkedTimegrid(): Promise<LinkedTimegridRow[]> {
  // TODO: return fetchCSV<LinkedTimegridRow>('/dashboard_exports/linked_timegrid_filtered.csv')
  return []
}
