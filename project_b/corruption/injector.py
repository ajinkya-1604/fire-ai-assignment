"""
Configurable 12-Type Data Corruption Injector for NYC 311 Service Requests.
Implements exact, reproducible corruption mechanisms across structural, temporal,
spatial, statistical, and semantic dimensions.

Each injection:
- Has its own dedicated function.
- Supports configurable corruption rate.
- Uses explicit random seeds for 100% reproducibility.
- Returns the modified DataFrame along with ground-truth binary labels (1=corrupted, 0=clean)
  and metadata describing injected row indices.
"""

from datetime import datetime, timedelta
import random
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from project_b.data.fetch_nyc_311 import NYC_BOROUGH_ZIPS
from shared.config import RANDOM_SEED
from shared.logging_config import get_logger

logger = get_logger("corruption_injector")

CORRUPTION_NAMES: Dict[int, str] = {
    1: "1_renamed_or_dropped_column",
    2: "2_column_type_change",
    3: "3_date_format_switch",
    4: "4_lat_lon_swapped",
    5: "5_exact_duplicates",
    6: "6_near_duplicates",
    7: "7_null_spike",
    8: "8_closed_before_created",
    9: "9_zip_borough_inconsistent",
    10: "10_complaint_descriptor_mismatch",
    11: "11_resolution_status_contradiction",
    12: "12_personal_data_leak",
}


class CorruptionResult:
    """Container for corrupted dataset, ground-truth labels, and injection metadata."""

    def __init__(
        self,
        df: pd.DataFrame,
        labels: np.ndarray,
        corruption_type: str,
        corrupted_indices: List[int],
        rate: float,
        seed: int,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.df = df
        self.labels = labels  # 1 = corrupted, 0 = clean
        self.corruption_type = corruption_type
        self.corrupted_indices = corrupted_indices
        self.rate = rate
        self.seed = seed
        self.metadata = metadata or {}

    def summary(self) -> Dict[str, Any]:
        return {
            "corruption_type": self.corruption_type,
            "total_rows": len(self.df),
            "corrupted_rows": len(self.corrupted_indices),
            "actual_rate": round(len(self.corrupted_indices) / max(1, len(self.df)), 4),
            "random_seed": self.seed,
            "metadata": self.metadata,
        }


class CorruptionInjector:
    """
    Modular suite of 12 distinct data corruptions.
    """

    def __init__(self, seed: int = RANDOM_SEED):
        self.seed = seed

    def _sample_indices(self, total: int, rate: float, rng: random.Random) -> List[int]:
        k = max(1, int(round(total * rate)))
        return rng.sample(range(total), min(k, total))

    # =========================================================================
    # CORRUPTION 1: Renamed or Dropped Column
    # =========================================================================
    def inject_renamed_or_dropped_column(
        self, df: pd.DataFrame, target_col: str = "agency", new_col: str = "dept_code", drop: bool = False
    ) -> CorruptionResult:
        df_mod = df.copy()
        total = len(df_mod)
        labels = np.ones(total, dtype=int)  # Entire batch has structural schema corruption

        if drop:
            if target_col in df_mod.columns:
                df_mod = df_mod.drop(columns=[target_col])
                desc = f"Dropped column '{target_col}'"
        else:
            if target_col in df_mod.columns:
                df_mod = df_mod.rename(columns={target_col: new_col})
                desc = f"Renamed column '{target_col}' to '{new_col}'"
            else:
                desc = f"Column '{target_col}' not found"

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="1_renamed_or_dropped_column",
            corrupted_indices=list(range(total)),
            rate=1.0,
            seed=self.seed,
            metadata={"description": desc},
        )

    # =========================================================================
    # CORRUPTION 2: Column Type Change
    # =========================================================================
    def inject_column_type_change(
        self, df: pd.DataFrame, col: str = "incident_zip", rate: float = 0.10, seed: Optional[int] = None
    ) -> CorruptionResult:
        df_mod = df.copy()
        rng = random.Random(seed or self.seed)
        total = len(df_mod)
        indices = self._sample_indices(total, rate, rng)
        labels = np.zeros(total, dtype=int)

        corrupt_strings = ["INVALID_ZIP", "99X99", "UNKNOWN", "N/A", "###", "NaN_ERR"]
        for idx in indices:
            df_mod.at[idx, col] = rng.choice(corrupt_strings)
            labels[idx] = 1

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="2_column_type_change",
            corrupted_indices=indices,
            rate=rate,
            seed=seed or self.seed,
            metadata={"column": col},
        )

    # =========================================================================
    # CORRUPTION 3: Date Format Switch Halfway Through Batch
    # =========================================================================
    def inject_date_format_switch(
        self, df: pd.DataFrame, col: str = "created_date", seed: Optional[int] = None
    ) -> CorruptionResult:
        df_mod = df.copy()
        total = len(df_mod)
        half = total // 2
        labels = np.zeros(total, dtype=int)
        corrupted_indices = list(range(half, total))

        for idx in corrupted_indices:
            orig = str(df_mod.at[idx, col])
            try:
                # Parse standard ISO
                dt = pd.to_datetime(orig)
                # Switch to non-standard format: MM/DD/YYYY hh:mm:ss AM/PM
                df_mod.at[idx, col] = dt.strftime("%m/%d/%Y %I:%M:%S %p")
            except Exception:
                df_mod.at[idx, col] = "06/31/2023 12:00:00 AM"  # Malformed date string
            labels[idx] = 1

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="3_date_format_switch",
            corrupted_indices=corrupted_indices,
            rate=0.50,
            seed=seed or self.seed,
            metadata={"switched_format": "MM/DD/YYYY %I:%M:%S %p"},
        )

    # =========================================================================
    # CORRUPTION 4: Latitude and Longitude Swapped
    # =========================================================================
    def inject_latitude_longitude_swapped(
        self, df: pd.DataFrame, rate: float = 0.10, seed: Optional[int] = None
    ) -> CorruptionResult:
        df_mod = df.copy()
        rng = random.Random(seed or self.seed)
        total = len(df_mod)
        indices = self._sample_indices(total, rate, rng)
        labels = np.zeros(total, dtype=int)

        for idx in indices:
            lat = df_mod.at[idx, "latitude"]
            lon = df_mod.at[idx, "longitude"]
            df_mod.at[idx, "latitude"] = lon
            df_mod.at[idx, "longitude"] = lat
            labels[idx] = 1

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="4_lat_lon_swapped",
            corrupted_indices=indices,
            rate=rate,
            seed=seed or self.seed,
        )

    # =========================================================================
    # CORRUPTION 5: Exact Duplicates
    # =========================================================================
    def inject_exact_duplicates(
        self, df: pd.DataFrame, rate: float = 0.05, seed: Optional[int] = None
    ) -> CorruptionResult:
        df_mod = df.copy()
        rng = random.Random(seed or self.seed)
        total = len(df_mod)
        num_dups = max(1, int(round(total * rate)))
        source_indices = rng.sample(range(total), num_dups)

        dup_rows = df_mod.iloc[source_indices].copy()
        corrupted_indices = list(range(total, total + len(dup_rows)))

        # Append duplicates to dataframe
        df_mod = pd.concat([df_mod, dup_rows], ignore_index=True)
        labels = np.zeros(len(df_mod), dtype=int)
        for idx in corrupted_indices:
            labels[idx] = 1

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="5_exact_duplicates",
            corrupted_indices=corrupted_indices,
            rate=rate,
            seed=seed or self.seed,
            metadata={"source_indices": source_indices},
        )

    # =========================================================================
    # CORRUPTION 6: Near-Duplicates
    # =========================================================================
    def inject_near_duplicates(
        self, df: pd.DataFrame, rate: float = 0.05, seed: Optional[int] = None
    ) -> CorruptionResult:
        df_mod = df.copy()
        rng = random.Random(seed or self.seed)
        total = len(df_mod)
        num_dups = max(1, int(round(total * rate)))
        source_indices = rng.sample(range(total), num_dups)

        near_dup_rows = []
        for idx in source_indices:
            row = df_mod.iloc[idx].copy()
            # Minor typo in incident_address or descriptor + slight whitespace
            if pd.notnull(row.get("incident_address")):
                row["incident_address"] = str(row["incident_address"]) + "  "
            if pd.notnull(row.get("descriptor")):
                row["descriptor"] = str(row["descriptor"]) + "."
            # Slight change in unique key to simulate distinct submission
            row["unique_key"] = str(int(row["unique_key"]) + 9000000)
            near_dup_rows.append(row)

        corrupted_indices = list(range(total, total + len(near_dup_rows)))
        df_mod = pd.concat([df_mod, pd.DataFrame(near_dup_rows)], ignore_index=True)
        labels = np.zeros(len(df_mod), dtype=int)
        for idx in corrupted_indices:
            labels[idx] = 1

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="6_near_duplicates",
            corrupted_indices=corrupted_indices,
            rate=rate,
            seed=seed or self.seed,
        )

    # =========================================================================
    # CORRUPTION 7: Null Spike in One Agency's Records
    # =========================================================================
    def inject_null_spike(
        self, df: pd.DataFrame, agency: str = "NYPD", spike_rate: float = 0.90, seed: Optional[int] = None
    ) -> CorruptionResult:
        df_mod = df.copy()
        rng = random.Random(seed or self.seed)
        total = len(df_mod)
        labels = np.zeros(total, dtype=int)

        agency_mask = df_mod["agency"] == agency
        agency_indices = df_mod[agency_mask].index.tolist()

        k = int(round(len(agency_indices) * spike_rate))
        spiked_indices = rng.sample(agency_indices, min(k, len(agency_indices)))

        for idx in spiked_indices:
            df_mod.at[idx, "resolution_description"] = np.nan
            labels[idx] = 1

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="7_null_spike",
            corrupted_indices=spiked_indices,
            rate=spike_rate,
            seed=seed or self.seed,
            metadata={"agency": agency, "affected_column": "resolution_description"},
        )

    # =========================================================================
    # CORRUPTION 8: Closed Date Earlier than Created Date
    # =========================================================================
    def inject_closed_before_created(
        self, df: pd.DataFrame, rate: float = 0.10, seed: Optional[int] = None
    ) -> CorruptionResult:
        df_mod = df.copy()
        rng = random.Random(seed or self.seed)
        total = len(df_mod)
        indices = self._sample_indices(total, rate, rng)
        labels = np.zeros(total, dtype=int)

        for idx in indices:
            created_str = str(df_mod.at[idx, "created_date"])
            try:
                dt = pd.to_datetime(created_str)
                # Set closed date to 3 hours before created date
                earlier = dt - timedelta(hours=rng.randint(1, 48))
                df_mod.at[idx, "closed_date"] = earlier.strftime("%Y-%m-%dT%H:%M:%S.000")
                df_mod.at[idx, "status"] = "Closed"
                labels[idx] = 1
            except Exception:
                pass

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="8_closed_before_created",
            corrupted_indices=indices,
            rate=rate,
            seed=seed or self.seed,
        )

    # =========================================================================
    # CORRUPTION 9: ZIP Code Inconsistent with Borough
    # =========================================================================
    def inject_zip_borough_inconsistent(
        self, df: pd.DataFrame, rate: float = 0.10, seed: Optional[int] = None
    ) -> CorruptionResult:
        df_mod = df.copy()
        rng = random.Random(seed or self.seed)
        total = len(df_mod)
        indices = self._sample_indices(total, rate, rng)
        labels = np.zeros(total, dtype=int)

        # Mappings of incompatible ZIPs:
        # Assign Manhattan ZIP 10001 to Brooklyn, Bronx ZIP 10451 to Staten Island, etc.
        mismatch_map = {
            "MANHATTAN": "11201",     # Brooklyn ZIP
            "BROOKLYN": "10001",      # Manhattan ZIP
            "QUEENS": "10451",        # Bronx ZIP
            "BRONX": "10314",         # Staten Island ZIP
            "STATEN ISLAND": "11101", # Queens ZIP
        }

        for idx in indices:
            borough = str(df_mod.at[idx, "borough"]).upper()
            if borough in mismatch_map:
                df_mod.at[idx, "incident_zip"] = mismatch_map[borough]
                labels[idx] = 1

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="9_zip_borough_inconsistent",
            corrupted_indices=indices,
            rate=rate,
            seed=seed or self.seed,
        )

    # =========================================================================
    # CORRUPTION 10: Complaint Type Inconsistent with Descriptor
    # =========================================================================
    def inject_complaint_descriptor_mismatch(
        self, df: pd.DataFrame, rate: float = 0.10, seed: Optional[int] = None
    ) -> CorruptionResult:
        df_mod = df.copy()
        rng = random.Random(seed or self.seed)
        total = len(df_mod)
        indices = self._sample_indices(total, rate, rng)
        labels = np.zeros(total, dtype=int)

        absurd_descriptors = [
            "Pothole on 3rd Floor Living Room",
            "Loud Music from Broken Sewer Pipe",
            "Barking Hydrant Running Water",
            "Rat Infestation in Traffic Light",
            "Entire Highway Missing in Kitchen",
        ]

        for idx in indices:
            df_mod.at[idx, "descriptor"] = rng.choice(absurd_descriptors)
            labels[idx] = 1

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="10_complaint_descriptor_mismatch",
            corrupted_indices=indices,
            rate=rate,
            seed=seed or self.seed,
        )

    # =========================================================================
    # CORRUPTION 11: Resolution Description Contradicting Status
    # =========================================================================
    def inject_resolution_status_contradiction(
        self, df: pd.DataFrame, rate: float = 0.10, seed: Optional[int] = None
    ) -> CorruptionResult:
        df_mod = df.copy()
        rng = random.Random(seed or self.seed)
        total = len(df_mod)
        indices = self._sample_indices(total, rate, rng)
        labels = np.zeros(total, dtype=int)

        for idx in indices:
            status = str(df_mod.at[idx, "status"])
            if status == "Closed":
                # Contradict Closed status with ongoing/pending text
                df_mod.at[idx, "resolution_description"] = (
                    "The Police Department has not yet responded to this complaint. "
                    "Case is currently pending active field investigation and remains wide open."
                )
            else:
                # Contradict Open/Pending status with closed/resolved text
                df_mod.at[idx, "status"] = "Open"
                df_mod.at[idx, "resolution_description"] = (
                    "The Department inspected the condition, issued citations, and fully resolved "
                    "the matter. The service request was successfully closed and completed."
                )
            labels[idx] = 1

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="11_resolution_status_contradiction",
            corrupted_indices=indices,
            rate=rate,
            seed=seed or self.seed,
        )

    # =========================================================================
    # CORRUPTION 12: Personal Data Inside Free-Text Fields
    # =========================================================================
    def inject_personal_data_leak(
        self, df: pd.DataFrame, rate: float = 0.10, seed: Optional[int] = None
    ) -> CorruptionResult:
        df_mod = df.copy()
        rng = random.Random(seed or self.seed)
        total = len(df_mod)
        indices = self._sample_indices(total, rate, rng)
        labels = np.zeros(total, dtype=int)

        pii_generators = [
            lambda: f"Complainant SSN is {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}. Call back immediately.",
            lambda: f"Contact tenant directly at mobile {rng.randint(200, 999)}-{rng.randint(200, 999)}-{rng.randint(1000, 9999)}.",
            lambda: f"Please email resident statements to resident_{rng.randint(10, 999)}@gmail.com.",
            lambda: f"Driver license ID NY-{rng.randint(1000000, 9999999)}, phone (212) 555-01{rng.randint(10, 99)}.",
        ]

        for idx in indices:
            orig = str(df_mod.at[idx, "resolution_description"] or "")
            pii_snippet = rng.choice(pii_generators)()
            df_mod.at[idx, "resolution_description"] = f"{orig} {pii_snippet}".strip()
            labels[idx] = 1

        return CorruptionResult(
            df=df_mod,
            labels=labels,
            corruption_type="12_personal_data_leak",
            corrupted_indices=indices,
            rate=rate,
            seed=seed or self.seed,
        )

    # =========================================================================
    # MASTER INJECTOR: Injects any of the 12 types by key
    # =========================================================================
    def inject(
        self, corruption_id: int, df: pd.DataFrame, rate: float = 0.10, seed: Optional[int] = None
    ) -> CorruptionResult:
        s = seed or self.seed
        injectors = {
            1: lambda: self.inject_renamed_or_dropped_column(df, drop=False),
            2: lambda: self.inject_column_type_change(df, rate=rate, seed=s),
            3: lambda: self.inject_date_format_switch(df, seed=s),
            4: lambda: self.inject_latitude_longitude_swapped(df, rate=rate, seed=s),
            5: lambda: self.inject_exact_duplicates(df, rate=rate, seed=s),
            6: lambda: self.inject_near_duplicates(df, rate=rate, seed=s),
            7: lambda: self.inject_null_spike(df, spike_rate=0.90, seed=s),
            8: lambda: self.inject_closed_before_created(df, rate=rate, seed=s),
            9: lambda: self.inject_zip_borough_inconsistent(df, rate=rate, seed=s),
            10: lambda: self.inject_complaint_descriptor_mismatch(df, rate=rate, seed=s),
            11: lambda: self.inject_resolution_status_contradiction(df, rate=rate, seed=s),
            12: lambda: self.inject_personal_data_leak(df, rate=rate, seed=s),
        }
        if corruption_id not in injectors:
            raise ValueError(f"Invalid corruption_id {corruption_id}. Must be 1 to 12.")

        return injectors[corruption_id]()
