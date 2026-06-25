# CHEWS — Climate-Health Early Warning System

**Malaria Risk Prediction for Low-Resource Settings (Sierra Leone)**

A fast MVP prototype that takes environmental and community health inputs, predicts malaria risk levels (Low / Medium / High), and returns actionable advice for mothers and caregivers.


##  Project Structure

```
SafetySphere_CHEWS/
├── backend/
│   ├── main.py              # FastAPI application
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── index.html            # UI entry point
│   ├── styles.css            # Dark-mode design system
│   └── app.js                # Client-side logic
└── README.md
```

##  Quick Start

### 1. Backend (FastAPI)

```bash
# Create a virtual environment (recommended)
cd backend
python3 -m venv venv
source venv/bin/activate       # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Start the API server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at **http://127.0.0.1:8000**.  
Swagger docs: **http://127.0.0.1:8000/docs**

### 2. Frontend

Open `frontend/index.html` in your browser, **or** serve it with any static server:

```bash
# Option A — Python built-in server
cd frontend
python3 -m http.server 3000

# Then visit http://localhost:3000
```

---

##  API Endpoints

| Method | Path       | Description                        |
|--------|------------|------------------------------------|
| GET    | `/health`  | System health check                |
| POST   | `/predict` | Predict malaria risk               |
| POST   | `/ask`     | Ask the health assistant a question|

### POST `/predict` — Example

**Request:**
```json
{
  "rainfall": 80,
  "temperature": 30,
  "humidity": 75,
  "symptoms": 8
}
```

**Response:**
```json
{
  "risk_level": "High",
  "risk_score": 0.72,
  "advice": " High malaria risk detected...",
  "breakdown": {
    "rainfall": 0.841,
    "temperature": 0.731,
    "humidity": 0.731,
    "symptoms": 0.841
  }
}
```

---

## How It Works

1. **Weighted Rule-Based Scoring** — Each environmental factor is compared against a threshold and normalised via a sigmoid function, then combined using expert-assigned weights.
2. **Optional ML Model** — If scikit-learn is installed, a Logistic Regression model trained on synthetic data provides a secondary prediction.
3. **Advice Engine** — Maps the risk level to actionable, plain-language guidance for community health workers, mothers, and caregivers.

---

##  Tech Stack

- **Backend:** Python 3.10+, FastAPI, Pydantic, NumPy
- **ML:** scikit-learn Logistic Regression
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **No database required** — stateless API

---

*Built by SafetySphere for communities in Sierra Leone 🇸🇱*
