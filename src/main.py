"""
BiaConnect Dashboard backend runner.

This is the filtered cohort version of your current BiAffect + REDCap linkage
pipeline. It is intentionally not single-participant-only. You can filter first,
then check Synapse, build a manifest, optionally download/parse sessions, and
build a linked 15-minute time-grid.

Example smoke-test commands:

    python main.py --ids data/raw/BiAffect\ IDs.xlsx --report data/raw/report.csv \
        --record-ids 127084 --build-manifest

    python main.py --ids data/raw/BiAffect\ IDs.xlsx --report data/raw/report.csv \
        --device-type ios --require-redcap --require-synapse --start-date 2025-01-01 \
        --end-date 2025-12-31 --build-manifest --max-rows-per-participant 10

    python main.py --ids data/raw/BiAffect\ IDs.xlsx --report data/raw/report.csv \
        --health-codes abc123,-abc123 --build-manifest --download --parse --build-grid
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from commonconst import (
    DAILY_OUTCOMES_FILENAME,
    DASHBOARD_EXPORT_DIR,
    DEFAULT_DEDUPLICATE_BY_RECORDID,
    DEFAULT_DIRS,
    DEFAULT_IDS_XLSX,
    DEFAULT_MAX_ROWS_PER_PARTICIPANT,
    DEFAULT_REDCAP_REPORT_CSV,
    DOWNLOAD_DIR,
    DOWNLOAD_LOG_FILENAME,
    EXTRACTED_DIR,
    IDS_CLEAN_FILENAME,
    KEYLOGS_LONG_FILENAME,
    ACCELS_LONG_FILENAME,
    LINKED_TIMEGRID_FILENAME,
    MANIFEST_DIR,
    METRIC_BINS_FILENAME,
    PARTICIPANT_INDEX_FILENAME,
    SESSION_MANIFEST_FILENAME,
    SYNAPSE_PRESENCE_FILENAME,
)
from utils import (
    apply_participant_filters,
    build_daily_outcomes,
    build_filtered_session_manifest,
    build_linked_timegrid,
    build_observed_metric_bins,
    build_participant_index,
    build_presence_summary,
    deduplicate_and_cap_manifest,
    download_from_manifest,
    ensure_dir,
    ensure_project_dirs,
    filter_manifest_by_date,
    get_synapse_client,
    load_participant_ids,
    parse_csv_arg,
    parse_session_files,
    summarize_ids,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filtered BiAffect + REDCap linkage pipeline")

    # Inputs/outputs
    parser.add_argument("--ids", default=str(DEFAULT_IDS_XLSX), help="Path to BiAffect IDs.xlsx")
    parser.add_argument("--report", default=str(DEFAULT_REDCAP_REPORT_CSV), help="Path to REDCap report.csv")
    parser.add_argument("--out-dir", default=str(DASHBOARD_EXPORT_DIR), help="Output directory for filtered app-ready files")
    parser.add_argument("--downloads-root", default=str(DOWNLOAD_DIR / "filtered"), help="Where downloaded Synapse files should go")
    parser.add_argument("--extracted-root", default=str(EXTRACTED_DIR / "filtered"), help="Where extracted Session.json files should go")

    # Participant filters
    parser.add_argument("--record-ids", default=None, help="Comma-separated REDCap/participant record IDs, e.g. 127084,091811")
    parser.add_argument("--aliases", default=None, help="Comma-separated aliases")
    parser.add_argument("--health-codes", default=None, help="Comma-separated health_code values")
    parser.add_argument("--device-type", default="all", choices=["all", "ios", "android", "unknown"], help="Device filter")
    parser.add_argument("--require-redcap", action="store_true", help="Keep only participants with linked REDCap outcomes")
    parser.add_argument("--require-synapse", action="store_true", help="Keep only participants matched in Synapse")
    parser.add_argument("--start-date", default=None, help="Filter Synapse session/timegrid dates from YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="Filter Synapse session/timegrid dates through YYYY-MM-DD")

    # Synapse/data actions
    parser.add_argument("--skip-synapse", action="store_true", help="Skip Synapse presence calls; useful for REDCap-only index building")
    parser.add_argument("--build-manifest", action="store_true", help="Fetch Synapse session manifest for filtered participants")
    parser.add_argument("--download", action="store_true", help="Download files from the filtered manifest")
    parser.add_argument("--parse", action="store_true", help="Parse Session.json files under extracted-root")
    parser.add_argument("--build-grid", action="store_true", help="Build linked 96-bin/day time-grid")

    # Manifest controls
    parser.add_argument("--max-rows-per-participant", type=int, default=DEFAULT_MAX_ROWS_PER_PARTICIPANT, help="0 means no cap")
    parser.add_argument("--no-deduplicate", action="store_true", help="Do not deduplicate manifest by [record_id, recordId]")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_project_dirs(DEFAULT_DIRS)
    out_dir = ensure_dir(args.out_dir)
    manifest_dir = ensure_dir(MANIFEST_DIR)
    downloads_root = ensure_dir(args.downloads_root)
    extracted_root = ensure_dir(args.extracted_root)

    print("\nBiaConnect filtered backend run")
    print(f"Output directory: {out_dir}")

    # 1. Load participant IDs.
    ids = load_participant_ids(args.ids)
    ids.to_csv(out_dir / IDS_CLEAN_FILENAME, index=False)
    print(f"Loaded participant IDs: {summarize_ids(ids)}")

    # 2. Build REDCap daily outcomes if report exists.
    outcomes = pd.DataFrame()
    report_path = Path(args.report)
    if report_path.exists():
        outcomes = build_daily_outcomes(report_path, ids)
        outcomes.to_csv(out_dir / DAILY_OUTCOMES_FILENAME, index=False)
        print(f"Built REDCap daily outcomes: {len(outcomes):,} rows")
    else:
        print(f"REDCap report not found; continuing without outcomes: {report_path}")

    # 3. Build participant index and apply filters before Synapse calls.
    participant_index = build_participant_index(ids, outcomes)
    filtered = apply_participant_filters(
        participant_index,
        record_ids=parse_csv_arg(args.record_ids, int),
        aliases=parse_csv_arg(args.aliases, int),
        health_codes=parse_csv_arg(args.health_codes, str),
        device_type=args.device_type,
        require_redcap=args.require_redcap,
    )
    filtered.to_csv(out_dir / PARTICIPANT_INDEX_FILENAME, index=False)
    print(f"Filtered participant index: {len(filtered):,} participant(s)")

    if filtered.empty:
        print("No participants matched the requested filters. Stopping before Synapse calls.")
        return

    presence = pd.DataFrame()
    syn = None

    # 4. Synapse presence check when needed.
    needs_synapse = not args.skip_synapse and (args.require_synapse or args.build_manifest or args.download)
    if needs_synapse:
        syn = get_synapse_client()
        print("Synapse login successful.")
        presence = build_presence_summary(syn, filtered)
        presence.to_csv(out_dir / SYNAPSE_PRESENCE_FILENAME, index=False)
        presence.to_csv(manifest_dir / SYNAPSE_PRESENCE_FILENAME, index=False)
        print(f"Synapse presence rows: {len(presence):,}; matched: {(presence['status'] == 'matched').sum():,}")

        if args.require_synapse:
            matched_health_codes = set(presence.loc[presence["status"].eq("matched"), "health_code"].astype(str))
            filtered = filtered[filtered["health_code"].astype(str).isin(matched_health_codes)].reset_index(drop=True)
            filtered.to_csv(out_dir / PARTICIPANT_INDEX_FILENAME, index=False)
            print(f"After require-synapse filter: {len(filtered):,} participant(s)")
            if filtered.empty:
                print("No participants remained after require-synapse. Stopping.")
                return

    # 5. Build filtered Synapse manifest.
    manifest = pd.DataFrame()
    if args.build_manifest or args.download:
        if syn is None:
            syn = get_synapse_client()
            print("Synapse login successful.")
        if presence.empty:
            presence = build_presence_summary(syn, filtered)
            presence.to_csv(out_dir / SYNAPSE_PRESENCE_FILENAME, index=False)

        manifest = build_filtered_session_manifest(syn, presence)
        manifest = filter_manifest_by_date(manifest, args.start_date, args.end_date)
        manifest = deduplicate_and_cap_manifest(
            manifest,
            max_rows_per_participant=args.max_rows_per_participant,
            deduplicate_by_recordid=not args.no_deduplicate,
        )
        manifest.to_csv(out_dir / SESSION_MANIFEST_FILENAME, index=False)
        manifest.to_csv(manifest_dir / SESSION_MANIFEST_FILENAME, index=False)
        print(f"Saved filtered session manifest: {len(manifest):,} row(s)")

    # 6. Optional download.
    if args.download:
        if manifest.empty:
            print("No manifest rows available for download.")
        else:
            log = download_from_manifest(syn, manifest, downloads_root, extracted_root)
            log.to_csv(out_dir / DOWNLOAD_LOG_FILENAME, index=False)
            print(f"Saved download log: {len(log):,} row(s)")

    # 7. Optional parse.
    metric_bins = pd.DataFrame()
    if args.parse:
        keylogs, accels = parse_session_files(extracted_root)
        metric_bins = build_observed_metric_bins(keylogs, accels)
        keylogs.to_csv(out_dir / KEYLOGS_LONG_FILENAME, index=False)
        accels.to_csv(out_dir / ACCELS_LONG_FILENAME, index=False)
        metric_bins.to_csv(out_dir / METRIC_BINS_FILENAME, index=False)
        print(f"Parsed keylogs={len(keylogs):,}, accelerations={len(accels):,}, metric bins={len(metric_bins):,}")

    # 8. Optional linked time-grid.
    if args.build_grid:
        if metric_bins.empty:
            metric_bins_path = out_dir / METRIC_BINS_FILENAME
            if metric_bins_path.exists():
                metric_bins = pd.read_csv(metric_bins_path)
        if manifest.empty:
            manifest_path = out_dir / SESSION_MANIFEST_FILENAME
            if manifest_path.exists():
                manifest = pd.read_csv(manifest_path)
        linked = build_linked_timegrid(
            participant_df=filtered,
            metric_bins=metric_bins,
            outcomes_df=outcomes,
            manifest_df=manifest,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        linked.to_csv(out_dir / LINKED_TIMEGRID_FILENAME, index=False)
        print(f"Saved linked time-grid: {len(linked):,} row(s)")

    print("\nFinished BiaConnect filtered backend run.")
    print(f"App-ready files are in: {out_dir}")


if __name__ == "__main__":
    main()
