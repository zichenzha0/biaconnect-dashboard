# BiaConnect Frontend

Next.js 14 (App Router) dashboard for BiAffect/Synapse + REDCap linkage data.

## Development

```bash
# From the project root:
npm run dev

# Or directly from this directory:
npx next dev
```

Starts the dev server at [http://localhost:3000](http://localhost:3000).

## Directory layout

```
frontend/
├── app/
│   ├── page.tsx          # main dashboard (client component)
│   ├── layout.tsx        # root layout + metadata
│   └── globals.css       # Tailwind directives
├── components/
│   ├── ParticipantFilterPanel.tsx   # sidebar filter form
│   ├── PresenceSummaryCards.tsx     # 5 cohort stat cards
│   ├── ParticipantSummaryTable.tsx  # participant index table
│   ├── SessionManifestTable.tsx     # Synapse session rows
│   ├── LinkedTimegridTable.tsx      # 15-min bin panel
│   └── EmptyState.tsx               # empty/no-match state
└── lib/
    ├── types.ts        # TypeScript interfaces for all CSV schemas
    ├── mockData.ts     # synthetic MVP data (8 fake participants)
    └── csvLoader.ts    # async loaders for real CSV outputs (TODO)
```

## Connecting to real data

1. Generate output CSVs with the Python pipeline (see project root README).
2. Copy CSVs to `public/dashboard_exports/`.
3. Un-comment the `fetchCSV` calls in `lib/csvLoader.ts`.
4. Replace mock imports in `app/page.tsx` with async loader calls.
