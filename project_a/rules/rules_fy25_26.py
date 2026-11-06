"""
Tax rules and rate configurations for Financial Year 2025-26 (Assessment Year 2026-27).
Implements the statutory changes introduced by the Finance Act, 2025.
Provides side-by-side comparability with FY 2024-25.
"""

from decimal import Decimal
from typing import List
from project_a.rules.base_rules import SlabRate
from project_a.rules.rules_fy24_25 import (
    OLD_REGIME_STANDARD_DEDUCTION,
    CAP_80C,
    CAP_80CCD_1B,
    CAP_80D_SELF_NON_SENIOR,
    CAP_80D_SELF_SENIOR,
    CAP_80D_PARENTS_NON_SENIOR,
    CAP_80D_PARENTS_SENIOR,
    CAP_24B_HOME_LOAN_INTEREST,
    OLD_87A_THRESHOLD,
    OLD_87A_MAX_REBATE,
    OLD_SLABS_REGULAR,
    OLD_SLABS_SENIOR,
    CESS_RATE,
)

# ==============================================================================
# NEW REGIME CONFIGURATION (FY 2025-26 - Finance Act, 2025)
# ==============================================================================

# Standard Deduction retained at ₹75,000
NEW_REGIME_STANDARD_DEDUCTION_FY25_26 = Decimal("75000.00")

# Section 87A Rebate under Finance Act 2025:
# Salaried individuals with taxable income up to ₹12,00,000 pay zero tax!
NEW_87A_THRESHOLD_FY25_26 = Decimal("1200000.00")
NEW_87A_MAX_REBATE_FY25_26 = Decimal("60000.00")

# Revised 7-tier Slabs under Finance Act, 2025
NEW_SLABS_FY25_26: List[SlabRate] = [
    SlabRate(lower_limit=Decimal("0.00"), upper_limit=Decimal("400000.00"), rate=Decimal("0.00")),
    SlabRate(lower_limit=Decimal("400000.00"), upper_limit=Decimal("800000.00"), rate=Decimal("0.05")),
    SlabRate(lower_limit=Decimal("800000.00"), upper_limit=Decimal("1200000.00"), rate=Decimal("0.10")),
    SlabRate(lower_limit=Decimal("1200000.00"), upper_limit=Decimal("1600000.00"), rate=Decimal("0.15")),
    SlabRate(lower_limit=Decimal("1600000.00"), upper_limit=Decimal("2000000.00"), rate=Decimal("0.20")),
    SlabRate(lower_limit=Decimal("2000000.00"), upper_limit=Decimal("2400000.00"), rate=Decimal("0.25")),
    SlabRate(lower_limit=Decimal("2400000.00"), upper_limit=None, rate=Decimal("0.30")),
]

