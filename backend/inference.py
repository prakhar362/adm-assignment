"""
inference.py
------------
Inference engine for the ticket-routing ML models.

Provides:
  - `TicketClassifier`: loads saved model artifacts and exposes a
    `.predict(text)` method that returns category, intent, and
    confidence scores.
  - `BusinessRuleRouter`: maps a prediction to a queue + priority
    using configurable business rules.
"""

import time
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

from train_model import clean_text  # reuse identical preprocessing

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths (must match train_model.py)
# ---------------------------------------------------------------------------
ARTIFACT_DIR = Path("artifacts")
CATEGORY_MODEL_PATH = ARTIFACT_DIR / "category_pipeline.pkl"
INTENT_MODEL_PATH = ARTIFACT_DIR / "intent_pipeline.pkl"
CATEGORY_ENCODER_PATH = ARTIFACT_DIR / "category_encoder.pkl"
INTENT_ENCODER_PATH = ARTIFACT_DIR / "intent_encoder.pkl"
METADATA_PATH = ARTIFACT_DIR / "model_metadata.json"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class PredictionResult:
    """Structured output from the classifier."""
    predicted_category: str
    category_confidence: float
    predicted_intent: str
    intent_confidence: float
    model_version: str
    inference_time_ms: float
    top_categories: list[dict] = field(default_factory=list)


@dataclass
class RoutingResult:
    """Structured output from the business-rule router."""
    assigned_queue: str
    priority: str       # low | medium | high | critical
    escalated: bool
    reason: str


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------
class TicketClassifier:
    """
    Loads serialised TF-IDF + LinearSVC pipelines and label encoders,
    then exposes `.predict(raw_text) -> PredictionResult`.
    """

    def __init__(self) -> None:
        self._loaded = False
        self.cat_pipe: Pipeline | None = None
        self.int_pipe: Pipeline | None = None
        self.cat_enc: LabelEncoder | None = None
        self.int_enc: LabelEncoder | None = None
        self.model_version: str = "unknown"

    # ---- lifecycle ----
    def load(self) -> None:
        """Load model artifacts from disk. Idempotent."""
        if self._loaded:
            return

        for path in (CATEGORY_MODEL_PATH, INTENT_MODEL_PATH,
                     CATEGORY_ENCODER_PATH, INTENT_ENCODER_PATH):
            if not path.exists():
                raise FileNotFoundError(
                    f"Model artifact not found: {path}. "
                    "Run `python train_model.py` first."
                )

        log.info("Loading model artifacts from %s/ …", ARTIFACT_DIR)
        self.cat_pipe = joblib.load(CATEGORY_MODEL_PATH)
        self.int_pipe = joblib.load(INTENT_MODEL_PATH)
        self.cat_enc = joblib.load(CATEGORY_ENCODER_PATH)
        self.int_enc = joblib.load(INTENT_ENCODER_PATH)

        if METADATA_PATH.exists():
            with open(METADATA_PATH) as f:
                meta = json.load(f)
            self.model_version = meta.get("model_version", "unknown")

        self._loaded = True
        log.info("Models loaded — version %s", self.model_version)

    # ---- prediction ----
    def predict(self, raw_text: str) -> PredictionResult:
        """
        Run inference on a single raw customer message.
        Returns a `PredictionResult` with category, intent, and confidences.
        """
        if not self._loaded:
            self.load()

        t0 = time.perf_counter()

        cleaned = clean_text(raw_text)

        # --- Category ---
        cat_proba = self.cat_pipe.predict_proba([cleaned])[0]
        cat_idx = int(np.argmax(cat_proba))
        cat_label = self.cat_enc.inverse_transform([cat_idx])[0]
        cat_conf = float(cat_proba[cat_idx])

        # all categories sorted by confidence (descending)
        all_indices = np.argsort(cat_proba)[::-1]
        top_categories = [
            {
                "category": self.cat_enc.inverse_transform([i])[0],
                "confidence": round(float(cat_proba[i]), 4),
            }
            for i in all_indices
        ]

        # --- Intent ---
        int_proba = self.int_pipe.predict_proba([cleaned])[0]
        int_idx = int(np.argmax(int_proba))
        int_label = self.int_enc.inverse_transform([int_idx])[0]
        int_conf = float(int_proba[int_idx])

        elapsed_ms = (time.perf_counter() - t0) * 1000

        return PredictionResult(
            predicted_category=cat_label,
            category_confidence=round(cat_conf, 4),
            predicted_intent=int_label,
            intent_confidence=round(int_conf, 4),
            model_version=self.model_version,
            inference_time_ms=round(elapsed_ms, 2),
            top_categories=top_categories,
        )


# ---------------------------------------------------------------------------
# Business-rule router
# ---------------------------------------------------------------------------

# Queue assignment map — maps each uppercase CATEGORY to a support queue
CATEGORY_QUEUE_MAP: dict[str, str] = {
    "ORDER":            "order-management",
    "SHIPPING":         "logistics-team",
    "DELIVERY":         "logistics-team",
    "REFUND":           "billing-disputes",
    "INVOICE":          "billing-disputes",
    "PAYMENT":          "billing-disputes",
    "ACCOUNT":          "account-services",
    "CONTACT":          "general-support",
    "FEEDBACK":         "customer-success",
    "CANCELLATION":     "retention-team",
    "CANCEL":           "retention-team",
    "SUBSCRIPTION":     "retention-team",
    "NEWSLETTER":       "marketing-ops",
}

# Keywords that indicate urgency
ESCALATION_KEYWORDS = {
    "urgent", "emergency", "immediately", "asap", "critical",
    "broken", "fraud", "unauthorized", "hacked", "legal",
    "lawyer", "attorney", "lawsuit", "threatening", "scam",
}


class BusinessRuleRouter:
    """
    Applies deterministic business rules on top of ML predictions
    to decide the final queue and priority.
    """

    @staticmethod
    def route(
        prediction: PredictionResult,
        raw_text: str,
    ) -> RoutingResult:
        category = prediction.predicted_category.upper()
        confidence = prediction.category_confidence

        # ---- Queue assignment ----
        queue = CATEGORY_QUEUE_MAP.get(category, "general-support")

        # ---- Priority logic ----
        #   confidence < 0.4  → uncertain → escalate to human
        #   escalation keywords → critical
        #   category-specific boosts (REFUND, CANCELLATION → high)
        priority = "medium"
        escalated = False
        reasons: list[str] = []

        text_lower = raw_text.lower()
        has_escalation_kw = bool(ESCALATION_KEYWORDS & set(text_lower.split()))

        if has_escalation_kw:
            priority = "critical"
            escalated = True
            reasons.append("Escalation keyword detected in ticket text.")

        if confidence < 0.40:
            priority = "high" if priority != "critical" else priority
            escalated = True
            reasons.append(
                f"Low model confidence ({confidence:.2f}); "
                "routing for human review."
            )

        if category in ("REFUND", "CANCELLATION", "CANCEL") and priority == "medium":
            priority = "high"
            reasons.append(f"Category '{category}' auto-elevated to high priority.")

        if not reasons:
            reasons.append(
                f"Standard routing — category '{category}' "
                f"(confidence {confidence:.2f})."
            )

        return RoutingResult(
            assigned_queue=queue,
            priority=priority,
            escalated=escalated,
            reason=" | ".join(reasons),
        )
