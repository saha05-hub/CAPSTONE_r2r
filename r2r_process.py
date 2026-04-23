"""
r2r_process.py
--------------
Core business logic for the SAP Record-to-Report (R2R) simulation.

Steps covered
    1. Journal Entry Validation        – verify each document balances
    2. Cost Center Allocation          – distribute shared departmental costs
    3. Trial Balance Generation        – aggregate debits/credits per GL account
    4. Account Reconciliation          – period-over-period variance + anomaly flags
    5. Financial Close Checklist       – simulate period-end tasks
    6. Report Export                   – Excel (multi-sheet) + CSV summary

Course : SAP DATA/Analytics Engineering (C_BCBDC)
Project: R2R – Month-End / Year-End Financial Close Simulation
"""

import os
import random
from datetime import datetime

import pandas as pd
from tabulate import tabulate

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 – JOURNAL ENTRY VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

def validate_journal_entries(df: pd.DataFrame) -> dict:
    """
    Verify every document is balanced (Σ debits == Σ credits).

    Returns a summary dict with counts and any unbalanced document details.
    """
    doc_agg = (
        df.groupby("doc_number")
        .agg(total_debit=("debit", "sum"), total_credit=("credit", "sum"))
        .reset_index()
    )
    doc_agg["balanced"] = (doc_agg["total_debit"] - doc_agg["total_credit"]).abs() < 0.01
    unbalanced = doc_agg[~doc_agg["balanced"]]

    return {
        "total_lines":           len(df),
        "total_documents":       len(doc_agg),
        "balanced_documents":    int(doc_agg["balanced"].sum()),
        "unbalanced_documents":  len(unbalanced),
        "unbalanced_details":    unbalanced.to_dict("records"),
    }


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 – COST CENTER ALLOCATION
# ═════════════════════════════════════════════════════════════════════════════

# Allocation rules: {source_CC: {target_CC: weight, …}}
# IT and HR share their costs with operational departments.
ALLOCATION_RULES: dict[str, dict[str, float]] = {
    "CC300": {"CC100": 0.40, "CC200": 0.30, "CC400": 0.30},  # IT  → Sales / HR / Ops
    "CC200": {"CC100": 0.50, "CC400": 0.50},                  # HR  → Sales / Ops
}

# GL account used for internal allocation postings (SAP: assessment cost element)
ALLOC_GL = "510000"   # reuse Salaries account as internal allocation account


def allocate_costs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Simulate SAP cost-center allocation cycles (transaction KSU1 / KSV1).

    For each source cost center:
      - Total the expense-account debits
      - Post credit on source CC  (reverse cost out)
      - Post debit  on each target CC (push cost in)
    Returns a DataFrame of allocation journal lines; empty if no data.
    """
    alloc_rows: list[dict] = []
    doc_num = 9_000_001
    today   = datetime.now().strftime("%Y-%m-%d")
    year    = today[:4]
    period  = today[5:7]

    for source_cc, targets in ALLOCATION_RULES.items():
        # Expense GL accounts start with 5xx
        mask = (
            (df["cost_center"] == source_cc) &
            (df["debit"] > 0) &
            (df["gl_account"].str.startswith("5"))
        )
        total_cost = df.loc[mask, "debit"].sum()
        if total_cost == 0:
            continue

        for target_cc, weight in targets.items():
            alloc_amt = round(total_cost * weight, 2)
            base = dict(doc_number=doc_num, doc_type="AB",
                        posting_date=today, fiscal_year=year,
                        fiscal_period=period, gl_account=ALLOC_GL,
                        account_name="Salaries Expense",
                        profit_center="PC100",
                        reference=f"ALLOC-{source_cc}-{target_cc}")

            # Credit source → push cost out
            alloc_rows.append({**base,
                "debit": 0.0, "credit": alloc_amt,
                "cost_center": source_cc,
                "text": f"Allocation out: {source_cc} → {target_cc}"})
            # Debit target → receive cost
            alloc_rows.append({**base,
                "debit": alloc_amt, "credit": 0.0,
                "cost_center": target_cc,
                "text": f"Allocation in: from {source_cc}"})
            doc_num += 1

    if not alloc_rows:
        return pd.DataFrame(columns=df.columns)
    return pd.DataFrame(alloc_rows)


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 – TRIAL BALANCE
# ═════════════════════════════════════════════════════════════════════════════

def generate_trial_balance(df: pd.DataFrame,
                            gl_master: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate all postings into a trial balance (one row per GL account).
    """
    tb = (
        df.groupby(["gl_account", "account_name"])
        .agg(total_debit=("debit", "sum"), total_credit=("credit", "sum"))
        .reset_index()
    )
    tb["net_balance"] = (tb["total_debit"] - tb["total_credit"]).round(2)
    tb = tb.merge(
        gl_master[["gl_account", "type", "normal_balance"]],
        on="gl_account", how="left"
    )
    tb["total_debit"]  = tb["total_debit"].round(2)
    tb["total_credit"] = tb["total_credit"].round(2)
    return tb.sort_values("gl_account").reset_index(drop=True)


def check_trial_balance(df: pd.DataFrame) -> dict:
    """
    Prove the accounting equation: Σ Debits == Σ Credits.
    Operates on the raw journal DataFrame (not the trial balance summary).
    """
    total_dr = round(df["debit"].sum(), 2)
    total_cr = round(df["credit"].sum(), 2)
    diff     = round(total_dr - total_cr, 2)
    return {
        "total_debits":  total_dr,
        "total_credits": total_cr,
        "difference":    diff,
        "is_balanced":   abs(diff) < 0.01,
    }


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 – ACCOUNT RECONCILIATION & ANOMALY DETECTION
# ═════════════════════════════════════════════════════════════════════════════

def reconcile_accounts(current_tb: pd.DataFrame,
                        previous_tb: pd.DataFrame,
                        threshold: float = 0.10) -> pd.DataFrame:
    """
    Period-over-period comparison.  Flags any GL account whose net balance
    changed by more than `threshold` (default 10 %) as an anomaly.
    """
    cur  = current_tb[["gl_account", "account_name",
                        "type", "net_balance"]].copy()
    cur.rename(columns={"net_balance": "current_balance"}, inplace=True)

    prev = previous_tb[["gl_account", "net_balance"]].copy()
    prev.rename(columns={"net_balance": "previous_balance"}, inplace=True)

    rec = cur.merge(prev, on="gl_account", how="outer").fillna(0)

    def _variance_pct(row: pd.Series) -> float:
        if row["previous_balance"] == 0:
            return 1.0 if row["current_balance"] != 0 else 0.0
        return abs(row["current_balance"] - row["previous_balance"]) / abs(row["previous_balance"])

    rec["variance_amount"] = (rec["current_balance"] - rec["previous_balance"]).round(2)
    rec["variance_pct"]    = rec.apply(_variance_pct, axis=1).round(4)
    rec["anomaly_flag"]    = rec["variance_pct"] > threshold
    rec["status"]          = rec["anomaly_flag"].map({True: "⚠️  ANOMALY", False: "✅ OK"})

    return rec.sort_values("variance_pct", ascending=False).reset_index(drop=True)


# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 – FINANCIAL CLOSE CHECKLIST
# ═════════════════════════════════════════════════════════════════════════════

_CHECKLIST_ITEMS = [
    ("CC-01", "Post all accrual entries",                  "Accruals"),
    ("CC-02", "Reverse prior-period accruals",             "Accruals"),
    ("CC-03", "Run asset depreciation (T-code: AFAB)",     "Asset Accounting"),
    ("CC-04", "Post depreciation document to FI",          "Asset Accounting"),
    ("CC-05", "Bank reconciliation & clearing",            "Cash & Bank"),
    ("CC-06", "AR aging analysis and doubtful debt write-off", "Receivables"),
    ("CC-07", "AP invoice matching and GR/IR clearing",    "Payables"),
    ("CC-08", "Cost center settlement (T-code: KSU1)",     "Controlling"),
    ("CC-09", "Profit center reposting (T-code: 9KE0)",    "Controlling"),
    ("CC-10", "Intercompany balance reconciliation",       "Intercompany"),
    ("CC-11", "Tax provision calculation and posting",     "Tax"),
    ("CC-12", "Reclassify prepaid and deferred items",     "Reclassification"),
    ("CC-13", "Trial balance extraction and review",       "Reporting"),
    ("CC-14", "Generate P&L and Balance Sheet (F.01)",     "Reporting"),
    ("CC-15", "Period lock in Financial Accounting (OB52)","Period Close"),
]


def run_close_checklist(completion_rate: float = 0.87) -> pd.DataFrame:
    """
    Simulate execution of period-end financial close tasks.
    completion_rate controls what fraction of tasks are marked COMPLETED.
    """
    random.seed(77)
    rows = []
    for task_id, task, category in _CHECKLIST_ITEMS:
        completed = random.random() < completion_rate
        rows.append({
            "task_id":      task_id,
            "category":     category,
            "task":         task,
            "status":       "COMPLETED" if completed else "PENDING",
            "completed_by": "BATCH_JOB" if completed else "—",
            "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S") if completed else "—",
        })
    return pd.DataFrame(rows)


# ═════════════════════════════════════════════════════════════════════════════
# STEP 6 – REPORT EXPORT
# ═════════════════════════════════════════════════════════════════════════════

def export_to_excel(journal_df: pd.DataFrame,
                    alloc_df: pd.DataFrame,
                    trial_balance: pd.DataFrame,
                    reconciliation: pd.DataFrame,
                    checklist: pd.DataFrame) -> str:
    """
    Write multi-sheet Excel workbook to reports/trial_balance.xlsx.
    Returns the absolute file path.
    """
    path = os.path.join(REPORTS_DIR, "trial_balance.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        journal_df.to_excel(   writer, sheet_name="Journal Entries",  index=False)
        alloc_df.to_excel(     writer, sheet_name="Cost Allocations", index=False)
        trial_balance.to_excel(writer, sheet_name="Trial Balance",    index=False)
        reconciliation.to_excel(writer, sheet_name="Reconciliation",  index=False)
        checklist.to_excel(    writer, sheet_name="Close Checklist",  index=False)

        # Auto-widen columns for readability
        for sheet in writer.sheets.values():
            for col in sheet.columns:
                max_len = max((len(str(c.value)) for c in col if c.value), default=10)
                sheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

    return os.path.abspath(path)


def export_close_report_csv(trial_balance: pd.DataFrame,
                             reconciliation: pd.DataFrame,
                             checklist: pd.DataFrame) -> str:
    """
    Write a flat summary CSV to reports/close_report.csv.
    Returns the absolute file path.
    """
    path = os.path.join(REPORTS_DIR, "close_report.csv")
    rows: list[dict] = []

    rows.append({"section": "=== TRIAL BALANCE ===", "detail": "", "value": ""})
    for _, r in trial_balance.iterrows():
        rows.append({
            "section": "Trial Balance",
            "detail":  f"{r['gl_account']}  {r['account_name']}",
            "value":   f"Dr: {r['total_debit']:,.2f}  |  Cr: {r['total_credit']:,.2f}  |  Net: {r['net_balance']:,.2f}",
        })

    rows.append({"section": "=== ANOMALIES (>10% variance) ===", "detail": "", "value": ""})
    for _, r in reconciliation[reconciliation["anomaly_flag"]].iterrows():
        rows.append({
            "section": "Anomaly",
            "detail":  f"{r['gl_account']}  {r['account_name']}",
            "value":   f"Variance: {r['variance_pct']*100:.1f}%  |  Curr: {r['current_balance']:,.2f}  |  Prev: {r['previous_balance']:,.2f}",
        })

    rows.append({"section": "=== CLOSE CHECKLIST ===", "detail": "", "value": ""})
    for _, r in checklist.iterrows():
        rows.append({
            "section": "Checklist",
            "detail":  f"{r['task_id']}  {r['task']}",
            "value":   r["status"],
        })

    pd.DataFrame(rows).to_csv(path, index=False)
    return os.path.abspath(path)


# ═════════════════════════════════════════════════════════════════════════════
# CONSOLE SUMMARY
# ═════════════════════════════════════════════════════════════════════════════

def print_console_summary(validation: dict,
                           tb_check: dict,
                           reconciliation: pd.DataFrame,
                           checklist: pd.DataFrame,
                           cost_center_summary: pd.DataFrame) -> None:
    """Print a rich terminal summary of the entire R2R run."""
    SEP  = "═" * 68
    SEP2 = "─" * 68

    print(f"\n{SEP}")
    print("  SAP R2R — Month-End Financial Close  |  Simulation Report")
    print(f"  Course: SAP DATA / Analytics Engineering  (C_BCBDC)")
    print(SEP)

    # ── Journal Entry Stats ───────────────────────────────────────────────
    print("\n  📋  STEP 1 — JOURNAL ENTRY VALIDATION")
    print(f"  {SEP2}")
    print(f"  {'Total Journal Lines':<35}: {validation['total_lines']:>8,}")
    print(f"  {'Total Documents':<35}: {validation['total_documents']:>8,}")
    print(f"  {'Balanced Documents':<35}: {validation['balanced_documents']:>8,}")
    unbal = validation['unbalanced_documents']
    unbal_icon = "✅" if unbal == 0 else "❌"
    print(f"  {'Unbalanced Documents':<35}: {unbal_icon} {unbal:>5,}")

    # ── Cost Center Allocation ────────────────────────────────────────────
    print(f"\n  📊  STEP 2 — COST CENTER ALLOCATION")
    print(f"  {SEP2}")
    if not cost_center_summary.empty:
        print(tabulate(cost_center_summary, headers="keys",
                       tablefmt="rounded_outline", showindex=False,
                       floatfmt=",.2f"))
    else:
        print("  No allocations generated.")

    # ── Trial Balance ─────────────────────────────────────────────────────
    print(f"\n  ⚖️   STEP 3 — TRIAL BALANCE PROOF")
    print(f"  {SEP2}")
    print(f"  {'Total Debits':<35}: ₹ {tb_check['total_debits']:>18,.2f}")
    print(f"  {'Total Credits':<35}: ₹ {tb_check['total_credits']:>18,.2f}")
    print(f"  {'Difference':<35}: ₹ {tb_check['difference']:>18,.2f}")
    bal_icon = "✅  BALANCED" if tb_check["is_balanced"] else "❌  UNBALANCED — INVESTIGATE"
    print(f"  {'Status':<35}: {bal_icon}")

    # ── Reconciliation / Anomalies ────────────────────────────────────────
    print(f"\n  🔍  STEP 4 — ACCOUNT RECONCILIATION (variance threshold: 10%)")
    print(f"  {SEP2}")
    anomalies = reconciliation[reconciliation["anomaly_flag"]].copy()
    if anomalies.empty:
        print("  ✅  No anomalies detected — all accounts within threshold.\n")
    else:
        disp = anomalies[["gl_account", "account_name",
                           "current_balance", "previous_balance",
                           "variance_pct", "status"]].copy()
        disp["variance_pct"] = (disp["variance_pct"] * 100).round(1).astype(str) + "%"
        disp.columns = ["GL Acct", "Account Name",
                        "Current", "Previous", "Var %", "Status"]
        print(tabulate(disp, headers="keys",
                       tablefmt="rounded_outline", showindex=False,
                       floatfmt=",.2f"))

    # ── Close Checklist ───────────────────────────────────────────────────
    print(f"\n  ✅  STEP 5 — FINANCIAL CLOSE CHECKLIST")
    print(f"  {SEP2}")
    summary = checklist.groupby("status").size().reset_index(name="count")
    total   = summary["count"].sum()
    for _, row in summary.iterrows():
        icon = "✅" if row["status"] == "COMPLETED" else "⏳"
        pct  = row["count"] / total * 100
        print(f"  {icon}  {row['status']:<14}: {row['count']:>3} tasks  ({pct:.0f}%)")

    pending = checklist.loc[checklist["status"] == "PENDING", "task"].tolist()
    if pending:
        print("\n  ⚠️   Pending Tasks:")
        for t in pending:
            print(f"       — {t}")

    print(f"\n{SEP}")
    print("  📁  Reports exported to /reports/")
    print(f"       • trial_balance.xlsx  (5 sheets)")
    print(f"       • close_report.csv")
    print(SEP + "\n")
