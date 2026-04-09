## 🎯 Customer Support Ticket Routing System

An end-to-end ML-powered backend that automatically classifies customer support tickets and routes them to the correct team queue using NLP — built entirely from scratch with no black-box APIs.

---

## 📌 Problem Statement

Enterprise support teams waste hours manually reading, categorizing, and routing incoming customer tickets to the right department. Misrouted tickets lead to slower resolution times, frustrated customers, and agent burnout.

## 💡 Solution

This system automates the entire triage pipeline:

1. **Ingests** a raw support ticket via REST API.
2. **Classifies** the ticket into one of **11 categories** and **27 intents** using a custom-trained NLP model.
3. **Applies business rules** to assign a queue, priority level, and escalation flag.
4. **Persists** the full decision trail (ticket → prediction → routing) to SQLite.
5. **Returns** a structured JSON routing decision in real time.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      FastAPI Server                              │
│                                                                  │
│  POST /api/tickets/route                                         │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────┐       │
│  │  Ticket   │───▶│   NLP Engine  │───▶│  Business Rules   │      │
│  │  Payload  │    │  TF-IDF +    │    │  Queue + Priority │      │
│  │           │    │  LinearSVC   │    │  + Escalation     │      │
│  └──────────┘    └──────────────┘    └───────┬───────────┘       │
│                                              │                   │
│                                              ▼                   │
│                                     ┌──────────────┐             │
│                                     │   SQLite DB   │             │
│                                     │  3 tables     │             │
│                                     └──────────────┘             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🧠 ML Pipeline

| Component | Detail |
|-----------|--------|
| **Dataset** | [Bitext Customer Support LLM Chatbot Training Dataset](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset) — 26,872 samples |
| **Preprocessing** | Lowercase → URL/email removal → punctuation strip → stopword removal → lemmatization (NLTK) |
| **Vectorizer** | TF-IDF (30K features, bigrams, sublinear TF) |
| **Classifier** | CalibratedClassifierCV(LinearSVC) — outputs calibrated probabilities |
| **Evaluation** | Stratified train/test split (85/15) + 5-fold cross-validation |

### Model Performance

| Model | Test Accuracy | 5-Fold CV |
|-------|:------------:|:---------:|
| **Category** (11 classes) | 99.85% | 99.72% ± 0.06% |
| **Intent** (27 classes) | 99.33% | 99.20% ± 0.12% |

### 11 Categories

`ACCOUNT` · `CANCEL` · `CONTACT` · `DELIVERY` · `FEEDBACK` · `INVOICE` · `ORDER` · `PAYMENT` · `REFUND` · `SHIPPING` · `SUBSCRIPTION`

### 27 Intents

`cancel_order` · `change_order` · `change_shipping_address` · `check_cancellation_fee` · `check_invoice` · `check_payment_methods` · `check_refund_policy` · `complaint` · `contact_customer_service` · `contact_human_agent` · `create_account` · `delete_account` · `delivery_options` · `delivery_period` · `edit_account` · `get_invoice` · `get_refund` · `newsletter_subscription` · `payment_issue` · `place_order` · `recover_password` · `registration_problems` · `review` · `set_up_shipping_address` · `switch_account` · `track_order` · `track_refund`

---

## 🗄️ Database Schema (SQLite)

**3 tables** with foreign-key relationships:

```
tickets                 predictions               routing_decisions
┌─────────────────┐     ┌─────────────────────┐   ┌────────────────────┐
│ id (PK)         │◄────│ ticket_id (FK)       │   │ ticket_id (FK)     │
│ customer_name   │     │ predicted_category   │   │ assigned_queue     │
│ customer_email  │     │ predicted_intent     │   │ priority           │
│ subject         │     │ confidence           │   │ escalated          │
│ description     │     │ model_version        │   │ reason             │
│ language        │     │ inference_time_ms    │   │ created_at         │
│ source_channel  │     │ created_at           │   └────────────────────┘
│ created_at      │     └─────────────────────┘
└─────────────────┘
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/tickets/route` | Ingest → Classify → Route → Persist → Respond |
| `GET` | `/api/tickets/{id}` | Retrieve a ticket with prediction & routing |
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/model/info` | Model version and training metadata |

### Request Body — `POST /api/tickets/route`

```json
{
  "customer_name": "Rahul Sharma",
  "customer_email": "rahul@gmail.com",
  "subject": "My PC is not working after software update",
  "description": "After I installed the latest update on my PC, the system keeps crashing and I cannot access my account settings.",
  "language": "en",
  "source_channel": "api"
}
```

### Response — `201 Created`

```json
{
  "ticket_id": 4,
  "status": "routed",
  "prediction": {
    "predicted_category": "ACCOUNT",
    "category_confidence": 0.9712,
    "predicted_intent": "recover_password",
    "intent_confidence": 0.3115,
    "model_version": "v1.0.0",
    "inference_time_ms": 5.4,
    "top_categories": [
      { "category": "ACCOUNT", "confidence": 0.9712 },
      { "category": "SHIPPING", "confidence": 0.0142 },
      { "category": "CONTACT", "confidence": 0.0109 },
      { "category": "ORDER", "confidence": 0.0011 },
      { "category": "PAYMENT", "confidence": 0.0009 },
      { "category": "REFUND", "confidence": 0.0005 },
      { "category": "FEEDBACK", "confidence": 0.0004 },
      { "category": "INVOICE", "confidence": 0.0004 },
      { "category": "SUBSCRIPTION", "confidence": 0.0003 },
      { "category": "CANCEL", "confidence": 0.0001 },
      { "category": "DELIVERY", "confidence": 0.0001 }
    ]
  },
  "routing": {
    "assigned_queue": "account-services",
    "priority": "medium",
    "escalated": false,
    "reason": "Standard routing — category 'ACCOUNT' (confidence 0.97)."
  },
  "created_at": "2026-04-09T04:40:02.160858"
}
```

---

## ⚙️ Business Rules

### Queue Assignment

| Category | Queue |
|----------|-------|
| ORDER | `order-management` |
| SHIPPING / DELIVERY | `logistics-team` |
| REFUND / INVOICE / PAYMENT | `billing-disputes` |
| ACCOUNT | `account-services` |
| CONTACT | `general-support` |
| FEEDBACK | `customer-success` |
| CANCEL / SUBSCRIPTION | `retention-team` |

### Priority Escalation

| Condition | Action |
|-----------|--------|
| Escalation keywords detected (`urgent`, `fraud`, `hacked`, `lawyer`, etc.) | Priority → **critical**, escalated = true |
| Model confidence < 0.40 | Priority → **high**, flagged for human review |
| Category is REFUND or CANCEL | Priority → **high** |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| API Framework | FastAPI + Uvicorn |
| Database | SQLite (via SQLAlchemy ORM) |
| ML / NLP | scikit-learn (TF-IDF + LinearSVC) |
| Text Processing | NLTK (stopwords, lemmatizer) |
| Dataset | HuggingFace `datasets` library |
| Serialization | joblib (.pkl artifacts) |

---

## 📂 Project Structure

```
adm_ca/
├── README.md
├── steps.txt
├── frontend/              # (UI — coming soon)
└── backend/
    ├── requirements.txt
    ├── database.py        # SQLAlchemy ORM — 3 tables
    ├── train_model.py     # Dataset fetch → preprocess → train → evaluate → save
    ├── inference.py       # Model loader + business-rule router
    ├── main.py            # FastAPI application (4 endpoints)
    ├── artifacts/         # Generated after training
    │   ├── category_pipeline.pkl
    │   ├── category_encoder.pkl
    │   ├── intent_pipeline.pkl
    │   ├── intent_encoder.pkl
    │   └── model_metadata.json
    └── ticket_routing.db  # Generated on first server start
```

---

## 🚀 Quick Start

See [`steps.txt`](steps.txt) for the full terminal walkthrough.

```bash
# 1. Navigate to backend
cd backend

# 2. Create & activate virtual environment
python -m venv venv
.\venv\Scripts\Activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Train the model (~30 seconds)
python train_model.py

# 5. Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 6. Open Swagger UI
# http://localhost:8000/docs
```

---

## 📝 License

This project is for educational and demonstration purposes.

---

*Built with Python, FastAPI, scikit-learn, and NLTK.*
