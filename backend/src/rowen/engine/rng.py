"""Randomness that can be replayed: the same seed always gives the same match."""

import random
from dataclasses import dataclass, replace


@dataclass(frozen=True, kw_only=True)
class Rng:
    """The source of every random choice in a match (ADR 0003).

    Python's ``random.Random`` changes every time it is used, so it can't be
    kept in an immutable game state. An ``Rng`` stores only the seed and how
    many times it has been used. Each use builds a new generator from those two
    numbers, uses it once and throws it away, and returns the ``Rng`` to use
    next. Using the same ``Rng`` twice gives the same result twice, so always
    continue with the one that is returned.

    Python only promises that ``random()`` gives the same numbers in every
    version, not ``shuffle`` or ``randrange``. The project pins its Python
    version (``backend/.python-version``), so a match always replays the same.

    Attributes:
        seed: The match's seed. Whoever knows it can work out the order of
            every deck, so it must never be sent to a player.
        uses: How many times the randomness has been used so far.
    """

    seed: int
    uses: int = 0

    def shuffled[T](self, items: tuple[T, ...]) -> tuple[tuple[T, ...], Rng]:
        """Return the items in a random order, and the ``Rng`` to use next."""
        order = list(items)
        self._generator().shuffle(order)
        return tuple(order), self._next()

    def coin_flip(self) -> tuple[int, Rng]:
        """Return 0 or 1, with the same chance, and the ``Rng`` to use next."""
        return self._generator().randrange(2), self._next()

    def _generator(self) -> random.Random:
        # A text seed is hashed, so "7:0" and "7:1" give unrelated numbers and
        # every seed is different. With a number, -7 would give the same as 7.
        return random.Random(f"{self.seed}:{self.uses}")

    def _next(self) -> Rng:
        return replace(self, uses=self.uses + 1)
