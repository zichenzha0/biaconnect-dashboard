/**
 * Shared TypeScript interfaces for BiaConnect Dashboard.
 *
 * Column schemas mirror the CSV files produced by the Python backend.
 * Participant linkage is strictly health_code-based.
 *
 * Output files consumed by the frontend (served from /dashboard_exports/):
 *   participant_index_filtered.csv
 *   self_report_daily_outcomes.csv
 *   synapse_presence_filtered.csv
 *   session_manifest_filtered.csv
 *   biaffect_metric_bins_filtered.csv
 *   linked_timegrid_filtered.csv
 */

// ─── participant_index_filtered.csv ────────────────────────────────────────
export interface ParticipantIndexRow {
  record_id: number | null
  alias: number | null
  /** Internal — used for row joins. Never render unmasked in UI. */
  health_code: string
  /** Safe to display: e.g. "abc***xyz" */
  health_code_masked: string
  device_type: 'ios' | 'android' | 'unknown'
  has_self_report: number   // 0 | 1 (CSV-parsed as number)
  self_report_rows: number
  self_report_days: number
  first_self_report_date: string | null
  last_self_report_date: string | null
  has_synapse: number        // 0 | 1
  synapse_sessions: number
  first_synapse_date: string | null
  last_synapse_date: string | null
  synapse_source_table: string | null
  /** Safe filename key (record_id or alias_{alias}). Empty if not yet generated. */
  participant_detail_key: string
  /** Public path to per-participant session manifest CSV. Empty if not generated. */
  session_manifest_detail_path: string
  /** Public path to per-participant linked timegrid CSV. Empty if not generated. */
  linked_timegrid_detail_path: string
}

// ─── self_report_daily_outcomes.csv ────────────────────────────────────────
export interface SelfReportOutcomesRow {
  health_code: string
  health_code_masked: string
  record_id: number | null
  alias: number | null
  date: string
  survey_timestamp: string
  has_redcap_outcome: number   // 0 | 1
  daily_suicidality_binary: number | null
  suicidality_0_9: number | null
  self_harm_binary: number | null
}

// ─── synapse_presence_filtered.csv ────────────────────────────────────────
export interface SynapsePresenceRow {
  record_id: number | null
  alias: number | null
  health_code: string
  input_healthcode: string
  matched_healthcode: string | null
  target_table_id: string | null
  source_label: string | null
  match_count: number
  status: 'matched' | 'not_found' | 'error'
  error: string | null
}

// ─── session_manifest_filtered.csv ────────────────────────────────────────
export interface SessionManifestRow {
  record_id: number | null
  alias: number | null
  /** Omitted from per-participant detail files to avoid exposing raw health_code. */
  health_code?: string
  health_code_masked?: string
  matched_healthcode: string
  source_table_id: string
  source_label: string
  recordId: string
  appVersion: string
  phoneInfo: string
  uploadDate: string
  createdOn: string
  createdOnTimeZone: string
  session_date: string
  row_num_within_participant: number
  dayInStudy: number | null
}

// ─── biaffect_metric_bins_filtered.csv ────────────────────────────────────
export interface MetricBinsRow {
  health_code: string
  health_code_masked: string
  record_id: number | null
  alias: number | null
  date: string
  bin_index: number
  bin_start: string
  bin_end: string
  observed_minutes: number
  keyboard_session_count: number
  typing_event_count: number
  backspace_count: number
  backspace_ratio: number | null
  mean_inter_key_interval: number | null
  median_inter_key_interval: number | null
  accelerometer_activity_mean: number | null
  accelerometer_activity_sd: number | null
  data_coverage_pct: number | null
}

// ─── linked_timegrid_filtered.csv ──────────────────────────────────────────
export interface LinkedTimegridRow {
  record_id: number | null
  alias: number | null
  health_code: string
  health_code_masked: string
  participant: string
  date: string
  bin_index: number
  bin_start: string
  bin_end: string
  n_keylogs: number
  n_backspace: number
  n_autocorrection: number
  n_suggestion: number
  n_alphanum: number
  n_punctuation: number
  n_accelerations: number
  n_sessions_in_bin: number
  has_keylog_observation: number   // 0 | 1
  has_accel_observation: number    // 0 | 1
  has_biaffect_for_bin: number     // 0 | 1
  has_self_report_for_day: number  // 0 | 1
  typing_intensity: number
  backspace_ratio: number | null
  observed_minutes_keylog: number
  observed_minutes_accel: number
  daily_suicidality_binary: number | null
  suicidality_0_9: number | null
  self_harm_binary: number | null
}

// ─── Dashboard-level types (computed, not directly from CSV rows) ──────────

export interface DashboardParticipant {
  record_id: number | null
  alias: number | null
  /** Full health_code — for internal joins only. Never render in UI. */
  health_code: string
  /** Masked version safe to display, e.g. "abc***xyz". */
  health_code_masked: string
  device_type: 'ios' | 'android' | 'unknown'
  has_self_report: boolean
  has_synapse: boolean
  self_report_rows: number
  self_report_days: number
  synapse_sessions: number
  first_self_report_date: string | null
  last_self_report_date: string | null
  first_synapse_date: string | null
  last_synapse_date: string | null
  /** Safe filename key used for per-participant detail file paths. */
  participant_detail_key: string
  /** Public URL for this participant's session manifest CSV (empty if not generated). */
  session_manifest_detail_path: string
  /** Public URL for this participant's linked timegrid CSV (empty if not generated). */
  linked_timegrid_detail_path: string
}

export interface PresenceSummaryStats {
  total: number
  withSelfReport: number
  withSynapse: number
  withBoth: number
  missingLinkage: number
}

export interface FilterState {
  record_id: string
  alias: string
  health_code: string
  device_type: 'all' | 'ios' | 'android' | 'unknown'
  require_self_report: boolean
  require_synapse: boolean
  start_date: string
  end_date: string
  max_rows: number
}

// ─── Utility ───────────────────────────────────────────────────────────────

/** Convert a ParticipantIndexRow (from CSV) to a DashboardParticipant. */
export function participantFromRow(row: ParticipantIndexRow): DashboardParticipant {
  return {
    record_id:                     row.record_id,
    alias:                         row.alias,
    health_code:                   row.health_code ?? '',
    health_code_masked:            row.health_code_masked ?? maskHealthCode(row.health_code ?? ''),
    device_type:                   (['ios', 'android', 'unknown'].includes(row.device_type)
                                     ? row.device_type
                                     : 'unknown') as DashboardParticipant['device_type'],
    has_self_report:               Number(row.has_self_report) === 1,
    has_synapse:                   Number(row.has_synapse) === 1,
    self_report_rows:              row.self_report_rows ?? 0,
    self_report_days:              row.self_report_days ?? 0,
    synapse_sessions:              row.synapse_sessions ?? 0,
    first_self_report_date:        row.first_self_report_date || null,
    last_self_report_date:         row.last_self_report_date || null,
    first_synapse_date:            row.first_synapse_date || null,
    last_synapse_date:             row.last_synapse_date || null,
    participant_detail_key:        row.participant_detail_key ?? '',
    session_manifest_detail_path:  row.session_manifest_detail_path ?? '',
    linked_timegrid_detail_path:   row.linked_timegrid_detail_path ?? '',
  }
}

export function maskHealthCode(hc: string): string {
  if (!hc || hc.length <= 4) return '***'
  if (hc.length <= 8) return hc.slice(0, 2) + '***' + hc.slice(-2)
  return hc.slice(0, 3) + '***' + hc.slice(-3)
}
