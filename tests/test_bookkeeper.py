"""Comprehensive tests for bookkeeper.py."""

import csv
import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

import bookkeeper
from tests.conftest import make_args


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def parse_json(text: str):
    """Parse JSON from printed output."""
    return json.loads(text.strip())


# ---------------------------------------------------------------------------
# DB initialisation & seed zones
# ---------------------------------------------------------------------------

class TestDBInit:
    def test_fresh_db_creates_tables(self):
        conn = bookkeeper.get_db()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert "revenue" in tables
        assert "fuel" in tables
        assert "expense" in tables
        assert "deduction" in tables
        assert "zone" in tables

    def test_seed_zones_created(self):
        conn = bookkeeper.get_db()
        count = conn.execute("SELECT COUNT(*) FROM zone").fetchone()[0]
        conn.close()
        assert count == 4  # 4 default zones

    def test_seed_zone_codes(self):
        conn = bookkeeper.get_db()
        codes = [r[0] for r in conn.execute("SELECT code FROM zone ORDER BY code").fetchall()]
        conn.close()
        assert codes == ["804C", "804D", "901C", "901D"]

    def test_seed_zones_not_duplicated_on_second_call(self):
        conn = bookkeeper.get_db()
        conn.close()
        # Open again — should NOT double-insert
        conn2 = bookkeeper.get_db()
        count = conn2.execute("SELECT COUNT(*) FROM zone").fetchone()[0]
        conn2.close()
        assert count == 4


# ---------------------------------------------------------------------------
# add-revenue
# ---------------------------------------------------------------------------

class TestAddRevenue:
    def test_default_unit_price(self, capsys):
        args = make_args(count=10, zone=None, unit_price=None)
        bookkeeper.cmd_add_revenue(args)
        out = parse_json(capsys.readouterr().out)
        assert out["action"] == "revenue_added"
        assert out["unit_price"] == bookkeeper.DEFAULT_UNIT_PRICE
        assert out["total"] == 10 * bookkeeper.DEFAULT_UNIT_PRICE
        assert out["unit_price_source"] == "default"

    def test_manual_unit_price(self, capsys):
        args = make_args(count=5, zone=None, unit_price=1200)
        bookkeeper.cmd_add_revenue(args)
        out = parse_json(capsys.readouterr().out)
        assert out["unit_price"] == 1200
        assert out["total"] == 6000
        assert out["unit_price_source"] == "manual"

    def test_zone_lookup(self, capsys):
        """Revenue with zone=804C should use the zone's unit_price (1050)."""
        args = make_args(count=20, zone="804c", unit_price=None)
        bookkeeper.cmd_add_revenue(args)
        out = parse_json(capsys.readouterr().out)
        assert out["zone"] == "804C"
        assert out["unit_price"] == 1050
        assert out["total"] == 20 * 1050
        assert out["unit_price_source"] == "zone"

    def test_zone_not_found_uses_default(self, capsys):
        args = make_args(count=3, zone="ZZXX", unit_price=None)
        bookkeeper.cmd_add_revenue(args)
        out = parse_json(capsys.readouterr().out)
        assert out["unit_price"] == bookkeeper.DEFAULT_UNIT_PRICE
        assert out["unit_price_source"] == "default"

    def test_zone_not_found_uses_manual(self, capsys):
        args = make_args(count=3, zone="ZZXX", unit_price=900)
        bookkeeper.cmd_add_revenue(args)
        out = parse_json(capsys.readouterr().out)
        assert out["unit_price"] == 900
        assert out["unit_price_source"] == "manual"

    def test_explicit_date(self, capsys):
        args = make_args(count=1, zone=None, unit_price=None, date="2026-01-15")
        bookkeeper.cmd_add_revenue(args)
        out = parse_json(capsys.readouterr().out)
        assert out["date"] == "2026-01-15"

    def test_output_is_valid_json(self, capsys):
        args = make_args(count=1, zone=None, unit_price=None)
        bookkeeper.cmd_add_revenue(args)
        raw = capsys.readouterr().out.strip()
        json.loads(raw)  # must not raise


# ---------------------------------------------------------------------------
# add-fuel
# ---------------------------------------------------------------------------

class TestAddFuel:
    def test_basic(self, capsys):
        args = make_args(price_per_liter=1000.0, liters=50.0)
        bookkeeper.cmd_add_fuel(args)
        out = parse_json(capsys.readouterr().out)
        assert out["action"] == "fuel_added"
        assert out["total_cost"] == 50000
        assert out["subsidy_per_liter"] == bookkeeper.LPG_SUBSIDY_PER_LITER
        assert out["subsidy_amount"] == 173 * 50
        assert out["net_cost"] == 50000 - 173 * 50

    def test_subsidy_calculation(self, capsys):
        args = make_args(price_per_liter=1200.0, liters=40.0)
        bookkeeper.cmd_add_fuel(args)
        out = parse_json(capsys.readouterr().out)
        expected_total = round(1200 * 40)
        expected_subsidy = round(173 * 40)
        assert out["total_cost"] == expected_total
        assert out["subsidy_amount"] == expected_subsidy
        assert out["net_cost"] == expected_total - expected_subsidy

    def test_output_is_valid_json(self, capsys):
        args = make_args(price_per_liter=900.0, liters=10.0)
        bookkeeper.cmd_add_fuel(args)
        raw = capsys.readouterr().out.strip()
        json.loads(raw)


# ---------------------------------------------------------------------------
# add-expense
# ---------------------------------------------------------------------------

class TestAddExpense:
    def test_valid_category(self, capsys):
        args = make_args(category="toll", description="고속도로", amount=5000)
        bookkeeper.cmd_add_expense(args)
        out = parse_json(capsys.readouterr().out)
        assert out["action"] == "expense_added"
        assert out["category"] == "toll"
        assert out["amount"] == 5000

    def test_unknown_category(self, capsys):
        args = make_args(category="INVALID", description="x", amount=100)
        with pytest.raises(SystemExit) as exc_info:
            bookkeeper.cmd_add_expense(args)
        assert exc_info.value.code == 1
        out = parse_json(capsys.readouterr().out)
        assert "error" in out
        assert "valid" in out

    def test_output_is_valid_json(self, capsys):
        args = make_args(category="meal", description="점심", amount=8000)
        bookkeeper.cmd_add_expense(args)
        raw = capsys.readouterr().out.strip()
        json.loads(raw)


# ---------------------------------------------------------------------------
# add-deduction
# ---------------------------------------------------------------------------

class TestAddDeduction:
    def test_valid_reason(self, capsys):
        args = make_args(reason="lost", description="분실 건", amount=30000)
        bookkeeper.cmd_add_deduction(args)
        out = parse_json(capsys.readouterr().out)
        assert out["action"] == "deduction_added"
        assert out["reason"] == "lost"
        assert out["amount"] == 30000

    def test_unknown_reason(self, capsys):
        args = make_args(reason="FAKE", description="x", amount=100)
        with pytest.raises(SystemExit) as exc_info:
            bookkeeper.cmd_add_deduction(args)
        assert exc_info.value.code == 1
        out = parse_json(capsys.readouterr().out)
        assert "error" in out

    def test_output_is_valid_json(self, capsys):
        args = make_args(reason="damage", description="파손", amount=5000)
        bookkeeper.cmd_add_deduction(args)
        raw = capsys.readouterr().out.strip()
        json.loads(raw)


# ---------------------------------------------------------------------------
# Zone CRUD
# ---------------------------------------------------------------------------

class TestZoneCRUD:
    def test_add_zone(self, capsys):
        args = make_args(
            code="999A", name="테스트", unit_price=1100,
            streets="테스트길", area_type="apartment",
            approx_units=500, district="강남구", note=None
        )
        bookkeeper.cmd_add_zone(args)
        out = parse_json(capsys.readouterr().out)
        assert out["action"] == "zone_added"
        assert out["code"] == "999A"
        assert out["unit_price"] == 1100

    def test_add_duplicate_zone(self, capsys):
        args = make_args(
            code="804C", name="dup", unit_price=999,
            streets=None, area_type=None,
            approx_units=None, district=None, note=None
        )
        with pytest.raises(SystemExit) as exc_info:
            bookkeeper.cmd_add_zone(args)
        assert exc_info.value.code == 1
        out = parse_json(capsys.readouterr().out)
        assert "error" in out

    def test_list_zones(self, capsys):
        args = make_args()
        bookkeeper.cmd_list_zones(args)
        out = parse_json(capsys.readouterr().out)
        assert isinstance(out, list)
        assert len(out) == 4
        codes = [z["code"] for z in out]
        assert "804C" in codes

    def test_update_zone(self, capsys):
        args = make_args(
            code="804C", name=None, unit_price=2000,
            streets=None, area_type=None,
            approx_units=None, district=None, note=None
        )
        bookkeeper.cmd_update_zone(args)
        out = parse_json(capsys.readouterr().out)
        assert out["action"] == "zone_updated"
        assert out["unit_price"] == 2000

    def test_update_nonexistent_zone(self, capsys):
        args = make_args(
            code="ZZZZ", name=None, unit_price=500,
            streets=None, area_type=None,
            approx_units=None, district=None, note=None
        )
        with pytest.raises(SystemExit):
            bookkeeper.cmd_update_zone(args)
        out = parse_json(capsys.readouterr().out)
        assert "error" in out

    def test_update_zone_no_fields(self, capsys):
        args = make_args(
            code="804C", name=None, unit_price=None,
            streets=None, area_type=None,
            approx_units=None, district=None, note=None
        )
        with pytest.raises(SystemExit):
            bookkeeper.cmd_update_zone(args)
        out = parse_json(capsys.readouterr().out)
        assert "error" in out

    def test_remove_zone(self, capsys):
        args = make_args(code="804D")
        bookkeeper.cmd_remove_zone(args)
        out = parse_json(capsys.readouterr().out)
        assert out["action"] == "zone_removed"
        assert out["code"] == "804D"

    def test_remove_nonexistent_zone(self, capsys):
        args = make_args(code="ZZZZ")
        with pytest.raises(SystemExit):
            bookkeeper.cmd_remove_zone(args)
        out = parse_json(capsys.readouterr().out)
        assert "error" in out


# ---------------------------------------------------------------------------
# Zone-based revenue integration
# ---------------------------------------------------------------------------

class TestZoneRevenue:
    def test_zone_804D_price(self, capsys):
        """804D has unit_price 850."""
        args = make_args(count=10, zone="804D", unit_price=None)
        bookkeeper.cmd_add_revenue(args)
        out = parse_json(capsys.readouterr().out)
        assert out["unit_price"] == 850
        assert out["total"] == 8500

    def test_zone_901C_price(self, capsys):
        """901C has unit_price 1000."""
        args = make_args(count=5, zone="901c", unit_price=None)
        bookkeeper.cmd_add_revenue(args)
        out = parse_json(capsys.readouterr().out)
        assert out["unit_price"] == 1000
        assert out["total"] == 5000

    def test_updated_zone_price_used(self, capsys):
        """After updating a zone's price, revenue should use the new price."""
        # Update 804C from 1050 to 1200
        upd = make_args(
            code="804C", name=None, unit_price=1200,
            streets=None, area_type=None,
            approx_units=None, district=None, note=None
        )
        bookkeeper.cmd_update_zone(upd)
        capsys.readouterr()  # discard

        args = make_args(count=10, zone="804C", unit_price=None)
        bookkeeper.cmd_add_revenue(args)
        out = parse_json(capsys.readouterr().out)
        assert out["unit_price"] == 1200
        assert out["total"] == 12000


# ---------------------------------------------------------------------------
# daily-summary
# ---------------------------------------------------------------------------

class TestDailySummary:
    def _add_test_data(self, d="2026-04-01"):
        bookkeeper.cmd_add_revenue(make_args(count=20, zone="804C", unit_price=None, date=d))
        bookkeeper.cmd_add_fuel(make_args(price_per_liter=1000.0, liters=50.0, date=d))
        bookkeeper.cmd_add_expense(make_args(category="toll", description="통행료", amount=5000, date=d))
        bookkeeper.cmd_add_deduction(make_args(reason="lost", description="분실", amount=3000, date=d))

    def test_summary_structure(self, capsys):
        self._add_test_data()
        capsys.readouterr()  # discard add outputs

        args = make_args(date="2026-04-01")
        bookkeeper.cmd_daily_summary(args)
        out = parse_json(capsys.readouterr().out)

        assert out["date"] == "2026-04-01"
        assert "revenue" in out
        assert "fuel" in out
        assert "expenses" in out
        assert "net_profit_estimate" in out

    def test_summary_calculations(self, capsys):
        self._add_test_data()
        capsys.readouterr()

        args = make_args(date="2026-04-01")
        bookkeeper.cmd_daily_summary(args)
        out = parse_json(capsys.readouterr().out)

        assert out["revenue"]["delivery_count"] == 20
        assert out["revenue"]["gross_total"] == 20 * 1050
        assert out["deduction_total"] == 3000
        assert out["net_revenue"] == 20 * 1050 - 3000

    def test_empty_day(self, capsys):
        args = make_args(date="2099-01-01")
        bookkeeper.cmd_daily_summary(args)
        out = parse_json(capsys.readouterr().out)
        assert out["revenue"]["delivery_count"] == 0
        assert out["net_profit_estimate"] == 0

    def test_output_is_valid_json(self, capsys):
        args = make_args(date="2026-04-01")
        bookkeeper.cmd_daily_summary(args)
        raw = capsys.readouterr().out.strip()
        json.loads(raw)


# ---------------------------------------------------------------------------
# monthly-summary
# ---------------------------------------------------------------------------

class TestMonthlySummary:
    def test_with_data(self, capsys):
        # Add data on two different days in same month
        bookkeeper.cmd_add_revenue(make_args(count=10, zone=None, unit_price=None, date="2026-03-01"))
        bookkeeper.cmd_add_revenue(make_args(count=15, zone=None, unit_price=None, date="2026-03-15"))
        bookkeeper.cmd_add_fuel(make_args(price_per_liter=1000.0, liters=30.0, date="2026-03-10"))
        capsys.readouterr()

        args = make_args(month="2026-03")
        bookkeeper.cmd_monthly_summary(args)
        out = parse_json(capsys.readouterr().out)

        assert out["month"] == "2026-03"
        assert out["working_days"] == 2
        assert out["revenue"]["delivery_count"] == 25
        assert out["revenue"]["gross_total"] == 25 * bookkeeper.DEFAULT_UNIT_PRICE

    def test_empty_month(self, capsys):
        args = make_args(month="2099-12")
        bookkeeper.cmd_monthly_summary(args)
        out = parse_json(capsys.readouterr().out)
        assert out["revenue"]["delivery_count"] == 0
        assert out["working_days"] == 0

    def test_output_is_valid_json(self, capsys):
        args = make_args(month="2026-04")
        bookkeeper.cmd_monthly_summary(args)
        raw = capsys.readouterr().out.strip()
        json.loads(raw)


# ---------------------------------------------------------------------------
# yearly-summary
# ---------------------------------------------------------------------------

class TestYearlySummary:
    def test_with_data(self, capsys):
        bookkeeper.cmd_add_revenue(make_args(count=10, zone=None, unit_price=None, date="2026-01-10"))
        bookkeeper.cmd_add_revenue(make_args(count=20, zone=None, unit_price=None, date="2026-06-10"))
        capsys.readouterr()

        args = make_args(year=2026)
        bookkeeper.cmd_yearly_summary(args)
        out = parse_json(capsys.readouterr().out)

        assert out["year"] == "2026"
        assert out["delivery_count"] == 30
        assert out["revenue_total"] == 30 * bookkeeper.DEFAULT_UNIT_PRICE
        assert len(out["monthly_breakdown"]) == 2

    def test_empty_year(self, capsys):
        args = make_args(year=2099)
        bookkeeper.cmd_yearly_summary(args)
        out = parse_json(capsys.readouterr().out)
        assert out["delivery_count"] == 0
        assert out["monthly_breakdown"] == []

    def test_output_is_valid_json(self, capsys):
        args = make_args(year=2026)
        bookkeeper.cmd_yearly_summary(args)
        raw = capsys.readouterr().out.strip()
        json.loads(raw)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

class TestExport:
    def test_export_creates_csv(self, capsys, tmp_path):
        bookkeeper.cmd_add_revenue(make_args(count=5, zone=None, unit_price=None, date="2026-05-01"))
        bookkeeper.cmd_add_fuel(make_args(price_per_liter=1000.0, liters=10.0, date="2026-05-01"))
        bookkeeper.cmd_add_expense(make_args(category="meal", description="점심", amount=8000, date="2026-05-01"))
        capsys.readouterr()

        outfile = str(tmp_path / "export.csv")
        args = make_args(month="2026-05", output=outfile)
        bookkeeper.cmd_export(args)
        out = parse_json(capsys.readouterr().out)

        assert out["action"] == "exported"
        assert out["rows"] == 3
        assert Path(outfile).exists()

        with open(outfile, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 3

    def test_export_empty_month(self, capsys, tmp_path):
        outfile = str(tmp_path / "empty.csv")
        args = make_args(month="2099-12", output=outfile)
        bookkeeper.cmd_export(args)
        out = parse_json(capsys.readouterr().out)
        assert out["rows"] == 0

    def test_output_is_valid_json(self, capsys, tmp_path):
        outfile = str(tmp_path / "test.csv")
        args = make_args(month="2026-01", output=outfile)
        bookkeeper.cmd_export(args)
        raw = capsys.readouterr().out.strip()
        json.loads(raw)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

class TestList:
    def test_list_with_data(self, capsys):
        bookkeeper.cmd_add_revenue(make_args(count=5, zone=None, unit_price=None, date="2026-04-10"))
        bookkeeper.cmd_add_fuel(make_args(price_per_liter=900.0, liters=20.0, date="2026-04-10"))
        bookkeeper.cmd_add_expense(make_args(category="supplies", description="테이프", amount=3000, date="2026-04-10"))
        capsys.readouterr()

        args = make_args(date="2026-04-10")
        bookkeeper.cmd_list(args)
        out = parse_json(capsys.readouterr().out)

        assert out["date"] == "2026-04-10"
        assert len(out["revenue"]) == 1
        assert len(out["fuel"]) == 1
        assert len(out["expenses"]) == 1

    def test_list_empty(self, capsys):
        args = make_args(date="2099-01-01")
        bookkeeper.cmd_list(args)
        out = parse_json(capsys.readouterr().out)
        assert out["revenue"] == []
        assert out["fuel"] == []
        assert out["expenses"] == []

    def test_output_is_valid_json(self, capsys):
        args = make_args(date="2026-01-01")
        bookkeeper.cmd_list(args)
        raw = capsys.readouterr().out.strip()
        json.loads(raw)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_revenue(self, capsys):
        bookkeeper.cmd_add_revenue(make_args(count=5, zone=None, unit_price=None, date="2026-04-01"))
        capsys.readouterr()

        args = make_args(table="revenue", id=1)
        bookkeeper.cmd_delete(args)
        out = parse_json(capsys.readouterr().out)
        assert out["action"] == "deleted"
        assert out["rows_affected"] == 1

    def test_delete_fuel(self, capsys):
        bookkeeper.cmd_add_fuel(make_args(price_per_liter=1000.0, liters=10.0, date="2026-04-01"))
        capsys.readouterr()

        args = make_args(table="fuel", id=1)
        bookkeeper.cmd_delete(args)
        out = parse_json(capsys.readouterr().out)
        assert out["rows_affected"] == 1

    def test_delete_expense(self, capsys):
        bookkeeper.cmd_add_expense(make_args(category="meal", description="x", amount=5000, date="2026-04-01"))
        capsys.readouterr()

        args = make_args(table="expense", id=1)
        bookkeeper.cmd_delete(args)
        out = parse_json(capsys.readouterr().out)
        assert out["rows_affected"] == 1

    def test_delete_nonexistent_id(self, capsys):
        args = make_args(table="revenue", id=9999)
        bookkeeper.cmd_delete(args)
        out = parse_json(capsys.readouterr().out)
        assert out["rows_affected"] == 0

    def test_delete_invalid_table(self, capsys):
        args = make_args(table="deduction", id=1)
        with pytest.raises(SystemExit) as exc_info:
            bookkeeper.cmd_delete(args)
        assert exc_info.value.code == 1
        out = parse_json(capsys.readouterr().out)
        assert "error" in out

    def test_delete_whitelist_zone(self, capsys):
        args = make_args(table="zone", id=1)
        with pytest.raises(SystemExit):
            bookkeeper.cmd_delete(args)
        out = parse_json(capsys.readouterr().out)
        assert "error" in out

    def test_delete_whitelist_arbitrary(self, capsys):
        args = make_args(table="sqlite_master", id=1)
        with pytest.raises(SystemExit):
            bookkeeper.cmd_delete(args)
        out = parse_json(capsys.readouterr().out)
        assert "error" in out

    def test_delete_output_is_valid_json(self, capsys):
        args = make_args(table="revenue", id=1)
        bookkeeper.cmd_delete(args)
        raw = capsys.readouterr().out.strip()
        json.loads(raw)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_all_expense_categories_accepted(self, capsys):
        for cat in bookkeeper.EXPENSE_CATEGORIES:
            bookkeeper.cmd_add_expense(make_args(
                category=cat, description=f"test {cat}", amount=1000, date="2026-01-01"
            ))
        capsys.readouterr()
        # If we get here without SystemExit, all categories are valid.

    def test_all_deduction_reasons_accepted(self, capsys):
        for reason in bookkeeper.DEDUCTION_REASONS:
            bookkeeper.cmd_add_deduction(make_args(
                reason=reason, description=f"test {reason}", amount=500, date="2026-01-01"
            ))
        capsys.readouterr()

    def test_zone_code_uppercased(self, capsys):
        args = make_args(count=1, zone="804c", unit_price=None)
        bookkeeper.cmd_add_revenue(args)
        out = parse_json(capsys.readouterr().out)
        assert out["zone"] == "804C"

    def test_add_zone_code_uppercased(self, capsys):
        args = make_args(
            code="abc1", name="Test", unit_price=800,
            streets=None, area_type=None,
            approx_units=None, district=None, note=None
        )
        bookkeeper.cmd_add_zone(args)
        out = parse_json(capsys.readouterr().out)
        assert out["code"] == "ABC1"

    def test_note_preserved(self, capsys):
        args = make_args(count=1, zone=None, unit_price=None, note="테스트 메모")
        bookkeeper.cmd_add_revenue(args)
        out = parse_json(capsys.readouterr().out)
        assert out["note"] == "테스트 메모"

    def test_fuel_type_always_lpg(self, capsys):
        args = make_args(price_per_liter=1000.0, liters=10.0)
        bookkeeper.cmd_add_fuel(args)
        out = parse_json(capsys.readouterr().out)
        assert out["fuel_type"] == "LPG"

    def test_constants_values(self):
        assert bookkeeper.LPG_SUBSIDY_PER_LITER == 173
        assert bookkeeper.DEFAULT_UNIT_PRICE == 1000


# ---------------------------------------------------------------------------
# Integration: full workflow
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_day_workflow(self, capsys):
        d = "2026-04-14"

        # Morning: add revenues
        bookkeeper.cmd_add_revenue(make_args(count=30, zone="804C", unit_price=None, date=d))
        bookkeeper.cmd_add_revenue(make_args(count=20, zone="804D", unit_price=None, date=d))

        # Fuel up
        bookkeeper.cmd_add_fuel(make_args(price_per_liter=1050.0, liters=45.0, date=d))

        # Expense
        bookkeeper.cmd_add_expense(make_args(category="toll", description="하이패스", amount=3400, date=d))

        # Deduction
        bookkeeper.cmd_add_deduction(make_args(reason="misdelivery", description="오배송 1건", amount=5000, date=d))

        capsys.readouterr()

        # Check daily summary
        bookkeeper.cmd_daily_summary(make_args(date=d))
        out = parse_json(capsys.readouterr().out)

        expected_rev = 30 * 1050 + 20 * 850  # 804C=1050, 804D=850
        assert out["revenue"]["gross_total"] == expected_rev
        assert out["revenue"]["delivery_count"] == 50
        assert out["deduction_total"] == 5000
        assert out["net_revenue"] == expected_rev - 5000

        fuel_total = round(1050 * 45)
        fuel_subsidy = round(173 * 45)
        assert out["fuel"]["total_cost"] == fuel_total
        assert out["fuel"]["subsidy"] == fuel_subsidy
        assert out["fuel"]["net_cost"] == fuel_total - fuel_subsidy

        assert out["expense_total"] == 3400

    def test_monthly_after_multiple_days(self, capsys):
        for day in range(1, 4):
            d = f"2026-02-{day:02d}"
            bookkeeper.cmd_add_revenue(make_args(count=10, zone=None, unit_price=None, date=d))
        capsys.readouterr()

        bookkeeper.cmd_monthly_summary(make_args(month="2026-02"))
        out = parse_json(capsys.readouterr().out)
        assert out["working_days"] == 3
        assert out["revenue"]["delivery_count"] == 30
