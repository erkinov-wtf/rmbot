# Frontend (React + shadcn)

Basic frontend scaffold for the Rent Market backend.

## Stack
- Vite
- React + TypeScript
- Tailwind CSS
- shadcn-style setup (`components.json`, `cn` utility, sample `Button`)

## Run

```bash
npm install
npm run dev
```

## Docker

From repository root:

```bash
docker compose up -d --build frontend
```

Frontend will be available on `http://localhost:5173` by default.
Set `VITE_API_BASE_URL` in the repository root `.env` before building.

## Environment

Create `.env` from `.env.example` and set backend URL:

```bash
VITE_API_BASE_URL=http://localhost:8005/api/v1
```

## Notes
- Backend health endpoint used by starter UI: `/api/v1/misc/health/`.
- Most backend endpoints are JWT protected and return a `success/message/data` envelope.
- Paginated endpoints return `results`, `total_count`, `page`, `page_count`, `per_page`.
