"""
Implementation 1: Deterministic Hand-Coded Indian Income Tax Engine.
Implements pure Decimal arithmetic with modular, provision-specific functions.
Covers FY 2024-25 and FY 2025-26 under both Old and New Tax Regimes.
Every calculation step is traced directly to its statutory legal clause.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from project_a.rules.base_rules import (
    SlabRate,
    TaxBreakdown,
    TaxInput,
    round_inr,
    to_decimal,
)
from project_a.rules.rules_fy24_25 import (
    CAP_24B_HOME_LOAN_INTEREST,
    CAP_80C,
    CAP_80CCD_1B,
    CAP_80D_PARENTS_NON_SENIOR,
    CAP_80D_PARENTS_SENIOR,
    CAP_80D_SELF_NON_SENIOR,
    CAP_80D_SELF_SENIOR,
    CESS_RATE,
    NEW_87A_MAX_REBATE_FY24_25,
    NEW_87A_THRESHOLD_FY24_25,
    NEW_REGIME_STANDARD_DEDUCTION_FY24_25,
    NEW_SLABS_FY24_25,
    OLD_87A_MAX_REBATE,
    OLD_87A_THRESHOLD,
    OLD_REGIME_STANDARD_DEDUCTION,
    OLD_SLABS_REGULAR,
    OLD_SLABS_SENIOR,
)
from project_a.rules.rules_fy25_26 import (
    NEW_87A_MAX_REBATE_FY25_26,
    NEW_87A_THRESHOLD_FY25_26,
    NEW_REGIME_STANDARD_DEDUCTION_FY25_26,
    NEW_SLABS_FY25_26,
)
from project_a.sources.tax_sources import OFFICIAL_TAX_SOURCES


def calculate_standard_deduction(
    gross_salary: Decimal, regime: str, financial_year: str
) -> Tuple[Decimal, str]:
    """
    Calculate Standard Deduction under Section 16(ia).
    - Old Regime: ₹50,000 (both FY 24-25 and FY 25-26)
    - New Regime FY 24-25: ₹75,000 (Finance (No. 2) Act 2024)
    - New Regime FY 25-26: ₹75,000 (Finance Act 2025)
    Cannot exceed gross salary.
    """
    if regime == "OLD":
        limit = OLD_REGIME_STANDARD_DEDUCTION
        clause_key = "STD_DEDUCTION_OLD"
    else:
        if financial_year == "2025-26":
            limit = NEW_REGIME_STANDARD_DEDUCTION_FY25_26
            clause_key = "STD_DEDUCTION_NEW_FY24_25"
        else:
            limit = NEW_REGIME_STANDARD_DEDUCTION_FY24_25
            clause_key = "STD_DEDUCTION_NEW_FY24_25"

    std_ded = min(gross_salary, limit)
    clause = OFFICIAL_TAX_SOURCES[clause_key].section
    return std_ded, clause


def calculate_hra_exemption(
    basic_salary: Decimal,
    hra_received: Decimal,
    rent_paid: Decimal,
    is_metro: bool,
    regime: str,
) -> Tuple[Decimal, str]:
    """
    Calculate HRA exemption under Section 10(13A) read with Rule 2A.
    Only available under Old Regime. In New Regime, HRA exemption is 0.
    Rule 2A formula: Least of:
    1. Actual HRA received
    2. Rent paid - 10% of (Basic + DA)
    3. 50% of Basic (Metro: Delhi, Mumbai, Kolkata, Chennai) or 40% (Non-Metro)
    """
    if regime == "NEW" or hra_received <= Decimal("0.00") or rent_paid <= Decimal("0.00"):
        return Decimal("0.00"), "Not applicable under New Regime or no rent paid"

    ten_percent_basic = basic_salary * Decimal("0.10")
    excess_rent = rent_paid - ten_percent_basic

    if excess_rent <= Decimal("0.00"):
        return Decimal("0.00"), OFFICIAL_TAX_SOURCES["HRA_EXEMPTION"].section

    metro_percentage = Decimal("0.50") if is_metro else Decimal("0.40")
    salary_limit = basic_salary * metro_percentage

    exemption = min(hra_received, excess_rent, salary_limit)
    return round_inr(max(Decimal("0.00"), exemption)), OFFICIAL_TAX_SOURCES["HRA_EXEMPTION"].section


def calculate_chapter_via_deductions(
    inp: TaxInput, regime: str
) -> Tuple[Dict[str, Decimal], Decimal, Dict[str, str]]:
    """
    Calculate Chapter VI-A deductions and Sec 24(b) home loan interest.
    Only available under Old Regime.
    """
    deductions: Dict[str, Decimal] = {}
    clauses: Dict[str, str] = {}

    if regime == "NEW":
        return deductions, Decimal("0.00"), clauses

    # 1. Section 80C (Capped at ₹1,50,000)
    c_ded = min(inp.section_80c, CAP_80C)
    if c_ded > Decimal("0.00"):
        deductions["80C"] = round_inr(c_ded)
        clauses["80C"] = OFFICIAL_TAX_SOURCES["SEC_80C"].section

    # 2. Section 80CCD(1B) (NPS, capped at ₹50,000)
    nps_ded = min(inp.section_80ccd_1b, CAP_80CCD_1B)
    if nps_ded > Decimal("0.00"):
        deductions["80CCD(1B)"] = round_inr(nps_ded)
        clauses["80CCD(1B)"] = OFFICIAL_TAX_SOURCES["SEC_80CCD_1B"].section

    # 3. Section 80D (Health Insurance)
    self_cap = CAP_80D_SELF_SENIOR if inp.is_senior_citizen_self else CAP_80D_SELF_NON_SENIOR
    parents_cap = CAP_80D_PARENTS_SENIOR if inp.is_senior_citizen_parents else CAP_80D_PARENTS_NON_SENIOR

    self_ded = min(inp.section_80d_self, self_cap)
    parents_ded = min(inp.section_80d_parents, parents_cap)
    total_80d = self_ded + parents_ded

    if total_80d > Decimal("0.00"):
        deductions["80D"] = round_inr(total_80d)
        clauses["80D"] = OFFICIAL_TAX_SOURCES["SEC_80D"].section

    # 4. Section 24(b) Home Loan Interest (Self-occupied capped at ₹2,00,000)
    hl_ded = min(inp.home_loan_interest_24b, CAP_24B_HOME_LOAN_INTEREST)
    if hl_ded > Decimal("0.00"):
        deductions["24(b)"] = round_inr(hl_ded)
        clauses["24(b)"] = OFFICIAL_TAX_SOURCES["SEC_24B"].section

    total = sum(deductions.values(), Decimal("0.00"))
    return deductions, total, clauses


def calculate_slab_tax(
    taxable_income: Decimal, slabs: List[SlabRate]
) -> Tuple[Decimal, List[Dict[str, Any]]]:
    """
    Progressively compute slab tax across configured tax slabs.
    Returns:
        total_slab_tax: Decimal
        slab_details: List of breakdown dicts for each tier
    """
    if taxable_income <= Decimal("0.00"):
        return Decimal("0.00"), []

    total_tax = Decimal("0.00")
    details: List[Dict[str, Any]] = []

    for slab in slabs:
        lower = slab.lower_limit
        upper = slab.upper_limit
        rate = slab.rate

        if taxable_income <= lower:
            # Income has not reached this slab
            break

        # Portion of income falling within this slab
        if upper is not None:
            taxable_in_slab = min(taxable_income, upper) - lower
        else:
            taxable_in_slab = taxable_income - lower

        tax_for_slab = taxable_in_slab * rate
        total_tax += tax_for_slab

        details.append({
            "lower": float(lower),
            "upper": float(upper) if upper is not None else "Above",
            "rate_percent": float(rate * Decimal("100.0")),
            "taxable_amount": float(taxable_in_slab),
            "tax_amount": float(tax_for_slab),
        })

        if upper is not None and taxable_income <= upper:
            break

    return round_inr(total_tax), details


def calculate_87a_rebate(
    taxable_income: Decimal, slab_tax: Decimal, regime: str, financial_year: str
) -> Tuple[Decimal, Decimal, str]:
    """
    Calculate Section 87A rebate and Section 87A marginal relief.

    Old Regime:
        Taxable income <= ₹5,00,000 -> 100% tax rebate (max ₹12,500).

    New Regime FY 2024-25:
        Taxable income <= ₹7,00,000 -> 100% tax rebate (max ₹25,000).
        First Proviso (Marginal Relief for 87A): If income marginally exceeds ₹7L,
        tax payable cannot exceed (taxable_income - ₹7,00,000).

    New Regime FY 2025-26 (Finance Act 2025):
        Taxable income <= ₹12,00,000 -> 100% tax rebate (max ₹60,000).
        Marginal Relief: tax payable cannot exceed (taxable_income - ₹12,00,000).

    Returns:
        (rebate_87a, marginal_relief_87a, clause)
    """
    rebate = Decimal("0.00")
    marginal_relief = Decimal("0.00")

    if regime == "OLD":
        if taxable_income <= OLD_87A_THRESHOLD:
            rebate = min(slab_tax, OLD_87A_MAX_REBATE)
        return round_inr(rebate), Decimal("0.00"), OFFICIAL_TAX_SOURCES["REBATE_87A_OLD"].section

    # NEW REGIME
    if financial_year == "2025-26":
        threshold = NEW_87A_THRESHOLD_FY25_26
        max_rebate = NEW_87A_MAX_REBATE_FY25_26
        clause = OFFICIAL_TAX_SOURCES["REBATE_87A_NEW_FY25_26"].section
    else:
        threshold = NEW_87A_THRESHOLD_FY24_25
        max_rebate = NEW_87A_MAX_REBATE_FY24_25
        clause = OFFICIAL_TAX_SOURCES["REBATE_87A_NEW_FY24_25"].section

    if taxable_income <= threshold:
        rebate = min(slab_tax, max_rebate)
    else:
        # Check Section 87A marginal relief
        excess_income = taxable_income - threshold
        if slab_tax > excess_income:
            # Tax payable cannot exceed excess income over threshold
            marginal_relief = slab_tax - excess_income

    return round_inr(rebate), round_inr(marginal_relief), clause


def calculate_surcharge_and_marginal_relief(
    taxable_income: Decimal,
    tax_after_rebate: Decimal,
    regime: str,
    slabs: List[SlabRate],
) -> Tuple[Decimal, Decimal, str]:
    """
    Calculate Surcharge on high income and statutory Marginal Relief on Surcharge.

    Surcharge rates:
    - ₹50 Lakh to ₹1 Crore: 10%
    - ₹1 Crore to ₹2 Crore: 15%
    - ₹2 Crore to ₹5 Crore: 25%
    - Above ₹5 Crore: 37% (Old Regime), capped at 25% (New Regime)

    Marginal Relief ensures:
    Total (Tax + Surcharge) <= (Tax on threshold with applicable surcharge) + (Income - Threshold).

    Returns:
        (effective_surcharge, marginal_relief, clause)
    """
    fifty_lakh = Decimal("5000000.00")
    one_crore = Decimal("10000000.00")
    two_crore = Decimal("20000000.00")
    five_crore = Decimal("50000000.00")

    if taxable_income <= fifty_lakh or tax_after_rebate <= Decimal("0.00"):
        return Decimal("0.00"), Decimal("0.00"), "No surcharge below ₹50 Lakh"

    # Determine applicable surcharge bracket and threshold
    if taxable_income <= one_crore:
        rate = Decimal("0.10")
        threshold = fifty_lakh
        prev_surcharge_rate = Decimal("0.00")
    elif taxable_income <= two_crore:
        rate = Decimal("0.15")
        threshold = one_crore
        prev_surcharge_rate = Decimal("0.10")
    elif taxable_income <= five_crore:
        rate = Decimal("0.25")
        threshold = two_crore
        prev_surcharge_rate = Decimal("0.15")
    else:
        # Above 5 Crore
        rate = Decimal("0.25") if regime == "NEW" else Decimal("0.37")
        threshold = five_crore
        prev_surcharge_rate = Decimal("0.25")

    nominal_surcharge = tax_after_rebate * rate
    nominal_total = tax_after_rebate + nominal_surcharge

    # Calculate tax payable at threshold
    threshold_tax, _ = calculate_slab_tax(threshold, slabs)
    threshold_surcharge = threshold_tax * prev_surcharge_rate
    max_allowable_tax = threshold_tax + threshold_surcharge + (taxable_income - threshold)

    if nominal_total > max_allowable_tax:
        marginal_relief = nominal_total - max_allowable_tax
        effective_surcharge = max(Decimal("0.00"), nominal_surcharge - marginal_relief)
    else:
        marginal_relief = Decimal("0.00")
        effective_surcharge = nominal_surcharge

    return (
        round_inr(effective_surcharge),
        round_inr(marginal_relief),
        OFFICIAL_TAX_SOURCES["SURCHARGE_MARGINAL_RELIEF"].section,
    )


def calculate_cess(tax_subject_to_cess: Decimal) -> Tuple[Decimal, str]:
    """
    Calculate 4% Health and Education Cess under Section 115JB / Finance Acts.
    """
    cess = round_inr(tax_subject_to_cess * CESS_RATE)
    return cess, OFFICIAL_TAX_SOURCES["HEALTH_EDUCATION_CESS"].section


def calculate_tax(inp: TaxInput, regime: str = "NEW") -> TaxBreakdown:
    """
    Master tax calculation pipeline for salaried individuals.
    Deterministic, auditable, and backed by statutory references.

    Args:
        inp: Salaried individual financial input
        regime: "OLD" or "NEW"

    Returns:
        TaxBreakdown containing detailed audit trail and exact amounts.
    """
    regime = regime.upper().strip()
    if regime not in ("OLD", "NEW"):
        raise ValueError(f"Invalid tax regime '{regime}'. Must be 'OLD' or 'NEW'.")

    fy = inp.financial_year.strip()
    if fy not in ("2024-25", "2025-26"):
        raise ValueError(f"Invalid financial year '{fy}'. Supported: '2024-25', '2025-26'.")

    source_clauses: Dict[str, str] = {}

    # 1. Standard Deduction
    std_ded, std_clause = calculate_standard_deduction(inp.gross_salary, regime, fy)
    source_clauses["standard_deduction"] = std_clause

    # 2. HRA Exemption (Old Regime only)
    effective_basic = inp.get_effective_basic()
    hra_exemption, hra_clause = calculate_hra_exemption(
        basic_salary=effective_basic,
        hra_received=inp.hra_received,
        rent_paid=inp.rent_paid,
        is_metro=inp.is_metro,
        regime=regime,
    )
    exemptions: Dict[str, Decimal] = {}
    if hra_exemption > Decimal("0.00"):
        exemptions["HRA"] = hra_exemption
        source_clauses["hra_exemption"] = hra_clause
    total_exemptions = sum(exemptions.values(), Decimal("0.00"))

    # 3. Chapter VI-A Deductions
    chap_via, total_chap_via, chap_clauses = calculate_chapter_via_deductions(inp, regime)
    source_clauses.update(chap_clauses)

    total_deductions = std_ded + total_chap_via

    # 4. Taxable Income (Rounded to nearest 10 rupees per Section 288A in actual IT Act, here exact Decimal)
    net_after_exemptions = max(Decimal("0.00"), inp.gross_salary - total_exemptions)
    taxable_income = max(Decimal("0.00"), net_after_exemptions - total_deductions)
    taxable_income = round_inr(taxable_income)

    # 5. Slabs Selection
    if regime == "OLD":
        slabs = OLD_SLABS_SENIOR if inp.is_senior_citizen_self else OLD_SLABS_REGULAR
        source_clauses["tax_slabs"] = OFFICIAL_TAX_SOURCES["OLD_SLABS"].section
    else:
        if fy == "2025-26":
            slabs = NEW_SLABS_FY25_26
            source_clauses["tax_slabs"] = OFFICIAL_TAX_SOURCES["NEW_SLABS_FY25_26"].section
        else:
            slabs = NEW_SLABS_FY24_25
            source_clauses["tax_slabs"] = OFFICIAL_TAX_SOURCES["NEW_SLABS_FY24_25"].section

    # 6. Slab Tax
    slab_tax, slab_details = calculate_slab_tax(taxable_income, slabs)

    # 7. Section 87A Rebate & 87A Marginal Relief
    rebate_87a, relief_87a, rebate_clause = calculate_87a_rebate(
        taxable_income, slab_tax, regime, fy
    )
    source_clauses["section_87a_rebate"] = rebate_clause

    tax_after_rebate = max(Decimal("0.00"), slab_tax - rebate_87a - relief_87a)

    # 8. Surcharge & Surcharge Marginal Relief
    surcharge, surcharge_marginal_relief, surcharge_clause = calculate_surcharge_and_marginal_relief(
        taxable_income=taxable_income,
        tax_after_rebate=tax_after_rebate,
        regime=regime,
        slabs=slabs,
    )
    source_clauses["surcharge"] = surcharge_clause

    # 9. Health & Education Cess (4%)
    tax_subject_to_cess = tax_after_rebate + surcharge
    cess, cess_clause = calculate_cess(tax_subject_to_cess)
    source_clauses["cess"] = cess_clause

    # 10. Total Tax Payable
    total_tax = round_inr(tax_subject_to_cess + cess)

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
        chapter_via_deductions=chap_via,
        total_deductions=total_deductions,
        taxable_income=taxable_income,
        slab_tax=slab_tax,
        slab_details=slab_details,
        rebate_87a=rebate_87a,
        tax_after_rebate=tax_after_rebate,
        surcharge=surcharge,
        marginal_relief=relief_87a + surcharge_marginal_relief,
        cess=cess,
        total_tax=total_tax,
        effective_tax_rate_percent=effective_rate,
        source_clauses=source_clauses,
    )
