"""
Shared constants for BiaConnect Dashboard.

This repo links BiAffect keyboard-session data from Synapse with REDCap
self-report data at the participant level. Keep paths, Synapse table IDs,
column conventions, and default filter settings here.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # project root (one level above src/)

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

OUTPUT_DIR = PROJECT_ROOT / "outputs"
MANIFEST_DIR = OUTPUT_DIR / "manifests"
DOWNLOAD_DIR = OUTPUT_DIR / "downloads"
EXTRACTED_DIR = OUTPUT_DIR / "extracted"
DASHBOARD_EXPORT_DIR = OUTPUT_DIR / "dashboard_exports"
QC_DIR = OUTPUT_DIR / "qc"

DEFAULT_DIRS = [
    DATA_DIR,
    RAW_DIR,
    INTERIM_DIR,
    PROCESSED_DIR,
    OUTPUT_DIR,
    MANIFEST_DIR,
    DOWNLOAD_DIR,
    EXTRACTED_DIR,
    DASHBOARD_EXPORT_DIR,
    QC_DIR,
]

# Default local inputs. Put real data here locally only; never commit them.
DEFAULT_IDS_XLSX = RAW_DIR / "BiAffect IDs.xlsx"
DEFAULT_REDCAP_REPORT_CSV = RAW_DIR / "report.csv"

# ---------------------------------------------------------------------
# Synapse settings
# ---------------------------------------------------------------------
IPHONE_TABLE_ID = "syn7841520"      # BiAffect KeyboardSession v2
ANDROID_TABLE_ID = "syn20727526"   # KeyboardSession v1
SYNAPSE_HEALTHCODE_COLUMN = "healthCode"

SYNAPSE_TABLE_OPTIONS = {
    "android": [(ANDROID_TABLE_ID, "android_keyboard_v1"), (IPHONE_TABLE_ID, "iphone_keyboard_v2")],
    "ios": [(IPHONE_TABLE_ID, "iphone_keyboard_v2"), (ANDROID_TABLE_ID, "android_keyboard_v1")],
    "unknown": [(IPHONE_TABLE_ID, "iphone_keyboard_v2"), (ANDROID_TABLE_ID, "android_keyboard_v1")],
}

SYNAPSE_SESSION_COLUMNS = [
    "recordId",
    "appVersion",
    "phoneInfo",
    "uploadDate",
    "healthCode",
    "externalId",
    "dataGroups",
    "createdOn",
    "createdOnTimeZone",
    "userSharingScope",
    "substudyMemberships",
    "dayInStudy",
    '"Session.json.duration"',
    '"Session.json.timestamp"',
    '"Session.json.timestamp.timezone"',
    '"Session.json.keylogs"',
    '"Session.json.accelerations"',
    "rawData",
    "rawMetadata",
]

SYNAPSE_FILE_COLUMNS = [
    "Session.json.keylogs",
    "Session.json.accelerations",
    "rawData",
    "rawMetadata",
]

# ---------------------------------------------------------------------
# Linkage and outcome conventions
# ---------------------------------------------------------------------
ID_RENAME_MAP = {
    "ID": "record_id",
    "Alias": "alias",
    "Phone Type": "phone_type_raw",
    "Health Code": "health_code",
}

ID_REQUIRED_COLUMNS = ["record_id", "alias", "phone_type_raw", "health_code"]

REDCAP_SURVEY_IDENTIFIER = "redcap_survey_identifier"
KNOWN_REDCAP_ID_FIXES = {
    # Known REDCap export issue from the current working files.
    # If report_record_id == 96 has blank/incorrect identifier, map to 127084.
    96: "127084",
}

OUTCOME_BINARY_CANDIDATE_KEYWORDS = ["binary", "yes", "thought", "ideation"]
OUTCOME_INTENSITY_CANDIDATE_KEYWORDS = ["intensity", "0_9", "score", "severity", "rating"]

# ---------------------------------------------------------------------
# Time-grid settings
# ---------------------------------------------------------------------
BIN_MINUTES = 15
BINS_PER_DAY = int(24 * 60 / BIN_MINUTES)
DEFAULT_TIMEZONE = None
DEFAULT_PREDICTION_HORIZONS = [1, 7]

# ---------------------------------------------------------------------
# Default run settings
# ---------------------------------------------------------------------
DEFAULT_MAX_ROWS_PER_PARTICIPANT = 0  # 0 means no cap; use 10 for smoke tests.
DEFAULT_DEDUPLICATE_BY_RECORDID = True
DEFAULT_SORT_MANIFEST_BY = "createdOn"

# ---------------------------------------------------------------------
# Output filenames
# ---------------------------------------------------------------------
IDS_CLEAN_FILENAME = "participants_clean.csv"
DAILY_OUTCOMES_FILENAME = "redcap_daily_outcomes.csv"
PARTICIPANT_INDEX_FILENAME = "participant_index_filtered.csv"
SYNAPSE_PRESENCE_FILENAME = "synapse_presence_filtered.csv"
SESSION_MANIFEST_FILENAME = "session_manifest_filtered.csv"
DOWNLOAD_LOG_FILENAME = "download_log_filtered.csv"
KEYLOGS_LONG_FILENAME = "keylogs_long_filtered.csv"
ACCELS_LONG_FILENAME = "accelerations_long_filtered.csv"
METRIC_BINS_FILENAME = "metric_bins_observed_filtered.csv"
LINKED_TIMEGRID_FILENAME = "linked_timegrid_filtered.csv"

# ---------------------------------------------------------------------
# Zero / missing interpretation used by dashboard documentation
# ---------------------------------------------------------------------
ZERO_MISSING_NA_RULES = {
    "true_zero": "The metric was observable in that bin and the count/value is zero.",
    "missing_unobserved": "No data were observed for that metric in that bin.",
    "undefined_na": "The value is mathematically undefined, e.g., a ratio with denominator zero.",
}
