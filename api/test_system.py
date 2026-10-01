"""Checks the behaviour the quiz promises. Run: .venv/bin/python -m unittest"""
import unittest

import db
import demos
import pipeline
import system


class SystemTest(unittest.TestCase):
    def setUp(self):  # system calls outside llm.session() use the replay model: no network in tests
        self.session = db.session()
        self.session.__enter__()

    def tearDown(self):
        self.session.__exit__(None, None, None)

    def test_guardrails_block_what_the_prompt_cannot(self):
        self.assertEqual(system.issue_refund("4519", 10_000, "x", "u_42")["status"], "blocked")  # over the total
        self.assertEqual(system.issue_refund("4530", 50, "x", "u_42")["status"], "blocked")  # someone else's order
        self.assertEqual(system.issue_refund("4519", 40, "x", "u_42")["status"], "issued")

    def test_agent_refunds_only_the_missing_item(self):
        reply = system.run_agent("My biryani from order #4519 was missing the raita. I want a refund.", "u_42")
        self.assertIn("₹40", reply)

    def test_agent_does_not_refund_food_still_on_the_way(self):
        reply = system.run_agent("Order #4521 was missing the garlic bread, refund please", "u_42")
        self.assertIn("on its way", reply)

    def test_rag_finds_the_refund_window(self):
        self.assertEqual(system.search_policy("Can I get a refund? I ordered 2 weeks ago.")[0]["id"], "4.2")

    def test_compaction_keeps_pinned_facts_and_cuts_tokens(self):
        chat = demos.long_chat()
        compacted = system.compact(chat)
        self.assertIn('"order_id": "4521"', compacted[0]["content"])
        self.assertIn("MG Road", compacted[0]["content"])
        self.assertLess(system.approx_tokens(compacted), system.approx_tokens(chat))

    def test_evals_pass_the_gate_with_one_known_failure(self):
        result = system.run_evals()
        self.assertTrue(result["ship"])
        self.assertEqual(len(result["failures"]), 1)


class PipelineTest(unittest.TestCase):
    def test_redaction_masks_pii_but_keeps_order_ids(self):
        text, found = pipeline.redact_text("order #4521, call 9876543210 or a.b@example.com, UPI rahul@okaxis, card 4111 1111 1111 1111")
        self.assertEqual(text, "order #4521, call [PHONE] or [EMAIL], UPI [UPI], card [CARD]")
        self.assertEqual(found, {"PHONE": 1, "EMAIL": 1, "UPI": 1, "CARD": 1})

    def test_clean_drops_empties_and_duplicates(self):
        base = {"ticket_id": "T-1", "created_at": "", "channel": "app", "text": " hi  there ", "first_response_min": 1, "resolved": True}
        chats, dropped = pipeline.clean([base, dict(base), {**base, "ticket_id": "T-2", "text": "  "}])
        self.assertEqual([c.text for c in chats], ["hi there"])
        self.assertEqual(dropped, {"duplicate": 1, "empty": 1})

    def test_requirements_cover_eighty_percent_without_other(self):
        reqs = system.analyze_chats()
        self.assertEqual(reqs["automate_first"], ["order_status", "refund", "address"])
        self.assertNotIn("Hand off to a human", reqs["functional"])


class DemoTest(unittest.TestCase):
    def test_every_level_traces_real_code(self):
        for level in range(len(demos.DEMOS)):
            run = demos.run(level, live=False)
            self.assertTrue(run["steps"], f"level {level} recorded no steps")
            for step in run["steps"]:
                self.assertIn(step["fn"], run["sources"], f"level {level}: no source for {step['fn']}")


if __name__ == "__main__":
    unittest.main()
