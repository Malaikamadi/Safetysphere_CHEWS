# CHEWS security

## Security architecture

CHEWS currently has **no server-side security architecture**. The FastAPI process accepts anonymous JSON and returns scores, facility coordinates, and (if used) symptom triage. The browser stores a role string. That is the whole control plane.

```text
[Any client] --HTTP--> [FastAPI] --files--> [CSV / joblib]
                         |
                         +-- optional HTTPS --> [Open-Meteo]
```

There is no identity provider, API key middleware, network allowlist in code, or audit log.

---

## Secrets management

- No `.env` loader in application code.  
- No cloud secret manager client.  
- **No live API keys, passwords, or private keys were found in the repository during this audit.** Open-Meteo is used without a key. OSM tiles require no key.

If a secret is introduced later, `.gitignore` is **too thin** to protect it.

---

## Environment variables

Unused for security. CORS and debug behaviour are **code constants**.

---

## Authentication status

**Not implemented.**

`frontend/auth.js` `requireRole()` / `getRole()` read `localStorage`. Empty role defaults to **admin**. Changing `chews-role` in DevTools unlocks any sidebar.

---

## Authorization status

**Not implemented** on the API. Partner, worker, and admin receive the same backend.

Admin sidebar hashes (`#admin-users`, `#admin-dhis2`, …) are **UI placeholders**, not protected resources.

---

## API security

| Control | Status |
| ------- | ------ |
| TLS | Depends on host (Vercel); not configured in repo |
| Auth headers | Ignored |
| Rate limiting | None |
| CSRF | N/A for token-less JSON; still open CORS |
| Output encoding | Browser; API returns JSON |

`frontend/partner.html` displays a **demo** Authorization header value for copy-paste. The API does **not** validate Bearer tokens. That string is not a production credential, but it trains users to believe keys exist.

---

## Input validation

**Present:** Pydantic ranges on many bodies (e.g. humidity 0–100, rainfall 0–500).  
**Gaps:** string fields such as `question`, `location`, `district` are not tightly enumerated on all routes; `symptoms` is a free list (`SYMPTOM_SCORES.get(s, 1)` scores **unknown tokens as 1**). Path `facility_id` is looked up, not globbed. No max JSON size configured in-repo. No sanitisation layer beyond Pydantic.

---

## CORS

```python
allow_origins=["*"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

This combination is **unsafe** (credentialed wildcards). For a cookie-less MVP it still allows any website to call the API from a browser.

---

## Information disclosure

`GET /api/debug` returns cwd, directory listings, import exception strings, and facility counts. Treat as **HIGH** for any internet-facing deploy.

Startup may print paths and model status to logs.

---

## Data privacy

- **MFL:** public facility locations — still a targeting-sensitive layer in some contexts; shipped in git.  
- **Triage/ask:** symptom and question text may hit hosting logs. **PHI-like.**  
- **No retention policy** (nothing stored — except git history of CSVs and host logs).  
- Synthetic epi files must not be published as real patient or outbreak data.

Health-data considerations for a future DHIS2 connection: data processing agreement, encryption at rest, role-based org-unit scope, audit, minimisation. **None of that is implemented.**

---

## Dependency concerns

- Unpinned upper bounds (`fastapi>=0.100.0`, etc.) — supply-chain drift.  
- No lockfile (`requirements.txt` only).  
- No Dependabot/CI CVE scan in repo.  
- CDN Leaflet / Lucide / fonts — **integrity hashes not verified in this audit** (check HTML tags).  
- `scikit-learn`/`joblib` load **pickle-equivalent** artifacts: only load joblib from this repo’s own training output.

---

## Other risks

- Open redirect: **not assessed beyond login paths.**  
- XSS: innerHTML used in `auth.js` sidebar construction from **local constants**, not API text — lower risk; Situation Room / other pages that interpolate API strings should be reviewed before production.  
- Path traversal: debug `os.listdir` on known data dir only.

---

## Production security requirements

1. Delete or gate `/api/debug`.  
2. Restrict CORS to the dashboard origin; `allow_credentials=False` unless cookies exist.  
3. Add authentication (and stop default-admin).  
4. Do not log raw triage bodies.  
5. Disable or hide BLOCKED ML routes.  
6. Pin dependencies; add CI.  
7. Secrets in a manager, never git.  
8. WAF / rate limit.  
9. Security.txt / contact — **not in repo**.

---

## Findings format (no secret values)

No CRITICAL committed credential was identified.

If one appears in a future commit:

```text
CRITICAL SECURITY FINDING:
File: <path>
Issue: Credential/API key appears to be committed to the repository.
Action: Rotate the credential immediately and remove it from repository history.
```

**HIGH (configuration, not a leaked password):**

```text
HIGH:
File: backend/main.py
Issue: Unauthenticated GET /api/debug discloses runtime and filesystem metadata.
Action: Remove from deployed builds; replace with an authenticated health check.
```

```text
HIGH:
File: backend/main.py
Issue: CORS allow_origins=["*"] with allow_credentials=True.
Action: Explicit origin list; disable credentials if unused.
```
