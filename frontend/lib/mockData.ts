/**
 * Synthetic mock data for BiaConnect Dashboard MVP.
 *
 * All identifiers are clearly fake. No real participant data is used.
 * This data is used only when real CSV files are unavailable.
 */
import type {
  DashboardParticipant,
  SessionManifestRow,
  SelfReportOutcomesRow,
  LinkedTimegridRow,
  MetricBinsRow,
} from './types'
import { maskHealthCode } from './types'

const RAW = [
  { record_id: 127084, alias: 1001, health_code: 'mock_a3f9b2c1', device_type: 'ios'     as const, has_self_report: true,  has_synapse: true,  self_report_rows: 142, self_report_days: 142, synapse_sessions: 87,  first_self_report_date: '2024-01-15', last_self_report_date: '2024-08-03', first_synapse_date: '2024-01-16', last_synapse_date: '2024-08-02' },
  { record_id: 91811,  alias: 1002, health_code: 'mock_d4e5f6a7', device_type: 'ios'     as const, has_self_report: true,  has_synapse: true,  self_report_rows: 98,  self_report_days: 98,  synapse_sessions: 54,  first_self_report_date: '2024-02-01', last_self_report_date: '2024-07-22', first_synapse_date: '2024-02-03', last_synapse_date: '2024-07-20' },
  { record_id: 234567, alias: 1003, health_code: 'mock_b8c9d0e1', device_type: 'android' as const, has_self_report: true,  has_synapse: false, self_report_rows: 61,  self_report_days: 61,  synapse_sessions: 0,   first_self_report_date: '2024-03-10', last_self_report_date: '2024-06-15', first_synapse_date: null,         last_synapse_date: null          },
  { record_id: 345678, alias: 1004, health_code: 'mock_f2a3b4c5', device_type: 'android' as const, has_self_report: false, has_synapse: true,  self_report_rows: 0,   self_report_days: 0,   synapse_sessions: 39,  first_self_report_date: null,         last_self_report_date: null,         first_synapse_date: '2024-04-05', last_synapse_date: '2024-09-01' },
  { record_id: 456789, alias: 1005, health_code: 'mock_e6d7c8b9', device_type: 'ios'     as const, has_self_report: true,  has_synapse: true,  self_report_rows: 210, self_report_days: 210, synapse_sessions: 131, first_self_report_date: '2023-11-20', last_self_report_date: '2024-08-31', first_synapse_date: '2023-11-22', last_synapse_date: '2024-08-30' },
  { record_id: 567890, alias: 1006, health_code: 'mock_a1b2c3d4', device_type: 'android' as const, has_self_report: false, has_synapse: false, self_report_rows: 0,   self_report_days: 0,   synapse_sessions: 0,   first_self_report_date: null,         last_self_report_date: null,         first_synapse_date: null,         last_synapse_date: null          },
  { record_id: 678901, alias: 1007, health_code: 'mock_e5f6a7b8', device_type: 'ios'     as const, has_self_report: true,  has_synapse: false, self_report_rows: 33,  self_report_days: 33,  synapse_sessions: 0,   first_self_report_date: '2024-05-02', last_self_report_date: '2024-06-30', first_synapse_date: null,         last_synapse_date: null          },
  { record_id: 789012, alias: 1008, health_code: 'mock_c9d0e1f2', device_type: 'unknown' as const, has_self_report: false, has_synapse: true,  self_report_rows: 0,   self_report_days: 0,   synapse_sessions: 12,  first_self_report_date: null,         last_self_report_date: null,         first_synapse_date: '2024-07-01', last_synapse_date: '2024-07-28' },
]

export const mockParticipants: DashboardParticipant[] = RAW.map(p => ({
  ...p,
  health_code_masked:           maskHealthCode(p.health_code),
  participant_detail_key:       p.record_id != null ? String(p.record_id) : `alias_${p.alias}`,
  session_manifest_detail_path: '',  // no detail files in mock mode
  linked_timegrid_detail_path:  '',
}))

// ─── Self-report outcomes ─────────────────────────────────────────────────────

export const mockSelfReportOutcomes: SelfReportOutcomesRow[] = [
  { health_code: 'mock_a3f9b2c1', health_code_masked: 'moc***c1', record_id: 127084, alias: 1001, date: '2024-03-10', survey_timestamp: '2024-03-10T20:01:00Z', has_redcap_outcome: 1, daily_suicidality_binary: 0, suicidality_0_9: 1, self_harm_binary: 0 },
  { health_code: 'mock_a3f9b2c1', health_code_masked: 'moc***c1', record_id: 127084, alias: 1001, date: '2024-03-11', survey_timestamp: '2024-03-11T19:45:00Z', has_redcap_outcome: 1, daily_suicidality_binary: 0, suicidality_0_9: 0, self_harm_binary: 0 },
  { health_code: 'mock_a3f9b2c1', health_code_masked: 'moc***c1', record_id: 127084, alias: 1001, date: '2024-03-14', survey_timestamp: '2024-03-14T21:10:00Z', has_redcap_outcome: 1, daily_suicidality_binary: 1, suicidality_0_9: 4, self_harm_binary: 0 },
  { health_code: 'mock_a3f9b2c1', health_code_masked: 'moc***c1', record_id: 127084, alias: 1001, date: '2024-03-15', survey_timestamp: '2024-03-15T20:30:00Z', has_redcap_outcome: 1, daily_suicidality_binary: 1, suicidality_0_9: 3, self_harm_binary: 0 },
  { health_code: 'mock_e6d7c8b9', health_code_masked: 'moc***b9', record_id: 456789, alias: 1005, date: '2024-01-08', survey_timestamp: '2024-01-08T20:00:00Z', has_redcap_outcome: 1, daily_suicidality_binary: 0, suicidality_0_9: 0, self_harm_binary: 0 },
  { health_code: 'mock_e6d7c8b9', health_code_masked: 'moc***b9', record_id: 456789, alias: 1005, date: '2024-01-09', survey_timestamp: '2024-01-09T20:00:00Z', has_redcap_outcome: 1, daily_suicidality_binary: 0, suicidality_0_9: 2, self_harm_binary: 0 },
]

// kept as alias for backward compat within the file
export { mockSelfReportOutcomes as mockRedcapOutcomes }

// ─── Session manifest ─────────────────────────────────────────────────────────

export const mockSessionManifest: SessionManifestRow[] = [
  { record_id: 127084, alias: 1001, health_code: 'mock_a3f9b2c1', matched_healthcode: 'mock_a3f9b2c1', source_table_id: 'syn7841520', source_label: 'iphone_keyboard_v2', recordId: 'mock_rec_001', appVersion: 'BiAffect/3.2.1', phoneInfo: 'iPhone 14 Pro', uploadDate: '2024-03-10T08:22:11Z', createdOn: '2024-03-10T08:22:11Z', createdOnTimeZone: '-0500', session_date: '2024-03-10', row_num_within_participant: 1, dayInStudy: 54 },
  { record_id: 127084, alias: 1001, health_code: 'mock_a3f9b2c1', matched_healthcode: 'mock_a3f9b2c1', source_table_id: 'syn7841520', source_label: 'iphone_keyboard_v2', recordId: 'mock_rec_002', appVersion: 'BiAffect/3.2.1', phoneInfo: 'iPhone 14 Pro', uploadDate: '2024-03-11T09:14:05Z', createdOn: '2024-03-11T09:14:05Z', createdOnTimeZone: '-0500', session_date: '2024-03-11', row_num_within_participant: 2, dayInStudy: 55 },
  { record_id: 456789, alias: 1005, health_code: 'mock_e6d7c8b9', matched_healthcode: 'mock_e6d7c8b9', source_table_id: 'syn7841520', source_label: 'iphone_keyboard_v2', recordId: 'mock_rec_101', appVersion: 'BiAffect/3.1.8', phoneInfo: 'iPhone 13',     uploadDate: '2024-01-08T10:30:00Z', createdOn: '2024-01-08T10:30:00Z', createdOnTimeZone: '-0600', session_date: '2024-01-08', row_num_within_participant: 1, dayInStudy: 49 },
]

// ─── BiAffect metric bins ─────────────────────────────────────────────────────

export const mockMetricBins: MetricBinsRow[] = [
  { health_code: 'mock_a3f9b2c1', health_code_masked: 'moc***c1', record_id: 127084, alias: 1001, date: '2024-03-10', bin_index: 36, bin_start: '2024-03-10T09:00:00', bin_end: '2024-03-10T09:15:00', observed_minutes: 15, keyboard_session_count: 1, typing_event_count: 64, backspace_count: 7, backspace_ratio: 0.109, mean_inter_key_interval: null, median_inter_key_interval: null, accelerometer_activity_mean: 0.42, accelerometer_activity_sd: 0.18, data_coverage_pct: 1.0 },
  { health_code: 'mock_a3f9b2c1', health_code_masked: 'moc***c1', record_id: 127084, alias: 1001, date: '2024-03-10', bin_index: 40, bin_start: '2024-03-10T10:00:00', bin_end: '2024-03-10T10:15:00', observed_minutes: 15, keyboard_session_count: 1, typing_event_count: 91, backspace_count: 5, backspace_ratio: 0.055, mean_inter_key_interval: null, median_inter_key_interval: null, accelerometer_activity_mean: 0.31, accelerometer_activity_sd: 0.12, data_coverage_pct: 1.0 },
  { health_code: 'mock_a3f9b2c1', health_code_masked: 'moc***c1', record_id: 127084, alias: 1001, date: '2024-03-11', bin_index: 38, bin_start: '2024-03-11T09:30:00', bin_end: '2024-03-11T09:45:00', observed_minutes: 15, keyboard_session_count: 1, typing_event_count: 45, backspace_count: 3, backspace_ratio: 0.067, mean_inter_key_interval: null, median_inter_key_interval: null, accelerometer_activity_mean: 0.55, accelerometer_activity_sd: 0.22, data_coverage_pct: 1.0 },
]

// ─── Linked timegrid ──────────────────────────────────────────────────────────

function makeBins(record_id: number, alias: number, health_code: string, date: string): LinkedTimegridRow[] {
  const rows: LinkedTimegridRow[] = []
  for (let bin = 0; bin < 96; bin++) {
    const hh = Math.floor((bin * 15) / 60).toString().padStart(2, '0')
    const mm = ((bin * 15) % 60).toString().padStart(2, '0')
    const active = bin >= 32 && bin <= 80 && Math.random() > 0.5
    const n_keylogs = active ? Math.floor(Math.random() * 80 + 10) : 0
    const n_backspace = active ? Math.floor(Math.random() * 8) : 0
    rows.push({
      record_id, alias, health_code,
      health_code_masked: maskHealthCode(health_code),
      participant: String(record_id),
      date, bin_index: bin,
      bin_start: `${date}T${hh}:${mm}:00`,
      bin_end:   `${date}T${hh}:${mm}:00`,
      n_keylogs, n_backspace,
      n_autocorrection: active ? Math.floor(Math.random() * 3) : 0,
      n_suggestion:     active ? Math.floor(Math.random() * 4) : 0,
      n_alphanum:       active ? Math.floor(n_keylogs * 0.7) : 0,
      n_punctuation:    active ? Math.floor(n_keylogs * 0.08) : 0,
      n_accelerations:  active ? Math.floor(Math.random() * 200 + 20) : 0,
      n_sessions_in_bin: active ? 1 : 0,
      has_keylog_observation: active ? 1 : 0,
      has_accel_observation:  active ? 1 : 0,
      has_biaffect_for_bin:   active ? 1 : 0,
      has_self_report_for_day: bin === 0 ? 1 : 0,
      typing_intensity:   active ? +(n_keylogs / 15).toFixed(2) : 0,
      backspace_ratio:    active && n_keylogs > 0 ? +(n_backspace / n_keylogs).toFixed(3) : null,
      observed_minutes_keylog: active ? 15 : 0,
      observed_minutes_accel:  active ? 15 : 0,
      daily_suicidality_binary: bin === 0 ? 0 : null,
      suicidality_0_9:          bin === 0 ? 1 : null,
      self_harm_binary:         bin === 0 ? 0 : null,
    })
  }
  return rows
}

export const mockLinkedTimegrid: LinkedTimegridRow[] = [
  ...makeBins(127084, 1001, 'mock_a3f9b2c1', '2024-03-10'),
  ...makeBins(127084, 1001, 'mock_a3f9b2c1', '2024-03-11'),
  ...makeBins(456789, 1005, 'mock_e6d7c8b9', '2024-01-08'),
]
