# URL Shortener

Create short links that redirect to long URLs and count clicks. FastAPI backend, PostgreSQL (SQLite fallback for local dev), single-page HTML frontend.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000. API docs are at http://localhost:8000/docs.

To use Postgres instead of SQLite:

```bash
export DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/links"
```

## Tests

```bash
pytest -q
```

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/links` | Create `{ "url": "https://...", "code"?: "custom" }` (409 if code taken) |
| GET | `/api/links` | List the 100 most recent links |
| GET | `/api/links/{code}` | Link details and click count |
| DELETE | `/api/links/{code}` | Delete |
| GET | `/{code}` | 302 redirect to the target URL, increments clicks |
