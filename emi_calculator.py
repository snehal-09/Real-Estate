"""
emi_calculator.py

Standard reducing-balance EMI (Equated Monthly Installment) calculation.
This is pure Python / math - never delegated to Gemini.

EMI formula:
    EMI = P * r * (1 + r)^n / ((1 + r)^n - 1)

Where:
    P = principal (loan amount)
    r = monthly interest rate (annual rate / 12 / 100)
    n = number of monthly installments (tenure in years * 12)
"""


def calculate_emi(loan_amount: float, interest_rate: float, tenure_years: float) -> dict:
    """
    Returns a dict with monthly_emi, total_interest, total_payment.
    Raises ValueError on invalid input.
    """
    if loan_amount is None or interest_rate is None or tenure_years is None:
        raise ValueError("loan_amount, interest_rate and tenure_years are required.")

    loan_amount = float(loan_amount)
    interest_rate = float(interest_rate)
    tenure_years = float(tenure_years)

    if loan_amount <= 0:
        raise ValueError("loan_amount must be greater than 0.")
    if interest_rate < 0:
        raise ValueError("interest_rate cannot be negative.")
    if tenure_years <= 0:
        raise ValueError("tenure_years must be greater than 0.")

    months = round(tenure_years * 12)
    monthly_rate = (interest_rate / 12) / 100

    if monthly_rate == 0:
        monthly_emi = loan_amount / months
    else:
        factor = (1 + monthly_rate) ** months
        monthly_emi = loan_amount * monthly_rate * factor / (factor - 1)

    total_payment = monthly_emi * months
    total_interest = total_payment - loan_amount

    return {
        "monthly_emi": round(monthly_emi),
        "total_interest": round(total_interest),
        "total_payment": round(total_payment),
    }
