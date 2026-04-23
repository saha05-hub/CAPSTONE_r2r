"""
main.py
-------
Entry point for the SAP R2R Financial Close Simulation.
Orchestrates all six steps of the Record-to-Report cycle.

Run:  python main.py

Course : SAP DATA/Analytics Engineering (C_BCBDC)
Project: R2R – Month-End / Year-End Financial Close Simulation
"""

import sys
import os

# ── Ensure project root is importable regardless of working directory ─────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

from data_generator import generate_journal_entries, get_master_data
from r2r_process import (
    validate_journal_entries,
    allocate_costs,
    generate_trial_balance,
    check_trial_balance,
    reconcile_accounts,
    run_close_checklist,
    export_to_excel,
    export_close_report_csv,
    print_console_summary,
)


def main() -> None:
    banner = "=" * 68
    print(f"\n{banner}")
    print("  SAP Record-to-Report (R2R) — Financial Close Simulation")
    print("  SAP DATA / Analytics Engineering  |  Course: C_BCBDC")
    print(f"{banner}\n")

    # ── STEP 1: Load master data ───────────────────────────────────────────
    print("  [1/7]  Loading GL accounts, cost centers, profit centers …")
    gl_master, cc_master, pc_master = get_master_data()
    print(f"         GL Accounts : {len(gl_master)}")
    print(f"         Cost Centers: {len(cc_master)}")
    print(f"         Profit Ctrs : {len(pc_master)}")

    # ── STEP 2: Generate synthetic journal entries ─────────────────────────
    print("\n  [2/7]  Generating synthetic GL journal entries …")
    current_df, previous_df = generate_journal_entries(
        n_current=115,    # 115 docs × 2 lines = 230 lines (current period)
        n_previous=105,   # 105 docs × 2 lines = 210 lines (previous period)
    )
    print(f"         Current  period: {len(current_df):>4} lines "
          f"({current_df['doc_number'].nunique()} documents)  "
          f"[{current_df['posting_date'].min()} → {current_df['posting_date'].max()}]")
    print(f"         Previous period: {len(previous_df):>4} lines "
          f"({previous_df['doc_number'].nunique()} documents)  "
          f"[{previous_df['posting_date'].min()} → {previous_df['posting_date'].max()}]")

    # ── STEP 3: Validate journal entries ──────────────────────────────────
    print("\n  [3/7]  Validating journal entry balance …")
    validation = validate_journal_entries(current_df)
    ok_icon = "✅" if validation["unbalanced_documents"] == 0 else "❌"
    print(f"         {ok_icon}  {validation['balanced_documents']} / "
          f"{validation['total_documents']} documents balanced")

    # ── STEP 4: Cost centre allocation ────────────────────────────────────
    print("\n  [4/7]  Running cost center allocation cycles …")
    alloc_df = allocate_costs(current_df)
    if alloc_df.empty:
        print("         ⚠️  No allocation entries generated (check cost data).")
    else:
        print(f"         ✅  {len(alloc_df)} allocation lines posted "
              f"({alloc_df['doc_number'].nunique()} allocation documents)")

    # Combined ledger = original entries + allocation entries
    full_df = pd.concat(
        [current_df, alloc_df] if not alloc_df.empty else [current_df],
        ignore_index=True,
    )

    # Build cost-centre summary for console display
    cc_summary = (
        full_df[full_df["debit"] > 0]
        .groupby("cost_center", as_index=False)
        .agg(total_debits=("debit", "sum"), doc_count=("doc_number", "nunique"))
        .rename(columns={"cost_center": "Cost Center"})
        .sort_values("total_debits", ascending=False)
    )
    cc_summary = cc_summary.merge(
        cc_master.rename(columns={"cost_center": "Cost Center"}),
        on="Cost Center", how="left",
    )
    cc_summary = cc_summary[["Cost Center", "cc_name", "total_debits", "doc_count"]]
    cc_summary.columns = ["Cost Center", "Name", "Total Debits (₹)", "Documents"]

    # ── STEP 5: Trial balance ──────────────────────────────────────────────
    print("\n  [5/7]  Generating trial balances …")
    current_tb  = generate_trial_balance(full_df,     gl_master)
    previous_tb = generate_trial_balance(previous_df, gl_master)
    tb_check    = check_trial_balance(full_df)
    bal_icon    = "✅" if tb_check["is_balanced"] else "❌"
    print(f"         {bal_icon}  Trial balance: "
          f"Dr ₹{tb_check['total_debits']:,.2f}  |  "
          f"Cr ₹{tb_check['total_credits']:,.2f}  |  "
          f"Diff ₹{tb_check['difference']:,.2f}")

    # ── STEP 6: Reconciliation & anomaly detection ─────────────────────────
    print("\n  [6/7]  Running account reconciliation (10% variance threshold) …")
    reconciliation = reconcile_accounts(current_tb, previous_tb, threshold=0.10)
    anomaly_count  = int(reconciliation["anomaly_flag"].sum())
    print(f"         ⚠️   {anomaly_count} account(s) flagged as anomalies")

    # ── STEP 7: Financial close checklist ─────────────────────────────────
    print("\n  [7/7]  Running financial close checklist …")
    checklist = run_close_checklist(completion_rate=0.87)
    completed = int((checklist["status"] == "COMPLETED").sum())
    pending   = int((checklist["status"] == "PENDING").sum())
    print(f"         ✅  {completed} tasks completed  |  ⏳ {pending} tasks pending")

    # ── Export reports ─────────────────────────────────────────────────────
    print("\n  📤  Exporting reports …")
    xl_path  = export_to_excel(
        current_df, alloc_df if not alloc_df.empty else pd.DataFrame(),
        current_tb, reconciliation, checklist,
    )
    csv_path = export_close_report_csv(current_tb, reconciliation, checklist)
    print(f"         📗  {xl_path}")
    print(f"         📄  {csv_path}")

    # ── Print rich console summary ─────────────────────────────────────────
    print_console_summary(
        validation, tb_check, reconciliation, checklist, cc_summary
    )


if __name__ == "__main__":
    main()
