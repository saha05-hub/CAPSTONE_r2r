# 📊 SAP R2R Financial Close Simulation

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![pandas](https://img.shields.io/badge/pandas-2.0%2B-150458?logo=pandas)
![openpyxl](https://img.shields.io/badge/openpyxl-3.1%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Course](https://img.shields.io/badge/Course-SAP%20C__BCBDC-orange)

> **Capstone Project** — SAP DATA / Analytics Engineering (C_BCBDC)  
> Simulates the complete **Record-to-Report (R2R)** cycle — from GL journal posting through month-end financial close — using pure Python (no live SAP system required).

---

## 🗂️ Project Structure

```
r2r_capstone/
├── main.py              # Entry point — orchestrates all 7 steps
├── data_generator.py    # Synthetic SAP master data & GL journal entries
├── r2r_process.py       # Core R2R business logic & report export
├── reports/             # Auto-generated output (Excel + CSV)
│   ├── trial_balance.xlsx
│   └── close_report.csv
├── requirements.txt
├── .gitignore
└── README.md
```

---

## ⚙️ Tech Stack

| Tool        | Version  | Purpose                                   |
|-------------|----------|-------------------------------------------|
| Python      | 3.10+    | Core language                             |
| pandas      | 2.0+     | Data manipulation & aggregation           |
| openpyxl    | 3.1+     | Multi-sheet Excel report generation       |
| Faker       | 19.0+    | Synthetic SAP transaction data            |
| tabulate    | 0.9+     | Console-formatted output tables           |
| NumPy       | 1.24+    | Numerical operations & random seeding     |

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/r2r_capstone.git
cd r2r_capstone
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the simulation
```bash
python main.py
```

Reports are saved to `reports/trial_balance.xlsx` and `reports/close_report.csv`.

---

## 📋 R2R Simulation Steps

| Step | SAP Process                      | Description                                            |
|------|----------------------------------|--------------------------------------------------------|
| 1    | Master Data Load                 | 12 GL accounts, 4 cost centers, 3 profit centers       |
| 2    | GL Journal Entry Generation      | 230+ balanced lines across 115 documents (Mar 2024)    |
| 3    | Journal Entry Validation         | Verifies every document: Σ Debits == Σ Credits         |
| 4    | Cost Center Allocation (KSU1)    | IT & HR costs distributed to Sales and Operations      |
| 5    | Trial Balance Generation         | Aggregated by GL account with net balance              |
| 6    | Account Reconciliation           | MoM variance analysis — flags anomalies > 10%          |
| 7    | Financial Close Checklist (OB52) | 15 period-end tasks simulated with completion tracking |

---

## 📂 Output Files

### `reports/trial_balance.xlsx` — 5 sheets
| Sheet              | Contents                                      |
|--------------------|-----------------------------------------------|
| Journal Entries    | 230+ synthetic GL postings for March 2024     |
| Cost Allocations   | Internal allocation journal entries            |
| Trial Balance      | Aggregated Dr / Cr / Net per GL account       |
| Reconciliation     | MoM variance table with anomaly flags          |
| Close Checklist    | 15 period-end tasks with status and timestamp  |

### `reports/close_report.csv`
Flat summary report combining trial balance, anomalies, and close checklist — ready for upload or email distribution.

---

## 📊 Sample Console Output

```
════════════════════════════════════════════════════════════════════
  SAP R2R — Month-End Financial Close  |  Simulation Report
════════════════════════════════════════════════════════════════════

  ⚖️  TRIAL BALANCE PROOF
  Total Debits    : ₹       4,485,723.90
  Total Credits   : ₹       4,485,723.90
  Difference      : ₹               0.00
  Status          : ✅  BALANCED

  🔍  ANOMALIES DETECTED (>10% variance)
  ╭──────────┬──────────────────────┬───────────────┬─────────╮
  │ GL Acct  │ Account Name         │    Variance % │ Status  │
  ├──────────┼──────────────────────┼───────────────┼─────────┤
  │ 110000   │ Accounts Receivable  │        328.1% │ ⚠️ FLAG │
  │ 400000   │ Revenue              │         67.9% │ ⚠️ FLAG │
  ╰──────────┴──────────────────────┴───────────────┴─────────╯

  ✅  CLOSE CHECKLIST: 14/15 tasks completed (93%)
```

---

## 🎯 Key Features

- **Balanced journal entries** — every document proves `Σ Dr = Σ Cr` (guaranteed)
- **SAP-aligned GL structure** — accounts match standard SAP FI chart of accounts
- **Realistic document types** — SA (G/L), AB (Accounting), ZP (Payment)
- **Cost center allocation engine** — simulates SAP transaction KSU1
- **Anomaly detection** — flags any account with >10% period-over-period variance
- **Multi-format output** — Excel (5 sheets) + CSV, auto-column widths

---

## 📝 License

MIT License — free to use for educational purposes.

---

## 👤 Author

**[Your Name]** | Roll No: [Your Roll No] | Batch: SAP DATA/Analytics Engineering (C_BCBDC)  
KIIT University
