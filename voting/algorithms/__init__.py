from .borda import BordaAlgorithm
from .condorcet import SchulzeAlgorithm
from .irv import IRVAlgorithm

ALGORITHMS = {
    "IRV": IRVAlgorithm,
    "BORDA": BordaAlgorithm,
    "CONDORCET": SchulzeAlgorithm,
}
