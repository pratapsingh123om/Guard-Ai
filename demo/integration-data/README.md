# SQLite integration demo

Create the synthetic local database from the repository root:

```powershell
.\demo\integration-data\setup.ps1 -Force
```

Start Guard-AI with an operator token and a confined SQLite root:

```powershell
$env:GUARD_ADMIN_TOKEN = '<at-least-32-random-characters>'
$env:GUARD_SQLITE_ROOT = (Resolve-Path .\demo\integration-data).Path
.\.venv\Scripts\uvicorn.exe backend.app.main:app --port 8080
```

Register this connection through `POST /api/v1/connections`:

```json
{
  "name": "Guard-AI Demo Database",
  "category": "database",
  "connector": "sqlite",
  "endpoint": "sqlite:///guard-ai-demo.db"
}
```

Calling `POST /api/v1/connections/{id}/test` opens the file in SQLite read-only mode and runs `SELECT 1`. The endpoint cannot select a file outside `GUARD_SQLITE_ROOT`. The database contains only synthetic organizations and orders.
