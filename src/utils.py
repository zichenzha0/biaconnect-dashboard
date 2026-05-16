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


def apply_participant_filters(
    participant_df: pd.DataFrame,
    record_ids: list[int] | None = None,
    aliases: list[int] | None = None,
    health_codes: list[str] | None = None,
    device_type: str | None = None,
    require_redcap: bool = False,
) -> pd.DataFrame:
    """Filter participants before any Synapse calls."""
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
    if require_redcap and "has_redcap_outcome" in df.columns:
        df = df[df["has_redcap_outcome"].eq(1)]

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
    df = manifest_df.copy()
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].fillna("").astype(str).str.strip()
    df["createdOn_dt"] = pd.to_datetime(df.get("createdOn"), errors="coerce")
    df["uploadDate_dt"] = pd.to_datetime(df.get("uploadDate"), errors="coerce")
    df["session_start_dt"] = df["createdOn_dt"].combine_first(df["uploadDate_dt"])
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

    return panel.sort_values(["record_id", "date", "bin_index"]).reset_index(drop=True)
