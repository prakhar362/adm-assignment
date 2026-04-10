"""
main.py
-------
FastAPI application for Customer Support Ticket Routing.

Endpoints:
  POST /api/tickets/route   — ingest a ticket, classify, route, persist, respond.
  GET  /api/tickets/{id}    — retrieve a ticket with its prediction and routing.
  GET  /api/health          — liveness / readiness check.
  GET  /api/model/info      — metadata about the loaded model.
"""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from database import init_db, get_db, Ticket, Prediction, RoutingDecision
from inference import TicketClassifier, BusinessRuleRouter, PredictionResult, RoutingResult

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton inference objects (loaded once at startup)
# ---------------------------------------------------------------------------
classifier = TicketClassifier()
router = BusinessRuleRouter()

# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown hooks)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB tables and load ML models at startup."""
    log.info("Initialising database …")
    init_db()
    log.info("Loading ML models …")
    classifier.load()
    log.info("🚀 Application ready.")
    yield
    log.info("Shutting down …")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Customer Support Ticket Router",
    description=(
        "Ingests customer support tickets, classifies them with a "
        "TF-IDF + LinearSVC model trained on the Bitext dataset, "
        "applies business rules, and returns a routing decision."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class TicketRequest(BaseModel):
    """Incoming ticket payload."""
    customer_name: str = Field(..., min_length=1, max_length=255, examples=["Jane Doe"])
    customer_email: str = Field(..., min_length=3, max_length=255, examples=["jane@example.com"])
    subject: str = Field(..., min_length=1, max_length=512, examples=["Order not delivered"])
    description: str = Field(
        ..., min_length=10, max_length=5000,
        examples=["I placed order #12345 three weeks ago and it still has not arrived. Please help."],
    )
    language: str = Field(default="en", max_length=10)
    source_channel: str = Field(default="api", max_length=50)


class PredictionResponse(BaseModel):
    predicted_category: str
    category_confidence: float
    predicted_intent: str
    intent_confidence: float
    model_version: str
    inference_time_ms: float
    top_categories: list[dict]


class RoutingResponse(BaseModel):
    assigned_queue: str
    priority: str
    escalated: bool
    reason: str


class TicketRouteResponse(BaseModel):
    """Full response returned after routing a ticket."""
    ticket_id: int
    status: str = "routed"
    prediction: PredictionResponse
    routing: RoutingResponse
    created_at: str


class TicketDetailResponse(BaseModel):
    """Response for GET /api/tickets/{id}."""
    ticket_id: int
    customer_name: str
    customer_email: str
    subject: str
    description: str
    language: str
    source_channel: str
    prediction: PredictionResponse | None
    routing: RoutingResponse | None
    created_at: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    database: str
    timestamp: str


class ModelInfoResponse(BaseModel):
    model_version: str
    metadata: dict | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/tickets/route",
    response_model=TicketRouteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest, classify, route, and persist a support ticket",
)
def route_ticket(payload: TicketRequest, db: Session = Depends(get_db)):
    """
    Main ticket ingestion endpoint.

    1. Persist the raw ticket.
    2. Run ML inference (category + intent).
    3. Apply business rules → queue + priority.
    4. Persist prediction and routing decision.
    5. Return the complete routing result.
    """
    # ---- 1. Save raw ticket ----
    ticket = Ticket(
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        subject=payload.subject,
        description=payload.description,
        language=payload.language,
        source_channel=payload.source_channel,
    )
    db.add(ticket)
    db.flush()  # get ticket.id without committing yet

    # ---- 2. ML inference ----
    combined_text = f"{payload.subject}. {payload.description}"
    pred: PredictionResult = classifier.predict(combined_text)

    # ---- 3. Business rules ----
    route: RoutingResult = router.route(pred, combined_text)

    # ---- 4. Persist prediction & routing ----
    prediction_row = Prediction(
        ticket_id=ticket.id,
        predicted_category=pred.predicted_category,
        predicted_intent=pred.predicted_intent,
        confidence=pred.category_confidence,
        intent_confidence=pred.intent_confidence,
        top_categories=json.dumps(pred.top_categories),
        model_version=pred.model_version,
        inference_time_ms=pred.inference_time_ms,
    )
    routing_row = RoutingDecision(
        ticket_id=ticket.id,
        assigned_queue=route.assigned_queue,
        priority=route.priority,
        escalated=int(route.escalated),
        reason=route.reason,
    )
    db.add(prediction_row)
    db.add(routing_row)
    db.commit()
    db.refresh(ticket)

    log.info(
        "Ticket #%d routed → queue=%s priority=%s category=%s (%.2f)",
        ticket.id,
        route.assigned_queue,
        route.priority,
        pred.predicted_category,
        pred.category_confidence,
    )

    # ---- 5. Response ----
    return TicketRouteResponse(
        ticket_id=ticket.id,
        status="routed",
        prediction=PredictionResponse(
            predicted_category=pred.predicted_category,
            category_confidence=pred.category_confidence,
            predicted_intent=pred.predicted_intent,
            intent_confidence=pred.intent_confidence,
            model_version=pred.model_version,
            inference_time_ms=pred.inference_time_ms,
            top_categories=pred.top_categories,
        ),
        routing=RoutingResponse(
            assigned_queue=route.assigned_queue,
            priority=route.priority,
            escalated=route.escalated,
            reason=route.reason,
        ),
        created_at=ticket.created_at.isoformat(),
    )


@app.get(
    "/api/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
    summary="Retrieve a ticket by ID",
)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """Look up a ticket and its associated prediction + routing decision."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket #{ticket_id} not found")

    pred_resp = None
    if ticket.prediction:
        p = ticket.prediction
        top_cats = []
        if p.top_categories:
            try:
                top_cats = json.loads(p.top_categories)
            except Exception:
                pass

        pred_resp = PredictionResponse(
            predicted_category=p.predicted_category,
            category_confidence=p.confidence,
            predicted_intent=p.predicted_intent or "",
            intent_confidence=p.intent_confidence or 0.0,
            model_version=p.model_version,
            inference_time_ms=p.inference_time_ms or 0.0,
            top_categories=top_cats,
        )

    route_resp = None
    if ticket.routing_decision:
        r = ticket.routing_decision
        route_resp = RoutingResponse(
            assigned_queue=r.assigned_queue,
            priority=r.priority,
            escalated=bool(r.escalated),
            reason=r.reason or "",
        )

    return TicketDetailResponse(
        ticket_id=ticket.id,
        customer_name=ticket.customer_name,
        customer_email=ticket.customer_email,
        subject=ticket.subject,
        description=ticket.description,
        language=ticket.language,
        source_channel=ticket.source_channel,
        prediction=pred_resp,
        routing=route_resp,
        created_at=ticket.created_at.isoformat(),
    )


@app.get(
    "/api/tickets",
    response_model=list[TicketDetailResponse],
    summary="Retrieve all tickets",
)
def get_tickets(db: Session = Depends(get_db), limit: int = 100):
    """Fetch the most recent tickets with their predictions and routing."""
    tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(limit).all()
    
    results = []
    for ticket in tickets:
        pred_resp = None
        if ticket.prediction:
            p = ticket.prediction
            top_cats = []
            if p.top_categories:
                try:
                    top_cats = json.loads(p.top_categories)
                except Exception:
                    pass

            pred_resp = PredictionResponse(
                predicted_category=p.predicted_category,
                category_confidence=p.confidence,
                predicted_intent=p.predicted_intent or "",
                intent_confidence=p.intent_confidence or 0.0,
                model_version=p.model_version,
                inference_time_ms=p.inference_time_ms or 0.0,
                top_categories=top_cats,
            )

        route_resp = None
        if ticket.routing_decision:
            r = ticket.routing_decision
            route_resp = RoutingResponse(
                assigned_queue=r.assigned_queue,
                priority=r.priority,
                escalated=bool(r.escalated),
                reason=r.reason or "",
            )

        results.append(TicketDetailResponse(
            ticket_id=ticket.id,
            customer_name=ticket.customer_name,
            customer_email=ticket.customer_email,
            subject=ticket.subject,
            description=ticket.description,
            language=ticket.language,
            source_channel=ticket.source_channel,
            prediction=pred_resp,
            routing=route_resp,
            created_at=ticket.created_at.isoformat(),
        ))
    return results

@app.get("/api/health", response_model=HealthResponse, summary="Health check")
def health_check():
    return HealthResponse(
        status="healthy",
        model_loaded=classifier._loaded,
        database="sqlite",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/model/info", response_model=ModelInfoResponse, summary="Model metadata")
def model_info():
    meta = None
    meta_path = Path("artifacts/model_metadata.json")
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
    return ModelInfoResponse(
        model_version=classifier.model_version,
        metadata=meta,
    )
