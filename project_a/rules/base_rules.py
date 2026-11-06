"""
Base models, data structures, and interfaces for the Indian Income Tax Engine.
Enforces strict Decimal arithmetic across all monetary values to prevent floating-point precision loss.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


def to_decimal(val: Any) -> Decimal:
    """Helper to safely convert int, float, str, or Decimal to Decimal."""
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def round_inr(val: Decimal) -> Decimal:
    """Round to nearest rupee or 2 decimal places using standard commercial ROUND_HALF_UP."""
    return val.quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)


class TaxInput(BaseModel):
    """
    Standardized salaried individual tax input model.
    All financial amounts use Decimal.
    """
    gross_salary: Decimal = Field(..., description="Annual Gross Salary in INR")
    basic_salary: Optional[Decimal] = Field(
        default=None,
        description="Annual Basic Salary + DA in INR (defaults to 50% of gross if omitted)"
    )
    hra_received: Decimal = Field(default=Decimal("0.00"), description="Annual HRA received")
    rent_paid: Decimal = Field(default=Decimal("0.00"), description="Annual Rent paid")
    is_metro: bool = Field(
        default=False,
        description="Whether residential accommodation is in Delhi, Mumbai, Kolkata, or Chennai"
    )
    section_80c: Decimal = Field(default=Decimal("0.00"), description="Investments under 80C")
    section_80ccd_1b: Decimal = Field(default=Decimal("0.00"), description="NPS under 80CCD(1B)")
    section_80d_self: Decimal = Field(default=Decimal("0.00"), description="Health insurance self/family")
    is_senior_citizen_self: bool = Field(default=False, description="Is individual >= 60 years")
    section_80d_parents: Decimal = Field(default=Decimal("0.00"), description="Health insurance for parents")
    is_senior_citizen_parents: bool = Field(default=False, description="Are parents >= 60 years")
    home_loan_interest_24b: Decimal = Field(
        default=Decimal("0.00"),
        description="Interest paid on self-occupied house property loan (Section 24b)"
    )
    financial_year: str = Field(default="2024-25", description="FY: '2024-25' or '2025-26'")

    @field_validator(
        "gross_salary", "basic_salary", "hra_received", "rent_paid",
        "section_80c", "section_80ccd_1b", "section_80d_self",
        "section_80d_parents", "home_loan_interest_24b",
        mode="before"
    )
    @classmethod
    def parse_to_decimal(cls, v):
        if v is None:
            return None
        return to_decimal(v)

    def get_effective_basic(self) -> Decimal:
        """Standard Indian industry benchmark: Basic is 50% of gross if not specified."""
        if self.basic_salary is not None and self.basic_salary > Decimal("0"):
            return min(self.basic_salary, self.gross_salary)
        return (self.gross_salary * Decimal("0.50")).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)


class SlabRate(BaseModel):
    """Tax Slab tier specification."""
    lower_limit: Decimal
    upper_limit: Optional[Decimal] = None  # None indicates infinity (top bracket)
    rate: Decimal                         # e.g., Decimal("0.05") for 5%


class TaxBreakdown(BaseModel):
    """
    Detailed, auditable tax calculation breakdown with source clauses.
    """
    financial_year: str
    regime: str  # "OLD" or "NEW"
    gross_salary: Decimal
    exemptions: Dict[str, Decimal] = Field(default_factory=dict)
    total_exemptions: Decimal = Decimal("0.00")
    standard_deduction: Decimal = Decimal("0.00")
    chapter_via_deductions: Dict[str, Decimal] = Field(default_factory=dict)
    total_deductions: Decimal = Decimal("0.00")
    taxable_income: Decimal = Decimal("0.00")
    slab_tax: Decimal = Decimal("0.00")
    slab_details: List[Dict[str, Any]] = Field(default_factory=list)
    rebate_87a: Decimal = Decimal("0.00")
    tax_after_rebate: Decimal = Decimal("0.00")
    surcharge: Decimal = Decimal("0.00")
    marginal_relief: Decimal = Decimal("0.00")
    cess: Decimal = Decimal("0.00")
    total_tax: Decimal = Decimal("0.00")
    effective_tax_rate_percent: Decimal = Decimal("0.00")
    source_clauses: Dict[str, str] = Field(default_factory=dict)

