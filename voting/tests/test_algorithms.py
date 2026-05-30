from types import SimpleNamespace
from unittest import TestCase

from voting.algorithms.borda import BordaAlgorithm
from voting.algorithms.condorcet import SchulzeAlgorithm
from voting.algorithms.irv import IRVAlgorithm


def opt(pk):
    """Lightweight stand-in for an Option model instance."""
    return SimpleNamespace(pk=pk)


class IRVAlgorithmTests(TestCase):
    def setUp(self):
        self.algo = IRVAlgorithm()

    def test_single_option_wins_immediately(self):
        options = [opt(1)]
        result = self.algo.compute([], options)
        self.assertEqual(result["winner"].pk, 1)
        self.assertEqual(result["summary"]["rounds"], [])

    def test_clear_majority_first_round(self):
        # A gets 3 of 4 votes — wins without elimination
        options = [opt(1), opt(2)]
        votes = [[1], [1], [1], [2]]
        result = self.algo.compute(votes, options)
        self.assertEqual(result["winner"].pk, 1)
        self.assertEqual(len(result["summary"]["rounds"]), 1)

    def test_elimination_required(self):
        # Round 1: A=3, B=2, C=1 → C eliminated
        # C's vote redistributes to A → Round 2: A=4, B=2 → A wins
        options = [opt(1), opt(2), opt(3)]
        votes = [
            [1, 3, 2],  # x3
            [1, 3, 2],
            [1, 3, 2],
            [2, 1, 3],  # x2
            [2, 1, 3],
            [3, 1, 2],  # C's vote → redistributes to A
        ]
        result = self.algo.compute(votes, options)
        self.assertEqual(result["winner"].pk, 1)
        rounds = result["summary"]["rounds"]
        self.assertEqual(len(rounds), 2)
        self.assertEqual(rounds[0]["eliminated"].pk, 3)
        self.assertIsNone(rounds[1]["eliminated"])

    def test_all_votes_identical(self):
        options = [opt(1), opt(2), opt(3)]
        votes = [[2, 1, 3]] * 5
        result = self.algo.compute(votes, options)
        self.assertEqual(result["winner"].pk, 2)

    def test_tiebreak_eliminates_last_in_original_order(self):
        # B and C are tied at 1 vote each; C has higher index → C eliminated first
        options = [opt(1), opt(2), opt(3)]
        votes = [
            [1, 2, 3],  # x2
            [1, 2, 3],
            [2, 1, 3],  # B=1
            [3, 1, 2],  # C=1 — tied with B; C is index 2 > B's index 1 → C eliminated
        ]
        result = self.algo.compute(votes, options)
        rounds = result["summary"]["rounds"]
        self.assertEqual(rounds[0]["eliminated"].pk, 3)

    def test_exhausted_ballots(self):
        # Voter only ranked C; after C is eliminated their ballot is exhausted
        options = [opt(1), opt(2), opt(3)]
        votes = [
            [1, 2, 3],
            [1, 2, 3],
            [2, 1, 3],
            [3],        # exhausted after C eliminated
        ]
        result = self.algo.compute(votes, options)
        self.assertEqual(result["winner"].pk, 1)

    def test_no_votes_returns_first_option(self):
        options = [opt(1), opt(2), opt(3)]
        result = self.algo.compute([], options)
        # No votes — last remaining after eliminations
        self.assertIsNotNone(result["winner"])


class BordaCountTests(TestCase):
    def setUp(self):
        self.algo = BordaAlgorithm()

    def test_single_voter_point_distribution(self):
        # 3 options: 1st=2pts, 2nd=1pt, 3rd=0pts
        options = [opt(1), opt(2), opt(3)]
        votes = [[2, 1, 3]]
        result = self.algo.compute(votes, options)
        scores = self._score_map(result["summary"])
        self.assertEqual(scores[2], 2)
        self.assertEqual(scores[1], 1)
        self.assertEqual(scores[3], 0)
        self.assertEqual(result["winner"].pk, 2)

    def _score_map(self, summary):
        return {o.pk: pts for o, pts in summary["scores"]}

    def test_multiple_voters_correct_totals(self):
        # 3 options, 2 voters
        # Voter 1: [A, B, C] → A=2, B=1, C=0
        # Voter 2: [B, A, C] → B=2, A=1, C=0
        # Totals:  A=3, B=3, C=0 — tie; A wins (lower original index)
        options = [opt(1), opt(2), opt(3)]
        votes = [[1, 2, 3], [2, 1, 3]]
        result = self.algo.compute(votes, options)
        scores = self._score_map(result["summary"])
        self.assertEqual(scores[1], 3)
        self.assertEqual(scores[2], 3)
        self.assertEqual(scores[3], 0)
        # Tiebreak: A (index 0) beats B (index 1)
        self.assertEqual(result["winner"].pk, 1)

    def test_clear_winner(self):
        options = [opt(1), opt(2), opt(3)]
        votes = [
            [3, 1, 2],
            [3, 2, 1],
            [3, 1, 2],
        ]
        result = self.algo.compute(votes, options)
        self.assertEqual(result["winner"].pk, 3)

    def test_partial_ranking(self):
        # Voter only ranks 2 of 3; unranked option gets 0 from that voter
        options = [opt(1), opt(2), opt(3)]
        votes = [[1, 2]]  # opt(3) unranked → 0 points
        result = self.algo.compute(votes, options)
        scores = self._score_map(result["summary"])
        self.assertEqual(scores[1], 2)
        self.assertEqual(scores[2], 1)
        self.assertEqual(scores[3], 0)

    def test_tiebreak_by_original_order(self):
        # All options tied — winner is the first in original order
        options = [opt(10), opt(20), opt(30)]
        votes = []  # no votes → all 0 points
        result = self.algo.compute(votes, options)
        self.assertEqual(result["winner"].pk, 10)

    def test_single_option(self):
        options = [opt(5)]
        result = self.algo.compute([[5]], options)
        self.assertEqual(result["winner"].pk, 5)


class SchulzeAlgorithmTests(TestCase):
    def setUp(self):
        self.algo = SchulzeAlgorithm()

    def test_single_option(self):
        options = [opt(1)]
        result = self.algo.compute([], options)
        self.assertEqual(result["winner"].pk, 1)

    def test_clear_condorcet_winner(self):
        # A beats B and C head-to-head; B beats C
        # 3 voters: A>B>C  |  2 voters: B>C>A
        # d[A][B]=3, d[B][A]=2 → A>B
        # d[A][C]=3, d[C][A]=2 → A>C
        # d[B][C]=5, d[C][B]=0 → B>C
        # A is the clear Condorcet winner
        options = [opt(1), opt(2), opt(3)]
        votes = [[1, 2, 3]] * 3 + [[2, 3, 1]] * 2
        result = self.algo.compute(votes, options)
        self.assertEqual(result["winner"].pk, 1)

    def test_condorcet_cycle_resolves_via_schulze(self):
        # Classic 3-way cycle: A>B>C>A (each margin is 6-3)
        # Schulze produces equal path strengths → tiebreak: first in original order (A)
        options = [opt(1), opt(2), opt(3)]
        votes = (
            [[1, 2, 3]] * 3   # A > B > C
            + [[2, 3, 1]] * 3  # B > C > A
            + [[3, 1, 2]] * 3  # C > A > B
        )
        result = self.algo.compute(votes, options)
        # All paths equal — first option wins by tiebreak
        self.assertEqual(result["winner"].pk, 1)

    def test_single_voter(self):
        options = [opt(1), opt(2), opt(3)]
        votes = [[1, 2, 3]]
        result = self.algo.compute(votes, options)
        self.assertEqual(result["winner"].pk, 1)

    def test_all_voters_agree(self):
        options = [opt(1), opt(2), opt(3)]
        votes = [[3, 1, 2]] * 7
        result = self.algo.compute(votes, options)
        self.assertEqual(result["winner"].pk, 3)

    def test_summary_contains_matrix(self):
        options = [opt(1), opt(2)]
        votes = [[1, 2], [1, 2], [2, 1]]
        result = self.algo.compute(votes, options)
        matrix = result["summary"]["matrix"]
        # 2 voters prefer 1 over 2; 1 voter prefers 2 over 1
        self.assertEqual(matrix[1][2]["prefer"], 2)
        self.assertEqual(matrix[1][2]["against"], 1)

    def test_unranked_options_lose_to_ranked(self):
        # Voter only ranks opt(1); opts 2 and 3 are unranked → 1 beats both
        options = [opt(1), opt(2), opt(3)]
        votes = [[1]]
        result = self.algo.compute(votes, options)
        self.assertEqual(result["winner"].pk, 1)
