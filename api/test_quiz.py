"""Server quiz rules: same cases as web/lib/quiz.test.ts, plus clients sending junk."""
import unittest

from quiz import QuizState, reduce

# Two levels: the right answer is B on level 0 and A on level 1.
LEVELS = [
    {"options": [{"fail": ["boom"]}, {"correct": True}]},
    {"options": [{"correct": True}, {"fail": ["boom"]}]},
]


def play(*actions):
    state = QuizState()
    for action in actions:
        state = reduce(state, action, LEVELS)
    return state


class QuizTest(unittest.TestCase):
    def test_a_wrong_pick_fails_and_retry_only_accepts_the_right_answer(self):
        s = play({"type": "pick", "option": 0})
        self.assertEqual(s, QuizState(lvl=0, phase="fail", picked=0, streak=0))
        s = reduce(s, {"type": "retry"}, LEVELS)
        self.assertEqual(reduce(s, {"type": "pick", "option": 0}, LEVELS), s)
        s = reduce(s, {"type": "pick", "option": 1}, LEVELS)
        self.assertEqual((s.phase, s.streak), ("run", 0))

    def test_first_try_answers_build_the_streak(self):
        s = play({"type": "pick", "option": 1}, {"type": "learn"}, {"type": "next"}, {"type": "pick", "option": 0})
        self.assertEqual(s, QuizState(lvl=1, phase="run", picked=-1, streak=2))

    def test_next_is_a_no_op_on_the_last_level_and_before_learn(self):
        self.assertEqual(play({"type": "next"}).lvl, 0)
        last = play({"type": "pick", "option": 1}, {"type": "learn"}, {"type": "next"}, {"type": "pick", "option": 0}, {"type": "learn"})
        self.assertEqual(reduce(last, {"type": "next"}, LEVELS), last)

    def test_junk_from_a_client_changes_nothing(self):
        for junk in ({}, {"type": "hack"}, {"type": "pick"}, {"type": "pick", "option": 99}, {"type": "pick", "option": "1"}):
            self.assertEqual(reduce(QuizState(), junk, LEVELS), QuizState(), junk)

    def test_reset_starts_over(self):
        self.assertEqual(play({"type": "pick", "option": 0}, {"type": "reset"}), QuizState())


if __name__ == "__main__":
    unittest.main()
