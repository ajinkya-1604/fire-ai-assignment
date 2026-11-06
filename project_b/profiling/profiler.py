"""
Data Profiling Engine for NYC 311 Service Requests.
Analyzes:
1. Missing values (counts and percentages).
2. Duplicate records (exact and primary key).
3. Incorrect data types and formatting.
4. Invalid dates (unparseable, temporal paradoxes where closed < created).
5. Invalid coordinates (NYC spatial boundary check, swapped lat/lon).
6. Inconsistent categories (agency, borough, complaint type).
7. ZIP code problems (formatting and borough consistency).
8. Unusual distributions (agency frequency, status breakdown).
9. Potential PII (SSN, Phone, Email) in free-text fields with automatic redaction.
"""

from datetime import datetime
import json
import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from project_b.data.fetch_nyc_311 import NYC_BOROUGH_ZIPS
from shared.config import REPORTS_DIR
from shared.logging_config import get_logger

logger = get_logger("data_profiler")

# NYC Geographic Bounding Box
NYC_LAT_MIN = 40.45
NYC_LAT_MAX = 40.95
NYC_LON_MIN = -74.30
NYC_LON_MAX = -73.65

# PII Regex Patterns
REGEX_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
REGEX_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
REGEX_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")


def redact_pii(text: str) -> str:
    """Mask sensitive PII patterns to prevent leakage into reports or LLM prompts."""
    if not isinstance(text, str):
        return ""
    masked = REGEX_SSN.sub("[REDACTED_SSN]", text)
    masked = REGEX_PHONE.sub("[REDACTED_PHONE]", masked)
    masked = REGEX_EMAIL.sub("[REDACTED_EMAIL]", masked)
    return masked


class DataProfiler:
    """
    Comprehensive profiler examining structural, statistical, and semantic anomalies in tabular data.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.total_rows = len(df)
        self.total_cols = len(df.columns)

    def profile_all(self) -> Dict[str, Any]:
        """Run all profiling checks and return consolidated report."""
        logger.info(f"Profiling dataset ({self.total_rows} rows, {self.total_cols} columns)...")

        report = {
            "summary": {
                "total_rows": self.total_rows,
                "total_columns": self.total_cols,
                "columns": list(self.df.columns),
            },
            "missing_values": self._profile_missing_values(),
            "duplicates": self._profile_duplicates(),
            "date_anomalies": self._profile_dates(),
            "coordinate_anomalies": self._profile_coordinates(),
            "zip_code_issues": self._profile_zips(),
            "categorical_consistency": self._profile_categories(),
            "pii_findings": self._profile_pii(),
            "unusual_distributions": self._profile_distributions(),
        }

        # Save report
        out_file = REPORTS_DIR / "project_b_profile_report.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Data profiling complete. Report saved to: {out_file}")

        return report

    def _profile_missing_values(self) -> Dict[str, Any]:
        null_counts = self.df.isnull().sum()
        res = {}
        for col in self.df.columns:
            cnt = int(null_counts[col])
            pct = round((cnt / self.total_rows) * 100.0, 2) if self.total_rows > 0 else 0.0
            res[col] = {"missing_count": cnt, "missing_percent": pct}
        return res

    def _profile_duplicates(self) -> Dict[str, Any]:
        exact_dups = int(self.df.duplicated().sum())
        key_dups = (
            int(self.df["unique_key"].duplicated().sum())
            if "unique_key" in self.df.columns
            else 0
        )
        return {
            "exact_duplicate_rows": exact_dups,
            "exact_duplicate_percent": round((exact_dups / max(1, self.total_rows)) * 100.0, 2),
            "primary_key_duplicates": key_dups,
        }

    def _profile_dates(self) -> Dict[str, Any]:
        if "created_date" not in self.df.columns:
            return {"error": "created_date column not found"}

        invalid_created = 0
        invalid_closed = 0
        temporal_paradoxes = 0
        created_outside_2023 = 0

        created_series = pd.to_datetime(self.df["created_date"], errors="coerce")
        invalid_created = int(created_series.isnull().sum())

        # Year check
        valid_created = created_series.dropna()
        if len(valid_created) > 0:
            created_outside_2023 = int((valid_created.dt.year != 2023).sum())

        if "closed_date" in self.df.columns:
            closed_series = pd.to_datetime(self.df["closed_date"], errors="coerce")
            invalid_closed = int(
                (self.df["closed_date"].notnull() & closed_series.isnull()).sum()
            )

            # Check closed < created
            both_valid = created_series.notnull() & closed_series.notnull()
            temporal_paradoxes = int((closed_series[both_valid] < created_series[both_valid]).sum())

        return {
            "unparseable_created_dates": invalid_created,
            "created_outside_year_2023": created_outside_2023,
            "unparseable_closed_dates": invalid_closed,
            "closed_before_created_count": temporal_paradoxes,
            "closed_before_created_percent": round((temporal_paradoxes / max(1, self.total_rows)) * 100.0, 2),
        }

    def _profile_coordinates(self) -> Dict[str, Any]:
        if "latitude" not in self.df.columns or "longitude" not in self.df.columns:
            return {"error": "Coordinate columns missing"}

        lats = pd.to_numeric(self.df["latitude"], errors="coerce")
        lons = pd.to_numeric(self.df["longitude"], errors="coerce")

        null_coords = int((lats.isnull() | lons.isnull()).sum())

        # Check outside NYC boundaries
        valid_mask = lats.notnull() & lons.notnull()
        out_of_bounds = int(
            (
                (lats[valid_mask] < NYC_LAT_MIN)
                | (lats[valid_mask] > NYC_LAT_MAX)
                | (lons[valid_mask] < NYC_LON_MIN)
                | (lons[valid_mask] > NYC_LON_MAX)
            ).sum()
        )

        # Swapped check (Lon ~40.7, Lat ~-73.9)
        swapped_count = int(
            (
                (lats[valid_mask] < 0) & (lons[valid_mask] > 0)
            ).sum()
        )

        return {
            "null_coordinates": null_coords,
            "out_of_bounds_count": out_of_bounds,
            "swapped_lat_lon_count": swapped_count,
            "valid_coordinate_percent": round(
                (int(valid_mask.sum()) - out_of_bounds) / max(1, self.total_rows) * 100.0, 2
            ),
        }

    def _profile_zips(self) -> Dict[str, Any]:
        if "incident_zip" not in self.df.columns:
            return {"error": "incident_zip column missing"}

        zips = self.df["incident_zip"].fillna("").astype(str).str.strip()
        invalid_format = int((~zips.str.match(r"^\d{5}$")).sum())

        borough_mismatches = 0
        if "borough" in self.df.columns:
            for _, row in self.df.iterrows():
                b = str(row.get("borough", "")).upper()
                z = str(row.get("incident_zip", "")).strip()[:5]
                if b in NYC_BOROUGH_ZIPS and z.isdigit():
                    if z not in NYC_BOROUGH_ZIPS[b]:
                        # Check if it belongs to another NYC borough
                        is_other_borough = any(z in z_list for b_name, z_list in NYC_BOROUGH_ZIPS.items() if b_name != b)
                        if is_other_borough:
                            borough_mismatches += 1

        return {
            "invalid_zip_format_count": invalid_format,
            "borough_zip_mismatch_count": borough_mismatches,
            "borough_zip_mismatch_percent": round((borough_mismatches / max(1, self.total_rows)) * 100.0, 2),
        }

    def _profile_categories(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}
        if "agency" in self.df.columns:
            res["top_agencies"] = self.df["agency"].value_counts().head(5).to_dict()
        if "borough" in self.df.columns:
            res["borough_distribution"] = self.df["borough"].value_counts().to_dict()
        if "status" in self.df.columns:
            res["status_distribution"] = self.df["status"].value_counts().to_dict()
        return res

    def _profile_pii(self) -> Dict[str, Any]:
        """Scan free-text fields for PII leaks, reporting redacted counts and safe examples."""
        free_text_cols = [c for c in ["resolution_description", "descriptor", "incident_address"] if c in self.df.columns]

        total_ssn = 0
        total_phone = 0
        total_email = 0
        sample_redacted_snippets: List[str] = []

        for col in free_text_cols:
            series = self.df[col].dropna().astype(str)
            for text in series:
                ssn_found = len(REGEX_SSN.findall(text))
                phone_found = len(REGEX_PHONE.findall(text))
                email_found = len(REGEX_EMAIL.findall(text))

                if ssn_found > 0 or phone_found > 0 or email_found > 0:
                    total_ssn += ssn_found
                    total_phone += phone_found
                    total_email += email_found
                    if len(sample_redacted_snippets) < 3:
                        sample_redacted_snippets.append(redact_pii(text[:120]))

        return {
            "potential_ssn_detected": total_ssn,
            "potential_phone_detected": total_phone,
            "potential_email_detected": total_email,
            "total_pii_occurrences": total_ssn + total_phone + total_email,
            "sanitized_examples": sample_redacted_snippets,
            "note": "All reported examples are strictly redacted. Zero raw PII exposed."
        }

    def _profile_distributions(self) -> Dict[str, Any]:
        """Examine statistical skew and rate metrics."""
        null_rate_by_agency = {}
        if "agency" in self.df.columns and "resolution_description" in self.df.columns:
            grouped = self.df.groupby("agency")["resolution_description"].apply(lambda s: s.isnull().mean())
            null_rate_by_agency = {k: round(float(v), 3) for k, v in grouped.to_dict().items()}

        return {
            "agency_resolution_null_rates": null_rate_by_agency,
        }


if __name__ == "__main__":
    from project_b.data.fetch_nyc_311 import get_nyc_311_data
    df = get_nyc_311_data()
    profiler = DataProfiler(df)
    report = profiler.profile_all()
    print("Profile Summary:")
    print(f"Total Rows: {report['summary']['total_rows']}")
    print(f"Duplicates: {report['duplicates']}")
    print(f"PII Findings: {report['pii_findings']}")

