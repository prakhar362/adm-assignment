"""
train_model.py
--------------
End-to-end training pipeline:
  1. Loads the Bitext customer-support dataset from Hugging Face.
  2. Preprocesses text (lowercasing, punctuation removal, stopword removal, lemmatization).
  3. Trains a TF-IDF + LinearSVC pipeline for *category* classification.
  4. Trains a TF-IDF + LinearSVC pipeline for *intent* classification.
  5. Evaluates on a held-out test set and prints a classification report.
  6. Serialises the trained pipelines + label encoders to `artifacts/`.

Usage:
    python train_model.py
"""

import os
import re
import json
import time
import logging
from pathlib import Path

import numpy as np
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import LabelEncoder
import joblib

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ARTIFACT_DIR = Path("artifacts")
CATEGORY_MODEL_PATH = ARTIFACT_DIR / "category_pipeline.pkl"
INTENT_MODEL_PATH = ARTIFACT_DIR / "intent_pipeline.pkl"
CATEGORY_ENCODER_PATH = ARTIFACT_DIR / "category_encoder.pkl"
INTENT_ENCODER_PATH = ARTIFACT_DIR / "intent_encoder.pkl"
METADATA_PATH = ARTIFACT_DIR / "model_metadata.json"

DATASET_NAME = "bitext/Bitext-customer-support-llm-chatbot-training-dataset"
TEST_SIZE = 0.15
RANDOM_STATE = 42

# ---------------------------------------------------------------------------
# NLTK bootstrap
# ---------------------------------------------------------------------------

def _ensure_nltk_data() -> None:
    """Download required NLTK data packages if missing."""
    for pkg in ("stopwords", "wordnet", "omw-1.4"):
        try:
            nltk.data.find(f"corpora/{pkg}")
        except LookupError:
            nltk.download(pkg, quiet=True)


# ---------------------------------------------------------------------------
# Text preprocessing
# ---------------------------------------------------------------------------
_lemmatizer: WordNetLemmatizer | None = None
_stop_words: set | None = None


def _init_nlp_resources() -> None:
    global _lemmatizer, _stop_words
    _ensure_nltk_data()
    _lemmatizer = WordNetLemmatizer()
    _stop_words = set(stopwords.words("english"))


def clean_text(text: str) -> str:
    """
    Normalise a raw customer message:
      - lowercase
      - strip URLs, emails, and special characters
      - remove stopwords
      - lemmatize
    """
    if _lemmatizer is None or _stop_words is None:
        _init_nlp_resources()

    text = text.lower()
    text = re.sub(r"http\S+|www\.\S+", " ", text)            # URLs
    text = re.sub(r"\S+@\S+", " ", text)                      # emails
    text = re.sub(r"[^a-z\s]", " ", text)                     # non-alpha
    text = re.sub(r"\s+", " ", text).strip()                   # collapse whitespace

    tokens = [
        _lemmatizer.lemmatize(tok)
        for tok in text.split()
        if tok not in _stop_words and len(tok) > 1
    ]
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_and_prepare() -> tuple[list[str], list[str], list[str]]:
    """
    Returns (texts, categories, intents) from the Bitext dataset.
    """
    log.info("Loading dataset from Hugging Face: %s", DATASET_NAME)
    ds = load_dataset(DATASET_NAME, split="train")
    log.info("Dataset loaded — %d samples", len(ds))

    texts: list[str] = []
    categories: list[str] = []
    intents: list[str] = []

    for row in ds:
        raw = row.get("instruction", "") or ""
        cat = row.get("category", "") or ""
        intent = row.get("intent", "") or ""
        if not raw.strip() or not cat.strip():
            continue
        texts.append(clean_text(raw))
        categories.append(cat.strip().upper())
        intents.append(intent.strip().lower())

    log.info("After cleaning — %d usable samples", len(texts))
    log.info("Unique categories: %d | Unique intents: %d",
             len(set(categories)), len(set(intents)))
    return texts, categories, intents


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

def build_pipeline() -> Pipeline:
    """
    TF-IDF → CalibratedClassifierCV(LinearSVC) pipeline.
    CalibratedClassifierCV wraps LinearSVC to expose `predict_proba`.
    """
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=30_000,
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=2,
            max_df=0.95,
        )),
        ("clf", CalibratedClassifierCV(
            estimator=LinearSVC(
                C=1.0,
                max_iter=5000,
                class_weight="balanced",
            ),
            cv=3,
        )),
    ])


def train_and_evaluate(
    texts: list[str],
    labels: list[str],
    label_name: str,
) -> tuple[Pipeline, LabelEncoder, dict]:
    """
    Train a pipeline for a given label set, evaluate, and return:
      (trained_pipeline, label_encoder, metrics_dict)
    """
    le = LabelEncoder()
    y = le.fit_transform(labels)

    X_train, X_test, y_train, y_test = train_test_split(
        texts, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    log.info("[%s] Train size: %d | Test size: %d", label_name, len(X_train), len(X_test))

    pipe = build_pipeline()

    log.info("[%s] Training pipeline …", label_name)
    t0 = time.perf_counter()
    pipe.fit(X_train, y_train)
    train_secs = time.perf_counter() - t0
    log.info("[%s] Training completed in %.1f s", label_name, train_secs)

    # --- Evaluation ---
    y_pred = pipe.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    report = classification_report(
        y_test, y_pred,
        target_names=le.classes_,
        output_dict=True,
    )
    report_str = classification_report(
        y_test, y_pred,
        target_names=le.classes_,
    )
    log.info("[%s] Test accuracy: %.4f", label_name, acc)
    print(f"\n{'='*60}")
    print(f"  Classification Report — {label_name}")
    print(f"{'='*60}")
    print(report_str)

    # Cross-val for robustness check
    cv_scores = cross_val_score(pipe, texts, le.transform(labels), cv=5, scoring="accuracy")
    log.info("[%s] 5-fold CV accuracy: %.4f ± %.4f", label_name, cv_scores.mean(), cv_scores.std())

    metrics = {
        "label": label_name,
        "test_accuracy": round(acc, 4),
        "cv_mean_accuracy": round(float(cv_scores.mean()), 4),
        "cv_std": round(float(cv_scores.std()), 4),
        "train_time_seconds": round(train_secs, 2),
        "n_classes": len(le.classes_),
        "classes": le.classes_.tolist(),
        "per_class": {
            cls: {
                "precision": round(report[cls]["precision"], 4),
                "recall": round(report[cls]["recall"], 4),
                "f1-score": round(report[cls]["f1-score"], 4),
            }
            for cls in le.classes_
        },
    }
    return pipe, le, metrics


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def save_artifacts(
    cat_pipe: Pipeline,
    cat_enc: LabelEncoder,
    int_pipe: Pipeline,
    int_enc: LabelEncoder,
    metadata: dict,
) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(cat_pipe, CATEGORY_MODEL_PATH)
    joblib.dump(cat_enc, CATEGORY_ENCODER_PATH)
    joblib.dump(int_pipe, INTENT_MODEL_PATH)
    joblib.dump(int_enc, INTENT_ENCODER_PATH)

    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    log.info("Artifacts saved to %s/", ARTIFACT_DIR)
    for p in ARTIFACT_DIR.iterdir():
        size_kb = p.stat().st_size / 1024
        log.info("  %-30s  %.1f KB", p.name, size_kb)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _init_nlp_resources()

    texts, categories, intents = load_and_prepare()

    # ---- Category model ----
    cat_pipe, cat_enc, cat_metrics = train_and_evaluate(texts, categories, "CATEGORY")

    # ---- Intent model ----
    int_pipe, int_enc, int_metrics = train_and_evaluate(texts, intents, "INTENT")

    # ---- Save ----
    metadata = {
        "model_version": "v1.0.0",
        "dataset": DATASET_NAME,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "category": cat_metrics,
        "intent": int_metrics,
    }
    save_artifacts(cat_pipe, cat_enc, int_pipe, int_enc, metadata)
    log.info("✅ Training pipeline complete.")


if __name__ == "__main__":
    main()
