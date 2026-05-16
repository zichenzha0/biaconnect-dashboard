/**
 * Mock data for BiaConnect Dashboard MVP.
 *
 * All health_codes, record_ids, and dates are synthetic and clearly labelled
 * as mock values. No real participant identifiers are used here.
 *
 * When the Python pipeline has run and produced CSV outputs, replace these
 * with real data loaded via csvLoader.ts.
 */
import type {
  DashboardParticipant,
  SessionManifestRow,
  RedcapOutcomesRow,
  LinkedTimegridRow,
} from './types'

/** Mask a health_code for safe display: "a3f9b2c1" → "a3f***c1" */
export function maskHealthCode(hc: string): string {
  if (!hc || hc.length <= 4) return '***'
  if (hc.length <= 8) return hc.slice(0, 2) + '***' + hc.slice(-2)
  return hc.slice(0, 3) + '***' + hc.slice(-3)
}

// ─── Participant index ──────────────────────────────────────────────────────

const RAW_PARTICIPANTS = [
  { record_id: 127084, alias: 1001, health_code: 'mock_a3f9b2c1', device_type: 'ios' as const,     has_redcap: true,  has_synapse: true,  self_report_days: 142, synapse_sessions: 87, first_observed_date: '2024-01-15', last_observed_date: '2024-08-03' },
  { record_id: 91811,  alias: 1002, health_code: 'mock_d4e5f6a7', device_type: 'ios' as const,     has_redcap: true,  has_synapse: true,  self_report_days: 98,  synapse_sessions: 54, first_observed_date: '2024-02-01', last_observed_date: '2024-07-22' },
  { record_id: 234567, alias: 1003, health_code: 'mock_b8c9d0e1', device_type: 'android' as const, has_redcap: true,  has_synapse: false, self_report_days: 61,  synapse_sessions: 0,  first_observed_date: '2024-03-10', last_observed_date: '2024-06-15' },
  { record_id: 345678, alias: 1004, health_code: 'mock_f2a3b4c5', device_type: 'android' as const, has_redcap: false, has_synapse: true,  self_report_days: 0,   synapse_sessions: 39, first_observed_date: '2024-04-05', last_observed_date: '2024-09-01' },
  { record_id: 456789, alias: 1005, health_code: 'mock_e6d7c8b9', device_type: 'ios' as const,     has_redcap: true,  has_synapse: true,  self_report_days: 210, synapse_sessions: 131,first_observed_date: '2023-11-20', last_observed_date: '2024-08-31' },
  { record_id: 567890, alias: 1006, health_code: 'mock_a1b2c3d4', device_type: 'android' as const, has_redcap: false, has_synapse: false, self_report_days: 0,   synapse_sessions: 0,  first_observed_date: null,         last_observed_date: null          },
  { record_id: 678901, alias: 1007, health_code: 'mock_e5f6a7b8', device_type: 'ios' as const,     has_redcap: true,  has_synapse: false, self_report_days: 33,  synapse_sessions: 0,  first_observed_date: '2024-05-02', last_observed_date: '2024-06-30' },
  { record_id: 789012, alias: 1008, health_code: 'mock_c9d0e1f2', device_type: 'unknown' as const, has_redcap: false, has_synapse: true,  self_report_days: 0,   synapse_sessions: 12, first_observed_date: '2024-07-01', last_observed_date: '2024-07-28' },
]

export const mockParticipants: DashboardParticipant[] = RAW_PARTICIPANTS.map(p => ({
  ...p,
  health_code_masked: maskHealthCode(p.health_code),
}))

// ─── Session manifest (for selected participant) ────────────────────────────

export const mockSessionManifest: SessionManifestRow[] = [
  { record_id: 127084, alias: 1001, health_code: 'mock_a3f9b2c1', matched_healthcode: 'mock_a3f9b2c1', source_table_id: 'syn7841520', source_label: 'iphone_keyboard_v2', recordId: 'mock_rec_001', appVersion: 'BiAffect/3.2.1', phoneInfo: 'iPhone 14 Pro', uploadDate: '2024-03-10T08:22:11Z', createdOn: '2024-03-10T08:22:11Z', createdOnTimeZone: '-0500', session_date: '2024-03-10', row_num_within_participant: 1, dayInStudy: 54 },
  { record_id: 127084, alias: 1001, health_code: 'mock_a3f9b2c1', matched_healthcode: 'mock_a3f9b2c1', source_table_id: 'syn7841520', source_label: 'iphone_keyboard_v2', recordId: 'mock_rec_002', appVersion: 'BiAffect/3.2.1', phoneInfo: 'iPhone 14 Pro', uploadDate: '2024-03-11T09:14:05Z', createdOn: '2024-03-11T09:14:05Z', createdOnTimeZone: '-0500', session_date: '2024-03-11', row_num_within_participant: 2, dayInStudy: 55 },
  { record_id: 127084, alias: 1001, health_code: 'mock_a3f9b2c1', matched_healthcode: 'mock_a3f9b2c1', source_table_id: 'syn7841520', source_label: 'iphone_keyboard_v2', recordId: 'mock_rec_003', appVersion: 'BiAffect/3.2.2', phoneInfo: 'iPhone 14 Pro', uploadDate: '2024-03-14T17:55:32Z', createdOn: '2024-03-14T17:55:32Z', createdOnTimeZone: '-0500', session_date: '2024-03-14', row_num_within_participant: 3, dayInStudy: 58 },
  { record_id: 456789, alias: 1005, health_code: 'mock_e6d7c8b9', matched_healthcode: 'mock_e6d7c8b9', source_table_id: 'syn7841520', source_label: 'iphone_keyboard_v2', recordId: 'mock_rec_101', appVersion: 'BiAffect/3.1.8', phoneInfo: 'iPhone 13',     uploadDate: '2024-01-08T10:30:00Z', createdOn: '2024-01-08T10:30:00Z', createdOnTimeZone: '-0600', session_date: '2024-01-08', row_num_within_participant: 1, dayInStudy: 49 },
  { record_id: 456789, alias: 1005, health_code: 'mock_e6d7c8b9', matched_healthcode: 'mock_e6d7c8b9', source_table_id: 'syn7841520', source_label: 'iphone_keyboard_v2', recordId: 'mock_rec_102', appVersion: 'BiAffect/3.1.8', phoneInfo: 'iPhone 13',     uploadDate: '2024-01-09T11:00:00Z', createdOn: '2024-01-09T11:00:00Z', createdOnTimeZone: '-0600', session_date: '2024-01-09', row_num_within_participant: 2, dayInStudy: 50 },
]

// ─── REDCap daily outcomes (for selected participant) ───────────────────────

export const mockRedcapOutcomes: RedcapOutcomesRow[] = [
  { record_id: 127084, alias: 1001, health_code: 'mock_a3f9b2c1', date: '2024-03-10', survey_timestamp: '2024-03-10T20:01:00Z', redcap_id_str: '127084', has_redcap_outcome: 1, daily_suicidality_binary: 0, suicidality_0_9: 1, self_harm_binary: 0 },
  { record_id: 127084, alias: 1001, health_code: 'mock_a3f9b2c1', date: '2024-03-11', survey_timestamp: '2024-03-11T19:45:00Z', redcap_id_str: '127084', has_redcap_outcome: 1, daily_suicidality_binary: 0, suicidality_0_9: 0, self_harm_binary: 0 },
  { record_id: 127084, alias: 1001, health_code: 'mock_a3f9b2c1', date: '2024-03-14', survey_timestamp: '2024-03-14T21:10:00Z', redcap_id_str: '127084', has_redcap_outcome: 1, daily_suicidality_binary: 1, suicidality_0_9: 4, self_harm_binary: 0 },
  { record_id: 127084, alias: 1001, health_code: 'mock_a3f9b2c1', date: '2024-03-15', survey_timestamp: '2024-03-15T20:30:00Z', redcap_id_str: '127084', has_redcap_outcome: 1, daily_suicidality_binary: 1, suicidality_0_9: 3, self_harm_binary: 0 },
  { record_id: 456789, alias: 1005, health_code: 'mock_e6d7c8b9', date: '2024-01-08', survey_timestamp: '2024-01-08T20:00:00Z', redcap_id_str: '456789', has_redcap_outcome: 1, daily_suicidality_binary: 0, suicidality_0_9: 0, self_harm_binary: 0 },
  { record_id: 456789, alias: 1005, health_code: 'mock_e6d7c8b9', date: '2024-01-09', survey_timestamp: '2024-01-09T20:00:00Z', redcap_id_str: '456789', has_redcap_outcome: 1, daily_suicidality_binary: 0, suicidality_0_9: 2, self_harm_binary: 0 },
]

// ─── Linked timegrid sample (a few bins across 2 days) ──────────────────────

function makeBins(
  record_id: number,
  alias: number,
  health_code: string,
  date: string,
  dayInStudy: number,
): LinkedTimegridRow[] {
  const rows: LinkedTimegridRow[] = []
  for (let bin = 0; bin < 96; bin++) {
    const hh = Math.floor((bin * 15) / 60).toString().padStart(2, '0')
    const mm = ((bin * 15) % 60).toString().padStart(2, '0')
    const active = bin >= 32 && bin <= 80 && Math.random() > 0.45
    rows.push({
      record_id,
      alias,
      health_code,
      participant: String(record_id),
      date,
      bin_index: bin,
      bin_start: `${date}T${hh}:${mm}:00`,
      bin_end:   `${date}T${hh}:${mm}:00`,
      n_keylogs:           active ? Math.floor(Math.random() * 80 + 10) : 0,
      n_backspace:         active ? Math.floor(Math.random() * 8) : 0,
      n_autocorrection:    active ? Math.floor(Math.random() * 4) : 0,
      n_suggestion:        active ? Math.floor(Math.random() * 6) : 0,
      n_alphanum:          active ? Math.floor(Math.random() * 50 + 5) : 0,
      n_punctuation:       active ? Math.floor(Math.random() * 10) : 0,
      n_accelerations:     active ? Math.floor(Math.random() * 200 + 20) : 0,
      n_sessions_in_bin:   active ? 1 : 0,
      n_accel_sessions_in_bin: active ? 1 : 0,
      has_keylog_observation: active ? 1 : 0,
      has_accel_observation:  active ? 1 : 0,
      typing_intensity:    active ? +(Math.random() * 5 + 0.5).toFixed(2) : 0,
      backspace_ratio:     active ? +(Math.random() * 0.12).toFixed(3) : null,
      autocorrect_rate:    active ? +(Math.random() * 0.06).toFixed(3) : null,
      suggestion_rate:     active ? +(Math.random() * 0.08).toFixed(3) : null,
      alphanum_rate:       active ? +(Math.random() * 0.7 + 0.3).toFixed(3) : null,
      punctuation_rate:    active ? +(Math.random() * 0.15).toFixed(3) : null,
      observed_minutes_keylog: active ? 15 : 0,
      observed_minutes_accel:  active ? 15 : 0,
      daily_suicidality_binary: bin === 0 ? (dayInStudy % 3 === 0 ? 1 : 0) : null,
      suicidality_0_9:          bin === 0 ? (dayInStudy % 3 === 0 ? 4 : 1) : null,
      self_harm_binary:         bin === 0 ? 0 : null,
    })
  }
  return rows
}

export const mockLinkedTimegrid: LinkedTimegridRow[] = [
  ...makeBins(127084, 1001, 'mock_a3f9b2c1', '2024-03-10', 54),
  ...makeBins(127084, 1001, 'mock_a3f9b2c1', '2024-03-11', 55),
  ...makeBins(456789, 1005, 'mock_e6d7c8b9', '2024-01-08', 49),
  ...makeBins(456789, 1005, 'mock_e6d7c8b9', '2024-01-09', 50),
]
