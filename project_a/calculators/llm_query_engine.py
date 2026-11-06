"""
Implementation 2: LLM at Query Time Indian Income Tax Engine.
Retrieves relevant statutory rule texts for the chosen FY and regime,
prompts Google Gemini to interpret rules and compute tax,
records latency, token usage, and cost, and validates model output against verified rules.
Never trusts LLM arithmetic blindly.
"""

from decimal import Decimal
import time
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel, Field

from project_a.calculators.hand_coded_engine import calculate_tax as calculate_verified_tax
from project_a.rules.base_rules import TaxBreakdown, TaxInput, round_inr, to_decimal
from project_a.sources.tax_sources import OFFICIAL_TAX_SOURCES
from shared.gemini_client import GeminiClient
from shared.logging_config import get_logger

logger = get_logger("llm_query_engine")


class LLMTaxResult(BaseModel):
    """Container for Query-Time LLM calculation with verification audit."""
    financial_year: str
    regime: str
    model_name: str
    status: str  # SUCCESS, API_ERROR, NOT_CONFIGURED, ARITHMETIC_ERROR
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float

    # Raw LLM reported numbers
    llm_taxable_income: Optional[Decimal] = None
    llm_slab_tax: Optional[Decimal] = None
    llm_rebate_87a: Optional[Decimal] = None
    llm_surcharge: Optional[Decimal] = None
    llm_cess: Optional[Decimal] = None
    llm_total_tax: Optional[Decimal] = None
    llm_reasoning: Optional[str] = None

    # Verified deterministic reference calculation
    verified_total_tax: Optional[Decimal] = None
    tax_discrepancy_inr: Optional[Decimal] = None
    is_arithmetic_exact: bool = False

    # Auditable source citations provided to/from model
    statutory_clauses: Dict[str, str] = Field(default_factory=dict)
    raw_response: Optional[Dict[str, Any]] = None


def build_tax_prompt(inp: TaxInput, regime: str) -> str:
    """Construct structured context and prompt containing official statutory rule texts."""
    fy = inp.financial_year
    regime = regime.upper()

    # Retrieve official text
    if regime == "OLD":
        slabs_info = OFFICIAL_TAX_SOURCES["OLD_SLABS"].description
        std_ded_info = OFFICIAL_TAX_SOURCES["STD_DEDUCTION_OLD"].description
        rebate_info = OFFICIAL_TAX_SOURCES["REBATE_87A_OLD"].description
    else:
        if fy == "2025-26":
            slabs_info = OFFICIAL_TAX_SOURCES["NEW_SLABS_FY25_26"].description
            rebate_info = OFFICIAL_TAX_SOURCES["REBATE_87A_NEW_FY25_26"].description
        else:
            slabs_info = OFFICIAL_TAX_SOURCES["NEW_SLABS_FY24_25"].description
            rebate_info = OFFICIAL_TAX_SOURCES["REBATE_87A_NEW_FY24_25"].description
        std_ded_info = OFFICIAL_TAX_SOURCES["STD_DEDUCTION_NEW_FY24_25"].description

    prompt = f"""You are an expert Indian Income Tax calculation assistant.
Calculate the exact income tax for a salaried individual for Financial Year {fy} under the {regime} Tax Regime.

OFFICIAL STATUTORY RULES APPLICABLE:
1. Slabs: {slabs_info}
2. Standard Deduction: {std_ded_info}
3. Section 87A Rebate: {rebate_info}
4. Health & Education Cess: 4% of (tax after rebate + surcharge).
5. Exemption & Deduction Rules:
   - Under NEW Regime: NO HRA, NO 80C, NO 80D, NO 24(b) deductions are allowed. Only Standard Deduction is allowed.
   - Under OLD Regime: HRA (least of rent-10% basic, HRA, 50%/40% basic), 80C (max 1.5L), 80CCD(1B) (max 50k), 80D (max 25k/50k), 24b (max 2L) are allowed.

TAXPAYER INPUTS:
- Annual Gross Salary: ₹{inp.gross_salary}
- Basic Salary + DA: ₹{inp.get_effective_basic()}
- HRA Received: ₹{inp.hra_received}
- Rent Paid: ₹{inp.rent_paid} (Metro Accommodation: {inp.is_metro})
- Section 80C: ₹{inp.section_80c}
- Section 80CCD(1B): ₹{inp.section_80ccd_1b}
- Section 80D (Self): ₹{inp.section_80d_self} (Senior: {inp.is_senior_citizen_self})
- Section 80D (Parents): ₹{inp.section_80d_parents} (Senior: {inp.is_senior_citizen_parents})
- Home Loan Interest (24b): ₹{inp.home_loan_interest_24b}

Calculate step by step and respond STRICTLY in JSON format with this exact JSON structure:
{{
  "taxable_income": <number>,
  "slab_tax": <number>,
  "rebate_87a": <number>,
  "tax_after_rebate": <number>,
  "surcharge": <number>,
  "cess": <number>,
  "total_tax": <number>,
  "reasoning": "<short explanation of calculation steps>"
}}
"""
    return prompt


class LLMQueryEngine:
    """
    Executes tax calculations by passing official rules and user inputs to Gemini at query time.
    Tracks latency, cost, and validates numerical correctness.
    """

    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()

    def calculate(self, inp: TaxInput, regime: str = "NEW") -> LLMTaxResult:
        """
        Query Gemini to calculate tax, then run deterministic verification.
        """
        regime = regime.upper().strip()
        fy = inp.financial_year.strip()

        # Always compute verified ground truth for comparison
        verified_breakdown = calculate_verified_tax(inp, regime)

        # Check if Gemini is configured
        if not self.client.is_configured():
            logger.info("Gemini API not configured. LLM query engine reporting unconfigured state.")
            return LLMTaxResult(
                financial_year=fy,
                regime=regime,
                model_name=self.client.model_name,
                status="NOT_CONFIGURED",
                latency_ms=0.0,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                verified_total_tax=verified_breakdown.total_tax,
                is_arithmetic_exact=False,
                statutory_clauses=verified_breakdown.source_clauses,
            )

        prompt = build_tax_prompt(inp, regime)
        parsed_json, meta = self.client.generate_json(
            prompt=prompt,
            temperature=0.0,  # Zero temperature for deterministic evaluation
        )

        if parsed_json is None or meta.get("status") != "SUCCESS":
            return LLMTaxResult(
                financial_year=fy,
                regime=regime,
                model_name=self.client.model_name,
                status=meta.get("status", "API_ERROR"),
                latency_ms=meta.get("latency_ms", 0.0),
                input_tokens=meta.get("input_tokens", 0),
                output_tokens=meta.get("output_tokens", 0),
                cost_usd=meta.get("cost_usd", 0.0),
                verified_total_tax=verified_breakdown.total_tax,
                statutory_clauses=verified_breakdown.source_clauses,
                raw_response=meta,
            )

        # Extract LLM values
        try:
            llm_taxable = round_inr(to_decimal(parsed_json.get("taxable_income", 0)))
            llm_slab = round_inr(to_decimal(parsed_json.get("slab_tax", 0)))
            llm_rebate = round_inr(to_decimal(parsed_json.get("rebate_87a", 0)))
            llm_surcharge = round_inr(to_decimal(parsed_json.get("surcharge", 0)))
            llm_cess = round_inr(to_decimal(parsed_json.get("cess", 0)))
            llm_total = round_inr(to_decimal(parsed_json.get("total_tax", 0)))
            reasoning = str(parsed_json.get("reasoning", ""))

            discrepancy = abs(llm_total - verified_breakdown.total_tax)
            is_exact = discrepancy == Decimal("0.00")

            return LLMTaxResult(
                financial_year=fy,
                regime=regime,
                model_name=self.client.model_name,
                status="SUCCESS",
                latency_ms=meta["latency_ms"],
                input_tokens=meta["input_tokens"],
                output_tokens=meta["output_tokens"],
                cost_usd=meta["cost_usd"],
                llm_taxable_income=llm_taxable,
                llm_slab_tax=llm_slab,
                llm_rebate_87a=llm_rebate,
                llm_surcharge=llm_surcharge,
                llm_cess=llm_cess,
                llm_total_tax=llm_total,
                llm_reasoning=reasoning,
                verified_total_tax=verified_breakdown.total_tax,
                tax_discrepancy_inr=discrepancy,
                is_arithmetic_exact=is_exact,
                statutory_clauses=verified_breakdown.source_clauses,
                raw_response=parsed_json,
            )
        except Exception as e:
            logger.error(f"Error parsing LLM tax response: {e}")
            return LLMTaxResult(
                financial_year=fy,
                regime=regime,
                model_name=self.client.model_name,
                status="PARSING_ERROR",
                latency_ms=meta["latency_ms"],
                input_tokens=meta["input_tokens"],
                output_tokens=meta["output_tokens"],
                cost_usd=meta["cost_usd"],
                verified_total_tax=verified_breakdown.total_tax,
                statutory_clauses=verified_breakdown.source_clauses,
                raw_response=parsed_json,
            )

