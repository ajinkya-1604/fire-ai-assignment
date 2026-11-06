"""
Standardized performance, statistical, and latency metrics utilities.
Provides explainable calculations for benchmarks and evaluation reports.
"""

from decimal import Decimal
from typing import Dict, List, Any
import numpy as np


def calculate_classification_metrics(
    y_true: List[int], y_pred: List[int]
) -> Dict[str, float]:
    """
    Calculate classification metrics:
    TP, FP, TN, FN, Precision, Recall, F1, Detection Rate, False Alarm Rate.

    Args:
        y_true: List of ground-truth binary labels (1 = anomaly/corrupted, 0 = clean)
        y_pred: List of predicted binary labels (1 = anomaly/corrupted, 0 = clean)

    Returns:
        Dictionary containing all evaluation metrics.
    """
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)

    total_positives = tp + fn
    total_negatives = tn + fp
    total_samples = len(y_true)

    # Precision = TP / (TP + FP)
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0

    # Recall / Detection Rate = TP / (TP + FN)
    recall = (tp / total_positives) if total_positives > 0 else 0.0
    detection_rate = recall

    # False Alarm Rate (Fall-out) = FP / (FP + TN)
    false_alarm_rate = (fp / total_negatives) if total_negatives > 0 else 0.0

    # F1 Score = 2 * (Precision * Recall) / (Precision + Recall)
    f1 = (
        (2.0 * precision * recall / (precision + recall))
        if (precision + recall) > 0
        else 0.0
    )

    accuracy = ((tp + tn) / total_samples) if total_samples > 0 else 0.0

    return {
        "total_samples": float(total_samples),
        "tp": float(tp),
        "fp": float(fp),
        "tn": float(tn),
        "fn": float(fn),
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "detection_rate": round(detection_rate, 4),
        "false_alarm_rate": round(false_alarm_rate, 4),
    }


def calculate_latency_metrics(latencies_ms: List[float]) -> Dict[str, float]:
    """
    Calculate summary latency metrics from a list of latencies in milliseconds.

    Args:
        latencies_ms: List of elapsed execution times in milliseconds.

    Returns:
        Dictionary with count, mean, median, p95, min, max.
    """
    if not latencies_ms:
        return {
            "count": 0.0,
            "mean_ms": 0.0,
            "median_ms": 0.0,
            "p95_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
        }

    arr = np.array(latencies_ms, dtype=float)
    return {
        "count": float(len(arr)),
        "mean_ms": round(float(np.mean(arr)), 3),
        "median_ms": round(float(np.median(arr)), 3),
        "p95_ms": round(float(np.percentile(arr, 95)), 3),
        "min_ms": round(float(np.min(arr)), 3),
        "max_ms": round(float(np.max(arr)), 3),
    }


def format_currency_inr(amount: Decimal | float | int) -> str:
    """
    Format a numeric amount according to Indian numbering convention (Lakhs, Crores).
    Example: 1250000 -> ₹12,50,000
    """
    if amount is None:
        return "₹0.00"

    # Convert to Decimal for exact string representation
    if not isinstance(amount, Decimal):
        d = Decimal(str(amount))
    else:
        d = amount

    is_negative = d < 0
    d = abs(d)

    parts = f"{d:.2f}".split(".")
    integer_part = parts[0]
    decimal_part = parts[1]

    if len(integer_part) <= 3:
        formatted_int = integer_part
    else:
        last3 = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_int = ",".join(groups) + "," + last3

    result = f"₹{formatted_int}.{decimal_part}"
    return f"-{result}" if is_negative else result

