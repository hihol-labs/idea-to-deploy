#!/usr/bin/env python3
"""Closed reviewer routing regression; no credentials or model transport."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("producer", ROOT / "skills/_shared/itd_free_reviewer_producer.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class CompatibilityTests(unittest.TestCase):
    def test_astra_maker_selects_only_terra_without_standby(self):
        for configured in ('gpt-6-astra', 'gpt-5.6-terra'):
            self.assertEqual('gpt-5.6-terra', p.select_openai_reviewer_model('gpt-6-astra', configured))
        for configured in ('gpt-6.1-sol', 'gpt-5.6-sol', 'unknown'):
            with self.subTest(configured=configured), self.assertRaises(p.FreeReviewError):
                p.select_openai_reviewer_model('gpt-6-astra', configured)
        self.assertEqual('', p.alternate_openai_reviewer_model('gpt-6-astra', 'gpt-5.6-terra'))

    def test_astra_provenance_is_preserved_and_astra_is_not_a_reviewer(self):
        maker = {'provider': 'openai', 'model': 'gpt-6-astra', 'session': 'actual-astra-maker'}
        reviewer = {'provider': 'openai-subscription', 'model': 'gpt-5.6-terra', 'session': 'fresh-terra'}
        original = dict(maker)
        p.require_opposite_openai_model(maker, reviewer)
        self.assertEqual(original, maker)
        for model in ('gpt-6-astra', 'gpt-6.1-sol', 'gpt-5.6-sol'):
            with self.subTest(model=model), self.assertRaises(p.FreeReviewError):
                p.require_opposite_openai_model(maker, dict(reviewer, model=model))
        with self.assertRaises(p.FreeReviewError):
            p.select_openai_reviewer_model('claude-opus-5', 'gpt-6-astra', maker_provider='anthropic-subscription')

    def test_approved_maker(self):
        for configured in ("gpt-6.1-sol", "gpt-5.6-terra"):
            with self.subTest(configured=configured):
                self.assertEqual(p.select_openai_reviewer_model("gpt-6.1-sol", configured), "gpt-5.6-terra")

    def test_observed_reviewer_identity(self):
        maker = {"provider": "openai", "model": "gpt-6.1-sol", "session": "maker"}
        reviewer = {"provider": "openai-subscription", "model": "gpt-5.6-terra", "session": "fresh"}
        p.require_opposite_openai_model(maker, reviewer)
        for model in ("gpt-6.1-sol", "gpt-5.6-sol", "gpt-6-astra"):
            with self.subTest(model=model), self.assertRaises(p.FreeReviewError):
                p.require_opposite_openai_model(maker, {**reviewer, "model": model})
        # REVIEWER-61SOL-1: gpt-6.1-sol reviews an Anthropic maker, and its degraded standby is gpt-5.6-terra
        p.require_opposite_openai_model({**maker, "provider": "anthropic-subscription", "model": "claude-opus-5"}, {**reviewer, "model": "gpt-6.1-sol"})
        p._reviewer_identity({**reviewer, "transportExecutableSha256": "a" * 64, "degradedFrom": "gpt-6.1-sol"})
        for origin in ("gpt-6-astra", "gpt-5.6-terra"):
            with self.subTest(origin=origin), self.assertRaises(p.FreeReviewError):
                p._reviewer_identity({**reviewer, "transportExecutableSha256": "a" * 64, "degradedFrom": origin})
        with self.assertRaises(p.FreeReviewError):
            p.require_opposite_openai_model({**maker, "provider": "anthropic-subscription", "model": "claude-opus-5"}, {**reviewer, "model": "gpt-6-astra"})

    def test_existing_pairs(self):
        for maker, reviewer in (("gpt-5.6-sol", "gpt-5.6-terra"), ("gpt-5.6-terra", "gpt-5.6-sol")):
            for configured in (maker, reviewer):
                self.assertEqual(p.select_openai_reviewer_model(maker, configured), reviewer)

    def test_refused_routes(self):
        for maker, configured, status in (("unknown", "gpt-5.6-terra", "UNAVAILABLE"), ("gpt-6.1-sol", "gpt-6-astra", "UNVERIFIED"), ("gpt-6.1-sol", "gpt-5.6-sol", "UNVERIFIED")):
            with self.subTest(maker=maker, configured=configured):
                with self.assertRaises(p.FreeReviewError) as caught:
                    p.select_openai_reviewer_model(maker, configured)
                self.assertEqual(caught.exception.status, status)

    def test_anthropic_route_reviewer_set(self):
        # REVIEWER-61SOL-1 (owner 2026-11-04): gpt-6.1-sol joins the cross-vendor reviewers; astra stays out
        for configured in ("gpt-6.1-sol", "gpt-5.6-sol", "gpt-5.6-terra"):
            self.assertEqual(p.select_openai_reviewer_model("claude-opus-5", configured, maker_provider="anthropic-subscription"), configured)
        for configured in ("gpt-6-astra", "unknown"):
            with self.subTest(configured=configured), self.assertRaises(p.FreeReviewError) as caught:
                p.select_openai_reviewer_model("claude-opus-5", configured, maker_provider="anthropic-subscription")
            self.assertEqual(caught.exception.status, "UNVERIFIED")

    def test_anthropic_route_standby(self):
        # the degraded standby of each cross-vendor reviewer is a different supported model
        for current, standby in (("gpt-6.1-sol", "gpt-5.6-terra"), ("gpt-5.6-sol", "gpt-5.6-terra"), ("gpt-5.6-terra", "gpt-5.6-sol")):
            with self.subTest(current=current):
                self.assertEqual(standby, p.alternate_openai_reviewer_model("claude-opus-5", current, maker_provider="anthropic-subscription"))
        self.assertEqual("", p.alternate_openai_reviewer_model("claude-opus-5", "gpt-6-astra", maker_provider="anthropic-subscription"))

    def test_default_reviewer_is_61_sol(self):
        sub = next(a for a in p.parser()._actions if a.__class__.__name__ == "_SubParsersAction")
        self.assertIsNone(sub.choices["review"].get_default("reviewer_model"))
        # no --reviewer-model: an Anthropic maker gets gpt-6.1-sol, an OpenAI maker its forced opposite model
        self.assertEqual("gpt-6.1-sol", p.default_reviewer_model("claude-opus-5", None, maker_provider="anthropic-subscription"))
        self.assertEqual("gpt-6.1-sol", p.select_openai_reviewer_model("claude-opus-5", p.default_reviewer_model("claude-opus-5", None, maker_provider="anthropic-subscription"), maker_provider="anthropic-subscription"))
        for maker, reviewer in (("gpt-5.6-sol", "gpt-5.6-terra"), ("gpt-5.6-terra", "gpt-5.6-sol"), ("gpt-6.1-sol", "gpt-5.6-terra")):
            with self.subTest(maker=maker):
                self.assertEqual(reviewer, p.select_openai_reviewer_model(maker, p.default_reviewer_model(maker, None, maker_provider="openai-codex"), maker_provider="openai-codex"))
        self.assertEqual("gpt-5.6-sol", p.default_reviewer_model("claude-opus-5", "gpt-5.6-sol", maker_provider="anthropic-subscription"))

if __name__ == "__main__":
    unittest.main()
