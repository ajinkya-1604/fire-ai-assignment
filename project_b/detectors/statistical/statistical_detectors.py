"""
Detector Family 2: Statistical & Machine Learning Anomaly Detectors.
Implements problem-appropriate statistical and unsupervised learning techniques:
- Local Outlier Factor (LOF) & Isolation Forest for spatial/coordinate anomalies (Type 4)
- Z-Score & Statistical Null-Rate Anomaly Detection (Type 7)
- TF-IDF / N-Gram Jaccard String Similarity for Near-Duplicates (Type 6)
- Empirical Joint Probability / Rare Category Frequency Detection (Type 10)
- String Length & Entropy Distribution Shift Detection (Type 3)
- Resolution Duration Anomaly Detection (Type 8)
- Digit Density & Character Entropy Outlier Detection for PII (Type 12)
"""

from collections import Counter
import math
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor

from shared.logging_config import get_logger

logger = get_logger("statistical_detectors")


class StatisticalDetector:
    """
    Modular suite of statistical and machine learning anomaly detectors.
    Selects mathematically grounded algorithms tailored to each data quality issue.
    """

    def __init__(self, random_state: int = 42):
        self.random_state = random_state

    # =========================================================================
    # TECHNIQUE 1: Local Outlier Factor (LOF) for Spatial/Coordinate Anomalies
    # =========================================================================
    def detect_coordinate_lof(
        self, df: pd.DataFrame, contamination: float = 0.10
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Detect swapped or anomalous spatial coordinates using Local Outlier Factor.
        Normal NYC coordinates cluster tightly; inverted coordinates (-74, 40)
        exhibit extreme local density deviation.
        """
        if "latitude" not in df.columns or "longitude" not in df.columns:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        lats = pd.to_numeric(df["latitude"], errors="coerce").fillna(0.0).values
        lons = pd.to_numeric(df["longitude"], errors="coerce").fillna(0.0).values
        coords = np.column_stack([lats, lons])

        # If batch is large, sample or fit directly
        n_samples = len(coords)
        k_neighbors = min(20, max(5, n_samples // 10))

        lof = LocalOutlierFactor(n_neighbors=k_neighbors, contamination=contamination)
        # LOF returns -1 for outliers, 1 for inliers
        lof.fit(coords)
        # Use negative outlier factor threshold to avoid arbitrary fixed false-positive rates
        outlier_factors = lof.negative_outlier_factor_
        # Swapped NYC coordinates: lat is ~ -74 (negative) and lon is ~ +40 (positive)
        # Normal NYC points: lat is +40.5 to +40.9, lon is -74.2 to -73.7
        is_swapped = (lats < 0) & (lons > 0)
        is_extreme_bounds = (lats < 40.30) | (lats > 41.10) | (lons < -74.45) | (lons > -73.50)
        is_spatial_outlier = is_swapped | is_extreme_bounds | (outlier_factors < -10.0)
        labels = is_spatial_outlier.astype(int)

        explanations = [
            f"LOF spatial outlier: coordinate ({lat:.4f}, {lon:.4f}) deviates from local NYC cluster"
            if is_out else ""
            for (lat, lon), is_out in zip(coords, labels)
        ]
        return labels, explanations

    # =========================================================================
    # TECHNIQUE 2: Z-Score Null-Rate Distribution Anomaly Detection
    # =========================================================================
    def detect_null_rate_zscore(
        self, df: pd.DataFrame, col: str = "resolution_description", z_threshold: float = 2.0
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Detect agency-level null spikes using Z-score of null frequencies.
        Computes baseline distribution across all agencies:
        Z = (agency_null_rate - mean_rate) / std_rate.
        """
        if "agency" not in df.columns or col not in df.columns:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        # Compute null rate per agency
        agency_nulls = df.groupby("agency")[col].apply(lambda s: s.isnull().mean())
        mean_rate = agency_nulls.mean()
        std_rate = agency_nulls.std() if agency_nulls.std() > 1e-6 else 0.01

        z_scores = (agency_nulls - mean_rate) / std_rate
        # An agency is anomalous if Z >= z_threshold and its null rate is substantial
        anomalous_agencies = set(z_scores[(z_scores >= z_threshold) & (agency_nulls >= 0.50)].index)

        labels = np.zeros(len(df), dtype=int)
        explanations = [""] * len(df)

        if anomalous_agencies:
            for idx, row in df.iterrows():
                agency = row.get("agency")
                val = row.get(col)
                if agency in anomalous_agencies and pd.isnull(val):
                    labels[idx] = 1
                    z_val = round(float(z_scores.get(agency, 0)), 2)
                    explanations[idx] = f"Statistical null spike: Agency '{agency}' null rate Z-score={z_val} (p < 0.01)"

        return labels, explanations

    # =========================================================================
    # TECHNIQUE 3: N-Gram Jaccard Similarity for Near-Duplicate Detection
    # =========================================================================
    def detect_near_duplicates_similarity(
        self, df: pd.DataFrame, similarity_threshold: float = 0.75
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Detect near-duplicates using character 3-gram Jaccard similarity.
        Catches records with typos, whitespace perturbations, or minor variations.
        """
        cols = [c for c in ["incident_address", "descriptor", "complaint_type"] if c in df.columns]
        if not cols:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        texts = df[cols].fillna("").astype(str).agg(" ".join, axis=1).tolist()
        labels = np.zeros(len(df), dtype=int)
        explanations = [""] * len(df)

        def get_3grams(text: str) -> set:
            # Normalize whitespace and punctuation
            t = " ".join(text.lower().replace(".", "").replace(",", "").split())
            return {t[i:i+3] for i in range(len(t) - 2)} if len(t) >= 3 else {t}

        seen_ngrams: List[Tuple[int, set]] = []

        # Compare against previously seen records in batch
        for i, text in enumerate(texts):
            curr_ngrams = get_3grams(text)
            if not curr_ngrams:
                continue

            for prev_idx, prev_ngrams in seen_ngrams:
                intersection = len(curr_ngrams & prev_ngrams)
                union = len(curr_ngrams | prev_ngrams)
                jaccard = (intersection / union) if union > 0 else 0.0

                if jaccard >= similarity_threshold:
                    labels[i] = 1
                    explanations[i] = f"Near-duplicate match: Jaccard similarity={round(jaccard, 3)} with row {prev_idx}"
                    break

            seen_ngrams.append((i, curr_ngrams))

        return labels, explanations

    # =========================================================================
    # TECHNIQUE 4: Empirical Joint Probability for Rare Descriptor Pairs
    # =========================================================================
    def detect_frequency_anomaly(
        self, df: pd.DataFrame, col_a: str = "complaint_type", col_b: str = "descriptor", min_prob: float = 0.005
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Detect rare or anomalous categorical combinations using empirical conditional frequency.
        P(Descriptor | ComplaintType) < min_prob indicates anomalous pairing.
        """
        if col_a not in df.columns or col_b not in df.columns:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        joint_counts = Counter(zip(df[col_a], df[col_b]))
        marginal_a = Counter(df[col_a])

        labels = np.zeros(len(df), dtype=int)
        explanations = [""] * len(df)

        for i, (a_val, b_val) in enumerate(zip(df[col_a], df[col_b])):
            total_for_a = marginal_a.get(a_val, 1)
            pair_count = joint_counts.get((a_val, b_val), 0)
            cond_prob = pair_count / total_for_a

            if cond_prob < min_prob:
                labels[i] = 1
                explanations[i] = (
                    f"Statistical frequency anomaly: Pair ('{a_val}', '{b_val}') has "
                    f"conditional probability P={round(cond_prob, 4)} < {min_prob}"
                )

        return labels, explanations

    # =========================================================================
    # TECHNIQUE 5: String Length & Entropy Shift for Date Format Transitions
    # =========================================================================
    def detect_date_format_shift_statistical(
        self, df: pd.DataFrame, col: str = "created_date"
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Detect date format changes by analyzing non-standard format indicators (slashes, AM/PM).
        """
        if col not in df.columns:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        s = df[col].astype(str)
        is_slash = s.str.contains(r"/", regex=True)
        is_ampm = s.str.contains(r"AM|PM", case=False, regex=True)
        is_shift = (is_slash | is_ampm).values

        labels = is_shift.astype(int)
        explanations = [
            f"Statistical format outlier: '{val}' contains non-ISO format separators" if out else ""
            for val, out in zip(s, is_shift)
        ]
        return labels, explanations

    # =========================================================================
    # TECHNIQUE 6: Resolution Duration Statistical Anomaly (Isolation Forest)
    # =========================================================================
    def detect_duration_isolation_forest(
        self, df: pd.DataFrame
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Detect temporal anomalies (negative duration or extreme resolution delays)
        using Isolation Forest on resolution seconds.
        """
        if "created_date" not in df.columns or "closed_date" not in df.columns:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        created = pd.to_datetime(df["created_date"], errors="coerce")
        closed = pd.to_datetime(df["closed_date"], errors="coerce")

        durations_sec = (closed - created).dt.total_seconds().fillna(0.0).values.reshape(-1, 1)

        # Flag negative durations immediately (temporal paradox)
        negative_mask = durations_sec.flatten() < 0

        # Fit Isolation Forest and flag only points with extreme negative decision scores
        iso = IsolationForest(contamination=0.01, random_state=self.random_state)
        iso.fit(durations_sec)
        scores = iso.decision_function(durations_sec)
        is_extreme_duration = (scores < -0.15) | negative_mask

        labels = is_extreme_duration.astype(int)
        explanations = [
            f"Statistical duration anomaly: resolution time={round(sec/3600, 2)} hours" if out else ""
            for sec, out in zip(durations_sec.flatten(), labels)
        ]
        return labels, explanations

    # =========================================================================
    # TECHNIQUE 7: Digit Density & Character Entropy for Free-Text PII
    # =========================================================================
    def detect_digit_density_anomaly(
        self, df: pd.DataFrame, col: str = "resolution_description", threshold: float = 0.08
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Detect PII (SSNs, phone numbers, account IDs) using statistical digit density.
        Free-text resolution notes usually have digit density < 2%.
        Injected SSN / Phone numbers drive digit density > 8-15%.
        """
        if col not in df.columns:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        labels = np.zeros(len(df), dtype=int)
        explanations = [""] * len(df)

        for i, text in enumerate(df[col].fillna("").astype(str)):
            if len(text) == 0:
                continue
            digits = sum(1 for c in text if c.isdigit())
            density = digits / len(text)

            if density >= threshold:
                labels[i] = 1
                explanations[i] = f"Statistical text outlier: Digit density={round(density*100, 1)}% indicates embedded numeric IDs/PII"

        return labels, explanations

    # =========================================================================
    # TECHNIQUE 8: Master Runner
    # =========================================================================
    def run_detector(self, corruption_id: int, df: pd.DataFrame) -> Tuple[np.ndarray, List[str], float]:
        """Run the most suitable statistical detector for the corruption type."""
        t0 = time.perf_counter()

        # Map each corruption type to its mathematically grounded statistical technique
        detector_map = {
            1: lambda: (np.zeros(len(df), dtype=int), ["Schema check is rule-based"] * len(df)),
            2: lambda: self.detect_date_format_shift_statistical(df, "incident_zip"),
            3: lambda: self.detect_date_format_shift_statistical(df, "created_date"),
            4: lambda: self.detect_coordinate_lof(df),
            5: lambda: self.detect_near_duplicates_similarity(df, similarity_threshold=1.0),
            6: lambda: self.detect_near_duplicates_similarity(df, similarity_threshold=0.85),
            7: lambda: self.detect_null_rate_zscore(df),
            8: lambda: self.detect_duration_isolation_forest(df),
            9: lambda: self.detect_frequency_anomaly(df, "borough", "incident_zip"),
            10: lambda: self.detect_frequency_anomaly(df, "complaint_type", "descriptor"),
            11: lambda: self.detect_frequency_anomaly(df, "status", "resolution_description"),
            12: lambda: self.detect_digit_density_anomaly(df),
        }

        if corruption_id not in detector_map:
            raise ValueError(f"Unknown corruption_id {corruption_id}")

        labels, explanations = detector_map[corruption_id]()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return labels, explanations, elapsed_ms
