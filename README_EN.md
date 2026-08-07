# Coupang QuickFlex Delivery Bookkeeping

[![Built with Claude](https://img.shields.io/badge/Built%20with-Claude%20at%20Every%20Layer-blueviolet)](#built-with-claude-at-every-layer)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](#installation)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)](#installation)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](#license)

> Built at 3 AM between delivery shifts — a bookkeeping CLI for Korean gig delivery drivers, powered by AI agents at every layer.

A daily bookkeeping tool for Coupang QuickFlex freight sole proprietors.
Connects with an AI agent (Hermes Agent) to record revenue, expenses, and fuel costs via natural language — and generates data ready for Korean tax filing (HomeTax self-reporting).

[한국어 README](./README.md)

---

## Why This Exists

Korean gig economy drivers — Coupang QuickFlex, Baemin, etc. — are registered as sole proprietors. That means filing your own income tax, VAT returns, and tracking every won of revenue and expenses yourself. Most drivers skip daily bookkeeping because after 10+ hours of deliveries, the last thing you want to do is open a spreadsheet.

This tool reduces it to **one sentence after each shift**.

Type something like _"151C 150 packages, LPG 1100 won 35 liters"_ into a Discord bot, and your books are done for the day. Built by a driver, for drivers.

---

## Built with Claude at Every Layer

This project was built using Claude at every layer of the stack:

- **Ideation & domain modeling** — claude.ai (Max, conversational planning)
- **Scaffolding & skill creation** — Hermes Agent (Claude API, orchestration)
- **Code iteration & refactoring** — Claude Code (Max OAuth, delegated via Hermes)
- **Daily usage interface** — Discord bot powered by Hermes gateway

Four Claudes, one codebase, zero manual coding.

---

## Features

- **Natural language input** — "151C 150 packages, LPG 1100 won 35 liters" → auto-parsed and recorded
- **Zone-based pricing** — 151C (₩1,100), 151D (₩850), and 152C/152D (₩1,100); legacy 804/901 codes retained
- **LPG fuel subsidy auto-deduction** — ₩115.14/L, verified from the fuel-subsidy app and official website and observed on a 2026-08-03 fill-up
- **Loss/misdelivery tracking** — settlement deduction history
- **Daily/monthly/yearly summaries** — ready for income tax and VAT filing
- **CSV export** — HomeTax/Excel compatible

## Who This Is For

- Coupang QuickFlex freight sole proprietors (general taxpayer status)
- LPG freight vehicle operators
- Delivery drivers who self-file taxes via HomeTax

## Installation

```bash
git clone https://github.com/u2em/coupang-delivery-bookkeeping.git
cd coupang-delivery-bookkeeping
```

Requires Python 3.8+. Zero external dependencies — sqlite3, csv, json are all Python standard library.

## Usage

### Recording Revenue

```bash
# By delivery zone
python3 bookkeeper.py add-revenue --zone 151C --count 150
python3 bookkeeper.py add-revenue --zone 151D --count 100

# No zone specified (default unit price ₩1,000)
python3 bookkeeper.py add-revenue --count 250

# Manual unit price
python3 bookkeeper.py add-revenue --count 200 --unit-price 980
```

### Recording Fuel Costs

```bash
# LPG refuel — fuel subsidy (₩115.14/L) auto-deducted
# Default verified from the fuel-subsidy app and official website
python3 bookkeeper.py add-fuel --price-per-liter 1100 --liters 35
# → Total ₩38,500 - subsidy ₩4,030 = actual expense ₩34,470
```

### Recording Expenses

```bash
python3 bookkeeper.py add-expense --category maintenance --description "Vehicle inspection" --amount 50000
python3 bookkeeper.py add-expense --category maintenance --description "Tire replacement" --amount 320000
python3 bookkeeper.py add-expense --category toll --description "Highway toll" --amount 3200
```

Expense categories: `fuel` (fuel costs), `maintenance` (vehicle maintenance), `insurance` (insurance), `depreciation` (depreciation), `telecom` (phone/data), `supplies` (consumables), `toll` (tolls), `other` (other)

### Recording Deductions (Loss/Misdelivery)

```bash
python3 bookkeeper.py add-deduction --reason lost --description "1 package lost" --amount 15000
python3 bookkeeper.py add-deduction --reason misdelivery --description "Misdelivery" --amount 8000
```

Deduction reasons: `lost` (lost package), `misdelivery` (wrong address), `return` (returned), `damage` (damaged), `other` (other)

### Summaries

```bash
# Today's summary
python3 bookkeeper.py daily-summary

# Specific date
python3 bookkeeper.py daily-summary --date 2026-04-14

# Monthly summary
python3 bookkeeper.py monthly-summary --month 2026-04

# Yearly summary (for income tax filing)
python3 bookkeeper.py yearly-summary --year 2026
```

### CSV Export

```bash
python3 bookkeeper.py export --month 2026-04 --output april_2026_books.csv
```

### Viewing/Deleting Records

```bash
# View today's records
python3 bookkeeper.py list

# Specific date
python3 bookkeeper.py list --date 2026-04-14

# Delete a wrong entry
python3 bookkeeper.py delete --table revenue --id 3
```

## Date Handling

All commands accept `--date YYYY-MM-DD`. If omitted, today's date is used.

## Data Storage

SQLite DB: `~/.hermes/data/coupang_books.db` (default)

Override with the `HERMES_HOME` environment variable:
```bash
export HERMES_HOME=/path/to/data
```

## AI Agent Integration

Used with [Hermes Agent](https://github.com/NousResearch/hermes-agent), you can manage your books in plain Korean via Discord:

```
Driver: "오늘 151C 150개 151D 100개 했고 분실 하나 만오천원, 자동차검사 5만원, LPG 천백원에 35리터"
        ("Today I did 151C 150, 151D 100, one lost package ₩15,000,
         vehicle inspection ₩50,000, LPG ₩1,100/L × 35 liters")

Agent:
  📋 2026-04-14 Books recorded

  Revenue:
    151C  150 deliveries × ₩1,100 = ₩165,000
    151D  100 deliveries ×   ₩850 =  ₩85,000

  Deductions:
    Lost package  -₩15,000

  Net revenue: ₩235,000

  Expenses:
    Maintenance   Vehicle inspection   ₩50,000
    Fuel          LPG 35L              ₩34,470
    ─────────────────────────────────
    Total                              ₩84,470

  Estimated net profit: ₩150,530
```

## Zone Pricing

| Zone Code | Unit Price | Camp / Effective Date |
|-----------|-----------:|-----------------------|
| 151C | ₩1,100 | F_삼선1, from 2026-07-29 (formerly 804C) |
| 151D | ₩850 | F_삼선1, from 2026-07-29 (formerly 804D) |
| 152C | ₩1,100 | F_삼선1, from 2026-07-29 (formerly 901C) |
| 152D | ₩1,100 | F_삼선1, from 2026-07-29 (formerly 901D) |

Legacy 804C/804D/901C/901D codes are retained for historical records. Zones are managed in the SQLite `zone` table.

## Tax Notes

- Based on general taxpayer status (일반과세자)
- LPG fuel subsidy (₩115.14/L, verified from the fuel-subsidy app and official website and observed on 2026-08-03) is refund income → deducted from expenses
- This tool assists with bookkeeping only and does not provide tax advice

## License

MIT
