"""
Implementation 3: LLM-Compiled Rules Indian Income Tax Engine.
Architecture:
1. Offline Compiler: Gemini reads statutory legal texts and compiles them into
   versioned, validated, structured rule specifications (JSON).
2. Query-Time Executor: Fast, 100% deterministic, zero-latency Decimal execution engine
   that runs directly against the compiled rule files without calling an LLM at query time.
"""

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from project_a.rules.base_rules import (
    SlabRate,
    TaxBreakdown,
    TaxInput,
    round_inr,
    to_decimal,
)
from project_a.sources.tax_sources import OFFICIAL_TAX_SOURCES
from shared.config import PROJECT_A_DIR
from shared.gemini_client import GeminiClient
from shared.logging_config import get_logger

logger = get_logger("compiled_engine")

COMPILED_RULES_DIR = PROJECT_A_DIR / "rules"


def load_compiled_rules(financial_year: str) -> Dict[str, Any]:
    """Load the versioned, validated compiled rules JSON file."""
    clean_fy = financial_year.replace("-", "_")
    file_path = COMPILED_RULES_DIR / f"compiled_rules_fy{clean_fy[-5:]}.json"
    if not file_path.exists():
        # Fallback to direct name match
        file_path = COMPILED_RULES_DIR / f"compiled_rules_fy{financial_year.replace('20', '')}.json"
        if not file_path.exists():
            # Standard FY24-25 default
            file_path = COMPILED_RULES_DIR / "compiled_rules_fy24_25.json"

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


class CompiledTaxEngine:
    """
    Executes tax calculations using pre-compiled, versioned rule specifications.
    Combines the flexibility of LLM rule extraction with the speed, zero query cost,
    and 100% determinism of a compiled rules engine.
    """

    def __init__(self, financial_year: str = "2024-25"):
        self.financial_year = financial_year
        self.rules_spec = load_compiled_rules(financial_year)

    def calculate(self, inp: TaxInput, regime: str = "NEW") -> TaxBreakdown:
        """Execute tax calculation using compiled rule tables."""
        regime = regime.upper().strip()
        fy = inp.financial_year.strip()

        # Reload if financial year differs
        if fy != self.financial_year:
            self.financial_year = fy
            self.rules_spec = load_compiled_rules(fy)

        source_clauses: Dict[str, str] = {}
        regime_spec = (
            self.rules_spec["old_regime"]
            if regime == "OLD"
            else self.rules_spec["new_regime"]
        )

        # 1. Standard Deduction
        std_ded_limit = to_decimal(regime_spec["standard_deduction"])
        std_ded = min(inp.gross_salary, std_ded_limit)
        clause_key = "STD_DEDUCTION_OLD" if regime == "OLD" else "STD_DEDUCTION_NEW_FY24_25"
        source_clauses["standard_deduction"] = OFFICIAL_TAX_SOURCES[clause_key].section

        # 2. HRA Exemption (only if enabled in compiled spec)
        exemptions: Dict[str, Decimal] = {}
        if regime_spec.get("hra_exemption_enabled", False):
            effective_basic = inp.get_effective_basic()
            ten_pct_basic = effective_basic * Decimal("0.10")
            excess_rent = inp.rent_paid - ten_pct_basic

            if inp.hra_received > Decimal("0") and excess_rent > Decimal("0"):
                metro_pct = Decimal("0.50") if inp.is_metro else Decimal("0.40")
                salary_cap = effective_basic * metro_pct
                hra_exempt = min(inp.hra_received, excess_rent, salary_cap)
                if hra_exempt > Decimal("0"):
                    exemptions["HRA"] = round_inr(hra_exempt)
                    source_clauses["hra_exemption"] = OFFICIAL_TAX_SOURCES["HRA_EXEMPTION"].section

        total_exemptions = sum(exemptions.values(), Decimal("0.00"))

        # 3. Chapter VI-A Deductions
        deductions: Dict[str, Decimal] = {}
        if regime_spec.get("chapter_via_enabled", False):
            caps = regime_spec.get("caps", {})

            # 80C
            c_cap = to_decimal(caps.get("section_80c", "150000.00"))
            c_val = min(inp.section_80c, c_cap)
            if c_val > Decimal("0"):
                deductions["80C"] = round_inr(c_val)
                source_clauses["80C"] = OFFICIAL_TAX_SOURCES["SEC_80C"].section

            # 80CCD(1B)
            nps_cap = to_decimal(caps.get("section_80ccd_1b", "50000.00"))
            nps_val = min(inp.section_80ccd_1b, nps_cap)
            if nps_val > Decimal("0"):
                deductions["80CCD(1B)"] = round_inr(nps_val)
                source_clauses["80CCD(1B)"] = OFFICIAL_TAX_SOURCES["SEC_80CCD_1B"].section

            # 80D
            self_cap_key = "section_80d_self_senior" if inp.is_senior_citizen_self else "section_80d_self_regular"
            parents_cap_key = "section_80d_parents_senior" if inp.is_senior_citizen_parents else "section_80d_parents_regular"
            d_self = min(inp.section_80d_self, to_decimal(caps.get(self_cap_key, "25000.00")))
            d_parents = min(inp.section_80d_parents, to_decimal(caps.get(parents_cap_key, "25000.00")))
            tot_80d = d_self + d_parents
            if tot_80d > Decimal("0"):
                deductions["80D"] = round_inr(tot_80d)
                source_clauses["80D"] = OFFICIAL_TAX_SOURCES["SEC_80D"].section

            # 24b
            hl_cap = to_decimal(caps.get("home_loan_interest_24b", "200000.00"))
            hl_val = min(inp.home_loan_interest_24b, hl_cap)
            if hl_val > Decimal("0"):
                deductions["24(b)"] = round_inr(hl_val)
                source_clauses["24(b)"] = OFFICIAL_TAX_SOURCES["SEC_24B"].section

        total_deductions = std_ded + sum(deductions.values(), Decimal("0.00"))

        # 4. Taxable Income
        net_income = max(Decimal("0.00"), inp.gross_salary - total_exemptions)
        taxable_income = max(Decimal("0.00"), net_income - total_deductions)
        taxable_income = round_inr(taxable_income)

        # 5. Compiled Slabs
        if regime == "OLD":
            raw_slabs = (
                regime_spec["slabs_senior"]
                if inp.is_senior_citizen_self
                else regime_spec["slabs_regular"]
            )
            source_clauses["tax_slabs"] = OFFICIAL_TAX_SOURCES["OLD_SLABS"].section
        else:
            raw_slabs = regime_spec["slabs"]
            clause_key = "NEW_SLABS_FY25_26" if fy == "2025-26" else "NEW_SLABS_FY24_25"
            source_clauses["tax_slabs"] = OFFICIAL_TAX_SOURCES[clause_key].section

        slabs = [
            SlabRate(
                lower_limit=to_decimal(s["lower"]),
                upper_limit=to_decimal(s["upper"]) if s["upper"] is not None else None,
                rate=to_decimal(s["rate"]),
            )
            for s in raw_slabs
        ]

        # 6. Slab Tax Calculation
        slab_tax = Decimal("0.00")
        slab_details: List[Dict[str, Any]] = []
        for slab in slabs:
            lower = slab.lower_limit
            upper = slab.upper_limit
            rate = slab.rate

            if taxable_income <= lower:
                break

            taxable_in_tier = (
                min(taxable_income, upper) - lower if upper is not None else taxable_income - lower
            )
            tax_in_tier = taxable_in_tier * rate
            slab_tax += tax_in_tier

            slab_details.append({
                "lower": float(lower),
                "upper": float(upper) if upper is not None else "Above",
                "rate_percent": float(rate * Decimal("100.0")),
                "taxable_amount": float(taxable_in_tier),
                "tax_amount": float(tax_in_tier),
            })

            if upper is not None and taxable_income <= upper:
                break

        slab_tax = round_inr(slab_tax)

        # 7. Section 87A Rebate & Marginal Relief
        rebate_cfg = regime_spec["rebate_87a"]
        rebate_threshold = to_decimal(rebate_cfg["threshold"])
        max_rebate = to_decimal(rebate_cfg["max_rebate"])
        has_marginal_relief = rebate_cfg.get("marginal_relief", False)

        rebate_87a = Decimal("0.00")
        marginal_relief_87a = Decimal("0.00")

        if taxable_income <= rebate_threshold:
            rebate_87a = min(slab_tax, max_rebate)
        elif has_marginal_relief:
            excess = taxable_income - rebate_threshold
            if slab_tax > excess:
                marginal_relief_87a = slab_tax - excess

        rebate_clause_key = (
            "REBATE_87A_OLD"
            if regime == "OLD"
            else ("REBATE_87A_NEW_FY25_26" if fy == "2025-26" else "REBATE_87A_NEW_FY24_25")
        )
        source_clauses["section_87a_rebate"] = OFFICIAL_TAX_SOURCES[rebate_clause_key].section

        tax_after_rebate = max(Decimal("0.00"), slab_tax - rebate_87a - marginal_relief_87a)

        # 8. Surcharge & Marginal Relief
        fifty_lakh = Decimal("5000000.00")
        one_crore = Decimal("10000000.00")
        two_crore = Decimal("20000000.00")
        five_crore = Decimal("50000000.00")
        surcharge = Decimal("0.00")
        surcharge_marginal_relief = Decimal("0.00")

        if taxable_income > fifty_lakh and tax_after_rebate > Decimal("0.00"):
            max_surch_rate = to_decimal(regime_spec.get("surcharge_max_rate", "0.25"))
            if taxable_income <= one_crore:
                surch_rate = Decimal("0.10")
                thresh = fifty_lakh
                prev_rate = Decimal("0.00")
            elif taxable_income <= two_crore:
                surch_rate = Decimal("0.15")
                thresh = one_crore
                prev_rate = Decimal("0.10")
            elif taxable_income <= five_crore:
                surch_rate = Decimal("0.25")
                thresh = two_crore
                prev_rate = Decimal("0.15")
            else:
                surch_rate = max_surch_rate
                thresh = five_crore
                prev_rate = Decimal("0.25")

            nom_surch = tax_after_rebate * surch_rate
            nom_tot = tax_after_rebate + nom_surch

            # Calculate threshold tax
            thresh_tax = Decimal("0.00")
            for slab in slabs:
                if thresh <= slab.lower_limit:
                    break
                t_in = min(thresh, slab.upper_limit) - slab.lower_limit if slab.upper_limit else thresh - slab.lower_limit
                thresh_tax += t_in * slab.rate
                if slab.upper_limit and thresh <= slab.upper_limit:
                    break

            thresh_tot = thresh_tax + (thresh_tax * prev_rate)
            max_allowed = thresh_tot + (taxable_income - thresh)

            if nom_tot > max_allowed:
                surcharge_marginal_relief = nom_tot - max_allowed
                surcharge = max(Decimal("0.00"), nom_surch - surcharge_marginal_relief)
            else:
                surcharge = nom_surch

        source_clauses["surcharge"] = OFFICIAL_TAX_SOURCES["SURCHARGE_MARGINAL_RELIEF"].section

        # 9. Health & Education Cess
        cess_rate = to_decimal(self.rules_spec.get("cess_rate", "0.04"))
        cess = round_inr((tax_after_rebate + surcharge) * cess_rate)
        source_clauses["cess"] = OFFICIAL_TAX_SOURCES["HEALTH_EDUCATION_CESS"].section

        # 10. Total Tax
        total_tax = round_inr(tax_after_rebate + surcharge + cess)
        effective_rate = (
            (total_tax / inp.gross_salary * Decimal("100.00")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if inp.gross_salary > Decimal("0.00")
            else Decimal("0.00")
        )

        return TaxBreakdown(
            financial_year=fy,
            regime=regime,
            gross_salary=inp.gross_salary,
            exemptions=exemptions,
            total_exemptions=total_exemptions,
            standard_deduction=std_ded,
            chapter_via_deductions=deductions,
            total_deductions=total_deductions,
            taxable_income=taxable_income,
            slab_tax=slab_tax,
            slab_details=slab_details,
            rebate_87a=rebate_87a,
            tax_after_rebate=tax_after_rebate,
            surcharge=surcharge,
            marginal_relief=marginal_relief_87a + surcharge_marginal_relief,
            cess=cess,
            total_tax=total_tax,
            effective_tax_rate_percent=effective_rate,
            source_clauses=source_clauses,
        )

