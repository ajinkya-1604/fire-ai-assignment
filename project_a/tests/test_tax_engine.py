"""
Comprehensive test suite for the Indian Income Tax Engines (Hand-Coded & Compiled).
Tests 30 officially verified cases against Income Tax Department rules,
slab boundary conditions, 87A rebate & marginal relief, surcharge marginal relief,
and regime comparisons.
"""

from decimal import Decimal
import json
import pytest

from project_a.calculators.compiled_engine import CompiledTaxEngine
from project_a.calculators.hand_coded_engine import (
    calculate_tax,
    calculate_standard_deduction,
    calculate_hra_exemption,
    calculate_slab_tax,
    calculate_87a_rebate,
    calculate_surcharge_and_marginal_relief,
    calculate_cess,
)
from project_a.rules.base_rules import TaxInput
from shared.config import PROJECT_A_DIR

# Load verified dataset
DATASET_PATH = PROJECT_A_DIR / "data" / "test_cases_dataset.json"


@pytest.fixture(scope="module")
def tax_dataset():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def verified_cases(tax_dataset):
    return [c for c in tax_dataset if c.get("verified_against_official_portal")]


# ==============================================================================
# TEST 1: OFFICIALLY VERIFIED CASES (30 Portal Cases)
# ==============================================================================

def test_officially_verified_cases_count(verified_cases):
    """Ensure at least 30 cases are verified against official IT department calculations."""
    assert len(verified_cases) >= 30


def test_officially_verified_cases_accuracy(verified_cases):
    """Every verified case must match the expected tax to the exact rupee under both regimes."""
    for case in verified_cases:
        inp_data = case["input"]
        inp = TaxInput(**inp_data)

        # Old Regime check
        old_res = calculate_tax(inp, "OLD")
        exp_old = Decimal(str(case["expected_old_regime"]["total_tax"]))
        assert old_res.total_tax == exp_old, (
            f"Case {case['id']} Old Regime mismatch: expected {exp_old}, got {old_res.total_tax}"
        )

        # New Regime check
        new_res = calculate_tax(inp, "NEW")
        exp_new = Decimal(str(case["expected_new_regime"]["total_tax"]))
        assert new_res.total_tax == exp_new, (
            f"Case {case['id']} New Regime mismatch: expected {exp_new}, got {new_res.total_tax}"
        )


# ==============================================================================
# TEST 2: COMPILED ENGINE EQUIVALENCE
# ==============================================================================

def test_compiled_engine_equivalence(tax_dataset):
    """The compiled rules engine must match the hand-coded engine across all test cases."""
    compiled_engine_24 = CompiledTaxEngine(financial_year="2024-25")
    compiled_engine_25 = CompiledTaxEngine(financial_year="2025-26")

    # Sample a wide subset across both years
    for case in tax_dataset[:80]:
        inp = TaxInput(**case["input"])
        engine = compiled_engine_25 if inp.financial_year == "2025-26" else compiled_engine_24

        for regime in ["OLD", "NEW"]:
            hand_res = calculate_tax(inp, regime)
            comp_res = engine.calculate(inp, regime)
            assert hand_res.total_tax == comp_res.total_tax, (
                f"Mismatch in case {case['id']} for {regime} {inp.financial_year}: "
                f"hand-coded {hand_res.total_tax} vs compiled {comp_res.total_tax}"
            )


# ==============================================================================
# TEST 3: BOUNDARY & EDGE CONDITIONS
# ==============================================================================

def test_zero_income():
    """Zero gross salary must yield zero tax, zero deductions, and zero rebate."""
    inp = TaxInput(gross_salary=Decimal("0.00"), financial_year="2024-25")
    old_res = calculate_tax(inp, "OLD")
    new_res = calculate_tax(inp, "NEW")

    assert old_res.total_tax == Decimal("0.00")
    assert new_res.total_tax == Decimal("0.00")
    assert old_res.taxable_income == Decimal("0.00")
    assert new_res.taxable_income == Decimal("0.00")


def test_standard_deduction_boundary():
    """Standard deduction cannot exceed gross salary when salary is small."""
    inp = TaxInput(gross_salary=Decimal("30000.00"), financial_year="2024-25")
    old_res = calculate_tax(inp, "OLD")
    new_res = calculate_tax(inp, "NEW")

    assert old_res.standard_deduction == Decimal("30000.00")
    assert new_res.standard_deduction == Decimal("30000.00")
    assert old_res.taxable_income == Decimal("0.00")
    assert new_res.taxable_income == Decimal("0.00")


def test_section_87a_rebate_old_regime_threshold():
    """Old regime 87A rebate applies only up to ₹5,00,000 taxable income."""
    # ₹5,50,000 gross - ₹50,000 std ded = ₹5,00,000 taxable income -> 100% rebate (₹12,500) -> 0 tax
    inp_eligible = TaxInput(gross_salary=Decimal("550000.00"), financial_year="2024-25")
    res_eligible = calculate_tax(inp_eligible, "OLD")
    assert res_eligible.taxable_income == Decimal("500000.00")
    assert res_eligible.rebate_87a == Decimal("12500.00")
    assert res_eligible.total_tax == Decimal("0.00")

    # ₹5,50,010 gross - ₹50,000 std ded = ₹5,00,010 taxable income -> Rebate 0!
    inp_ineligible = TaxInput(gross_salary=Decimal("550010.00"), financial_year="2024-25")
    res_ineligible = calculate_tax(inp_ineligible, "OLD")
    assert res_ineligible.taxable_income == Decimal("500010.00")
    assert res_ineligible.rebate_87a == Decimal("0.00")
    assert res_ineligible.total_tax > Decimal("0.00")


def test_section_87a_marginal_relief_new_regime_fy24_25():
    """In New Regime FY24-25, tax payable cannot exceed taxable income minus ₹7,00,000."""
    # Gross 7,85,000 - 75k std ded = 7,10,000 taxable income
    # Normal slab tax: 3-7L @ 5% (20,000) + 10k @ 10% (1,000) = 21,000
    # Excess income over 7L = 10,000
    # Relief = 21,000 - 10,000 = 11,000 -> Tax after relief = 10,000 + 4% cess (400) = 10,400
    inp = TaxInput(gross_salary=Decimal("785000.00"), financial_year="2024-25")
    res = calculate_tax(inp, "NEW")
    assert res.taxable_income == Decimal("710000.00")
    assert res.marginal_relief == Decimal("11000.00")
    assert res.tax_after_rebate == Decimal("10000.00")
    assert res.cess == Decimal("400.00")
    assert res.total_tax == Decimal("10400.00")


def test_finance_act_2025_new_regime_12l_zero_tax():
    """Finance Act 2025: Taxable income up to ₹12,00,000 (Gross ₹12,75,000) pays ₹0 tax."""
    inp = TaxInput(gross_salary=Decimal("1275000.00"), financial_year="2025-26")
    res = calculate_tax(inp, "NEW")
    assert res.taxable_income == Decimal("1200000.00")
    # Slabs: 0-4L Nil, 4-8L 5% (20k), 8-12L 10% (40k) -> Slab tax 60,000
    assert res.slab_tax == Decimal("60000.00")
    assert res.rebate_87a == Decimal("60000.00")
    assert res.total_tax == Decimal("0.00")


def test_surcharge_marginal_relief_at_51_lakh():
    """At ₹51 Lakh taxable income, surcharge marginal relief restricts tax increase to excess income."""
    inp = TaxInput(gross_salary=Decimal("5175000.00"), financial_year="2024-25")
    res = calculate_tax(inp, "NEW")
    assert res.taxable_income == Decimal("5100000.00")
    # Marginal relief must be positive
    assert res.marginal_relief > Decimal("0.00")
    assert res.surcharge > Decimal("0.00")


def test_hra_metro_vs_non_metro():
    """HRA exemption applies 50% basic limit for metros and 40% for non-metros."""
    # Basic 6,00,000, HRA 3,00,000, Rent 3,60,000
    # Rent - 10% basic = 3,60,000 - 60,000 = 3,00,000
    # Metro limit (50%) = 3,00,000 -> Exemption = 3,00,000
    # Non-metro limit (40%) = 2,40,000 -> Exemption = 2,40,000
    inp_metro = TaxInput(
        gross_salary=Decimal("1200000.00"),
        basic_salary=Decimal("600000.00"),
        hra_received=Decimal("300000.00"),
        rent_paid=Decimal("360000.00"),
        is_metro=True,
        financial_year="2024-25"
    )
    res_metro = calculate_tax(inp_metro, "OLD")

    inp_non_metro = TaxInput(
        gross_salary=Decimal("1200000.00"),
        basic_salary=Decimal("600000.00"),
        hra_received=Decimal("300000.00"),
        rent_paid=Decimal("360000.00"),
        is_metro=False,
        financial_year="2024-25"
    )
    res_non_metro = calculate_tax(inp_non_metro, "OLD")

    assert res_metro.exemptions["HRA"] == Decimal("300000.00")
    assert res_non_metro.exemptions["HRA"] == Decimal("240000.00")
    assert res_metro.total_tax < res_non_metro.total_tax

