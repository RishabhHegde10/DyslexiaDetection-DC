from pathlib import Path
import logging
import sys
import joblib

logger = logging.getLogger(__name__)

# Backward-compatibility safeguard for scikit-learn Cython loss unpickling
try:
    import sklearn._loss._loss
    if '_loss' not in sys.modules:
        sys.modules['_loss'] = sklearn._loss._loss
except Exception:
    pass

# ------------------ LOAD MODEL ------------------
def load_model():
    candidates = [
        Path("models/model_behavior.pkl"),
        Path("models/model.pkl"),
    ]

    for p in candidates:
        if p.exists():
            logger.info(f"Loading model: {p}")
            return joblib.load(p)

    raise FileNotFoundError("No model file found")

# ------------------ TRANSFORM INPUT ------------------
def transform_input(data):
    def safe_float(value, default=0.0):
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"", "no", "null", "none", "nan", "n/a"}:
                return default
            try:
                return float(cleaned)
            except (TypeError, ValueError):
                return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def safe_int(value, default=0):
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"", "no", "null", "none", "nan", "n/a"}:
                return default
            try:
                return int(float(cleaned))
            except (TypeError, ValueError):
                return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    total_errors = safe_int(data.get("total_errors", 0))
    accuracy = safe_float(data.get("overall_accuracy", 0.0))
    typing_speed = safe_float(data.get("typing_speed", 0.0))

    total_hits = max(1, 100 - total_errors)
    total_clicks = typing_speed * 10

    # total_score must align with training schema:
    # [overall_accuracy, total_errors, total_hits, total_score, total_clicks, error_rate, efficiency]
    total_score = safe_float(data.get("total_score"), max(0.0, total_hits - total_errors))

    error_rate = total_errors / (total_hits + total_errors + 1)
    efficiency = total_hits / (total_clicks + 1)

    features = [
        accuracy,
        total_errors,
        total_hits,
        total_score,
        total_clicks,
        error_rate,
        efficiency
    ]

    logger.info(
        "Final features [overall_accuracy, total_errors, total_hits, total_score, total_clicks, error_rate, efficiency]: %s",
        features,
    )
    logger.info("Feature length: %s", len(features))

    return features

# ------------------ NORMALIZE PREDICTION ------------------
def normalize_prediction(raw_prediction):
    """
    Supports numeric model outputs (0/1) and string labels (e.g., Yes/No, High/Low).
    Returns (prediction_int, risk_level).
    """
    if isinstance(raw_prediction, str):
        label = raw_prediction.strip().lower()
        high_labels = {"yes", "high", "1", "true", "positive", "risk"}
        prediction_int = 1 if label in high_labels else 0
    else:
        try:
            prediction_int = 1 if float(raw_prediction) >= 1 else 0
        except (TypeError, ValueError):
            prediction_int = 0

    risk_level = "high" if prediction_int == 1 else "low"
    return prediction_int, risk_level
