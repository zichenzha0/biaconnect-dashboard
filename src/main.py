"""
BiaConnect Dashboard — filtered cohort backend runner.

Participant linkage is strictly health_code-based.
Self-report (REDCap-style) and Synapse (BiAffect) data are only linked
when a matching health_code is found in both sources.

Example commands (run from project root):

    # Build participant index + self-report linkage only (no Synapse)
    python src/main.py \\
        --ids "data/raw/BiAffect IDs.xlsx" \\
        --report "data/raw/report.csv"

    # Require both self-report and Synapse, copy outputs to frontend
    python src/main.py \\
        --ids "data/raw/BiAffect IDs.xlsx" \\
        --report "data/raw/report.csv" \\
        --require-self-report \\
        --require-synapse \\
        --build-manifest \\
        --build-grid \\
        --copy-to-frontend

    # Filter by record_id; cap Synapse manifest rows
    python src/main.py \\
        --ids "data/raw/BiAffect IDs.xlsx" \\
        --report "data/raw/report.csv" \\
        --record-ids 127084,091811 \\
        --build-manifest \\
        --max-rows-per-participant 10

    # Download, parse, build timegrid, copy to frontend
    python src/main.py \\
        --ids "data/raw/BiAffect IDs.xlsx" \\
        --report "data/raw/report.csv" \\
        --require-synapse \\
        --build-manifest \\
        --download \\
        --parse \\
        --build-grid \\
        --copy-to-frontend
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from commonconst import (
    BIAFFECT_METRIC_BINS_FILENAME,
    DASHBOARD_EXPORT_DIR,
    DASHBOARD_FRONTEND_FILES,
    DEFAULT_DEDUPLICATE_BY_RECORDID,
    DEFAULT_DIRS,
    DEFAULT_IDS_XLSX,
    DEFAULT_MAX_ROWS_PER_PARTICIPANT,
    DEFAULT_REDCAP_REPORT_CSV,
    DOWNLOAD_DIR,
    DOWNLOAD_LOG_FILENAME,
    EXTRACTED_DIR,
    FRONTEND_DASHBOARD_EXPORT_DIR,
    IDS_CLEAN_FILENAME,
    KEYLOGS_LONG_FILENAME,
    ACCELS_LONG_FILENAME,
    LINKED_TIMEGRID_FILENAME,
    MANIFEST_DIR,
    PARTICIPANT_INDEX_FILENAME,
    SELF_REPORT_DAILY_OUTCOMES_FILENAME,
    SESSION_MANIFEST_FILENAME,
    SYNAPSE_PRESENCE_FILENAME,
)
from utils import (
    apply_participant_filters,
    build_biaffect_metric_bins,
    build_filtered_session_manifest,
    build_healthcode_linkage,
    build_linked_timegrid,
    build_observed_metric_bins,
    build_presence_summary,
    compute_synapse_date_range,
    copy_exports_to_frontend,
    deduplicate_and_cap_manifest,
    download_from_manifest,
    ensure_dir,
    ensure_project_dirs,
    export_participant_details,
    filter_manifest_by_date,
    get_synapse_client,
    load_participant_ids,
    load_self_report,
    merge_synapse_into_index,
    parse_csv_arg,
    parse_session_files,
    summarize_ids,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BiaConnect filtered BiAffect + self-report linkage pipeline"
    )

    # ── Inputs / outputs ────────────────────────────────────────────────
    parser.add_argument("--ids",    default=str(DEFAULT_IDS_XLSX),         help="Path to BiAffect IDs.xlsx")
    parser.add_argument("--report", default=str(DEFAULT_REDCAP_REPORT_CSV), help="Path to self-report (REDCap) report.csv")
    parser.add_argument("--out-dir", default=str(DASHBOARD_EXPORT_DIR),     help="Output directory for dashboard CSVs")
    parser.add_argument("--downloads-root", default=str(DOWNLOAD_DIR / "filtered"), help="Where downloaded Synapse files go")
    parser.add_argument("--extracted-root", default=str(EXTRACTED_DIR / "filtered"), help="Where extracted Session.json files go")

    # ── Participant filters ──────────────────────────────────────────────
    parser.add_argument("--record-ids",  default=None, help="Comma-separated record IDs, e.g. 127084,091811")
    parser.add_argument("--aliases",     default=None, help="Comma-separated alias values")
    parser.add_argument("--health-codes",default=None, help="Comma-separated health_code values (exact match)")
    parser.add_argument("--device-type", default="all", choices=["all", "ios", "android", "unknown"])
    parser.add_argument("--require-self-report", action="store_true",
                        help="Keep only participants with linked self-report data")
    parser.add_argument("--require-redcap", action="store_true",
                        help="Alias for --require-self-report (backward compat)")
    parser.add_argument("--require-synapse", action="store_true",
                        help="Keep only participants matched in Synapse")
    parser.add_argument("--start-date", default=None, help="Filter from YYYY-MM-DD")
    parser.add_argument("--end-date",   default=None, help="Filter through YYYY-MM-DD")

    # ── Synapse / data actions ───────────────────────────────────────────
    parser.add_argument("--skip-synapse",   action="store_true", help="Skip all Synapse calls")
    parser.add_argument("--build-manifest", action="store_true", help="Fetch Synapse session manifest")
    parser.add_argument("--download",       action="store_true", help="Download files from manifest")
    parser.add_argument("--parse",          action="store_true", help="Parse Session.json files")
    parser.add_argument("--build-grid",     action="store_true", help="Build linked 15-min timegrid")

    # ── Manifest controls ────────────────────────────────────────────────
    parser.add_argument("--max-rows-per-participant", type=int, default=DEFAULT_MAX_ROWS_PER_PARTICIPANT,
                        help="Cap rows per participant in manifest (0 = no cap)")
    parser.add_argument("--no-deduplicate", action="store_true",
                        help="Do not deduplicate manifest by [record_id, recordId]")

    # ── Frontend copy ────────────────────────────────────────────────────
    parser.add_argument("--copy-to-frontend", action="store_true",
                        help="Copy generated CSVs to frontend/public/dashboard_exports/")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_project_dirs(DEFAULT_DIRS)
    out_dir = ensure_dir(args.out_dir)
    manifest_dir = ensure_dir(MANIFEST_DIR)
    downloads_root = ensure_dir(args.downloads_root)
    extracted_root = ensure_dir(args.extracted_root)

    require_sr = args.require_self_report or args.require_redcap

    print("\nBiaConnect backend run")
    print(f"  IDs file:       {args.ids}")
    print(f"  Report file:    {args.report}")
    print(f"  Output dir:     {out_dir}")

    # ── 1. Load participant IDs ────────────────────────────────────────
    ids = load_participant_ids(args.ids)
    ids.to_csv(out_dir / IDS_CLEAN_FILENAME, index=False)
    print(f"\n[1] Loaded participant IDs: {summarize_ids(ids)}")

    # ── 2. Load self-report data ───────────────────────────────────────
    self_report = pd.DataFrame()
    report_path = Path(args.report)
    if report_path.exists():
        self_report = load_self_report(report_path, ids)
        self_report.to_csv(out_dir / SELF_REPORT_DAILY_OUTCOMES_FILENAME, index=False)
        linked_rows = self_report["health_code"].notna().sum()
        print(f"[2] Self-report rows loaded: {len(self_report):,}  (health_code linked: {linked_rows:,})")
    else:
        print(f"[2] Self-report file not found, continuing without it: {report_path}")

    # ── 3. Build participant index (health_code linkage) ───────────────
    participant_index = build_healthcode_linkage(ids, self_report if not self_report.empty else None)
    print(f"[3] Participant index built: {len(participant_index):,} participants")
    print(f"    With self-report: {participant_index['has_self_report'].sum():,}")

    # ── 4. Apply pre-Synapse filters ──────────────────────────────────
    filtered = apply_participant_filters(
        participant_index,
        record_ids=parse_csv_arg(args.record_ids, int),
        aliases=parse_csv_arg(args.aliases, int),
        health_codes=parse_csv_arg(args.health_codes, str),
        device_type=args.device_type,
        require_self_report=require_sr,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(f"[4] After pre-Synapse filters: {len(filtered):,} participant(s)")

    if filtered.empty:
        print("    No participants matched. Stopping.")
        return

    # ── 5. Synapse presence check ─────────────────────────────────────
    presence = pd.DataFrame()
    syn = None
    needs_synapse = not args.skip_synapse and (
        args.require_synapse or args.build_manifest or args.download
    )

    if needs_synapse:
        try:
            syn = get_synapse_client()
            print("[5] Synapse login successful.")
            presence = build_presence_summary(syn, filtered)
            presence.to_csv(out_dir / SYNAPSE_PRESENCE_FILENAME, index=False)
            presence.to_csv(manifest_dir / SYNAPSE_PRESENCE_FILENAME, index=False)
            n_matched = (presence["status"] == "matched").sum()
            print(f"    Synapse presence: {len(presence):,} rows, {n_matched:,} matched")

            # Merge synapse info back into participant index
            filtered = merge_synapse_into_index(filtered, presence)

            if args.require_synapse:
                filtered = apply_participant_filters(
                    filtered, require_synapse=True
                )
                print(f"    After require-synapse: {len(filtered):,} participant(s)")
                if filtered.empty:
                    print("    No participants after require-synapse. Stopping.")
                    return
        except Exception as exc:
            print(f"[5] WARNING: Synapse check failed: {exc}")
            print("    Continuing without Synapse presence data.")
    else:
        print("[5] Skipping Synapse presence check.")
        presence.to_csv(out_dir / SYNAPSE_PRESENCE_FILENAME, index=False)

    # Save final filtered participant index (includes synapse columns)
    filtered.to_csv(out_dir / PARTICIPANT_INDEX_FILENAME, index=False)
    print(f"    Saved participant_index_filtered.csv: {len(filtered):,} row(s)")

    # ── 6. Build Synapse session manifest ─────────────────────────────
    manifest = pd.DataFrame()
    if args.build_manifest or args.download:
        if syn is None:
            try:
                syn = get_synapse_client()
                print("[6] Synapse login successful.")
            except Exception as exc:
                print(f"[6] Cannot build manifest — Synapse login failed: {exc}")
                syn = None

        if syn is not None:
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
            print(f"[6] Saved session manifest: {len(manifest):,} row(s)")

            # Compute first/last Synapse session date from manifest and update index
            syn_dates = compute_synapse_date_range(manifest)
            if not syn_dates.empty:
                for col in ["first_synapse_date", "last_synapse_date"]:
                    if col in filtered.columns:
                        filtered = filtered.drop(columns=[col])
                filtered = filtered.merge(syn_dates, on="health_code", how="left")
                filtered.to_csv(out_dir / PARTICIPANT_INDEX_FILENAME, index=False)
                n_dated = syn_dates["first_synapse_date"].notna().sum()
                print(f"    Synapse date range updated for {n_dated} participant(s)")
        else:
            print("[6] Skipped manifest build (no Synapse connection).")
    else:
        print("[6] --build-manifest not requested.")

    # ── 7. Optional download ──────────────────────────────────────────
    if args.download:
        if manifest.empty:
            print("[7] No manifest rows to download.")
        elif syn is None:
            print("[7] Download skipped — no Synapse connection.")
        else:
            log = download_from_manifest(syn, manifest, downloads_root, extracted_root)
            log.to_csv(out_dir / DOWNLOAD_LOG_FILENAME, index=False)
            print(f"[7] Download log: {len(log):,} row(s)")

    # ── 8. Optional parse ─────────────────────────────────────────────
    keylogs = pd.DataFrame()
    accels = pd.DataFrame()
    if args.parse:
        keylogs, accels = parse_session_files(extracted_root)
        keylogs.to_csv(out_dir / KEYLOGS_LONG_FILENAME, index=False)
        accels.to_csv(out_dir / ACCELS_LONG_FILENAME, index=False)
        print(f"[8] Parsed keylogs={len(keylogs):,}, accelerations={len(accels):,}")

        # Build standardized BiAffect metric bins
        metric_bins = build_biaffect_metric_bins(keylogs, accels, filtered)
        metric_bins.to_csv(out_dir / BIAFFECT_METRIC_BINS_FILENAME, index=False)
        print(f"    Metric bins: {len(metric_bins):,} row(s)")
    else:
        print("[8] --parse not requested.")

    # ── 9. Optional linked timegrid ───────────────────────────────────
    linked = pd.DataFrame()  # initialised here so step 10 can always reference it
    if args.build_grid:
        # Load parsed data from disk if not just computed
        if keylogs.empty:
            kl_path = out_dir / KEYLOGS_LONG_FILENAME
            if kl_path.exists():
                keylogs = pd.read_csv(kl_path)
        if accels.empty:
            ac_path = out_dir / ACCELS_LONG_FILENAME
            if ac_path.exists():
                accels = pd.read_csv(ac_path)

        metric_bins_for_grid = build_observed_metric_bins(keylogs, accels)
        manifest_for_grid = manifest
        if manifest_for_grid.empty:
            mp = out_dir / SESSION_MANIFEST_FILENAME
            if mp.exists():
                manifest_for_grid = pd.read_csv(mp)

        linked = build_linked_timegrid(
            participant_df=filtered,
            metric_bins=metric_bins_for_grid,
            outcomes_df=self_report,
            manifest_df=manifest_for_grid if not manifest_for_grid.empty else None,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        linked.to_csv(out_dir / LINKED_TIMEGRID_FILENAME, index=False)
        print(f"[9] Linked timegrid: {len(linked):,} row(s)")
    else:
        print("[9] --build-grid not requested.")

    # ── 10. Export participant details + copy to frontend ─────────────
    if args.copy_to_frontend:
        print("\n[10] Generating participant-level detail exports ...")

        # Resolve manifest: use in-memory copy or fall back to saved CSV
        manifest_for_details = manifest
        if manifest_for_details.empty:
            mp = out_dir / SESSION_MANIFEST_FILENAME
            if mp.exists():
                print("    Loading session manifest from disk ...")
                manifest_for_details = pd.read_csv(mp)

        # Resolve timegrid: use in-memory copy or fall back to saved CSV
        timegrid_for_details = linked
        if timegrid_for_details.empty:
            tp = out_dir / LINKED_TIMEGRID_FILENAME
            if tp.exists():
                print("    Loading linked timegrid from disk ...")
                timegrid_for_details = pd.read_csv(tp)

        if not manifest_for_details.empty or not timegrid_for_details.empty:
            filtered = export_participant_details(
                filtered,
                manifest_for_details,
                timegrid_for_details,
                out_dir,
                FRONTEND_DASHBOARD_EXPORT_DIR,
            )
            # Re-save participant index with the new path columns
            filtered.to_csv(out_dir / PARTICIPANT_INDEX_FILENAME, index=False)
            print("    Participant detail files written.")
        else:
            print("    No manifest or timegrid available — skipping detail export.")

        print("\n    Copying top-level exports to frontend ...")
        copied = copy_exports_to_frontend(out_dir, FRONTEND_DASHBOARD_EXPORT_DIR)
        print(f"    Copied {len(copied)} file(s).")
    else:
        print("\n[10] --copy-to-frontend not set; skipping copy.")

    print(f"\nFinished. App-ready files are in: {out_dir}")


if __name__ == "__main__":
    main()
