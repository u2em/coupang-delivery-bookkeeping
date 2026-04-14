#!/usr/bin/env python3
"""쿠팡친구 화물 개인사업자 장부 관리 스크립트.

SQLite DB에 매출/경비/유류비를 기록하고 집계한다.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

# --- Constants ---
LPG_SUBSIDY_PER_LITER = 173  # 화물차 LPG 유가보조금 (원/L)
DEFAULT_UNIT_PRICE = 1000     # 기본 배송 건당 단가
DB_DIR = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "data"
DB_PATH = DB_DIR / "coupang_books.db"

# 구역별 배송 단가
ZONE_PRICES = {
    "804C": 1050,
    "804D": 850,
    "901CD": 1000,
}

DEDUCTION_REASONS = {
    "lost": "분실",
    "misdelivery": "오배송",
    "return": "반품",
    "damage": "파손",
    "other": "기타",
}

EXPENSE_CATEGORIES = {
    "fuel": "유류비",
    "maintenance": "차량유지비",
    "insurance": "보험료",
    "depreciation": "감가상각",
    "telecom": "통신비",
    "supplies": "소모품",
    "toll": "통행료",
    "meal": "식비",
    "other": "기타",
}


def get_db() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS revenue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            zone TEXT,
            delivery_count INTEGER NOT NULL,
            unit_price INTEGER NOT NULL,
            total INTEGER NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS fuel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            fuel_type TEXT NOT NULL DEFAULT 'LPG',
            price_per_liter REAL NOT NULL,
            liters REAL NOT NULL,
            total_cost REAL NOT NULL,
            subsidy_per_liter REAL NOT NULL,
            subsidy_amount REAL NOT NULL,
            net_cost REAL NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS expense (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            amount INTEGER NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS deduction (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            reason TEXT NOT NULL,
            description TEXT,
            amount INTEGER NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_revenue_date ON revenue(date);
        CREATE INDEX IF NOT EXISTS idx_fuel_date ON fuel(date);
        CREATE INDEX IF NOT EXISTS idx_expense_date ON expense(date);
        CREATE INDEX IF NOT EXISTS idx_deduction_date ON deduction(date);
    """)


def today_str():
    return date.today().isoformat()


# --- Commands ---

def cmd_add_revenue(args):
    d = args.date or today_str()
    count = args.count
    zone = args.zone.upper() if args.zone else None

    if zone and zone in ZONE_PRICES:
        unit = ZONE_PRICES[zone]
    elif args.unit_price:
        unit = args.unit_price
    else:
        unit = DEFAULT_UNIT_PRICE

    total = count * unit

    conn = get_db()
    conn.execute(
        "INSERT INTO revenue (date, zone, delivery_count, unit_price, total, note) VALUES (?, ?, ?, ?, ?, ?)",
        (d, zone, count, unit, total, args.note)
    )
    conn.commit()
    conn.close()

    result = {
        "action": "revenue_added",
        "date": d,
        "zone": zone,
        "delivery_count": count,
        "unit_price": unit,
        "total": total,
        "note": args.note,
        "unit_price_source": "zone" if (zone and zone in ZONE_PRICES) else ("manual" if args.unit_price else "default"),
    }
    print(json.dumps(result, ensure_ascii=False))


def cmd_add_fuel(args):
    d = args.date or today_str()
    price = args.price_per_liter
    liters = args.liters
    total_cost = round(price * liters, 0)
    subsidy = LPG_SUBSIDY_PER_LITER
    subsidy_amount = round(subsidy * liters, 0)
    net = round(total_cost - subsidy_amount, 0)

    conn = get_db()
    conn.execute(
        """INSERT INTO fuel (date, fuel_type, price_per_liter, liters, total_cost,
           subsidy_per_liter, subsidy_amount, net_cost, note)
           VALUES (?, 'LPG', ?, ?, ?, ?, ?, ?, ?)""",
        (d, price, liters, total_cost, subsidy, subsidy_amount, net, args.note)
    )
    conn.commit()
    conn.close()

    result = {
        "action": "fuel_added",
        "date": d,
        "fuel_type": "LPG",
        "price_per_liter": price,
        "liters": liters,
        "total_cost": int(total_cost),
        "subsidy_per_liter": subsidy,
        "subsidy_amount": int(subsidy_amount),
        "net_cost": int(net),
        "note": args.note,
    }
    print(json.dumps(result, ensure_ascii=False))


def cmd_add_expense(args):
    d = args.date or today_str()
    cat = args.category
    if cat not in EXPENSE_CATEGORIES:
        print(json.dumps({"error": f"Unknown category: {cat}", "valid": list(EXPENSE_CATEGORIES.keys())}, ensure_ascii=False))
        sys.exit(1)

    conn = get_db()
    conn.execute(
        "INSERT INTO expense (date, category, description, amount, note) VALUES (?, ?, ?, ?, ?)",
        (d, cat, args.description, args.amount, args.note)
    )
    conn.commit()
    conn.close()

    result = {
        "action": "expense_added",
        "date": d,
        "category": cat,
        "category_name": EXPENSE_CATEGORIES[cat],
        "description": args.description,
        "amount": args.amount,
        "note": args.note,
    }
    print(json.dumps(result, ensure_ascii=False))


def cmd_add_deduction(args):
    d = args.date or today_str()
    reason = args.reason
    if reason not in DEDUCTION_REASONS:
        print(json.dumps({"error": f"Unknown reason: {reason}", "valid": list(DEDUCTION_REASONS.keys())}, ensure_ascii=False))
        sys.exit(1)

    conn = get_db()
    conn.execute(
        "INSERT INTO deduction (date, reason, description, amount, note) VALUES (?, ?, ?, ?, ?)",
        (d, reason, args.description, args.amount, args.note)
    )
    conn.commit()
    conn.close()

    result = {
        "action": "deduction_added",
        "date": d,
        "reason": reason,
        "reason_name": DEDUCTION_REASONS[reason],
        "description": args.description,
        "amount": args.amount,
        "note": args.note,
    }
    print(json.dumps(result, ensure_ascii=False))


def cmd_daily_summary(args):
    d = args.date or today_str()
    conn = get_db()

    # Revenue (with zone breakdown)
    rev_total_row = conn.execute(
        "SELECT SUM(delivery_count) as cnt, SUM(total) as total FROM revenue WHERE date = ?", (d,)
    ).fetchone()
    rev_by_zone = conn.execute(
        "SELECT zone, SUM(delivery_count) as cnt, unit_price, SUM(total) as total FROM revenue WHERE date = ? GROUP BY zone, unit_price ORDER BY zone",
        (d,)
    ).fetchall()

    # Deductions
    ded_rows = conn.execute(
        "SELECT reason, description, amount FROM deduction WHERE date = ? ORDER BY reason", (d,)
    ).fetchall()

    # Fuel
    fuel_rows = conn.execute(
        "SELECT SUM(liters) as liters, SUM(total_cost) as total, SUM(subsidy_amount) as subsidy, SUM(net_cost) as net FROM fuel WHERE date = ?", (d,)
    ).fetchone()

    # Expenses (non-fuel)
    exp_rows = conn.execute(
        "SELECT category, description, amount FROM expense WHERE date = ? ORDER BY category", (d,)
    ).fetchall()

    conn.close()

    revenue_total = rev_total_row["total"] or 0
    delivery_count = rev_total_row["cnt"] or 0

    revenue_by_zone = [{"zone": r["zone"] or "미지정", "count": r["cnt"],
                        "unit_price": r["unit_price"], "total": r["total"]} for r in rev_by_zone]

    deductions = [{"reason": r["reason"], "reason_name": DEDUCTION_REASONS.get(r["reason"], r["reason"]),
                   "description": r["description"], "amount": r["amount"]} for r in ded_rows]
    deduction_total = sum(d["amount"] for d in deductions)

    net_revenue = revenue_total - deduction_total

    fuel_total = int(fuel_rows["total"] or 0)
    fuel_subsidy = int(fuel_rows["subsidy"] or 0)
    fuel_net = int(fuel_rows["net"] or 0)
    fuel_liters = fuel_rows["liters"] or 0

    expenses = [{"category": r["category"], "category_name": EXPENSE_CATEGORIES.get(r["category"], r["category"]),
                 "description": r["description"], "amount": r["amount"]} for r in exp_rows]
    expense_total = sum(e["amount"] for e in expenses)

    total_expense = fuel_net + expense_total
    net_profit = net_revenue - total_expense

    result = {
        "date": d,
        "revenue": {
            "delivery_count": delivery_count,
            "gross_total": revenue_total,
            "by_zone": revenue_by_zone,
        },
        "deductions": deductions,
        "deduction_total": deduction_total,
        "net_revenue": net_revenue,
        "fuel": {
            "liters": fuel_liters,
            "total_cost": fuel_total,
            "subsidy": fuel_subsidy,
            "net_cost": fuel_net,
        },
        "expenses": expenses,
        "expense_total": expense_total,
        "total_expense": total_expense,
        "net_profit_estimate": net_profit,
    }
    print(json.dumps(result, ensure_ascii=False))


def cmd_monthly_summary(args):
    month = args.month  # format: 2026-04
    conn = get_db()

    rev = conn.execute(
        "SELECT SUM(delivery_count) as cnt, SUM(total) as total, COUNT(DISTINCT date) as days FROM revenue WHERE date LIKE ?",
        (f"{month}%",)
    ).fetchone()

    ded = conn.execute(
        "SELECT SUM(amount) as total FROM deduction WHERE date LIKE ?", (f"{month}%",)
    ).fetchone()

    fuel = conn.execute(
        "SELECT SUM(liters) as liters, SUM(total_cost) as total, SUM(subsidy_amount) as subsidy, SUM(net_cost) as net FROM fuel WHERE date LIKE ?",
        (f"{month}%",)
    ).fetchone()

    exp = conn.execute(
        "SELECT category, SUM(amount) as total FROM expense WHERE date LIKE ? GROUP BY category ORDER BY total DESC",
        (f"{month}%",)
    ).fetchall()

    conn.close()

    revenue_total = rev["total"] or 0
    delivery_count = rev["cnt"] or 0
    working_days = rev["days"] or 0
    deduction_total = ded["total"] or 0
    net_revenue = revenue_total - deduction_total

    fuel_net = int(fuel["net"] or 0)
    fuel_subsidy = int(fuel["subsidy"] or 0)

    expenses_by_cat = [{"category": r["category"], "category_name": EXPENSE_CATEGORIES.get(r["category"], r["category"]),
                        "total": r["total"]} for r in exp]
    expense_total = sum(e["total"] for e in expenses_by_cat)

    total_expense = fuel_net + expense_total
    net_profit = net_revenue - total_expense

    result = {
        "month": month,
        "working_days": working_days,
        "revenue": {
            "delivery_count": delivery_count,
            "gross_total": revenue_total,
            "deduction_total": deduction_total,
            "net_total": net_revenue,
            "avg_per_day": round(net_revenue / working_days) if working_days else 0,
        },
        "fuel": {
            "liters": fuel["liters"] or 0,
            "total_cost": int(fuel["total"] or 0),
            "subsidy": fuel_subsidy,
            "net_cost": fuel_net,
        },
        "expenses_by_category": expenses_by_cat,
        "expense_total": expense_total,
        "total_expense": total_expense,
        "net_profit_estimate": net_profit,
    }
    print(json.dumps(result, ensure_ascii=False))


def cmd_yearly_summary(args):
    year = str(args.year)
    conn = get_db()

    rev = conn.execute(
        "SELECT SUM(delivery_count) as cnt, SUM(total) as total, COUNT(DISTINCT date) as days FROM revenue WHERE date LIKE ?",
        (f"{year}%",)
    ).fetchone()

    fuel = conn.execute(
        "SELECT SUM(liters) as liters, SUM(total_cost) as total, SUM(subsidy_amount) as subsidy, SUM(net_cost) as net FROM fuel WHERE date LIKE ?",
        (f"{year}%",)
    ).fetchone()

    exp = conn.execute(
        "SELECT category, SUM(amount) as total FROM expense WHERE date LIKE ? GROUP BY category ORDER BY total DESC",
        (f"{year}%",)
    ).fetchall()

    # Monthly breakdown
    monthly = conn.execute(
        """SELECT substr(date,1,7) as month,
           SUM(delivery_count) as cnt, SUM(total) as rev
           FROM revenue WHERE date LIKE ? GROUP BY substr(date,1,7) ORDER BY month""",
        (f"{year}%",)
    ).fetchall()

    conn.close()

    revenue_total = rev["total"] or 0
    fuel_net = int(fuel["net"] or 0)
    fuel_subsidy = int(fuel["subsidy"] or 0)
    expenses_by_cat = [{"category": r["category"], "category_name": EXPENSE_CATEGORIES.get(r["category"], r["category"]),
                        "total": r["total"]} for r in exp]
    expense_total = sum(e["total"] for e in expenses_by_cat)
    total_expense = fuel_net + expense_total

    result = {
        "year": year,
        "working_days": rev["days"] or 0,
        "revenue_total": revenue_total,
        "delivery_count": rev["cnt"] or 0,
        "fuel_net": fuel_net,
        "fuel_subsidy_received": fuel_subsidy,
        "expenses_by_category": expenses_by_cat,
        "expense_total": expense_total,
        "total_expense": total_expense,
        "net_income_estimate": revenue_total - total_expense,
        "monthly_breakdown": [{"month": r["month"], "deliveries": r["cnt"], "revenue": r["rev"]} for r in monthly],
    }
    print(json.dumps(result, ensure_ascii=False))


def cmd_export(args):
    import csv
    month = args.month
    output = args.output or f"coupang_{month.replace('-','_')}.csv"
    conn = get_db()

    rows = []

    # Revenue records
    for r in conn.execute("SELECT * FROM revenue WHERE date LIKE ? ORDER BY date", (f"{month}%",)):
        rows.append({
            "날짜": r["date"], "구분": "매출", "분류": "배송",
            "내용": f"배송 {r['delivery_count']}건 × {r['unit_price']}원",
            "수입": r["total"], "지출": "", "비고": r["note"] or ""
        })

    # Fuel records
    for r in conn.execute("SELECT * FROM fuel WHERE date LIKE ? ORDER BY date", (f"{month}%",)):
        rows.append({
            "날짜": r["date"], "구분": "경비", "분류": "유류비",
            "내용": f"LPG {r['liters']}L × {r['price_per_liter']}원 (보조금 -{int(r['subsidy_amount'])}원)",
            "수입": "", "지출": int(r["net_cost"]), "비고": r["note"] or ""
        })

    # Expense records
    for r in conn.execute("SELECT * FROM expense WHERE date LIKE ? ORDER BY date", (f"{month}%",)):
        rows.append({
            "날짜": r["date"], "구분": "경비",
            "분류": EXPENSE_CATEGORIES.get(r["category"], r["category"]),
            "내용": r["description"],
            "수입": "", "지출": r["amount"], "비고": r["note"] or ""
        })

    conn.close()

    rows.sort(key=lambda x: x["날짜"])

    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["날짜", "구분", "분류", "내용", "수입", "지출", "비고"])
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({"action": "exported", "month": month, "output": output, "rows": len(rows)}, ensure_ascii=False))


def cmd_delete(args):
    """Delete a record by table and ID."""
    table = args.table
    if table not in ("revenue", "fuel", "expense"):
        print(json.dumps({"error": f"Invalid table: {table}"}))
        sys.exit(1)
    conn = get_db()
    cursor = conn.execute(f"DELETE FROM {table} WHERE id = ?", (args.id,))
    conn.commit()
    conn.close()
    print(json.dumps({"action": "deleted", "table": table, "id": args.id, "rows_affected": cursor.rowcount}))


def cmd_list(args):
    """List records for a date or date range."""
    d = args.date or today_str()
    conn = get_db()

    result = {"date": d, "revenue": [], "fuel": [], "expenses": []}

    for r in conn.execute("SELECT * FROM revenue WHERE date = ?", (d,)):
        result["revenue"].append(dict(r))
    for r in conn.execute("SELECT * FROM fuel WHERE date = ?", (d,)):
        result["fuel"].append(dict(r))
    for r in conn.execute("SELECT * FROM expense WHERE date = ?", (d,)):
        result["expenses"].append(dict(r))

    conn.close()
    print(json.dumps(result, ensure_ascii=False, default=str))


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="쿠팡친구 장부 관리")
    sub = parser.add_subparsers(dest="command")

    # add-revenue
    p = sub.add_parser("add-revenue")
    p.add_argument("--date", type=str)
    p.add_argument("--zone", type=str, help="구역코드 (804C, 804D, 901CD)")
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--unit-price", type=int, help="구역코드 없을 때 수동 단가")
    p.add_argument("--note", type=str)

    # add-fuel
    p = sub.add_parser("add-fuel")
    p.add_argument("--date", type=str)
    p.add_argument("--price-per-liter", type=float, required=True)
    p.add_argument("--liters", type=float, required=True)
    p.add_argument("--note", type=str)

    # add-expense
    p = sub.add_parser("add-expense")
    p.add_argument("--date", type=str)
    p.add_argument("--category", type=str, required=True, choices=list(EXPENSE_CATEGORIES.keys()))
    p.add_argument("--description", type=str, required=True)
    p.add_argument("--amount", type=int, required=True)
    p.add_argument("--note", type=str)

    # add-deduction
    p = sub.add_parser("add-deduction")
    p.add_argument("--date", type=str)
    p.add_argument("--reason", type=str, required=True, choices=list(DEDUCTION_REASONS.keys()))
    p.add_argument("--description", type=str)
    p.add_argument("--amount", type=int, required=True, help="차감 금액 (양수로 입력)")
    p.add_argument("--note", type=str)

    # daily-summary
    p = sub.add_parser("daily-summary")
    p.add_argument("--date", type=str)

    # monthly-summary
    p = sub.add_parser("monthly-summary")
    p.add_argument("--month", type=str, required=True, help="YYYY-MM format")

    # yearly-summary
    p = sub.add_parser("yearly-summary")
    p.add_argument("--year", type=int, required=True)

    # export
    p = sub.add_parser("export")
    p.add_argument("--month", type=str, required=True)
    p.add_argument("--output", type=str)

    # delete
    p = sub.add_parser("delete")
    p.add_argument("--table", type=str, required=True, choices=["revenue", "fuel", "expense"])
    p.add_argument("--id", type=int, required=True)

    # list
    p = sub.add_parser("list")
    p.add_argument("--date", type=str)

    args = parser.parse_args()

    commands = {
        "add-revenue": cmd_add_revenue,
        "add-fuel": cmd_add_fuel,
        "add-expense": cmd_add_expense,
        "add-deduction": cmd_add_deduction,
        "daily-summary": cmd_daily_summary,
        "monthly-summary": cmd_monthly_summary,
        "yearly-summary": cmd_yearly_summary,
        "export": cmd_export,
        "delete": cmd_delete,
        "list": cmd_list,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
