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

## Public Stats Subdomain

This frontend image supports host-based SPA fallback:
- default host -> `/index.html` (main app)
- `hrgame.rentmarket.uz` (and `hrgame.market.uz`) -> `/public-stats.html`

That means if the request host is `hrgame.rentmarket.uz`, opening `/` will render the Public Stats app.

### What you still need to configure outside this repo

1. DNS:
   - Create `A`/`CNAME` for `hrgame.rentmarket.uz` to your server.

2. TLS + reverse proxy on your edge Nginx (or similar):
   - Proxy both `hr.rentmarket.uz` and `hrgame.rentmarket.uz` to the same frontend container (`127.0.0.1:${FRONTEND_PORT}`).
   - Keep host header forwarding enabled.

Example upstream block:

```nginx
location / {
    proxy_pass http://127.0.0.1:5173;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Environment

Create `.env` from `.env.example` and set backend URL:

```bash
VITE_API_BASE_URL=http://localhost:8005/api/v1
```

## Notes
- Backend health endpoint used by starter UI: `/api/v1/misc/health/`.
- Most backend endpoints are JWT protected and return a `success/message/data` envelope.
- Paginated endpoints return `results`, `total_count`, `page`, `page_count`, `per_page`.
