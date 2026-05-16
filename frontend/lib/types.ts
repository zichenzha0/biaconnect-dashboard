/**
 * Shared TypeScript interfaces for BiaConnect Dashboard.
 *
 * These types mirror the column schemas of the CSV files produced by
 * the Python backend pipeline (src/main.py). When the frontend connects
 * to real output files, these interfaces are the contract between the
 * Python outputs and the React components.
 *
 * Expected output files from Python:
 *   outputs/dashboard_exports/participant_index_filtered.csv
 *   outputs/dashboard_exports/synapse_presence_filtered.csv
 *   outputs/dashboard_exports/session_manifest_filtered.csv
 *   outputs/dashboard_exports/redcap_daily_outcomes.csv
 *   outputs/dashboard_exports/metric_bins_observed_filtered.csv
 *   outputs/dashboard_exports/linked_timegrid_filtered.csv
 */

// ─── participant_index_filtered.csv ────────────────────────────────────────
export interface ParticipantIndexRow {
  record_id: number | null
  alias: number | null
  health_code: string
  phone_type_raw: string
  device_type: 'ios' | 'android' | 'unknown'
  record_id_str: string
  has_redcap_outcome: 0 | 1
  redcap_n_rows: number
  redcap_n_days: number
  redcap_first_date: string | null
  redcap_last_date: string | null
}

// ─── synapse_presence_filtered.csv ────────────────────────────────────────
export interface SynapsePresenceRow {
  record_id: number | null
  alias: number | null
  phone_type_raw: string
  device_type: string
  health_code: string
  input_healthcode: string
  matched_healthcode: string | null
  target_table_id: string | null
  source_table_id: string | null
  source_label: string | null
  match_count: number
  status: 'matched' | 'not_found' | 'error'
  tried_all_tables: string
  error: string | null
}

// ─── session_manifest_filtered.csv ────────────────────────────────────────
export interface SessionManifestRow {
  record_id: number | null
  alias: number | null
  health_code: string
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

// ─── redcap_daily_outcomes.csv ─────────────────────────────────────────────
export interface RedcapOutcomesRow {
  record_id: number | null
  alias: number | null
  health_code: string
  date: string
  survey_timestamp: string
  redcap_id_str: string
  has_redcap_outcome: 0 | 1
  daily_suicidality_binary: number | null
  suicidality_0_9: number | null
  self_harm_binary: number | null
}

// ─── metric_bins_observed_filtered.csv ────────────────────────────────────
export interface MetricBinsRow {
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
  typing_intensity: number
  backspace_ratio: number | null
  autocorrect_rate: number | null
  suggestion_rate: number | null
  alphanum_rate: number | null
  punctuation_rate: number | null
  key_duration_mean: number | null
  key_duration_median: number | null
  key_duration_sd: number | null
  distance_from_center_mean: number | null
  distance_from_previous_mean: number | null
  n_sessions_in_bin: number
  n_accelerations: number
  accelerometer_activity: number | null
  accelerometer_activity_sd: number | null
  n_accel_sessions_in_bin: number
}

// ─── linked_timegrid_filtered.csv ──────────────────────────────────────────
export interface LinkedTimegridRow {
  record_id: number | null
  alias: number | null
  health_code: string
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
  n_accel_sessions_in_bin: number
  has_keylog_observation: 0 | 1
  has_accel_observation: 0 | 1
  typing_intensity: number
  backspace_ratio: number | null
  autocorrect_rate: number | null
  suggestion_rate: number | null
  alphanum_rate: number | null
  punctuation_rate: number | null
  observed_minutes_keylog: number
  observed_minutes_accel: number
  daily_suicidality_binary: number | null
  suicidality_0_9: number | null
  self_harm_binary: number | null
}

// ─── Dashboard-level types (computed/joined, not directly from CSVs) ───────

export interface DashboardParticipant {
  record_id: number | null
  alias: number | null
  /** Full health_code — never render this directly in the UI. */
  health_code: string
  /** Pre-masked health_code for display (e.g. "a3f***c1"). */
  health_code_masked: string
  device_type: 'ios' | 'android' | 'unknown'
  has_redcap: boolean
  has_synapse: boolean
  self_report_days: number
  synapse_sessions: number
  first_observed_date: string | null
  last_observed_date: string | null
}

export interface PresenceSummaryStats {
  total: number
  withRedcap: number
  withSynapse: number
  withBoth: number
  missingLinkage: number
}

export interface FilterState {
  record_id: string
  alias: string
  health_code: string
  device_type: 'all' | 'ios' | 'android' | 'unknown'
  require_redcap: boolean
  require_synapse: boolean
  start_date: string
  end_date: string
  max_rows: number
}
