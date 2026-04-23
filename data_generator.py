"""
data_generator.py
-----------------
Generates synthetic SAP master data (GL accounts, cost centers, profit centers)
and balanced GL journal entries for current and previous periods.

Course : SAP DATA/Analytics Engineering (C_BCBDC)
Project: R2R – Month-End / Year-End Financial Close Simulation
"""

import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker("en_IN")
random.seed(42)
np.random.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# MASTER DATA
# ─────────────────────────────────────────────────────────────────────────────

GL_ACCOUNTS: dict[str, dict] = {
    "100000": {"name": "Cash & Bank",          "type": "Asset",     "normal_balance": "Debit"},
    "110000": {"name": "Accounts Receivable",  "type": "Asset",     "normal_balance": "Debit"},
    "120000": {"name": "Fixed Assets",         "type": "Asset",     "normal_balance": "Debit"},
    "200000": {"name": "Accounts Payable",     "type": "Liability", "normal_balance": "Credit"},
    "210000": {"name": "Tax Payable",          "type": "Liability", "normal_balance": "Credit"},
    "300000": {"name": "Retained Earnings",    "type": "Equity",    "normal_balance": "Credit"},
    "400000": {"name": "Revenue",              "type": "Income",    "normal_balance": "Credit"},
    "500000": {"name": "Cost of Goods Sold",   "type": "Expense",   "normal_balance": "Debit"},
    "510000": {"name": "Salaries Expense",     "type": "Expense",   "normal_balance": "Debit"},
    "520000": {"name": "Rent Expense",         "type": "Expense",   "normal_balance": "Debit"},
    "530000": {"name": "Depreciation Expense", "type": "Expense",   "normal_balance": "Debit"},
    "540000": {"name": "Tax Expense",          "type": "Expense",   "normal_balance": "Debit"},
}

COST_CENTERS: dict[str, str] = {
    "CC100": "Sales",
    "CC200": "HR",
    "CC300": "IT",
    "CC400": "Operations",
}

PROFIT_CENTERS: dict[str, str] = {
    "PC100": "North Region",
    "PC200": "South Region",
    "PC300": "Export Division",
}

# SAP document types: SA=G/L acctg doc, AB=accounting doc, ZP=payment doc
DOC_TYPES = ["SA", "AB", "ZP"]

PERIODS = {
    "current":  {"year": 2024, "month": 3},   # March 2024 – close period
    "previous": {"year": 2024, "month": 2},   # February 2024 – comparison period
}


# ─────────────────────────────────────────────────────────────────────────────
# TRANSACTION TEMPLATES
# Each tuple: (debit_gl, credit_gl, cost_center, profit_center,
#              doc_type, min_amount, max_amount, description_prefix)
# ─────────────────────────────────────────────────────────────────────────────

TRANSACTION_TEMPLATES = [
    # Revenue cycle
    ("100000", "400000", "CC100", "PC100", "SA", 20_000, 100_000, "Cash Revenue"),
    ("110000", "400000", "CC100", "PC200", "SA", 10_000,  80_000, "Credit Revenue"),
    ("100000", "110000", "CC100", "PC300", "ZP",  5_000,  60_000, "AR Collection"),

    # Cost of Goods Sold
    ("500000", "100000", "CC400", "PC100", "AB", 15_000,  70_000, "COGS – Cash Pmt"),
    ("500000", "200000", "CC400", "PC300", "AB",  8_000,  50_000, "COGS – Vendor AP"),

    # Salaries
    ("510000", "100000", "CC200", "PC100", "ZP", 30_000,  90_000, "Payroll – HR"),
    ("510000", "100000", "CC300", "PC200", "ZP", 20_000,  60_000, "Payroll – IT"),
    ("510000", "100000", "CC100", "PC100", "ZP", 25_000,  75_000, "Payroll – Sales"),
    ("510000", "100000", "CC400", "PC300", "ZP", 22_000,  65_000, "Payroll – Ops"),

    # Rent
    ("520000", "100000", "CC300", "PC100", "SA", 10_000,  30_000, "Office Rent"),
    ("520000", "200000", "CC400", "PC100", "SA",  5_000,  20_000, "Warehouse Rent AP"),

    # Depreciation
    ("530000", "120000", "CC400", "PC300", "SA",  2_000,  15_000, "Depreciation Run"),

    # Tax
    ("540000", "210000", "CC200", "PC100", "SA",  5_000,  25_000, "Tax Provision"),
    ("210000", "100000", "CC200", "PC100", "ZP",  3_000,  20_000, "Tax Payment"),

    # Retained Earnings adjustment
    ("300000", "400000", "CC100", "PC200", "AB",  1_000,   8_000, "Retained Earnings Adj"),
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _random_date(year: int, month: int) -> str:
    """Return a random date string within the given year/month."""
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = datetime(year, month + 1, 1) - timedelta(days=1)
    days_in_month = (end - start).days
    return (start + timedelta(days=random.randint(0, days_in_month))).strftime("%Y-%m-%d")


def _make_line(doc_num: int, doc_type: str, date: str,
               gl: str, debit: float, credit: float,
               cc: str, pc: str, ref: str, text: str) -> dict:
    return {
        "doc_number":    doc_num,
        "doc_type":      doc_type,
        "posting_date":  date,
        "fiscal_year":   date[:4],
        "fiscal_period": date[5:7],
        "gl_account":    gl,
        "account_name":  GL_ACCOUNTS[gl]["name"],
        "debit":         debit,
        "credit":        credit,
        "cost_center":   cc,
        "profit_center": pc,
        "reference":     ref,
        "text":          text,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def generate_journal_entries(n_current: int = 115,
                              n_previous: int = 105) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate two balanced GL journal entry datasets.

    Parameters
    ----------
    n_current  : number of documents (× 2 lines each) for current period
    n_previous : number of documents for previous period

    Returns
    -------
    (current_df, previous_df)  — each row = one journal line
    """
    def _build(n: int, year: int, month: int, start_doc: int) -> list[dict]:
        rows: list[dict] = []
        doc_num = start_doc
        for _ in range(n):
            tpl = random.choice(TRANSACTION_TEMPLATES)
            dr_gl, cr_gl, cc, pc, doc_type, mn, mx, desc = tpl
            amount  = round(random.uniform(mn, mx), 2)
            date    = _random_date(year, month)
            ref     = fake.bothify(text="REF-####??").upper()
            # Each document: one debit line + one credit line → always balanced
            rows.append(_make_line(doc_num, doc_type, date, dr_gl,
                                   amount, 0.0, cc, pc, ref, f"{desc} – DR"))
            rows.append(_make_line(doc_num, doc_type, date, cr_gl,
                                   0.0, amount, cc, pc, ref, f"{desc} – CR"))
            doc_num += 1
        return rows

    cur_p  = PERIODS["current"]
    pre_p  = PERIODS["previous"]
    cur_df = pd.DataFrame(_build(n_current,  cur_p["year"],  cur_p["month"],  5_000_001))
    pre_df = pd.DataFrame(_build(n_previous, pre_p["year"],  pre_p["month"],  4_000_001))
    return cur_df, pre_df


def get_master_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (gl_accounts_df, cost_centers_df, profit_centers_df)."""
    gl_df = pd.DataFrame(
        [{"gl_account": k, **v} for k, v in GL_ACCOUNTS.items()]
    )
    cc_df = pd.DataFrame(
        [{"cost_center": k, "cc_name": v} for k, v in COST_CENTERS.items()]
    )
    pc_df = pd.DataFrame(
        [{"profit_center": k, "pc_name": v} for k, v in PROFIT_CENTERS.items()]
    )
    return gl_df, cc_df, pc_df
