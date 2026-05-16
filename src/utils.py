"""
Core utility functions for BiaConnect Dashboard.

This file consolidates the current linkage, REDCap outcome building, Synapse
presence/manifest retrieval, optional download, raw Session.json parsing, and
participant-level time-grid construction logic.

Design goal:
    This is no longer a single-participant-only pipeline. The main workflow can
    filter by record_id, alias, health_code, device type, REDCap availability,
    Synapse availability, and date range, then build a filtered cohort manifest.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

from commonconst import (
    ANDROID_TABLE_ID,
    BIN_MINUTES,
    BINS_PER_DAY,
    DEFAULT_DEDUPLICATE_BY_RECORDID,
    DEFAULT_MAX_ROWS_PER_PARTICIPANT,
    DEFAULT_SORT_MANIFEST_BY,
    EXTRACTED_DIR,
    FRONTEND_DASHBOARD_EXPORT_DIR,
    ID_RENAME_MAP,
    ID_REQUIRED_COLUMNS,
    IPHONE_TABLE_ID,
    KNOWN_REDCAP_ID_FIXES,
    OUTCOME_BINARY_CANDIDATE_KEYWORDS,
    OUTCOME_INTENSITY_CANDIDATE_KEYWORDS,
    REDCAP_SURVEY_IDENTIFIER,
    SYNAPSE_FILE_COLUMNS,
    SYNAPSE_HEALTHCODE_COLUMN,
    SYNAPSE_SESSION_COLUMNS,
    SYNAPSE_TABLE_OPTIONS,
)

if load_dotenv is not None:
    load_dotenv()

# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_project_dirs(dirs: Iterable[str | Path]) -> None:
    for d in dirs:
        ensure_dir(d)


def parse_csv_arg(value: str | None, cast: type = str) -> list[Any] | None:
    if value is None or str(value).strip() == "":
        return None
    out: list[Any] = []
    for item in str(value).split(","):
        item = item.strip()
        if not item:
            continue
        try:
            out.append(cast(item))
        except Exception:
            out.append(item)
    return out or None


def sql_escape(value: Any) -> str:
    return str(value).replace("'", "''")


def safe_name(value: Any) -> str:
    value = str(value).strip()
    return re.sub(r"[/\\:*?\"<>|\s]+", "_", value).strip("_")


def normalize_phone_type(value: Any) -> str:
    x = str(value).strip().lower()
    if "android" in x:
        return "android"
    if "iphone" in x or "ipad" in x or "ipod" in x or x == "ios":
        return "ios"
    return "unknown"


def robust_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def standardize_binary(s: pd.Series | None) -> pd.Series:
    if s is None:
        return pd.Series(dtype="float")
    x = s.astype("string").str.strip().str.lower()
    yes_values = {"1", "yes", "y", "true", "t", "positive", "present"}
    no_values = {"0", "no", "n", "false", "f", "negative", "absent"}
    out = pd.Series(np.nan, index=s.index, dtype="float")
    out[x.isin(yes_values)] = 1.0
    out[x.isin(no_values)] = 0.0
    numeric = pd.to_numeric(x, errors="coerce")
    out[numeric.notna()] = numeric[numeric.notna()].clip(lower=0, upper=1)
    return out


def normalize_date_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.normalize()


def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_to_original = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower_to_original:
            return lower_to_original[c.lower()]
    return None


def mask_health_code(hc: Any) -> str:
    """Return a display-safe masked health_code: 'abcdef12' → 'abc***f12'.
    Never call this with a real health_code in a public log or UI string directly —
    only use the returned masked value.
    """
    s = str(hc).strip()
    if not s or s.lower() in ("nan", "none", ""):
        return "***"
    if len(s) <= 4:
        return s[:1] + "***"
    if len(s) <= 8:
        return s[:2] + "***" + s[-2:]
    return s[:3] + "***" + s[-3:]


def export_participant_details(
    participant_df: pd.DataFrame,
    manifest_df: pd.DataFrame,
    timegrid_df: pd.DataFrame,
    backend_out_dir: str | Path,
    frontend_out_dir: str | Path,
) -> pd.DataFrame:
    """Export per-participant session manifest and linked timegrid CSVs.

    Creates:
      <backend_out_dir>/participant_details/<key>_session_manifest.csv
      <backend_out_dir>/participant_details/<key>_linked_timegrid.csv
    And mirrors both trees into <frontend_out_dir>/participant_details/.

    The safe participant_detail_key is the record_id integer (e.g. "127084").
    Falls back to "alias_<alias>" or "part_<index>" if record_id is absent.
    Full health_code is dropped from public detail files; health_code_masked is kept.

    Returns an updated participant_df with three new columns:
      participant_detail_key, session_manifest_detail_path, linked_timegrid_detail_path
    """
    backend_out_dir = Path(backend_out_dir)
    frontend_out_dir = Path(frontend_out_dir)
    detail_backend  = ensure_dir(backend_out_dir  / "participant_details")
    detail_frontend = ensure_dir(frontend_out_dir / "participant_details")

    out = participant_df.copy()

    def make_key(row: pd.Series, fallback_idx: int) -> str:
        rid = row.get("record_id")
        if pd.notna(rid):
            return str(int(rid))
        alias = row.get("alias")
        if pd.notna(alias):
            return f"alias_{int(alias)}"
        return f"part_{fallback_idx}"

    out["participant_detail_key"]         = [make_key(r, i) for i, r in out.iterrows()]
    out["session_manifest_detail_path"]   = ""
    out["linked_timegrid_detail_path"]    = ""

    has_manifest  = not manifest_df.empty  and "health_code" in manifest_df.columns
    has_timegrid  = not timegrid_df.empty  and "health_code" in timegrid_df.columns

    total = len(out)
    for i, (idx, row) in enumerate(out.iterrows(), 1):
        hc  = str(row["health_code"])
        key = str(row["participant_detail_key"])
        print(f"  [{i}/{total}] exporting detail for key={key}")

        if has_manifest:
            sub = manifest_df[manifest_df["health_code"].astype(str).eq(hc)].copy()
            if not sub.empty:
                if "health_code_masked" not in sub.columns:
                    sub["health_code_masked"] = sub["health_code"].apply(mask_health_code)
                sub = sub.drop(columns=["health_code"], errors="ignore")
                fname = f"{key}_session_manifest.csv"
                sub.to_csv(detail_backend / fname, index=False)
                shutil.copy2(detail_backend / fname, detail_frontend / fname)
                out.at[idx, "session_manifest_detail_path"] = (
                    f"/dashboard_exports/participant_details/{fname}"
                )

        if has_timegrid:
            sub = timegrid_df[timegrid_df["health_code"].astype(str).eq(hc)].copy()
            if not sub.empty:
                if "health_code_masked" not in sub.columns:
                    sub["health_code_masked"] = sub["health_code"].apply(mask_health_code)
                sub = sub.drop(columns=["health_code"], errors="ignore")
                fname = f"{key}_linked_timegrid.csv"
                sub.to_csv(detail_backend / fname, index=False)
                shutil.copy2(detail_backend / fname, detail_frontend / fname)
                out.at[idx, "linked_timegrid_detail_path"] = (
                    f"/dashboard_exports/participant_details/{fname}"
                )

    return out


def copy_exports_to_frontend(
    out_dir: str | Path,
    frontend_dir: str | Path | None = None,
    filenames: list[str] | None = None,
) -> list[Path]:
    """Copy CSV exports from out_dir to the Next.js public directory.

    Files are placed under frontend/public/dashboard_exports/ so that
    Next.js can serve them at /dashboard_exports/<filename>.
    Returns list of destination paths that were successfully copied.
    """
    from commonconst import DASHBOARD_FRONTEND_FILES

    out_dir = Path(out_dir)
    if frontend_dir is None:
        frontend_dir = FRONTEND_DASHBOARD_EXPORT_DIR
    frontend_dir = ensure_dir(frontend_dir)

    targets = filenames if filenames else DASHBOARD_FRONTEND_FILES
    copied: list[Path] = []
    for fname in targets:
        src = out_dir / fname
        dst = frontend_dir / fname
        if src.exists():
            shutil.copy2(src, dst)
            copied.append(dst)
            print(f"  copied {fname} → {dst}")
        else:
            print(f"  skipped (not found): {src}")
    return copied

# ---------------------------------------------------------------------
# ID linkage and REDCap outcomes
# ---------------------------------------------------------------------

def load_participant_ids(xlsx_path: str | Path) -> pd.DataFrame:
    """Load and normalize the BiAffect ID linkage sheet."""
    df = pd.read_excel(xlsx_path).dropna(how="all").copy()
    df = df.rename(columns=ID_RENAME_MAP)

    missing = set(ID_REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"ID file missing required columns: {sorted(missing)}")

    df["record_id"] = pd.to_numeric(df["record_id"], errors="coerce").astype("Int64")
    df["alias"] = pd.to_numeric(df["alias"], errors="coerce").astype("Int64")
    df["health_code"] = df["health_code"].astype("string").str.strip()
    df = df[
        df["health_code"].notna()
        & df["health_code"].ne("")
        & df["health_code"].str.lower().ne("nan")
        & df["health_code"].str.lower().ne("never assigned")
    ].copy()
    df["device_type"] = df["phone_type_raw"].apply(normalize_phone_type)
    df["record_id_str"] = df["record_id"].astype("Int64").astype(str).str.replace("<NA>", "", regex=False).str.zfill(6)
    return df.drop_duplicates(subset=["health_code"], keep="first").reset_index(drop=True)


def summarize_ids(ids_df: pd.DataFrame) -> dict[str, int]:
    return {
        "n_valid_rows": int(len(ids_df)),
        "n_unique_health_codes": int(ids_df["health_code"].nunique()),
        "n_unique_record_ids": int(ids_df["record_id"].nunique()),
        "n_unique_aliases": int(ids_df["alias"].nunique()),
        "n_duplicate_health_codes": int(ids_df["health_code"].duplicated().sum()),
    }


def infer_redcap_date_column(report: pd.DataFrame) -> str:
    preferred = [
        "survey_timestamp",
        "date",
        "timestamp",
        "biaffect_survey_v1_timestamp",
        "biaffect_survey_v2_timestamp",
        "biaffect_survey_v3_timestamp",
        "biaffect_survey_v4_timestamp",
        "biaffect_survey_v5_timestamp",
        "biaffect_survey_v6_timestamp",
    ]
    found = _first_existing_column(report, preferred)
    if found:
        return found
    date_cols = [c for c in report.columns if "timestamp" in c.lower() or "date" in c.lower()]
    if not date_cols:
        raise ValueError("Could not find any date/timestamp column in the REDCap report.")
    return date_cols[0]


def build_daily_outcomes(report_csv: str | Path, ids_df: pd.DataFrame) -> pd.DataFrame:
    """Build a participant-linked daily outcome table from REDCap export."""
    report = pd.read_csv(report_csv)
    report.columns = [c.strip() for c in report.columns]

    if REDCAP_SURVEY_IDENTIFIER not in report.columns:
        raise ValueError(f"Expected REDCap column '{REDCAP_SURVEY_IDENTIFIER}' was not found.")

    report[REDCAP_SURVEY_IDENTIFIER] = report[REDCAP_SURVEY_IDENTIFIER].astype("string")

    if "report_record_id" in report.columns:
        report["report_record_id"] = pd.to_numeric(report["report_record_id"], errors="coerce").astype("Int64")
        for report_record_id, fixed_identifier in KNOWN_REDCAP_ID_FIXES.items():
            report.loc[report["report_record_id"].eq(report_record_id), REDCAP_SURVEY_IDENTIFIER] = fixed_identifier

    date_col = infer_redcap_date_column(report)
    report["date"] = normalize_date_series(report[date_col])
    report["survey_timestamp_source_col"] = date_col
    report["survey_timestamp"] = pd.to_datetime(report[date_col], errors="coerce")

    report["redcap_id_str"] = (
        report[REDCAP_SURVEY_IDENTIFIER]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(6)
    )

    anna = ids_df.copy()
    if "record_id_str" not in anna.columns:
        anna["record_id_str"] = anna["record_id"].astype("Int64").astype(str).str.replace("<NA>", "", regex=False).str.zfill(6)

    out = report.merge(
        anna[["record_id", "alias", "health_code", "device_type", "record_id_str"]],
        left_on="redcap_id_str",
        right_on="record_id_str",
        how="left",
    )

    binary_candidates = [
        c for c in out.columns
        if "suic" in c.lower() and any(k in c.lower() for k in OUTCOME_BINARY_CANDIDATE_KEYWORDS)
    ]
    intensity_candidates = [
        c for c in out.columns
        if "suic" in c.lower() and any(k in c.lower() for k in OUTCOME_INTENSITY_CANDIDATE_KEYWORDS)
    ]
    selfharm_candidates = [c for c in out.columns if "harm" in c.lower()]

    out["daily_suicidality_binary"] = standardize_binary(out[binary_candidates[0]]) if binary_candidates else np.nan
    out["suicidality_0_9"] = robust_numeric(out[intensity_candidates[0]]) if intensity_candidates else np.nan
    out["self_harm_binary"] = standardize_binary(out[selfharm_candidates[0]]) if selfharm_candidates else np.nan
    out["has_redcap_outcome"] = out["health_code"].notna().astype(int)

    return out


def load_self_report(report_csv: str | Path, ids_df: pd.DataFrame) -> pd.DataFrame:
    """Load report.csv and link each row to a health_code via the participant ID file.

    Linkage path: report.csv[redcap_survey_identifier] → ids_df[record_id_str] → health_code.
    Strictly health_code-based after join; no downstream code should re-join on record_id.
    Returns a DataFrame with a populated `health_code` column and a `health_code_masked` column.
    Falls back gracefully if the report file is missing or the identifier column is absent.
    """
    report_path = Path(report_csv)
    if not report_path.exists():
        print(f"Self-report file not found, continuing without it: {report_path}")
        return pd.DataFrame()
    try:
        df = build_daily_outcomes(report_path, ids_df)
    except Exception as exc:
        print(f"WARNING: Could not load self-report data: {exc}")
        return pd.DataFrame()
    # Add masked health_code column for safe logging/export.
    if "health_code" in df.columns:
        df["health_code_masked"] = df["health_code"].apply(
            lambda hc: mask_health_code(hc) if pd.notna(hc) else "***"
        )
    return df


def build_participant_index(ids_df: pd.DataFrame, outcomes_df: pd.DataFrame | None = None) -> pd.DataFrame:
    out = ids_df.copy()
    if outcomes_df is None or outcomes_df.empty:
        out["has_redcap_outcome"] = 0
        out["redcap_n_days"] = 0
        out["redcap_first_date"] = pd.NaT
        out["redcap_last_date"] = pd.NaT
        return out

    tmp = outcomes_df.dropna(subset=["health_code"]).copy()
    if tmp.empty:
        out["has_redcap_outcome"] = 0
        out["redcap_n_days"] = 0
        out["redcap_first_date"] = pd.NaT
        out["redcap_last_date"] = pd.NaT
        return out

    summary = (
        tmp.groupby("health_code", dropna=False)
        .agg(
            redcap_n_rows=("date", "size"),
            redcap_n_days=("date", "nunique"),
            redcap_first_date=("date", "min"),
            redcap_last_date=("date", "max"),
        )
        .reset_index()
    )
    summary["has_redcap_outcome"] = summary["redcap_n_rows"].gt(0).astype(int)
    out = out.merge(summary, on="health_code", how="left")
    for c in ["redcap_n_rows", "redcap_n_days", "has_redcap_outcome"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype(int)
    return out


def build_healthcode_linkage(
    ids_df: pd.DataFrame,
    self_report_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build participant index linked strictly by health_code.

    Aggregates self-report statistics per health_code and left-joins to the
    participant ID table. Adds health_code_masked for safe display.
    Does NOT contact Synapse; has_synapse/synapse_sessions are added later
    by merging with the presence summary.
    """
    out = ids_df.copy()
    out["health_code_masked"] = out["health_code"].apply(mask_health_code)
    # Synapse columns — populated later after presence check.
    out["has_synapse"] = False
    out["synapse_sessions"] = 0
    out["first_synapse_date"] = pd.NaT
    out["last_synapse_date"] = pd.NaT
    out["synapse_source_table"] = pd.NA

    if self_report_df is None or self_report_df.empty:
        out["has_self_report"] = False
        out["self_report_rows"] = 0
        out["self_report_days"] = 0
        out["first_self_report_date"] = pd.NaT
        out["last_self_report_date"] = pd.NaT
        return out

    tmp = self_report_df.dropna(subset=["health_code"]).copy()
    tmp["date"] = pd.to_datetime(tmp.get("date"), errors="coerce").dt.normalize()

    if tmp.empty:
        out["has_self_report"] = False
        out["self_report_rows"] = 0
        out["self_report_days"] = 0
        out["first_self_report_date"] = pd.NaT
        out["last_self_report_date"] = pd.NaT
        return out

    summary = (
        tmp.groupby("health_code", dropna=False)
        .agg(
            self_report_rows=("date", "size"),
            self_report_days=("date", "nunique"),
            first_self_report_date=("date", "min"),
            last_self_report_date=("date", "max"),
        )
        .reset_index()
    )
    summary["has_self_report"] = summary["self_report_rows"].gt(0)

    out = out.merge(summary, on="health_code", how="left")
    out["has_self_report"] = out["has_self_report"].fillna(False)
    for c in ["self_report_rows", "self_report_days"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype(int)
    return out


def merge_synapse_into_index(
    participant_df: pd.DataFrame,
    presence_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge Synapse presence statistics into the participant index by health_code."""
    if presence_df.empty:
        return participant_df.copy()

    matched = presence_df[presence_df["status"].astype(str).str.lower().eq("matched")].copy()
    if matched.empty:
        return participant_df.copy()

    syn_stats = (
        matched.groupby("health_code", dropna=False)
        .agg(
            synapse_sessions=("match_count", "sum"),
            synapse_source_table=("source_label", "first"),
        )
        .reset_index()
    )
    syn_stats["has_synapse"] = True

    # session date range comes from the manifest if available; leave NaT for now
    syn_stats["first_synapse_date"] = pd.NaT
    syn_stats["last_synapse_date"] = pd.NaT

    out = participant_df.copy()
    # Drop old synapse columns before merge to avoid duplicates
    for col in ["has_synapse", "synapse_sessions", "synapse_source_table",
                "first_synapse_date", "last_synapse_date"]:
        if col in out.columns:
            out = out.drop(columns=[col])

    out = out.merge(syn_stats, on="health_code", how="left")
    out["has_synapse"] = out["has_synapse"].fillna(False)
    out["synapse_sessions"] = pd.to_numeric(out["synapse_sessions"], errors="coerce").fillna(0).astype(int)
    return out


def compute_synapse_date_range(manifest_df: pd.DataFrame) -> pd.DataFrame:
    """Compute first and last Synapse session date per health_code from the manifest.

    Returns a DataFrame with columns:
      health_code, first_synapse_date (str YYYY-MM-DD), last_synapse_date (str YYYY-MM-DD)

    Tries these date columns in priority order:
      uploadDate, createdOn, session_date, startedOn, startTime, session_start,
      timestamp, created_on, created_at

    Prints a warning listing available columns if none of the candidates exist.
    """
    if manifest_df.empty:
        return pd.DataFrame(columns=["health_code", "first_synapse_date", "last_synapse_date"])

    # normalize_manifest_dates already resolves uploadDate and createdOn into session_date
    df = normalize_manifest_dates(manifest_df.copy())

    # Priority: session_date (resolved above), then raw candidates
    date_candidates = [
        "session_date", "uploadDate_dt", "createdOn_dt",
        "startedOn", "startTime", "session_start",
        "timestamp", "created_on", "created_at",
    ]
    date_col: str | None = None
    for cand in date_candidates:
        if cand in df.columns:
            parsed = pd.to_datetime(df[cand], errors="coerce")
            if parsed.notna().any():
                date_col = cand
                df["_synapse_date"] = parsed.dt.normalize()
                break

    if date_col is None:
        available = ", ".join(str(c) for c in manifest_df.columns.tolist())
        print(f"WARNING: No usable date column found in manifest. Available: {available}")
        return pd.DataFrame(columns=["health_code", "first_synapse_date", "last_synapse_date"])

    date_range = (
        df.dropna(subset=["health_code", "_synapse_date"])
        .groupby("health_code", dropna=False)
        .agg(
            first_synapse_date=("_synapse_date", "min"),
            last_synapse_date=("_synapse_date", "max"),
        )
        .reset_index()
    )
    date_range["first_synapse_date"] = pd.to_datetime(
        date_range["first_synapse_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    date_range["last_synapse_date"] = pd.to_datetime(
        date_range["last_synapse_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    return date_range


def apply_participant_filters(
    participant_df: pd.DataFrame,
    record_ids: list[int] | None = None,
    aliases: list[int] | None = None,
    health_codes: list[str] | None = None,
    device_type: str | None = None,
    require_redcap: bool = False,
    require_self_report: bool = False,
    require_synapse: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    max_rows_per_participant: int = 0,
) -> pd.DataFrame:
    """Filter participants. All ID/metadata filters applied after linkage is built."""
    df = participant_df.copy()

    if record_ids:
        df = df[df["record_id"].isin(record_ids)]
    if aliases:
        df = df[df["alias"].isin(aliases)]
    if health_codes:
        hc = {str(x).strip() for x in health_codes}
        df = df[df["health_code"].astype(str).str.strip().isin(hc)]
    if device_type and device_type.lower() != "all":
        df = df[df["device_type"].eq(device_type.lower())]

    # require_redcap and require_self_report are equivalent — check whichever column exists.
    if require_redcap or require_self_report:
        if "has_self_report" in df.columns:
            df = df[df["has_self_report"].eq(True)]
        elif "has_redcap_outcome" in df.columns:
            df = df[df["has_redcap_outcome"].eq(1)]

    if require_synapse and "has_synapse" in df.columns:
        df = df[df["has_synapse"].eq(True)]

    if start_date and "first_self_report_date" in df.columns:
        start_dt = pd.to_datetime(start_date, errors="coerce")
        if pd.notna(start_dt):
            df = df[
                pd.to_datetime(df["last_self_report_date"], errors="coerce").ge(start_dt)
                | pd.to_datetime(df["last_synapse_date"], errors="coerce").ge(start_dt)
            ]
    if end_date and "last_self_report_date" in df.columns:
        end_dt = pd.to_datetime(end_date, errors="coerce")
        if pd.notna(end_dt):
            df = df[
                pd.to_datetime(df["first_self_report_date"], errors="coerce").le(end_dt)
                | pd.to_datetime(df["first_synapse_date"], errors="coerce").le(end_dt)
            ]

    if max_rows_per_participant and max_rows_per_participant > 0:
        df = df.head(max_rows_per_participant)

    return df.reset_index(drop=True)

# ---------------------------------------------------------------------
# Synapse presence and manifest logic
# ---------------------------------------------------------------------

def candidate_healthcodes(hc: str) -> list[str]:
    hc = str(hc).strip()
    candidates = [hc]
    candidates.append(hc[1:] if hc.startswith("-") else "-" + hc)
    out: list[str] = []
    for x in candidates:
        if x and x not in out:
            out.append(x)
    return out


def get_synapse_client():
    try:
        import synapseclient
    except ImportError as exc:  # pragma: no cover
        raise ImportError("Install synapseclient first: pip install synapseclient") from exc

    token = os.environ.get("SYNAPSE_AUTH_TOKEN")
    if not token:
        raise ValueError("SYNAPSE_AUTH_TOKEN is not set in environment or .env")
    syn = synapseclient.Synapse()
    syn.login(authToken=token)
    return syn


def safe_match_healthcode(syn: Any, table_id: str, hc: str) -> dict[str, Any]:
    tried = []
    for hc_try in candidate_healthcodes(hc):
        q = f"SELECT COUNT(*) FROM {table_id} WHERE {SYNAPSE_HEALTHCODE_COLUMN} = '{sql_escape(hc_try)}'"
        try:
            count = int(syn.tableQuery(q).asDataFrame().iloc[0, 0])
            tried.append((hc_try, count))
            if count > 0:
                return {"matched_healthcode": hc_try, "count": count, "tried": tried, "error": None}
        except Exception as e:
            return {"matched_healthcode": None, "count": None, "tried": tried, "error": str(e)}
    return {"matched_healthcode": None, "count": 0, "tried": tried, "error": None}


def build_presence_summary(syn: Any, participant_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, row in participant_df.iterrows():
        found = False
        tried_all = []
        first_error = None
        options = SYNAPSE_TABLE_OPTIONS.get(row.get("device_type", "unknown"), SYNAPSE_TABLE_OPTIONS["unknown"])

        for table_id, source_label in options:
            res = safe_match_healthcode(syn, table_id, row["health_code"])
            tried_all.extend([(table_id, source_label, x[0], x[1]) for x in res.get("tried", [])])
            first_error = first_error or res.get("error")
            if res.get("count") and res["count"] > 0:
                found = True
                rows.append({
                    **{k: row.get(k) for k in ["record_id", "alias", "phone_type_raw", "device_type", "health_code"] if k in row.index},
                    "input_healthcode": row.get("health_code"),
                    "matched_healthcode": res["matched_healthcode"],
                    "target_table_id": table_id,
                    "source_table_id": table_id,
                    "source_label": source_label,
                    "match_count": res["count"],
                    "status": "matched",
                    "tried_all_tables": json.dumps(tried_all),
                    "error": res.get("error"),
                })

        if not found:
            rows.append({
                **{k: row.get(k) for k in ["record_id", "alias", "phone_type_raw", "device_type", "health_code"] if k in row.index},
                "input_healthcode": row.get("health_code"),
                "matched_healthcode": None,
                "target_table_id": None,
                "source_table_id": None,
                "source_label": None,
                "match_count": 0,
                "status": "error" if first_error else "not_found",
                "tried_all_tables": json.dumps(tried_all),
                "error": first_error,
            })

    return pd.DataFrame(rows)


def select_synapse_columns(table_id: str) -> str:
    return ",\n        ".join(SYNAPSE_SESSION_COLUMNS)


def fetch_manifest_rows_for_healthcode(syn: Any, table_id: str, matched_hc: str) -> pd.DataFrame:
    query = f"""
    SELECT
        {select_synapse_columns(table_id)}
    FROM {table_id}
    WHERE {SYNAPSE_HEALTHCODE_COLUMN} = '{sql_escape(matched_hc)}'
    """
    return syn.tableQuery(query).asDataFrame()


def normalize_manifest_dates(manifest_df: pd.DataFrame) -> pd.DataFrame:
    """Parse Synapse manifest date columns into consistent datetime columns.

    createdOn is a Unix millisecond timestamp (e.g. 1748640572354). Standard
    pd.to_datetime() treats bare integers as nanoseconds and produces 1970-01-01.
    We use parse_biaffect_timestamp() which detects ms vs s automatically.

    uploadDate is a clean "YYYY-MM-DD" string — parsed normally and preferred
    for session_date because it is always the calendar date of the session.
    """
    df = manifest_df.copy()
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].fillna("").astype(str).str.strip()

    # createdOn: Unix ms timestamp → use ms-aware parser
    if "createdOn" in df.columns:
        df["createdOn_dt"] = parse_biaffect_timestamp(
            pd.to_numeric(df["createdOn"].replace("", np.nan), errors="coerce")
        )
    else:
        df["createdOn_dt"] = pd.NaT

    # uploadDate: standard "YYYY-MM-DD" or ISO string → direct parse
    df["uploadDate_dt"] = pd.to_datetime(
        df.get("uploadDate", pd.Series(dtype="object")), errors="coerce"
    )

    # Prefer uploadDate (clean calendar date) over createdOn (raw epoch ms)
    df["session_start_dt"] = df["uploadDate_dt"].combine_first(df["createdOn_dt"])
    df["session_date"] = df["session_start_dt"].dt.normalize()
    return df


def build_filtered_session_manifest(syn: Any, presence_df: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    matched = presence_df[presence_df["status"].astype(str).str.lower().eq("matched")].copy()

    for _, row in matched.iterrows():
        table_id = row.get("target_table_id") or row.get("source_table_id")
        matched_hc = row.get("matched_healthcode") or row.get("health_code")
        try:
            df = fetch_manifest_rows_for_healthcode(syn, str(table_id), str(matched_hc))
            if df.empty:
                continue
            for col, val in {
                "record_id": row.get("record_id"),
                "alias": row.get("alias"),
                "phone_type_raw": row.get("phone_type_raw"),
                "device_type": row.get("device_type"),
                "input_healthcode": row.get("input_healthcode"),
                "matched_healthcode": matched_hc,
                "health_code": row.get("health_code"),
                "source_table_id": table_id,
                "target_table_id": table_id,
                "source_label": row.get("source_label"),
            }.items():
                df[col] = val
            frames.append(df)
        except Exception as e:
            print(f"ERROR building manifest for health_code={matched_hc}: {e}")

    if not frames:
        return pd.DataFrame()
    return normalize_manifest_dates(pd.concat(frames, ignore_index=True))


def filter_manifest_by_date(
    manifest_df: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    if manifest_df.empty:
        return manifest_df.copy()
    df = normalize_manifest_dates(manifest_df)
    if start_date:
        df = df[df["session_date"].ge(pd.to_datetime(start_date).normalize())]
    if end_date:
        df = df[df["session_date"].le(pd.to_datetime(end_date).normalize())]
    return df.reset_index(drop=True)


def deduplicate_and_cap_manifest(
    manifest_df: pd.DataFrame,
    max_rows_per_participant: int = DEFAULT_MAX_ROWS_PER_PARTICIPANT,
    sort_by: str = DEFAULT_SORT_MANIFEST_BY,
    deduplicate_by_recordid: bool = DEFAULT_DEDUPLICATE_BY_RECORDID,
) -> pd.DataFrame:
    if manifest_df.empty:
        return manifest_df.copy()
    df = normalize_manifest_dates(manifest_df)
    sort_col = "uploadDate_dt" if sort_by == "uploadDate" and "uploadDate_dt" in df.columns else "createdOn_dt"
    if deduplicate_by_recordid and "recordId" in df.columns:
        df = df.sort_values(["record_id", sort_col, "recordId"], na_position="last")
        df = df.drop_duplicates(subset=["record_id", "recordId"], keep="first")
    df = df.sort_values(["record_id", sort_col, "recordId"], na_position="last")
    df["row_num_within_participant"] = df.groupby("record_id", dropna=False).cumcount() + 1
    if max_rows_per_participant and max_rows_per_participant > 0:
        df = df[df["row_num_within_participant"] <= max_rows_per_participant].copy()
    return df.reset_index(drop=True)



def query_single_record(syn: Any, table_id: str, record_id: str):
    query = f"""
    SELECT
        recordId,
        "Session.json.keylogs",
        "Session.json.accelerations",
        rawData,
        rawMetadata
    FROM {table_id}
    WHERE recordId = '{sql_escape(record_id)}'
    """
    return syn.tableQuery(query)

def unzip_downloads_in_dir(download_dir: str | Path, extract_dir: str | Path) -> None:
    download_dir = Path(download_dir)
    extract_dir = ensure_dir(extract_dir)
    for root, _, files in os.walk(download_dir):
        for filename in files:
            if not filename.lower().endswith(".zip"):
                continue
            zip_path = Path(root) / filename
            rel_root = Path(root).relative_to(download_dir)
            target_dir = extract_dir / rel_root / filename.rsplit(".", 1)[0]
            ensure_dir(target_dir)
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(target_dir)
                print(f"extracted: {zip_path} -> {target_dir}")
            except Exception as e:
                print(f"could not extract {zip_path}: {e}")


def download_from_manifest(
    syn: Any,
    manifest_df: pd.DataFrame,
    downloads_root: str | Path,
    extracted_root: str | Path,
) -> pd.DataFrame:
    downloads_root = ensure_dir(downloads_root)
    extracted_root = ensure_dir(extracted_root)
    logs: list[dict[str, Any]] = []
    total = len(manifest_df)

    for idx, row in manifest_df.reset_index(drop=True).iterrows():
        source_label = safe_name(row.get("source_label", "unknown_source"))
        matched_hc = safe_name(row.get("matched_healthcode", row.get("healthCode", "unknown_hc")))
        record_id = str(row.get("recordId", "")).strip()
        table_id = str(row.get("source_table_id", row.get("target_table_id", ""))).strip()

        record_download_dir = downloads_root / source_label / matched_hc / record_id
        record_extract_dir = extracted_root / source_label / matched_hc / record_id
        ensure_dir(record_download_dir)
        ensure_dir(record_extract_dir)

        print(f"[{idx + 1}/{total}] downloading recordId={record_id} | participant={row.get('record_id')}")
        try:
            results = query_single_record(syn=syn, table_id=table_id, record_id=record_id)
            file_map = syn.downloadTableColumns(results, SYNAPSE_FILE_COLUMNS, downloadLocation=str(record_download_dir))
            downloaded_paths = []
            if isinstance(file_map, dict):
                downloaded_paths = [str(p) for p in file_map.values() if p]
            unzip_downloads_in_dir(record_download_dir, record_extract_dir)
            logs.append({
                "record_id": row.get("record_id"),
                "alias": row.get("alias"),
                "source_label": row.get("source_label"),
                "matched_healthcode": row.get("matched_healthcode"),
                "recordId": record_id,
                "source_table_id": table_id,
                "row_num_within_participant": row.get("row_num_within_participant"),
                "status": "downloaded",
                "download_dir": str(record_download_dir),
                "extract_dir": str(record_extract_dir),
                "n_files_downloaded": len(downloaded_paths),
                "downloaded_paths": " | ".join(downloaded_paths),
                "error": "",
            })
        except Exception as e:
            logs.append({
                "record_id": row.get("record_id"),
                "alias": row.get("alias"),
                "source_label": row.get("source_label"),
                "matched_healthcode": row.get("matched_healthcode"),
                "recordId": record_id,
                "source_table_id": table_id,
                "row_num_within_participant": row.get("row_num_within_participant"),
                "status": "error",
                "download_dir": str(record_download_dir),
                "extract_dir": str(record_extract_dir),
                "n_files_downloaded": 0,
                "downloaded_paths": "",
                "error": str(e),
            })
    return pd.DataFrame(logs)

# ---------------------------------------------------------------------
# Raw Session.json parser and feature aggregation
# ---------------------------------------------------------------------

def safe_load_json(path: Path) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1") as f:
            return json.load(f)
    except Exception as e:
        print(f"Could not load JSON {path}: {e}")
        return None


def recursive_find_key(obj: Any, target_key: str) -> list[Any]:
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == target_key:
                found.append(v)
            found.extend(recursive_find_key(v, target_key))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(recursive_find_key(item, target_key))
    return found


def flatten_list_values(values: list[Any]) -> list[dict]:
    rows: list[dict] = []
    for value in values:
        if isinstance(value, list):
            rows.extend([x for x in value if isinstance(x, dict)])
        elif isinstance(value, dict):
            rows.append(value)
    return rows


def record_id_from_session_path(path: Path) -> str:
    parts = list(path.parts)
    for part in reversed(parts):
        if re.fullmatch(r"\d+", str(part)):
            return str(part)
    return path.parent.name


def participant_from_session_path(path: Path) -> str | None:
    for part in path.parts:
        if str(part).startswith("participant_"):
            return str(part).replace("participant_", "", 1)
    return None


def source_label_from_session_path(path: Path) -> str | None:
    for part in path.parts:
        if "iphone" in str(part).lower() or "android" in str(part).lower():
            return str(part)
    return None


def parse_biaffect_timestamp(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().mean() > 0.5:
        # BiAffect timestamps may appear in milliseconds or seconds.
        median_val = numeric.dropna().median() if numeric.notna().any() else np.nan
        unit = "ms" if pd.notna(median_val) and median_val > 10_000_000_000 else "s"
        return pd.to_datetime(numeric, unit=unit, errors="coerce")
    return pd.to_datetime(series, errors="coerce")


def add_time_bins(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    out = df.copy()
    if timestamp_col not in out.columns:
        return pd.DataFrame()
    out["timestamp_parsed"] = parse_biaffect_timestamp(out[timestamp_col])
    out = out[out["timestamp_parsed"].notna()].copy()
    if out.empty:
        return out
    out["date"] = out["timestamp_parsed"].dt.normalize()
    out["bin_index"] = ((out["timestamp_parsed"].dt.hour * 60 + out["timestamp_parsed"].dt.minute) // BIN_MINUTES).astype(int)
    out["bin_start"] = out["date"] + pd.to_timedelta(out["bin_index"] * BIN_MINUTES, unit="m")
    out["bin_end"] = out["bin_start"] + pd.to_timedelta(BIN_MINUTES, unit="m")
    return out


def parse_session_files(extracted_root: str | Path = EXTRACTED_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    extracted_root = Path(extracted_root)
    session_files = sorted(extracted_root.rglob("Session.json"))
    keylog_rows: list[dict] = []
    accel_rows: list[dict] = []

    for path in session_files:
        data = safe_load_json(path)
        if data is None:
            continue
        record_id = record_id_from_session_path(path)
        participant = participant_from_session_path(path)
        source_label = source_label_from_session_path(path)

        keylogs = flatten_list_values(recursive_find_key(data, "keylogs"))
        accelerations = flatten_list_values(recursive_find_key(data, "accelerations"))

        if not keylogs and isinstance(data, list):
            if data and isinstance(data[0], dict) and ("value" in data[0] or "timestamp" in data[0] or "duration" in data[0]):
                keylogs = [x for x in data if isinstance(x, dict)]

        for row in keylogs:
            r = dict(row)
            r["recordId"] = record_id
            r["participant"] = participant
            r["source_label"] = source_label
            r["source_file"] = str(path)
            keylog_rows.append(r)

        for row in accelerations:
            r = dict(row)
            r["recordId"] = record_id
            r["participant"] = participant
            r["source_label"] = source_label
            r["source_file"] = str(path)
            accel_rows.append(r)

    return pd.DataFrame(keylog_rows), pd.DataFrame(accel_rows)


def build_keylog_bins(keylogs: pd.DataFrame) -> pd.DataFrame:
    if keylogs.empty:
        return pd.DataFrame()
    keylogs = add_time_bins(keylogs, "timestamp")
    if keylogs.empty:
        return pd.DataFrame()

    if "value" not in keylogs.columns:
        keylogs["value"] = pd.NA
    for raw_col, num_col in [
        ("duration", "duration_num"),
        ("distanceFromCenter", "distanceFromCenter_num"),
        ("distanceFromPrevious", "distanceFromPrevious_num"),
    ]:
        keylogs[num_col] = pd.to_numeric(keylogs[raw_col], errors="coerce") if raw_col in keylogs.columns else np.nan

    value_lower = keylogs["value"].astype("string").str.lower()
    keylogs["is_backspace"] = value_lower.eq("backspace")
    keylogs["is_autocorrection"] = value_lower.eq("autocorrection")
    keylogs["is_suggestion"] = value_lower.eq("suggestion")
    keylogs["is_alphanum"] = value_lower.eq("alphanum")
    keylogs["is_punctuation"] = value_lower.eq("punctuation")

    gcols = ["participant", "date", "bin_index", "bin_start", "bin_end"]
    out = (
        keylogs.groupby(gcols, dropna=False)
        .agg(
            n_keylogs=("value", "size"),
            n_backspace=("is_backspace", "sum"),
            n_autocorrection=("is_autocorrection", "sum"),
            n_suggestion=("is_suggestion", "sum"),
            n_alphanum=("is_alphanum", "sum"),
            n_punctuation=("is_punctuation", "sum"),
            key_duration_mean=("duration_num", "mean"),
            key_duration_median=("duration_num", "median"),
            key_duration_sd=("duration_num", "std"),
            distance_from_center_mean=("distanceFromCenter_num", "mean"),
            distance_from_previous_mean=("distanceFromPrevious_num", "mean"),
            n_sessions_in_bin=("recordId", "nunique"),
        )
        .reset_index()
    )
    out["typing_intensity"] = out["n_keylogs"] / BIN_MINUTES
    out["backspace_ratio"] = out["n_backspace"] / out["n_keylogs"]
    out["autocorrect_rate"] = out["n_autocorrection"] / out["n_keylogs"]
    out["suggestion_rate"] = out["n_suggestion"] / out["n_keylogs"]
    out["alphanum_rate"] = out["n_alphanum"] / out["n_keylogs"]
    out["punctuation_rate"] = out["n_punctuation"] / out["n_keylogs"]
    return out.sort_values(["participant", "date", "bin_index"]).reset_index(drop=True)


def build_acceleration_bins(accels: pd.DataFrame) -> pd.DataFrame:
    if accels.empty:
        return pd.DataFrame()
    timestamp_candidates = [c for c in ["timestamp", "time", "createdOn", "timestamp_parsed"] if c in accels.columns]
    if not timestamp_candidates:
        return pd.DataFrame()
    accels = add_time_bins(accels, timestamp_candidates[0])
    if accels.empty:
        return pd.DataFrame()

    for c in ["x", "y", "z"]:
        accels[c] = pd.to_numeric(accels[c], errors="coerce") if c in accels.columns else np.nan
    accels["accel_magnitude"] = (accels["x"] ** 2 + accels["y"] ** 2 + accels["z"] ** 2) ** 0.5

    gcols = ["participant", "date", "bin_index", "bin_start", "bin_end"]
    return (
        accels.groupby(gcols, dropna=False)
        .agg(
            n_accelerations=("accel_magnitude", "size"),
            accelerometer_activity=("accel_magnitude", "mean"),
            accelerometer_activity_sd=("accel_magnitude", "std"),
            accel_x_mean=("x", "mean"),
            accel_y_mean=("y", "mean"),
            accel_z_mean=("z", "mean"),
            n_accel_sessions_in_bin=("recordId", "nunique"),
        )
        .reset_index()
        .sort_values(["participant", "date", "bin_index"])
        .reset_index(drop=True)
    )


def build_observed_metric_bins(keylogs: pd.DataFrame, accels: pd.DataFrame) -> pd.DataFrame:
    key_bins = build_keylog_bins(keylogs)
    accel_bins = build_acceleration_bins(accels)
    if key_bins.empty and accel_bins.empty:
        return pd.DataFrame()
    if key_bins.empty:
        return accel_bins
    if accel_bins.empty:
        return key_bins
    return key_bins.merge(
        accel_bins,
        on=["participant", "date", "bin_index", "bin_start", "bin_end"],
        how="outer",
    ).sort_values(["participant", "date", "bin_index"]).reset_index(drop=True)

def build_biaffect_metric_bins(
    keylogs: pd.DataFrame,
    accels: pd.DataFrame,
    participant_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build participant-labeled 15-min metric bins with standardized column names.

    Output columns:
      health_code, health_code_masked, record_id, alias, date,
      bin_index, bin_start, bin_end,
      observed_minutes,           # 15 if any data in bin, else 0
      keyboard_session_count,     # distinct Synapse recordIds in bin
      typing_event_count,         # total keylog events
      backspace_count,
      backspace_ratio,
      mean_inter_key_interval,    # key_duration_mean (ms)
      median_inter_key_interval,  # key_duration_median (ms)
      accelerometer_activity_mean,
      accelerometer_activity_sd,
      data_coverage_pct           # 1.0 if observed, 0.0 if not (bin-level)

    Columns that cannot be computed from current data are included as null
    with a code comment below.
    """
    base = build_observed_metric_bins(keylogs, accels)
    if base.empty:
        return pd.DataFrame()

    # Build lookup: participant label (record_id string) → participant row
    p_lookup: dict[str, Any] = {}
    for _, row in participant_df.iterrows():
        p_lookup[str(row.get("record_id", ""))] = row

    def _get(label: str, field: str) -> Any:
        row = p_lookup.get(str(label))
        return row.get(field) if row is not None else None

    out = base.copy()
    out["record_id"] = out["participant"].apply(lambda p: _get(p, "record_id"))
    out["alias"] = out["participant"].apply(lambda p: _get(p, "alias"))
    out["health_code"] = out["participant"].apply(lambda p: _get(p, "health_code"))
    out["health_code_masked"] = out["health_code"].apply(
        lambda hc: mask_health_code(hc) if pd.notna(hc) else "***"
    )

    col_map = {
        "n_keylogs":          "typing_event_count",
        "n_backspace":        "backspace_count",
        "n_sessions_in_bin":  "keyboard_session_count",
        "key_duration_mean":  "mean_inter_key_interval",
        "key_duration_median":"median_inter_key_interval",
        "accelerometer_activity":    "accelerometer_activity_mean",
        "accelerometer_activity_sd": "accelerometer_activity_sd",
    }
    out = out.rename(columns={k: v for k, v in col_map.items() if k in out.columns})

    has_key = out.get("typing_event_count", pd.Series(0, index=out.index)).fillna(0).gt(0)
    has_acc = out.get("n_accelerations", pd.Series(0, index=out.index)).fillna(0).gt(0)
    out["observed_minutes"] = (has_key | has_acc).astype(int) * BIN_MINUTES
    out["data_coverage_pct"] = (out["observed_minutes"] / BIN_MINUTES).round(4)

    # Columns below are null because they cannot currently be derived from the
    # Session.json summary data (would require raw inter-keystroke timestamps).
    for null_col in ["mean_inter_key_interval", "median_inter_key_interval"]:
        if null_col not in out.columns:
            out[null_col] = np.nan  # not computable from current aggregated keylog data

    keep_cols = [
        "health_code", "health_code_masked", "record_id", "alias",
        "date", "bin_index", "bin_start", "bin_end",
        "observed_minutes", "keyboard_session_count", "typing_event_count",
        "backspace_count", "backspace_ratio",
        "mean_inter_key_interval", "median_inter_key_interval",
        "accelerometer_activity_mean", "accelerometer_activity_sd",
        "data_coverage_pct",
    ]
    for c in keep_cols:
        if c not in out.columns:
            out[c] = np.nan
    return (
        out[keep_cols]
        .sort_values(["health_code", "date", "bin_index"])
        .reset_index(drop=True)
    )

# ---------------------------------------------------------------------
# Linked time-grid construction
# ---------------------------------------------------------------------

def complete_96_grid(participants: pd.DataFrame, dates_by_health_code: dict[str, list[pd.Timestamp]]) -> pd.DataFrame:
    rows = []
    for _, p in participants.iterrows():
        health_code = str(p.get("health_code"))
        participant_label = safe_name(p.get("record_id") or health_code)
        dates = pd.to_datetime(pd.Series(dates_by_health_code.get(health_code, [])), errors="coerce").dropna().dt.normalize().drop_duplicates().sort_values()
        for d in dates:
            for i in range(BINS_PER_DAY):
                start = d + pd.Timedelta(minutes=i * BIN_MINUTES)
                rows.append({
                    "record_id": p.get("record_id"),
                    "alias": p.get("alias"),
                    "health_code": health_code,
                    "participant": participant_label,
                    "date": d,
                    "bin_index": i,
                    "bin_start": start,
                    "bin_end": start + pd.Timedelta(minutes=BIN_MINUTES),
                })
    return pd.DataFrame(rows)


def prepare_outcome_daily(outcomes_df: pd.DataFrame) -> pd.DataFrame:
    if outcomes_df is None or outcomes_df.empty:
        return pd.DataFrame(columns=["health_code", "date"])
    out = outcomes_df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    return out.sort_values(["health_code", "date"]).drop_duplicates(subset=["health_code", "date"], keep="first")


def build_linked_timegrid(
    participant_df: pd.DataFrame,
    metric_bins: pd.DataFrame,
    outcomes_df: pd.DataFrame,
    manifest_df: pd.DataFrame | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Build participant-level 96-bin/day panel for the filtered cohort."""
    participants = participant_df.copy()

    dates_by_hc: dict[str, list[pd.Timestamp]] = {}
    if outcomes_df is not None and not outcomes_df.empty:
        tmp = outcomes_df.copy()
        tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce").dt.normalize()
        for hc, g in tmp.dropna(subset=["health_code", "date"]).groupby("health_code"):
            dates_by_hc.setdefault(str(hc), []).extend(g["date"].tolist())

    if manifest_df is not None and not manifest_df.empty:
        mf = normalize_manifest_dates(manifest_df)
        for hc, g in mf.dropna(subset=["health_code", "session_date"]).groupby("health_code"):
            dates_by_hc.setdefault(str(hc), []).extend(g["session_date"].tolist())

    if metric_bins is not None and not metric_bins.empty:
        mb = metric_bins.copy()
        mb["date"] = pd.to_datetime(mb["date"], errors="coerce").dt.normalize()
        # participant labels are record_id-based in this pipeline; this fallback keeps parsed data usable.
        if "participant" in mb.columns:
            for participant, g in mb.dropna(subset=["participant", "date"]).groupby("participant"):
                match = participants[participants["record_id"].astype(str).eq(str(participant))]
                if not match.empty:
                    hc = str(match.iloc[0]["health_code"])
                    dates_by_hc.setdefault(hc, []).extend(g["date"].tolist())

    if start_date or end_date:
        for hc, dates in list(dates_by_hc.items()):
            s = pd.to_datetime(pd.Series(dates), errors="coerce").dropna().dt.normalize()
            if start_date:
                s = s[s.ge(pd.to_datetime(start_date).normalize())]
            if end_date:
                s = s[s.le(pd.to_datetime(end_date).normalize())]
            dates_by_hc[hc] = s.drop_duplicates().tolist()

    grid = complete_96_grid(participants, dates_by_hc)
    if grid.empty:
        return grid

    panel = grid.copy()
    if metric_bins is not None and not metric_bins.empty:
        mb = metric_bins.copy()
        mb["date"] = pd.to_datetime(mb["date"], errors="coerce").dt.normalize()
        panel = panel.merge(mb, on=["participant", "date", "bin_index", "bin_start", "bin_end"], how="left")

    outcome_daily = prepare_outcome_daily(outcomes_df)
    keep_outcome_cols = [c for c in outcome_daily.columns if c not in {"record_id", "alias", "device_type", "record_id_str"}]
    if keep_outcome_cols:
        panel = panel.merge(outcome_daily[keep_outcome_cols], on=["health_code", "date"], how="left", suffixes=("", "_outcome"))

    count_cols = ["n_keylogs", "n_backspace", "n_autocorrection", "n_suggestion", "n_alphanum", "n_punctuation", "n_accelerations", "n_sessions_in_bin", "n_accel_sessions_in_bin"]
    for c in count_cols:
        if c not in panel.columns:
            panel[c] = 0
        panel[c] = pd.to_numeric(panel[c], errors="coerce").fillna(0).astype(int)

    panel["has_keylog_observation"] = panel["n_keylogs"].gt(0).astype(int)
    panel["has_accel_observation"] = panel["n_accelerations"].gt(0).astype(int)
    panel["observed_minutes_keylog"] = panel["has_keylog_observation"] * BIN_MINUTES
    panel["observed_minutes_accel"] = panel["has_accel_observation"] * BIN_MINUTES
    panel["observed_pct_keylog"] = panel["has_keylog_observation"].astype(float)
    panel["observed_pct_accel"] = panel["has_accel_observation"].astype(float)
    panel["typing_intensity"] = panel["n_keylogs"] / BIN_MINUTES

    ratio_cols = ["backspace_ratio", "autocorrect_rate", "suggestion_rate", "alphanum_rate", "punctuation_rate"]
    for c in ratio_cols:
        if c not in panel.columns:
            panel[c] = np.nan
        panel.loc[panel["n_keylogs"].eq(0), c] = np.nan

    # Convenience flags for the dashboard frontend.
    panel["has_biaffect_for_bin"] = (
        panel["has_keylog_observation"].eq(1) | panel["has_accel_observation"].eq(1)
    ).astype(int)

    # has_self_report_for_day: 1 if any self-report outcome row exists for this date.
    if "has_redcap_outcome" in panel.columns:
        day_sr = (
            panel.groupby(["health_code", "date"], dropna=False)["has_redcap_outcome"]
            .transform("max")
            .fillna(0)
            .astype(int)
        )
        panel["has_self_report_for_day"] = day_sr
    else:
        panel["has_self_report_for_day"] = 0

    # Add health_code_masked
    panel["health_code_masked"] = panel["health_code"].apply(mask_health_code)

    return panel.sort_values(["record_id", "date", "bin_index"]).reset_index(drop=True)
