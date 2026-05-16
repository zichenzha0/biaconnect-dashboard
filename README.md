# BiaConnect Dashboard

Participant-level linkage dashboard for BiAffect/Synapse keyboard-session data and REDCap-style self-report data.

> **Internal research use only.** Do not expose participant identifiers, raw data, or credentials publicly.

---

## Project structure

```
biaconnect-dashboard/
├── .env.example               # environment variable template (copy to .env)
├── .gitignore
├── requirements.txt           # Python backend dependencies
├── package.json               # root workspace — delegates npm scripts to frontend/
├── src/
│   ├── main.py                # filtered cohort backend runner
│   ├── utils.py               # core utility functions
│   └── commonconst.py         # shared paths, Synapse table IDs, constants
├── data/
│   └── raw/                   # local data files — gitignored
│       ├── BiAffect IDs.xlsx
│       └── report.csv
├── outputs/
│   └── dashboard_exports/     # pipeline outputs consumed by the frontend — gitignored
└── frontend/                  # self-contained Next.js 14 app
    ├── package.json
    ├── next.config.ts
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── app/
    │   ├── page.tsx            # main dashboard page
    │   ├── layout.tsx
    │   └── globals.css
    ├── components/
    │   ├── ParticipantFilterPanel.tsx
    │   ├── PresenceSummaryCards.tsx
    │   ├── ParticipantSummaryTable.tsx
    │   ├── SessionManifestTable.tsx
    │   ├── LinkedTimegridTable.tsx
    │   └── EmptyState.tsx
    └── lib/
        ├── types.ts            # TypeScript interfaces for all CSV schemas
        ├── mockData.ts         # synthetic mock data for MVP
        └── csvLoader.ts        # TODO: connect to real CSV outputs
```

---

## Quick start

### 1. Copy environment variables

```bash
cp .env.example .env
# Edit .env and add your SYNAPSE_AUTH_TOKEN
```

### 2. Install Python backend dependencies

```bash
pip install -r requirements.txt
```

### 3. Install and run the frontend

```bash
npm run install:frontend   # installs frontend/node_modules
npm run dev                # starts Next.js dev server at http://localhost:3000
```

> The `npm run dev` command delegates to `frontend/` via `npm --prefix frontend run dev`.

---

## Python backend runner

Run from the **project root** directory. Paths to `--ids` and `--report` are relative to where you run the command.

### Basic: build filtered participant index + REDCap outcomes

```bash
python src/main.py \
  --ids "data/raw/BiAffect IDs.xlsx" \
  --report "data/raw/report.csv"
```

### Filter by record ID and build Synapse manifest

```bash
python src/main.py \
  --ids "data/raw/BiAffect IDs.xlsx" \
  --report "data/raw/report.csv" \
  --record-ids 127084,091811 \
  --build-manifest
```

### Require both data sources, limit date range, cap rows per participant

```bash
python src/main.py \
  --ids "data/raw/BiAffect IDs.xlsx" \
  --report "data/raw/report.csv" \
  --require-redcap \
  --require-synapse \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --build-manifest \
  --max-rows-per-participant 10
```

### Filter by health_code

```bash
python src/main.py \
  --ids "data/raw/BiAffect IDs.xlsx" \
  --report "data/raw/report.csv" \
  --health-codes abc123,def456 \
  --build-manifest
```

### Filter by device type (iOS only)

```bash
python src/main.py \
  --ids "data/raw/BiAffect IDs.xlsx" \
  --report "data/raw/report.csv" \
  --device-type ios \
  --require-synapse \
  --build-manifest
```

### Build manifest only (no download)

```bash
python src/main.py \
  --ids "data/raw/BiAffect IDs.xlsx" \
  --report "data/raw/report.csv" \
  --require-synapse \
  --build-manifest
```

### Download, parse, and build linked timegrid

```bash
python src/main.py \
  --ids "data/raw/BiAffect IDs.xlsx" \
  --report "data/raw/report.csv" \
  --require-synapse \
  --build-manifest \
  --download \
  --parse \
  --build-grid
```

### Build timegrid from already-downloaded files

```bash
python src/main.py \
  --ids "data/raw/BiAffect IDs.xlsx" \
  --report "data/raw/report.csv" \
  --skip-synapse \
  --build-grid
```

> **Note:** `SYNAPSE_AUTH_TOKEN` must be set in `.env` for any command that contacts Synapse
> (`--build-manifest`, `--download`, or Synapse presence checks).

---

## Dashboard output files

After running the Python pipeline, output CSVs land in `outputs/dashboard_exports/`:

| File | Description |
|------|-------------|
| `participant_index_filtered.csv` | One row per participant with REDCap linkage metadata |
| `synapse_presence_filtered.csv` | Synapse match status per participant |
| `session_manifest_filtered.csv` | Filtered Synapse session rows |
| `redcap_daily_outcomes.csv` | Participant-linked daily REDCap survey outcomes |
| `metric_bins_observed_filtered.csv` | 15-min keystroke/accelerometer aggregates |
| `linked_timegrid_filtered.csv` | Full 96-bin/day panel with linked outcomes |

To connect these to the frontend, copy them to `frontend/public/dashboard_exports/` and
un-comment the `fetchCSV` calls in `frontend/lib/csvLoader.ts`.

---

## Connecting the frontend to real data

1. Run the Python pipeline to generate output CSVs.
2. Copy the CSVs to `frontend/public/dashboard_exports/`.
3. Open `frontend/lib/csvLoader.ts` and un-comment the `fetchCSV` return statements.
4. Update `frontend/app/page.tsx` to call `loadParticipantIndex()` etc. instead of importing `mockParticipants`.

---

## Vercel deployment

1. Push to a GitHub repository.
2. Import the project in Vercel.
3. Set **Root Directory** to `frontend/` in Vercel project settings.
4. Add `SYNAPSE_AUTH_TOKEN` and any other env vars in the Vercel Environment Variables panel.

> Vercel is suitable for the Next.js frontend only. Long-running Synapse downloads must be run
> locally or on a separate compute environment. Pre-generate the CSV outputs and commit them to
> `frontend/public/dashboard_exports/` (or serve them via a separate API).

---

## Security

- **Never commit `.env`** — it is gitignored.
- **Never commit raw participant data** — `data/raw/`, `data/interim/`, `data/processed/`, and `outputs/` are gitignored.
- Health codes are masked in the dashboard (`abc***xyz`). Full values are never rendered in the UI.
- REDCap identifiers and clinical outcome data are not logged to the browser console.
- `SYNAPSE_AUTH_TOKEN` is accessed only by the Python backend, never the frontend.

---

## Data files

Place these files locally under `data/raw/` (gitignored):

- `data/raw/BiAffect IDs.xlsx` — participant ID linkage sheet
- `data/raw/report.csv` — REDCap-style self-report export

These are never committed to the repository.
