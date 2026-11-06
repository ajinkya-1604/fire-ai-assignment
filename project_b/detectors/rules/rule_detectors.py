"""
Detector Family 1: Deterministic Rules-Based Data Quality Detectors.
Vectorized, O(1) checks for:
- Required schema and column presence (Type 1)
- Column data types and formatting (Type 2)
- Date format switches (Type 3)
- Coordinate bounds and lat/lon swaps (Type 4)
- Exact duplicates (Type 5)
- Near-duplicates via whitespace/normalization (Type 6)
- Agency-level null rate thresholds (Type 7)
- Temporal ordering: closed < created (Type 8)
- Cross-column borough vs ZIP consistency (Type 9)
- Complaint type vs Descriptor dictionary validation (Type 10)
- Status vs Resolution text keyword contradictions (Type 11)
- Regex pattern matching for PII in free-text fields (Type 12)
"""

from datetime import datetime
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from project_b.data.fetch_nyc_311 import NYC_BOROUGH_ZIPS, COMPLAINT_TYPES_MAP
from shared.logging_config import get_logger

logger = get_logger("rule_detectors")

EXPECTED_SCHEMA = [
    "unique_key", "created_date", "closed_date", "agency", "agency_name",
    "complaint_type", "descriptor", "incident_zip", "incident_address",
    "status", "resolution_description", "borough", "latitude", "longitude"
]

REGEX_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
REGEX_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
REGEX_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")


class RulesDetector:
    """
    High-throughput, deterministic rules engine.
    Zero external API dependency, zero query cost, microsecond execution per row.
    """

    def detect_schema(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Detect dropped or renamed schema columns (Corruption Type 1)."""
        missing_cols = [c for c in EXPECTED_SCHEMA if c not in df.columns]
        is_corrupted = len(missing_cols) > 0
        labels = np.ones(len(df), dtype=int) if is_corrupted else np.zeros(len(df), dtype=int)
        explanations = [f"Schema violation: Missing expected columns: {missing_cols}"] * len(df) if is_corrupted else [""] * len(df)
        return labels, explanations

    def detect_type_corruption(self, df: pd.DataFrame, col: str = "incident_zip") -> Tuple[np.ndarray, List[str]]:
        """Detect invalid format or corrupted non-numeric ZIP codes (Corruption Type 2)."""
        if col not in df.columns:
            return np.ones(len(df), dtype=int), ["Missing column"] * len(df)

        s = df[col].fillna("").astype(str).str.strip()
        is_invalid = ~s.str.match(r"^\d{5}$")
        labels = is_invalid.astype(int).values
        explanations = [f"Invalid {col} format: '{val}'" if inv else "" for val, inv in zip(s, is_invalid)]
        return labels, explanations

    def detect_date_format_switch(self, df: pd.DataFrame, col: str = "created_date") -> Tuple[np.ndarray, List[str]]:
        """Detect date format inconsistency across batch (Corruption Type 3)."""
        if col not in df.columns:
            return np.ones(len(df), dtype=int), ["Missing date column"] * len(df)

        s = df[col].fillna("").astype(str).str.strip()
        # Expected standard format: ISO YYYY-MM-DDTHH:MM:SS
        is_iso = s.str.match(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}")
        is_corrupted = ~is_iso
        labels = is_corrupted.astype(int).values
        explanations = [f"Non-standard date format: '{val}'" if inv else "" for val, inv in zip(s, is_corrupted)]
        return labels, explanations

    def detect_coordinate_bounds_and_swap(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Detect swapped coordinates or out-of-bounds coordinates (Corruption Type 4)."""
        if "latitude" not in df.columns or "longitude" not in df.columns:
            return np.ones(len(df), dtype=int), ["Missing coordinate columns"] * len(df)

        lats = pd.to_numeric(df["latitude"], errors="coerce")
        lons = pd.to_numeric(df["longitude"], errors="coerce")

        # Swapped: latitude is negative (~-74) and longitude is positive (~40)
        swapped = (lats < 0) & (lons > 0)
        out_of_bounds = (lats < 40.40) | (lats > 41.00) | (lons < -74.35) | (lons > -73.60)

        flagged = (swapped | out_of_bounds | lats.isnull() | lons.isnull()).fillna(True)
        labels = flagged.astype(int).values
        explanations = [
            f"Coordinate anomaly: lat={lat}, lon={lon} (swapped={sw})" if f else ""
            for lat, lon, sw, f in zip(df["latitude"], df["longitude"], swapped, flagged)
        ]
        return labels, explanations

    def detect_exact_duplicates(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Detect exact duplicate rows across all or key columns (Corruption Type 5)."""
        dups = df.duplicated(keep="first")
        labels = dups.astype(int).values
        explanations = ["Duplicate row detected" if d else "" for d in dups]
        return labels, explanations

    def detect_near_duplicates(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Detect near-duplicates by normalized string hashing (Corruption Type 6)."""
        cols_to_check = [c for c in ["incident_address", "descriptor", "borough"] if c in df.columns]
        if not cols_to_check:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        norm_series = df[cols_to_check].fillna("").astype(str).apply(
            lambda row: " ".join(row.values).lower().strip().replace(".", "").replace("  ", " "), axis=1
        )
        dups = norm_series.duplicated(keep="first")
        labels = dups.astype(int).values
        explanations = ["Near-duplicate row detected" if d else "" for d in dups]
        return labels, explanations

    def detect_null_spike(
        self, df: pd.DataFrame, agency: str = "NYPD", col: str = "resolution_description", threshold: float = 0.50
    ) -> Tuple[np.ndarray, List[str]]:
        """Detect agency-specific null spikes exceeding threshold (Corruption Type 7)."""
        if "agency" not in df.columns or col not in df.columns:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        agency_mask = df["agency"] == agency
        agency_null_rate = df.loc[agency_mask, col].isnull().mean() if agency_mask.sum() > 0 else 0.0

        is_spike = agency_null_rate >= threshold
        labels = np.zeros(len(df), dtype=int)
        explanations = [""] * len(df)

        if is_spike:
            # Flag rows belonging to the spiked agency that have nulls
            flagged_mask = agency_mask & df[col].isnull()
            labels[flagged_mask] = 1
            for idx in df[flagged_mask].index:
                explanations[idx] = f"Agency {agency} null spike anomaly: {round(agency_null_rate*100, 1)}% nulls in {col}"

        return labels, explanations

    def detect_closed_before_created(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Detect temporal paradox where closed date is earlier than created date (Corruption Type 8)."""
        if "created_date" not in df.columns or "closed_date" not in df.columns:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        created = pd.to_datetime(df["created_date"], errors="coerce")
        closed = pd.to_datetime(df["closed_date"], errors="coerce")

        both_valid = created.notnull() & closed.notnull()
        paradox = both_valid & (closed < created)

        labels = paradox.astype(int).values
        explanations = [
            f"Temporal paradox: closed_date ({cl}) < created_date ({cr})" if p else ""
            for cr, cl, p in zip(df["created_date"], df["closed_date"], paradox)
        ]
        return labels, explanations

    def detect_zip_borough_inconsistency(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Detect cross-column geographical mismatch between Borough and ZIP (Corruption Type 9)."""
        if "borough" not in df.columns or "incident_zip" not in df.columns:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        labels = np.zeros(len(df), dtype=int)
        explanations = [""] * len(df)

        for i, (b, z) in enumerate(zip(df["borough"], df["incident_zip"])):
            b_clean = str(b).upper().strip()
            z_clean = str(z).strip()[:5]

            if b_clean in NYC_BOROUGH_ZIPS and z_clean.isdigit():
                if z_clean not in NYC_BOROUGH_ZIPS[b_clean]:
                    # Check if it's a known valid ZIP of another borough
                    other_boroughs = [ob for ob, zips in NYC_BOROUGH_ZIPS.items() if z_clean in zips]
                    if other_boroughs:
                        labels[i] = 1
                        explanations[i] = f"Borough-ZIP mismatch: ZIP {z_clean} belongs to {other_boroughs[0]}, not {b_clean}."

        return labels, explanations

    def detect_complaint_descriptor_mismatch(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Detect semantic mismatch between complaint type and descriptor via dictionary (Corruption Type 10)."""
        if "complaint_type" not in df.columns or "descriptor" not in df.columns:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        labels = np.zeros(len(df), dtype=int)
        explanations = [""] * len(df)

        for i, (ct, desc) in enumerate(zip(df["complaint_type"], df["descriptor"])):
            ct_clean = str(ct).strip()
            desc_clean = str(desc).strip()

            if ct_clean in COMPLAINT_TYPES_MAP:
                allowed_descriptors = COMPLAINT_TYPES_MAP[ct_clean]
                if desc_clean not in allowed_descriptors:
                    labels[i] = 1
                    explanations[i] = f"Descriptor mismatch: '{desc_clean}' is not an authorized descriptor for '{ct_clean}'"

        return labels, explanations

    def detect_resolution_status_contradiction(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Detect contradiction between Status and Resolution Description (Corruption Type 11)."""
        if "status" not in df.columns or "resolution_description" not in df.columns:
            return np.zeros(len(df), dtype=int), [""] * len(df)

        labels = np.zeros(len(df), dtype=int)
        explanations = [""] * len(df)

        closed_contradiction_patterns = ["pending active investigation", "not yet responded", "remains wide open", "under review"]
        open_contradiction_patterns = ["fully resolved", "successfully closed and completed", "citations issued and resolved"]

        for i, (st, rd) in enumerate(zip(df["status"], df["resolution_description"])):
            st_clean = str(st).strip().lower()
            rd_clean = str(rd).strip().lower()

            if "closed" in st_clean and any(p in rd_clean for p in closed_contradiction_patterns):
                labels[i] = 1
                explanations[i] = f"Status '{st}' contradicts resolution text describing active/pending investigation."
            elif ("open" in st_clean or "pending" in st_clean) and any(p in rd_clean for p in open_contradiction_patterns):
                labels[i] = 1
                explanations[i] = f"Status '{st}' contradicts resolution text describing completed/closed resolution."

        return labels, explanations

    def detect_pii(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Detect personal data leaks (SSN, Phone, Email) in free-text fields via regex (Corruption Type 12)."""
        free_text_cols = [c for c in ["resolution_description", "descriptor", "incident_address"] if c in df.columns]
        labels = np.zeros(len(df), dtype=int)
        explanations = [""] * len(df)

        for i in range(len(df)):
            detected_types = []
            for col in free_text_cols:
                val = str(df.at[i, col] or "")
                if REGEX_SSN.search(val):
                    detected_types.append("SSN")
                if REGEX_PHONE.search(val):
                    detected_types.append("Phone")
                if REGEX_EMAIL.search(val):
                    detected_types.append("Email")

            if detected_types:
                labels[i] = 1
                explanations[i] = f"PII detected in free-text: {list(set(detected_types))}"

        return labels, explanations

    def run_detector(self, corruption_id: int, df: pd.DataFrame) -> Tuple[np.ndarray, List[str], float]:
        """
        Run the specific rule detector corresponding to the corruption type id.
        Returns: (labels, explanations, latency_ms)
        """
        t0 = time.perf_counter()
        detector_map = {
            1: lambda: self.detect_schema(df),
            2: lambda: self.detect_type_corruption(df),
            3: lambda: self.detect_date_format_switch(df),
            4: lambda: self.detect_coordinate_bounds_and_swap(df),
            5: lambda: self.detect_exact_duplicates(df),
            6: lambda: self.detect_near_duplicates(df),
            7: lambda: self.detect_null_spike(df),
            8: lambda: self.detect_closed_before_created(df),
            9: lambda: self.detect_zip_borough_inconsistency(df),
            10: lambda: self.detect_complaint_descriptor_mismatch(df),
            11: lambda: self.detect_resolution_status_contradiction(df),
            12: lambda: self.detect_pii(df),
        }
        if corruption_id not in detector_map:
            raise ValueError(f"Unknown corruption_id {corruption_id}")

        labels, explanations = detector_map[corruption_id]()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return labels, explanations, elapsed_ms

