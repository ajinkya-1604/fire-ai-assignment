"""
Tax rules and rate configurations for Financial Year 2024-25 (Assessment Year 2025-26).
Implements provisions of the Income-tax Act, 1961 as amended by Finance (No. 2) Act, 2024.
All rates, caps, and slab structures use Decimal.
"""

from decimal import Decimal
from typing import List
from project_a.rules.base_rules import SlabRate

# ==============================================================================
# OLD REGIME CONFIGURATION (FY 2024-25)
# ==============================================================================

# Standard Deduction under Section 16(ia)
OLD_REGIME_STANDARD_DEDUCTION = Decimal("50000.00")

# Chapter VI-A Deduction Caps
CAP_80C = Decimal("150000.00")
CAP_80CCD_1B = Decimal("50000.00")
CAP_80D_SELF_NON_SENIOR = Decimal("25000.00")
CAP_80D_SELF_SENIOR = Decimal("50000.00")
CAP_80D_PARENTS_NON_SENIOR = Decimal("25000.00")
CAP_80D_PARENTS_SENIOR = Decimal("50000.00")
CAP_24B_HOME_LOAN_INTEREST = Decimal("200000.00")

# Section 87A Rebate Threshold & Max Amount (Old Regime)
OLD_87A_THRESHOLD = Decimal("500000.00")
OLD_87A_MAX_REBATE = Decimal("12500.00")

# Slabs for Individuals (<60 years)
OLD_SLABS_REGULAR: List[SlabRate] = [
    SlabRate(lower_limit=Decimal("0.00"), upper_limit=Decimal("250000.00"), rate=Decimal("0.00")),
    SlabRate(lower_limit=Decimal("250000.00"), upper_limit=Decimal("500000.00"), rate=Decimal("0.05")),
    SlabRate(lower_limit=Decimal("500000.00"), upper_limit=Decimal("1000000.00"), rate=Decimal("0.20")),
    SlabRate(lower_limit=Decimal("1000000.00"), upper_limit=None, rate=Decimal("0.30")),
]

# Slabs for Senior Citizens (>= 60 years)
OLD_SLABS_SENIOR: List[SlabRate] = [
    SlabRate(lower_limit=Decimal("0.00"), upper_limit=Decimal("300000.00"), rate=Decimal("0.00")),
    SlabRate(lower_limit=Decimal("300000.00"), upper_limit=Decimal("500000.00"), rate=Decimal("0.05")),
    SlabRate(lower_limit=Decimal("500000.00"), upper_limit=Decimal("1000000.00"), rate=Decimal("0.20")),
    SlabRate(lower_limit=Decimal("1000000.00"), upper_limit=None, rate=Decimal("0.30")),
]

# ==============================================================================
# NEW REGIME CONFIGURATION (FY 2024-25 - Section 115BAC)
# As amended by Finance (No. 2) Act, 2024 (Budget July 2024)
# ==============================================================================

# Enhanced Standard Deduction under Section 16(ia)
NEW_REGIME_STANDARD_DEDUCTION_FY24_25 = Decimal("75000.00")

# Section 87A Rebate under New Regime (FY 2024-25)
# Full rebate up to ₹7,00,000 taxable income (max ₹25,000 rebate)
NEW_87A_THRESHOLD_FY24_25 = Decimal("700000.00")
NEW_87A_MAX_REBATE_FY24_25 = Decimal("25000.00")

# Revised 6-tier Slabs under Finance (No. 2) Act, 2024
NEW_SLABS_FY24_25: List[SlabRate] = [
    SlabRate(lower_limit=Decimal("0.00"), upper_limit=Decimal("300000.00"), rate=Decimal("0.00")),
    SlabRate(lower_limit=Decimal("300000.00"), upper_limit=Decimal("700000.00"), rate=Decimal("0.05")),
    SlabRate(lower_limit=Decimal("700000.00"), upper_limit=Decimal("1000000.00"), rate=Decimal("0.10")),
    SlabRate(lower_limit=Decimal("1000000.00"), upper_limit=Decimal("1200000.00"), rate=Decimal("0.15")),
    SlabRate(lower_limit=Decimal("1200000.00"), upper_limit=Decimal("1500000.00"), rate=Decimal("0.20")),
    SlabRate(lower_limit=Decimal("1500000.00"), upper_limit=None, rate=Decimal("0.30")),
]

# Health & Education Cess
CESS_RATE = Decimal("0.04")

