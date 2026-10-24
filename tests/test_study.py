"""The tests are synthetic unit tests, not historical profit claims."""
import unittest
from decimal import Decimal
from arb_research.archive import date_from_event, strike, get, choose_groups
from arb_research.screen import study, taker_fee, candle


def market(ticker, threshold=20, *, name="Jane Doe", event="KXNBAPTS-26JAN20BOSNYK"):
    return {
        "series": "KXNBAPTS", "ticker": ticker,
        "market": {
            "ticker": ticker, "market_type": "binary",
            "event_ticker": event,
            "yes_sub_title": f"{name}: {threshold}+ points",
            "floor_strike": threshold - 0.5,
            "result": "no",
        },
    }


def quote(ticker, minute, bid, ask):
    return {
        "series": "KXNBAPTS", "ticker": ticker,
        "candle": {"end_period_ts": minute,
                   "yes_bid": {"close_dollars": str(bid)},
                   "yes_ask": {"close_dollars": str(ask)}},
    }


class HistoricalBacktest(unittest.TestCase):
    def setUp(self):
        self.markets = [market("L", 20), market("H", 30)]
        self.t = 1768910400

    def test_exact_time_fee_adjusted_candidate(self):
        data = [quote("L", self.t, .30, .35),
                quote("H", self.t, .40, .45)]
        res = study(self.markets, data, quantity=10)
        self.assertEqual(res["aligned_price_pair_checks"], 1)
        self.assertEqual(res["gross_positive_player_time_samples"], 1)
        self.assertEqual(res["illustratively_fee_positive_samples"], 1)
        self.assertAlmostEqual(res["candidates"][0]["illustrative_net_usd"], .17)
        self.assertIsNone(res["realized_profit_usd"])
        self.assertFalse(res["candidates"][0]["confirmed_executable_trade"])

    def test_order_size_changes_fee_rounding_not_fills(self):
        data = [quote("L", self.t, ".04", ".05"),
                quote("H", self.t, ".06", ".08")]
        at_one = study(self.markets, data, quantity=1)
        at_ten = study(self.markets, data, quantity=10)
        self.assertEqual(at_one["illustratively_fee_positive_samples"], 0)
        self.assertEqual(at_ten["illustratively_fee_positive_samples"], 1)
        self.assertEqual(at_ten["candidates"][0]["illustrative_net_usd"], .02)
        self.assertFalse(at_ten["historical_orderbook_depth_verified"])

    def test_stale_quote_cannot_match(self):
        data = [quote("L", self.t, .30, .35),
                quote("H", self.t + 60, .40, .45)]
        res = study(self.markets, data)
        self.assertEqual(res["aligned_price_pair_checks"], 0)
        self.assertEqual(res["gross_positive_player_time_samples"], 0)

    def test_one_per_timestamp_and_nonadjacent(self):
        middle = market("M", 25)
        data = [quote("L", self.t, .30, .35),
                quote("M", self.t, .36, .38),
                quote("H", self.t, .50, .55)]
        res = study(self.markets + [middle], data)
        self.assertEqual(res["aligned_price_pair_checks"], 3)
        self.assertEqual(res["gross_positive_player_time_samples"], 1)

    def test_different_player_not_paired(self):
        other = market("H", 30, name="Other Player")
        data = [quote("L", self.t, .30, .35),
                quote("H", self.t, .40, .45)]
        self.assertEqual(study([self.markets[0], other], data)["aligned_price_pair_checks"], 0)

    def test_fee_rounds_up_separately(self):
        self.assertEqual(taker_fee(Decimal("0.5"), 1), Decimal(".02"))

    def test_legacy_cents_are_parsed(self):
        self.assertEqual(
            candle({"end_period_ts": self.t,
                    "yes_bid": {"close": 40},
                    "yes_ask": {"close": 45}}),
            (self.t, Decimal(".4"), Decimal(".45")),
        )

    def test_wrong_market_type_or_bad_strike_is_excluded(self):
        item = self.markets[0]["market"].copy()
        item["market_type"] = "scalar"
        self.assertIsNone(strike(item))
        item["market_type"] = "binary"
        item["floor_strike"] = 100
        self.assertIsNone(strike(item))

    def test_no_portfolio_or_orders_endpoint(self):
        with self.assertRaises(ValueError):
            get("/portfolio/orders", {})
        with self.assertRaises(ValueError):
            get("/markets/L/orderbook", {})

    def test_event_date_parser(self):
        self.assertEqual(str(date_from_event("KXNBAPTS-26JAN20BOSNYK")), "2026-01-20")

    def test_ladder_group_is_not_split_by_cap(self):
        markets = {m["ticker"]: m["market"] for m in self.markets}
        groups, _ = choose_groups({"KXNBAPTS": list(markets.values())}, max_markets=1)
        self.assertEqual(groups, [])


if __name__ == "__main__":
    unittest.main()
