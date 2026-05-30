from .base import RankedChoiceAlgorithm


class BordaAlgorithm(RankedChoiceAlgorithm):
    label = "Borda Count"

    def compute(self, votes, options):
        if not options:
            return {"winner": None, "summary": {"scores": []}}

        n = len(options)
        scores = {o.pk: 0 for o in options}
        original_order = [o.pk for o in options]

        for vote in votes:
            normalized = [int(pk) for pk in vote if int(pk) in scores]
            for rank, pk in enumerate(normalized):
                # Points: 1st place gets n-1, 2nd gets n-2, …, last gets 0
                scores[pk] += n - 1 - rank

        sorted_options = sorted(
            options,
            key=lambda o: (-scores[o.pk], original_order.index(o.pk)),
        )

        return {
            "winner": sorted_options[0],
            "summary": {"scores": [(o, scores[o.pk]) for o in sorted_options]},
        }
