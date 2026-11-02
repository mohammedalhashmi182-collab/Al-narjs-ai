"""Three-scenario financial forecast with a formula workbook.

Every rate, factor and total is an estimate derived from the caller's inputs.
The workbook repeats the arithmetic in cell formulas so a reviewer can change
an assumption and see the sheets recalculate.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO

from openpyxl import Workbook

from src.services.capabilities.config import forecast_default_vat, forecast_max_horizon

ESTIMATE_NOTE_AR = (
    "كل السيناريوهات تقديرات مبنية على الأرقام التي أدخلتها، وليست نتائج فعلية "
    "ولا توقعاً مضموناً. ضريبة القيمة المضافة تُحسب على الإيراد قبل الضريبة ولا تُعد ربحاً."
)
ESTIMATE_NOTE_EN = (
    "Every scenario is an estimate built from the figures you entered, not an actual "
    "result and not a guaranteed forecast. VAT is calculated on pre-tax revenue and is not profit."
)

# Relative to the caller's growth and churn. Documented as estimate factors.
SCENARIO_FACTORS: dict[str, dict[str, float]] = {
    "conservative": {"growth": 0.60, "churn": 1.25},
    "base": {"growth": 1.00, "churn": 1.00},
    "optimistic": {"growth": 1.35, "churn": 0.75},
}
SCENARIO_LABELS = {
    "conservative": ("متحفظ", "Conservative"),
    "base": ("أساسي", "Base"),
    "optimistic": ("متفائل", "Optimistic"),
}


class ForecastError(ValueError):
    pass


@dataclass
class PlanInput:
    name: str
    price_sar: float
    customers: float


def _clamp_rate(growth: float, churn: float, factors: dict[str, float]) -> tuple[float, float]:
    g = float(growth) * factors["growth"]
    c = min(0.95, float(churn) * factors["churn"])
    return g, c


def _step(customers: float, growth: float, churn: float) -> float:
    return max(0.0, customers * (1.0 + growth - churn))


def _round_money(value: float) -> float:
    return round(float(value), 2)


def build_forecast(
    plans: list[PlanInput],
    *,
    monthly_growth: float,
    monthly_churn: float,
    fixed_costs_sar: float,
    variable_cost_per_customer_sar: float,
    vat_rate: float | None = None,
    horizon_months: int = 12,
) -> dict:
    if not plans:
        raise ForecastError("at least one plan is required")
    horizon = int(horizon_months)
    if horizon < 1 or horizon > forecast_max_horizon():
        raise ForecastError(f"horizon must be between 1 and {forecast_max_horizon()} months")
    if monthly_growth < -0.5 or monthly_growth > 2:
        raise ForecastError("monthly growth must be between -0.5 and 2")
    if monthly_churn < 0 or monthly_churn > 0.95:
        raise ForecastError("monthly churn must be between 0 and 0.95")
    vat = forecast_default_vat() if vat_rate is None else float(vat_rate)
    if vat < 0 or vat > 1:
        raise ForecastError("VAT rate must be between 0 and 1")
    if fixed_costs_sar < 0 or variable_cost_per_customer_sar < 0:
        raise ForecastError("costs cannot be negative")

    customers0 = 0.0
    weighted = 0.0
    clean_plans = []
    for plan in plans:
        name = (plan.name or "Plan").strip()[:80] or "Plan"
        price = float(plan.price_sar)
        customers = float(plan.customers)
        if price < 0 or customers < 0:
            raise ForecastError("price and customers cannot be negative")
        customers0 += customers
        weighted += price * customers
        clean_plans.append({"name": name, "price_sar": _round_money(price), "customers": _round_money(customers)})
    if customers0 <= 0:
        raise ForecastError("starting customers must be greater than zero")
    price = weighted / customers0

    scenarios = {}
    for key, factors in SCENARIO_FACTORS.items():
        g, c = _clamp_rate(monthly_growth, monthly_churn, factors)
        label_ar, label_en = SCENARIO_LABELS[key]
        months = []
        current = customers0
        cumulative = 0.0
        break_even = None
        for index in range(1, horizon + 1):
            current = _step(current, g, c)
            revenue_ex = current * price
            vat_amount = revenue_ex * vat
            variable = current * variable_cost_per_customer_sar
            costs = fixed_costs_sar + variable
            profit = revenue_ex - costs
            cumulative += profit
            if break_even is None and cumulative >= 0:
                break_even = index
            months.append(
                {
                    "month": index,
                    "customers": _round_money(current),
                    "revenue_ex_vat_sar": _round_money(revenue_ex),
                    "vat_sar": _round_money(vat_amount),
                    "revenue_inc_vat_sar": _round_money(revenue_ex + vat_amount),
                    "costs_sar": _round_money(costs),
                    "profit_ex_vat_sar": _round_money(profit),
                    "cumulative_profit_ex_vat_sar": _round_money(cumulative),
                    "estimate": True,
                }
            )
        last = months[-1]
        scenarios[key] = {
            "key": key,
            "label_ar": label_ar,
            "label_en": label_en,
            "estimate": True,
            "growth_used": round(g, 6),
            "churn_used": round(c, 6),
            "factors": dict(factors),
            "break_even_month": break_even,
            "ending_customers": last["customers"],
            "total_revenue_ex_vat_sar": _round_money(sum(m["revenue_ex_vat_sar"] for m in months)),
            "total_profit_ex_vat_sar": last["cumulative_profit_ex_vat_sar"],
            "months": months,
        }

    assumptions = {
        "estimate": True,
        "starting_customers": _round_money(customers0),
        "blended_price_sar": _round_money(price),
        "monthly_growth": round(float(monthly_growth), 6),
        "monthly_churn": round(float(monthly_churn), 6),
        "fixed_costs_sar": _round_money(fixed_costs_sar),
        "variable_cost_per_customer_sar": _round_money(variable_cost_per_customer_sar),
        "vat_rate": round(vat, 6),
        "horizon_months": horizon,
        "plans": clean_plans,
        "scenario_factors": SCENARIO_FACTORS,
        "note_ar": ESTIMATE_NOTE_AR,
        "note_en": ESTIMATE_NOTE_EN,
    }
    payload = {
        "estimate": True,
        "note_ar": ESTIMATE_NOTE_AR,
        "note_en": ESTIMATE_NOTE_EN,
        "assumptions": assumptions,
        "scenarios": scenarios,
    }
    payload["xlsx_base64"] = base64.b64encode(_workbook(assumptions)).decode("ascii")
    return payload


def _workbook(assumptions: dict) -> bytes:
    wb = Workbook()
    assumptions_sheet = wb.active
    assumptions_sheet.title = "Assumptions"
    assumptions_sheet["A1"] = ESTIMATE_NOTE_EN
    assumptions_sheet["A2"] = ESTIMATE_NOTE_AR
    rows = [
        (4, "starting_customers", assumptions["starting_customers"]),
        (5, "blended_price_sar", assumptions["blended_price_sar"]),
        (6, "monthly_growth_fraction", assumptions["monthly_growth"]),
        (7, "monthly_churn_fraction", assumptions["monthly_churn"]),
        (8, "fixed_costs_sar", assumptions["fixed_costs_sar"]),
        (9, "variable_cost_per_customer_sar", assumptions["variable_cost_per_customer_sar"]),
        (10, "vat_rate", assumptions["vat_rate"]),
        (11, "horizon_months", assumptions["horizon_months"]),
        (13, "conservative_growth_factor_ESTIMATE", SCENARIO_FACTORS["conservative"]["growth"]),
        (14, "conservative_churn_factor_ESTIMATE", SCENARIO_FACTORS["conservative"]["churn"]),
        (15, "base_growth_factor_ESTIMATE", SCENARIO_FACTORS["base"]["growth"]),
        (16, "base_churn_factor_ESTIMATE", SCENARIO_FACTORS["base"]["churn"]),
        (17, "optimistic_growth_factor_ESTIMATE", SCENARIO_FACTORS["optimistic"]["growth"]),
        (18, "optimistic_churn_factor_ESTIMATE", SCENARIO_FACTORS["optimistic"]["churn"]),
    ]
    assumptions_sheet["A3"] = "input"
    assumptions_sheet["B3"] = "value"
    assumptions_sheet["C3"] = "unit"
    for row, label, value in rows:
        assumptions_sheet[f"A{row}"] = label
        assumptions_sheet[f"B{row}"] = value
        assumptions_sheet[f"C{row}"] = "estimate"

    factor_cells = {
        "conservative": ("$B$13", "$B$14"),
        "base": ("$B$15", "$B$16"),
        "optimistic": ("$B$17", "$B$18"),
    }
    horizon = int(assumptions["horizon_months"])
    headers = [
        "month",
        "customers",
        "revenue_ex_vat",
        "vat",
        "revenue_inc_vat",
        "costs",
        "profit_ex_vat",
        "cumulative_profit_ex_vat",
        "estimate",
    ]
    for key, (growth_cell, churn_cell) in factor_cells.items():
        sheet = wb.create_sheet(SCENARIO_LABELS[key][1])
        sheet["A1"] = "ESTIMATE — " + ESTIMATE_NOTE_EN
        sheet["A2"] = ESTIMATE_NOTE_AR
        for col, header in enumerate(headers, 1):
            sheet.cell(3, col, header)
        growth_expr = f"Assumptions!$B$6*{growth_cell}"
        churn_expr = f"MIN(0.95,Assumptions!$B$7*{churn_cell})"
        net = f"(1+{growth_expr}-{churn_expr})"
        for offset in range(horizon):
            row = 4 + offset
            sheet.cell(row, 1, offset + 1)
            if offset == 0:
                sheet.cell(row, 2, f"=MAX(0,Assumptions!$B$4*{net})")
            else:
                sheet.cell(row, 2, f"=MAX(0,B{row - 1}*{net})")
            sheet.cell(row, 3, f"=B{row}*Assumptions!$B$5")
            sheet.cell(row, 4, f"=C{row}*Assumptions!$B$10")
            sheet.cell(row, 5, f"=C{row}+D{row}")
            sheet.cell(row, 6, f"=Assumptions!$B$8+B{row}*Assumptions!$B$9")
            sheet.cell(row, 7, f"=C{row}-F{row}")
            if offset == 0:
                sheet.cell(row, 8, f"=G{row}")
            else:
                sheet.cell(row, 8, f"=H{row - 1}+G{row}")
            sheet.cell(row, 9, "estimate")
        last = 3 + horizon
        sheet["J3"] = "break_even_month"
        sheet["J4"] = f'=IF(COUNTIF(H4:H{last},">=0")=0,"",MATCH(TRUE,INDEX(H4:H{last}>=0,0),0))'

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
