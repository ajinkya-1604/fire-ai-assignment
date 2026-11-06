"""
Plain-Language Tax Input Parser supporting English and Hinglish natural language.
Parses conversational salary and deduction declarations into structured TaxInput objects.
Explicitly detects missing critical fields, contradictory statements, and ambiguous values.
Asks targeted clarification questions without ever inventing missing numbers.
"""

from decimal import Decimal
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from project_a.rules.base_rules import TaxInput, round_inr, to_decimal
from shared.logging_config import get_logger

logger = get_logger("tax_input_parser")


class ParseResult(BaseModel):
    """Structured result of plain-language input parsing."""
    raw_query: str
    is_valid: bool
    tax_input: Optional[TaxInput] = None
    clarification_question: Optional[str] = None
    contradictions: List[str] = Field(default_factory=list)
    ambiguities: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    detected_fields: Dict[str, Any] = Field(default_factory=dict)


def parse_indian_amount(amount_str: str) -> Optional[Decimal]:
    """
    Parse an Indian currency amount string with support for L/Lakh/Lac, Cr/Crore, K/Thousand.
    Examples:
        '12 lakh' -> 1200000
        '1.5L' -> 150000
        '20k' -> 20000
        '1.2 crore' -> 12000000
        '80,000' -> 80000
    """
    if not amount_str:
        return None

    clean = amount_str.lower().replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "").strip()

    # Match Crore / Cr
    cr_match = re.search(r"([\d\.]+)\s*(?:crore|crores|cr)", clean)
    if cr_match:
        try:
            return round_inr(Decimal(cr_match.group(1)) * Decimal("10000000"))
        except Exception:
            return None

    # Match Lakh / Lac / L
    lakh_match = re.search(r"([\d\.]+)\s*(?:lakh|lakhs|lac|lacs|lpa|l\b)", clean)
    if lakh_match:
        try:
            return round_inr(Decimal(lakh_match.group(1)) * Decimal("100000"))
        except Exception:
            return None

    # Match Thousand / K
    k_match = re.search(r"([\d\.]+)\s*(?:thousand|thousands|k\b)", clean)
    if k_match:
        try:
            return round_inr(Decimal(k_match.group(1)) * Decimal("1000"))
        except Exception:
            return None

    # Match raw number
    raw_match = re.search(r"^[\d\.]+$", clean)
    if raw_match:
        try:
            return round_inr(Decimal(clean))
        except Exception:
            return None

    return None


class TaxInputParser:
    """
    Deterministic rule-based NLP parser with Hinglish and English entity extraction.
    Adheres strictly to requirement: 'Never invent missing values. When essential
    information is missing, ask a clarification question.'
    """

    METRO_CITIES = {"delhi", "mumbai", "kolkata", "chennai", "bombay", "calcutta", "new delhi"}

    def _extract_amount_around_keywords(
        self, text: str, keywords: List[str]
    ) -> Optional[Decimal]:
        """
        Search for amounts either before or after any of the keywords.
        Handles both:
        - 'invested 1.5 lakh in 80C' (amount before keyword)
        - '80C investment is 1.5 lakh' (amount after keyword)
        """
        for kw in keywords:
            # Pattern 1: keyword ... amount
            pattern_after = rf"{kw}\s*(?:me|investment|invested|invest|of|is|around|paid|ke liye|bima|interest|byaj|hai)?\s*([₹]?\s*[\d\.,]+\s*(?:crore|crores|cr|lakh|lakhs|lac|lacs|lpa|l|k|thousand|thousands)?)"
            m1 = re.search(pattern_after, text)
            if m1:
                val = parse_indian_amount(m1.group(1))
                if val is not None and val > Decimal("0"):
                    return val

            # Pattern 2: amount ... keyword
            pattern_before = rf"([₹]?\s*[\d\.,]+\s*(?:crore|crores|cr|lakh|lakhs|lac|lacs|lpa|l|k|thousand|thousands)?)\s*(?:in|me|towards|for|ka|ki|monthly|per month)?\s*{kw}"
            m2 = re.search(pattern_before, text)
            if m2:
                val = parse_indian_amount(m2.group(1))
                if val is not None and val > Decimal("0"):
                    return val

        return None

    def parse(self, text: str) -> ParseResult:
        """Parse natural language query into TaxInput or generate clarification request."""
        text_clean = text.strip()
        lower = text_clean.lower()

        contradictions: List[str] = []
        ambiguities: List[str] = []
        detected: Dict[str, Any] = {}

        # 1. Financial Year Detection
        fy = "2024-25"
        if any(term in lower for term in ["2025-26", "fy25-26", "ay 2026-27", "next year", "budget 2025"]):
            fy = "2025-26"
        detected["financial_year"] = fy

        # 2. Metro City Detection
        is_metro = any(city in lower for city in self.METRO_CITIES)
        if "metro" in lower and "non-metro" not in lower:
            is_metro = True
        detected["is_metro"] = is_metro

        # 3. Salary / Income Detection
        monthly_salary: Optional[Decimal] = None
        annual_salary: Optional[Decimal] = None

        # Check for explicit annual salary (excluding monthly indicators)
        annual_m = re.search(
            r"(?<!monthly\s)(?:annual salary|gross salary|annual ctc|annual package|ctc|package|saal ka vetan|salary|earn|earns|earning|income)\s*(?:is|of|around|hai)?\s*([₹]?\s*[\d\.,]+\s*(?:crore|crores|cr|lakh|lakhs|lac|lacs|lpa|l|k|thousand)?)(?!\s*(?:in 80|towards 80|rent|kiraya|mediclaim|health|per month|monthly|p\.m\.|har mahine|mahina))",
            lower,
        )
        if annual_m:
            val = parse_indian_amount(annual_m.group(1))
            if val and val > Decimal("0"):
                annual_salary = val
        else:
            # Check generic salary if not explicitly monthly
            if not re.search(r"(?:salary|package|ctc)\s*(?:is|of)?\s*[^,\.]*?(?:per month|monthly|har mahine)", lower):
                gen_m = re.search(
                    r"(?:salary|vetan|tankhwah)\s*(?:is|of|around|hai)?\s*([₹]?\s*[\d\.,]+\s*(?:crore|crores|cr|lakh|lakhs|lac|lacs|lpa|l|k|thousand)?)(?!\s*(?:in 80|rent|kiraya|mediclaim))",
                    lower,
                )
                if gen_m:
                    val = parse_indian_amount(gen_m.group(1))
                    if val and val > Decimal("0"):
                        annual_salary = val

        # Check for explicit monthly salary / earning
        monthly_m = re.search(
            r"(?:monthly salary|monthly package|earn|earns|earning|kamata|kamaata)\s*(?:is|of|around|hai)?\s*([₹]?\s*[\d\.,]+\s*(?:lakh|l|k|thousand)?)\s*(?:per month|monthly|p\.m\.|har mahine|mahina|mahine)",
            lower,
        )
        if monthly_m:
            val = parse_indian_amount(monthly_m.group(1))
            if val and val > Decimal("0"):
                monthly_salary = val
        else:
            # Pattern: '100k per month' or '75,000 monthly'
            m_alt = re.search(
                r"([₹]?\s*[\d\.,]+\s*(?:lakh|l|k|thousand)?)\s*(?:per month|monthly|p\.m\.|har mahine|mahina)\b",
                lower,
            )
            if m_alt:
                # Ensure this is not rent
                context = lower[max(0, m_alt.start()-20):min(len(lower), m_alt.end()+20)]
                if "rent" not in context and "kiraya" not in context and "bhaada" not in context:
                    val = parse_indian_amount(m_alt.group(1))
                    if val and val > Decimal("0"):
                        monthly_salary = val

        # Check LPA format
        if not annual_salary:
            lpa_m = re.search(r"([₹]?\s*[\d\.,]+)\s*lpa\b", lower)
            if lpa_m:
                val = parse_indian_amount(lpa_m.group(1) + " lakh")
                if val:
                    annual_salary = val

        # Check for ambiguous raw number salary
        if not annual_salary and not monthly_salary:
            generic_salary = re.search(
                r"(?:salary|package|ctc|income|earning|kamata|kamaata)\s*(?:hai)?\s*(?:of|is|around)?\s*([₹]?\s*[\d\.,]+)(?!\s*(?:in 80|rent|kiraya|mediclaim))",
                lower,
            )
            if generic_salary:
                val = parse_indian_amount(generic_salary.group(1))
                if val:
                    if val < Decimal("100000"):
                        ambiguities.append(f"Ambiguous salary amount ₹{val}. Unclear if monthly or annual.")
                    else:
                        annual_salary = val

        # Contradiction check: monthly vs annual salary
        if monthly_salary and annual_salary:
            annualized_from_monthly = monthly_salary * Decimal("12")
            discrepancy = abs(annualized_from_monthly - annual_salary)
            if discrepancy > (annual_salary * Decimal("0.20")):
                contradictions.append(
                    f"Contradictory salary stated: Annual salary stated as ₹{annual_salary}, "
                    f"but monthly salary stated as ₹{monthly_salary} (which equals ₹{annualized_from_monthly}/year)."
                )

        final_gross = annual_salary or (monthly_salary * Decimal("12") if monthly_salary else None)
        if final_gross is not None:
            detected["gross_salary"] = final_gross

        # 4. Rent / HRA Detection
        rent_paid: Decimal = Decimal("0.00")
        rent_patterns = [
            # '30,000 monthly kiraya' or '20,000 rent monthly'
            r"([₹]?\s*[\d\.,]+\s*(?:k|thousand|lakh|l)?)\s*(?:monthly|per month|p\.m\.|har mahine|mahina)?\s*(?:rent|kiraya|bhaada)",
            # 'rent of 25000 per month' or 'kiraya 20,000'
            r"(?:rent|kiraya|bhaada|paying rent|pay rent)\s*(?:is|of|around|hai|deta|de raha)?\s*([₹]?\s*[\d\.,]+\s*(?:k|thousand|lakh|l)?)\s*(?:per month|monthly|p\.m\.|har mahine|mahina)?",
        ]
        for rp in rent_patterns:
            rm = re.search(rp, lower)
            if rm:
                r_val = parse_indian_amount(rm.group(1))
                if r_val and r_val > Decimal("0"):
                    # Check if monthly indicator exists around match
                    matched_text = lower[max(0, rm.start()-10):min(len(lower), rm.end()+15)]
                    is_monthly = any(m in matched_text for m in ["month", "p.m.", "mahina", "har mahine"]) or r_val < Decimal("100000")
                    rent_paid = r_val * Decimal("12") if is_monthly else r_val
                    break

        # Contradiction check: own house / no rent vs positive rent
        has_no_rent_claim = any(phrase in lower for phrase in ["own house", "apna ghar", "no rent", "koi kiraya nahi", "don't pay rent", "do not pay rent"])
        if has_no_rent_claim and rent_paid > Decimal("0"):
            contradictions.append(
                f"Contradiction: You mentioned living in your own house / paying no rent, but also specified a rent payment of ₹{rent_paid}."
            )

        detected["rent_paid"] = rent_paid

        # HRA received
        hra_received = self._extract_amount_around_keywords(lower, ["hra received", "hra component", "hra of", "hra"]) or Decimal("0.00")
        if hra_received >= (final_gross or Decimal("10000000")):
            hra_received = Decimal("0.00")
        detected["hra_received"] = hra_received

        # 5. Section 80C
        sec_80c = self._extract_amount_around_keywords(lower, ["80c", "ppf", "elss", "provident fund", "epf", "lic", "life insurance"]) or Decimal("0.00")
        detected["section_80c"] = sec_80c

        # 6. Section 80CCD(1B)
        sec_80ccd = self._extract_amount_around_keywords(lower, ["80ccd(1b)", "80ccd", "nps", "national pension"]) or Decimal("0.00")
        detected["section_80ccd_1b"] = sec_80ccd

        # 7. Section 80D (Health Insurance & Parents)
        is_senior_self = any(w in lower for w in ["i am senior citizen", "senior citizen myself", "age 60", "age 65", "age 70"])
        is_senior_parents = any(w in lower for w in ["parents are senior", "senior citizen parents", "mummy papa senior", "parents >= 60", "bujurg"])

        d_parents = self._extract_amount_around_keywords(lower, ["parents", "mummy papa", "mother", "father"]) or Decimal("0.00")
        d_self = self._extract_amount_around_keywords(lower, ["health insurance", "mediclaim", "medical insurance", "80d"]) or Decimal("0.00")
        if d_self == d_parents and d_parents > Decimal("0"):
            # If parents matched the health insurance amount, don't duplicate to self
            d_self = Decimal("0.00")

        # Age contradiction check
        age_match = re.search(r"(?:i am|my age is|age)\s*(\d{2})", lower)
        if age_match:
            age = int(age_match.group(1))
            if age < 60 and is_senior_self:
                contradictions.append(
                    f"Contradiction: You stated your age is {age}, but also claimed to be a senior citizen."
                )

        detected["section_80d_self"] = d_self
        detected["section_80d_parents"] = d_parents
        detected["is_senior_citizen_self"] = is_senior_self
        detected["is_senior_citizen_parents"] = is_senior_parents

        # 8. Section 24(b) Home Loan Interest
        hl_interest = self._extract_amount_around_keywords(lower, ["home loan interest", "housing loan interest", "home loan ka byaj", "home loan"]) or Decimal("0.00")
        detected["home_loan_interest_24b"] = hl_interest

        # 9. Clarification & Contradiction Resolution
        if contradictions:
            clarification = (
                "Please clarify the following contradiction(s):\n" + "\n".join(f"- {c}" for c in contradictions)
            )
            return ParseResult(
                raw_query=text,
                is_valid=False,
                clarification_question=clarification,
                contradictions=contradictions,
                ambiguities=ambiguities,
                confidence=0.3,
                detected_fields=detected,
            )

        if final_gross is None:
            clarification = (
                "Essential information missing: Could you please provide your annual gross salary or monthly CTC?"
            )
            return ParseResult(
                raw_query=text,
                is_valid=False,
                clarification_question=clarification,
                contradictions=contradictions,
                ambiguities=ambiguities,
                confidence=0.2,
                detected_fields=detected,
            )

        if ambiguities:
            clarification = "Clarification needed:\n" + "\n".join(f"- {a}" for a in ambiguities)
            return ParseResult(
                raw_query=text,
                is_valid=False,
                clarification_question=clarification,
                contradictions=contradictions,
                ambiguities=ambiguities,
                confidence=0.5,
                detected_fields=detected,
            )

        tax_inp = TaxInput(
            gross_salary=final_gross,
            hra_received=hra_received,
            rent_paid=rent_paid,
            is_metro=is_metro,
            section_80c=sec_80c,
            section_80ccd_1b=sec_80ccd,
            section_80d_self=d_self,
            is_senior_citizen_self=is_senior_self,
            section_80d_parents=d_parents,
            is_senior_citizen_parents=is_senior_parents,
            home_loan_interest_24b=hl_interest,
            financial_year=fy,
        )

        return ParseResult(
            raw_query=text,
            is_valid=True,
            tax_input=tax_inp,
            clarification_question=None,
            confidence=0.95,
            detected_fields=detected,
        )
