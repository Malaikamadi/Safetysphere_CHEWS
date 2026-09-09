# CHEWS user guide

**Audience:** UNICEF evaluators, demonstration users, and (later) health workers.  
**Product today:** an **early-warning prototype**. It does **not** diagnose malaria, replace a clinician, or confirm a real outbreak.

If you are viewing a hosted demo, start at `login.html`. Roles are a **display switch** stored in the browser. They are not verified by the server.

---

## What the result does **not** mean

- **Low / Medium / High** on `/predict` is a **heuristic score**, not a lab result.  
- Live Forecast / Surge climate values remain prototype constants. Malaria **case counts** overlay DHIS2 only after `POST /api/dhis2/ingest` (mock or live). Until then they stay hardcoded.  
- Situation Room maps, sensors, and “digital twins” are **simulated**.  
- The chat assistant **matches keywords**; it is not a doctor and not a large language model.  
- The facility map shows **real MoH facility locations**. It does **not** show real-time bed occupancy or staffing.

Seek in-person care for fever in children, pregnancy, convulsions, difficulty breathing, or any emergency. Call local emergency services where they exist.

---

## Mothers / caregivers

The current MVP is built as **health-system dashboards**, not a consumer app store product. There is no dedicated “mother account.”

**If a facilitator shows you the Point of Care or CHW pages:**

1. Open `point-of-care.html` or `chw.html` (from login, choose Health Worker).  
2. Enter **symptoms** from the provided list (for example fever, headache). Do not enter the child’s name, address, or phone number.  
3. Run triage. Read the colour (Green / Yellow / Orange / Red) as **demo guidance only**.  
4. Follow the written actions **and** go to a real clinic if the child is unwell.

**Chat (`/poc/ask`):** type a short question such as “how to prevent malaria”. Answers are canned public-health text.

You cannot “run a malaria outbreak prediction” as a parent in this UI. Ignore any score that appears without a health worker explaining it.

---

## Community health workers

### Entering information

- **Triage:** select symptoms and patient group; optional climate risk sliders if the page shows them (they default to 0).  
- **Do not** treat POST `/predict` climate fields as something you must collect in the field for the Healthcare Forecast page — that page is **view-only** (area and disease filters only).

### Running a prediction (demo / technical)

If you use OpenAPI (`/docs`) `POST /predict`, you are feeding **hypothetical** rainfall, temperature, humidity, and case counts into a **rule engine**.

### Understanding Low / Medium / High

From `risk_engine.py`:

| Level | Score | Intended meaning in the prototype |
| ----- | ----- | --------------------------------- |
| Low | below 0.30 | Heuristic composite in the “routine” band |
| Medium | 0.30–0.60 | Elevated heuristic composite |
| High | above 0.60 | Highest heuristic band |

Advice strings (ITNs, IRS, RDTs) are **generic programme reminders**, not an authorised MoH order.

### Healthcare Facility Explorer

1. Open Healthcare Readiness.  
2. Use the map/list of MoH facilities.  
3. Missing beds/power/water means **the extract does not contain that field**, not that the facility has zero.

### Forecast and Surge tabs

1. Choose disease and area.  
2. Wait for refresh (~60 seconds in `healthcare.js`).  
3. Interpret as **illustrative pressure**, not a MoH bulletin.

### Early warning / Flood Atlas

Flood colours mix a **static zone catalogue** with **weather fetch or simulated rain**. Confirm with NDMA / local observation before any community action.

### Errors

- Blank map: check network; API must be reachable at `/api`.  
- “Facility not found”: bad id.  
- Assistant “I can help with…”: your phrase did not match a keyword.  
- Login loop: set a role on `login.html`; technical default is admin if localStorage is empty (`getRole()`).

---

## Administrators / technical users

### Operate the demo

1. Start backend and frontend ([DEPLOYMENT.md](DEPLOYMENT.md)).  
2. Open `login.html`, pick a role (changes sidebar only).  
3. Command Centre (`index.html`) loads **Situation Room mock APIs**.  
4. Healthcare MFL is the **real coordinate registry**.  
5. `ai-models.html` is a catalogue page; live `/api/health` from that page is **mis-pathed** relative to `GET /health`.

### What you can demonstrate to an evaluator

- Map of 1,615 facilities with honest “not assessed” operational fields.  
- Rule-based `/predict` in Swagger.  
- View-only forecast/surge JSON.  
- Flood dashboard movement (weather or jitter).  
- That sklearn endpoints exist **and** that community-flood is scientifically unsafe (model card).

### What you should not demonstrate as production

- Partner “Bearer” example on `partner.html` — the API does not check it.  
- Perfect ML metrics.  
- Situation Room as live national surveillance.

### Handling errors

- Startup prints `[CHEWS] Startup warnings` if imports fail.  
- `/api/debug` should be **disabled** before any public URL is shared.

---

## Understanding the advice

Recommendations are **static lists** keyed by risk band (`risk_engine.RECOMMENDATIONS`) or triage templates (`triage_assistant.TRANSLATIONS`). They are not personalised to a named patient or facility stock level (live MFL has no stock).

---

## Languages

`GET /api/poc/languages` reflects `TRANSLATIONS` in `triage_assistant.py`: **en**, **kri** (Krio), **fr**. Unknown language codes fall back to English. Only triage template strings are translated, not the whole dashboard.
