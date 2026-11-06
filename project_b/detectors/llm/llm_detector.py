"""
Detector Family 3: LLM Reviewer using Google Gemini.
Reviews suspicious records sampled from candidate queues.
Architecture:
1. Strict PII Pre-Redaction: Masks SSN, Phone, Email before generating any external API prompt.
2. Batch Sampling: Does NOT send every row to Gemini (cost and rate-limit guard).
3. Structured JSON Responses: Returns classification, confidence score (0.0 to 1.0), and semantic explanation.
4. Token, Latency, and Cost Accounting.
5. Resilient offline handling when API key is missing.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from project_b.profiling.profiler import redact_pii
from shared.config import USD_TO_INR
from shared.gemini_client import GeminiClient
from shared.logging_config import get_logger

logger = get_logger("llm_detector")


class LLMReviewer:
    """
    Intelligent LLM auditing agent for semantic contradictions, nuanced PII, and ambiguous anomalies.
    """

    def __init__(self, client: Optional[GeminiClient] = None, max_sample_size: int = 15):
        self.client = client or GeminiClient()
        self.max_sample_size = max_sample_size

    def is_available(self) -> bool:
        return self.client.is_configured()

    def review_batch(
        self, df: pd.DataFrame, candidate_indices: Optional[List[int]] = None
    ) -> Tuple[np.ndarray, List[str], Dict[str, Any]]:
        """
        Review a sampled batch of records using Gemini.

        Args:
            df: DataFrame to review
            candidate_indices: Optional list of pre-filtered suspicious row indices

        Returns:
            Tuple of:
            - labels: np.ndarray (1 = anomaly, 0 = clean)
            - explanations: List[str]
            - metadata: Dict with tokens, latency, cost, and API status
        """
        total_rows = len(df)
        labels = np.zeros(total_rows, dtype=int)
        explanations = [""] * total_rows

        meta = {
            "status": "NOT_CONFIGURED" if not self.is_available() else "SUCCESS",
            "model": self.client.model_name,
            "latency_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "cost_inr": 0.0,
            "reviewed_count": 0,
        }

        # Select sample rows to review (do NOT review every row)
        if candidate_indices:
            eval_indices = candidate_indices[:self.max_sample_size]
        else:
            eval_indices = list(range(min(self.max_sample_size, total_rows)))

        meta["reviewed_count"] = len(eval_indices)

        if not self.is_available():
            # Graceful unconfigured mode - do NOT fabricate live results
            for idx in eval_indices:
                explanations[idx] = "LLM review not executed (GEMINI_API_KEY unconfigured)."
            return labels, explanations, meta

        # Build redacted records for prompt
        sample_records = []
        for idx in eval_indices:
            row = df.iloc[idx].to_dict()
            sanitized_row = {
                "row_index": idx,
                "agency": str(row.get("agency", "")),
                "complaint_type": str(row.get("complaint_type", "")),
                "descriptor": str(row.get("descriptor", "")),
                "incident_zip": str(row.get("incident_zip", "")),
                "borough": str(row.get("borough", "")),
                "status": str(row.get("status", "")),
                # Strictly redact any potential PII before sending to LLM
                "resolution_description": redact_pii(str(row.get("resolution_description", ""))),
            }
            sample_records.append(sanitized_row)

        prompt = f"""You are a Data Quality Auditor for the NYC 311 Service Requests database.
Review the following records for anomalies, contradictions, or data quality defects.

Look specifically for:
1. Contradictions between Status and Resolution Description (e.g. Status is Closed but text says investigation pending).
2. Semantic mismatches between Complaint Type and Descriptor (e.g. Noise paired with Pothole).
3. Borough and ZIP mismatches.
4. Any suspicious text patterns.

RECORDS TO AUDIT:
{sample_records}

Respond STRICTLY in JSON format with an array of objects:
[
  {{
    "row_index": <int>,
    "is_corrupted": <true/false>,
    "detected_issue": "<concise description of issue or 'Clean'>",
    "confidence": <float between 0.0 and 1.0>,
    "reasoning": "<short justification>"
  }}
]
"""
        parsed_json, call_meta = self.client.generate_json(prompt=prompt, temperature=0.0)

        meta["latency_ms"] = call_meta.get("latency_ms", 0.0)
        meta["input_tokens"] = call_meta.get("input_tokens", 0)
        meta["output_tokens"] = call_meta.get("output_tokens", 0)
        meta["cost_usd"] = call_meta.get("cost_usd", 0.0)
        meta["cost_inr"] = round(meta["cost_usd"] * USD_TO_INR, 4)
        meta["status"] = call_meta.get("status", "API_ERROR")

        if parsed_json and isinstance(parsed_json, list):
            for item in parsed_json:
                idx = item.get("row_index")
                is_corrupt = item.get("is_corrupted", False)
                conf = item.get("confidence", 0.8)
                issue = item.get("detected_issue", "Anomalous record flagged by LLM")

                if idx is not None and 0 <= idx < total_rows:
                    if is_corrupt and conf >= 0.60:
                        labels[idx] = 1
                        explanations[idx] = f"LLM Review ({conf*100:.0f}% confidence): {issue}"

        return labels, explanations, meta

