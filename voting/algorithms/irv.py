from .base import RankedChoiceAlgorithm


class IRVAlgorithm(RankedChoiceAlgorithm):
    label = "Instant Runoff Voting"

    def compute(self, votes, options):
        if not options:
            return {"winner": None, "summary": {"rounds": []}}

        if len(options) == 1:
            return {"winner": options[0], "summary": {"rounds": []}}

        option_map = {o.pk: o for o in options}
        original_order = [o.pk for o in options]
        remaining = list(original_order)
        rounds = []

        while len(remaining) > 1:
            tallies = {pk: 0 for pk in remaining}

            for vote in votes:
                for choice in vote:
                    pk = int(choice)
                    if pk in tallies:
                        tallies[pk] += 1
                        break

            total = sum(tallies.values())
            sorted_tallies = sorted(tallies.items(), key=lambda x: -x[1])

            majority_winner = next(
                (pk for pk, count in tallies.items() if total > 0 and count * 2 > total),
                None,
            )

            if majority_winner:
                rounds.append({
                    "tallies": [(option_map[pk], count) for pk, count in sorted_tallies],
                    "eliminated": None,
                })
                return {"winner": option_map[majority_winner], "summary": {"rounds": rounds}}

            # Eliminate the lowest vote-getter; tiebreak: last in original order
            min_count = min(tallies.values())
            last_place = [pk for pk, count in tallies.items() if count == min_count]
            eliminate_pk = max(last_place, key=lambda pk: original_order.index(pk))

            rounds.append({
                "tallies": [(option_map[pk], count) for pk, count in sorted_tallies],
                "eliminated": option_map[eliminate_pk],
            })
            remaining.remove(eliminate_pk)

        winner_pk = remaining[0]
        return {"winner": option_map[winner_pk], "summary": {"rounds": rounds}}
