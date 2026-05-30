from .base import RankedChoiceAlgorithm


class SchulzeAlgorithm(RankedChoiceAlgorithm):
    label = "Condorcet (Schulze)"

    def compute(self, votes, options):
        if not options:
            return {"winner": None, "summary": {"options": [], "matrix": {}}}

        if len(options) == 1:
            return {"winner": options[0], "summary": {"options": list(options), "matrix": {}}}

        n = len(options)
        pks = [o.pk for o in options]
        option_map = {o.pk: o for o in options}
        pk_to_idx = {pk: i for i, pk in enumerate(pks)}

        # d[i][j] = number of voters who prefer option i over option j
        d = [[0] * n for _ in range(n)]

        for vote in votes:
            normalized = [int(pk) for pk in vote if int(pk) in pk_to_idx]
            ranked_set = set(normalized)

            for pos_a, pk_a in enumerate(normalized):
                for pk_b in normalized[pos_a + 1:]:
                    d[pk_to_idx[pk_a]][pk_to_idx[pk_b]] += 1

            # Ranked options are preferred over any unranked options
            for pk_a in normalized:
                for pk_b in pks:
                    if pk_b not in ranked_set:
                        d[pk_to_idx[pk_a]][pk_to_idx[pk_b]] += 1

        # Schulze: compute strongest paths via Floyd-Warshall
        # p[i][j] = strength of the strongest path from i to j
        p = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    p[i][j] = d[i][j] if d[i][j] > d[j][i] else 0

        for k in range(n):
            for i in range(n):
                if i == k:
                    continue
                for j in range(n):
                    if j == k or j == i:
                        continue
                    p[i][j] = max(p[i][j], min(p[i][k], p[k][j]))

        # Winner: candidate whose strongest path beats or ties all others
        # Tiebreak: first in original order
        winner_idx = next(
            (i for i in range(n) if all(p[i][j] >= p[j][i] for j in range(n) if j != i)),
            0,
        )

        matrix = {
            pk_i: {
                pk_j: {"prefer": d[i][j], "against": d[j][i]}
                for j, pk_j in enumerate(pks)
                if i != j
            }
            for i, pk_i in enumerate(pks)
        }

        return {
            "winner": option_map[pks[winner_idx]],
            "summary": {
                "options": [option_map[pk] for pk in pks],
                "matrix": matrix,
            },
        }
