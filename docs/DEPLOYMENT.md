# CHEWS deployment

This document separates **local development** (what the repo supports) from **production** (mostly **not implemented**).

---

## Development setup

### Environment requirements

| Requirement | Evidence | Notes |
| ----------- | -------- | ----- |
| Python 3.10+ | `float \| None` / `str \| None` in backend | **Not pinned**; no `runtime.txt` / `.python-version` |
| pip | `backend/requirements.txt` | |
| Modern browser | Leaflet + ES modules in static JS | |
| Node.js | **Not required** for product UI | Only if you run `frontend-react/` (incomplete) |

### Python dependencies (runtime)

From `backend/requirements.txt`:

- fastapi ≥ 0.100.0  
- uvicorn[standard] ≥ 0.25.0  
- pydantic ≥ 2.0.0  
- numpy ≥ 1.26.0  
- joblib ≥ 1.3.0  
- scikit-learn ≥ 1.3.0  

### Training extras

`backend/requirements-dev.txt`: scikit-learn, pandas, matplotlib, seaborn.

### Environment variables

**None required.** The app does not load dotenv. CORS origins are hardcoded.

### Backend startup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Startup loads joblib models (if present) and the MoH MFL CSV. Environmental GBT trains in-process (CPU spike on boot).

### Frontend startup

```bash
cd frontend
python3 -m http.server 3000
```

JS uses `fetch('/api/...')`. A static server on :3000 **will 404 `/api`** unless you add a reverse proxy. For evaluator checks of HTTP, use `http://127.0.0.1:8000/docs` or deploy behind Vercel-style routing.

### API configuration

Frontend constant: `const API = "/api"` (several files). No build-time env injection.

---

## Hosted / Vercel (present in repo)

`vercel.json`:

- Build `backend/main.py` with `@vercel/python`, `includeFiles: backend/**`  
- Build `frontend/**` with `@vercel/static`  
- Route `/api/(.*)` → Python  
- Route `/(.*)` → `frontend/$1`

**Consequences:**

- Dashboard calls such as `/api/healthcare/facilities` can work.  
- `GET /health`, `POST /predict`, `POST /ask` are **not** under `/api` and may be served as missing static files.  
- Serverless Python: in-memory alerts and weather cache **do not persist** across instances; cold starts retrigger `initialize()`.  
- `includeFiles: backend/**` is required so CSVs and joblib ship with the function.

Python version on Vercel is **not verifiable from this repository**.

---

## Production considerations (mostly gaps)

| Topic | Development | Production-ready in repo? |
| ----- | ----------- | ------------------------- |
| Hosting | Laptop Uvicorn | Vercel config only; no SLO |
| HTTPS | Optional | Relies on host |
| AuthN/Z | None | **No** |
| Secrets | None used | `/api/debug` still public |
| Database | None | **No** |
| Migrations | N/A | N/A |
| CORS | `*` + credentials | Unsafe |
| Rate limits | None | **No** |
| Docker | Absent | **No** |
| CI/CD | Absent | **No** |
| Monitoring | `print` | **No** |
| Logging | stdout | Unstructured |
| Backups | Git | MFL is in git; no backup job |
| Scaling | Single process | Serverless: scale-out **resets memory**; no shared alert store |

### Security requirements before any public pilot

See [SECURITY.md](SECURITY.md): remove debug, restrict CORS, add authentication, stop logging symptom payloads, disable blocked ML in public builds.

### Monitoring (planned)

Not implemented: uptime checks, model-drift dashboards, DHIS2 lag monitors, error tracking (Sentry etc. — **not in dependencies**).

### Logging

`print(f"[CHEWS] ...")` and weather `print` on failure. No request-id middleware.

### Scaling considerations

- MFL (~1,615 rows) fits in memory. Compact list is designed to be smaller than nested objects.  
- Training is offline (`train_all_models.py`), not a request path, except environmental GBT at startup.  
- Open-Meteo: 2s timeout, 1h cache per rounded lat/lon — still a **single dependency** without circuit-breaker metrics.  
- Do not scale by adding more unauthenticated `/predict` workers facing the internet.

---

## Docker / Kubernetes / cloud services

**Not present.** No Dockerfile, compose file, Terraform, or AWS/GCP modules.

---

## Re-training in an environment

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python -m training.train_all_models
```

Confirm CSV paths inside the script (`data/raw/...`) still exist. Output: `data/trained_models/`. Runtime loaders must point at the files you actually deploy.
