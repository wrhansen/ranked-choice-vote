class RankedChoiceAlgorithm:
    label = ""

    def compute(self, votes, options):
        """
        votes:   list of rankings, each ranking is an ordered list of Option PKs
                 (index 0 = 1st choice)
        options: list of Option model instances for this poll

        Returns {"winner": Option, "summary": <algorithm-specific dict>}
        """
        raise NotImplementedError
