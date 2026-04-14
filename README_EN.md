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

Type something like _"804C 150 packages, LPG 1100 won 35 liters"_ into a Discord bot, and your books are done for the day. Built by a driver, for drivers.

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

- **Natural language input** — "804C 150 packages, LPG 1100 won 35 liters" → auto-parsed and recorded
- **Zone-based pricing** — 804C (₩1,050), 804D (₩850), 901CD (₩1,000) auto-applied
- **LPG fuel subsidy auto-deduction** — ₩173/L (Korean freight truck subsidy program)
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
python3 bookkeeper.py add-revenue --zone 804C --count 150
python3 bookkeeper.py add-revenue --zone 804D --count 100

# No zone specified (default unit price ₩1,000)
python3 bookkeeper.py add-revenue --count 250

# Manual unit price
python3 bookkeeper.py add-revenue --count 200 --unit-price 980
```

### Recording Fuel Costs

```bash
# LPG refuel — fuel subsidy (₩173/L) auto-deducted
python3 bookkeeper.py add-fuel --price-per-liter 1100 --liters 35
# → Total ₩38,500 - subsidy ₩6,055 = actual expense ₩32,445
```

### Recording Expenses

```bash
python3 bookkeeper.py add-expense --category maintenance --description "Vehicle inspection" --amount 50000
python3 bookkeeper.py add-expense --category maintenance --description "Tire replacement" --amount 320000
python3 bookkeeper.py add-expense --category toll --description "Highway toll" --amount 3200
```

Expense categories: `fuel` (fuel costs), `maintenance` (vehicle maintenance), `insurance` (insurance), `depreciation` (depreciation), `telecom` (phone/data), `supplies` (consumables), `toll` (tolls), `meal` (meals), `other` (other)

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
Driver: "오늘 804C 150개 804D 100개 했고 분실 하나 만오천원, 자동차검사 5만원, LPG 천백원에 35리터"
        ("Today I did 804C 150, 804D 100, one lost package ₩15,000,
         vehicle inspection ₩50,000, LPG ₩1,100/L × 35 liters")

Agent:
  📋 2026-04-14 Books recorded

  Revenue:
    804C  150 deliveries × ₩1,050 = ₩157,500
    804D  100 deliveries ×   ₩850 =  ₩85,000

  Deductions:
    Lost package  -₩15,000

  Net revenue: ₩227,500

  Expenses:
    Maintenance   Vehicle inspection   ₩50,000
    Fuel          LPG 35L              ₩32,445
    ─────────────────────────────────
    Total                              ₩82,445

  Estimated net profit: ₩145,055
```

## Zone Pricing

| Zone Code | Unit Price |
|-----------|-----------|
| 804C | ₩1,050 |
| 804D | ₩850 |
| 901CD | ₩1,000 |

To add new zones, update the `ZONE_PRICES` dictionary in `bookkeeper.py`.

## Tax Notes

- Based on general taxpayer status (일반과세자)
- Fuel subsidy (₩173/L) is a refund income → deducted from expenses
- This tool assists with bookkeeping only and does not provide tax advice

## License

MIT
