"""Complete, immutable offer allocations. No fallback to dominated draft choices."""

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from random import Random

from chase201.draft_rules import ROLES, rating_band

TRADEOFF_SELECTION = "tradeoffs-v1"
PLAYSTYLES = ("Anchor", "Rotator", "Hitter")


def playstyle(attributes: tuple[float, float, float]) -> str:
    return PLAYSTYLES[max(range(3), key=lambda i: attributes[i])]


@dataclass(frozen=True)
class DraftProfile:
    id: str
    role: str
    overall_rating: int
    attributes: tuple[float, float, float]


def valid_offer(players: list[DraftProfile]) -> bool:
    return (
        len(players) == 5
        and len({p.id for p in players}) == 5
        and {playstyle(p.attributes) for p in players} == set(PLAYSTYLES)
        and all(max(p.attributes) - min(p.attributes) >= 12 for p in players)
        and all(
            not all(a <= b for a, b in zip(p.attributes, q.attributes, strict=True))
            for p in players
            for q in players
            if p.id != q.id
        )
    )


def validate_allocation(catalog: list[DraftProfile], allocation: list[list[str]]) -> None:
    by_id = {p.id: p for p in catalog}
    ids = [i for group in allocation for i in group]
    if len(by_id) != len(catalog) or len(allocation) != 11 or len(ids) != len(set(ids)):
        raise ValueError("Catalog needs eleven disjoint five-player tradeoff offers")
    for position, group in enumerate(allocation):
        band = rating_band(position)
        if any(i not in by_id for i in group):
            raise ValueError("Offer references a missing catalog profile")
        players = [by_id[i] for i in group]
        if not valid_offer(players) or any(
            p.role != ROLES[position] or not band.minimum <= p.overall_rating <= band.maximum
            for p in players
        ):
            raise ValueError(f"Invalid tradeoffs, playstyles or rating band in slot {position + 1}")


def allocate(catalog: list[DraftProfile]) -> list[list[str]]:
    return [list(group) for group in _allocate(tuple(catalog))]


@lru_cache(maxsize=8)
def _allocate(catalog: tuple[DraftProfile, ...]) -> tuple[tuple[str, ...], ...]:
    """Exact search per role/tier; backtracks across slots instead of relaxing requirements.

    Slots sharing a role/tier are interchangeable. Increasing combination indices remove
    permutations of the same partition, while memoized failures avoid repeated subproblems.
    Unused catalog players are allowed, but every selectable path yields a legal XI.
    """
    allocation: list[list[str]] = [[] for _ in ROLES]
    groups: dict[tuple[str, int, int], list[int]] = {}
    for position, role in enumerate(ROLES):
        band = rating_band(position)
        groups.setdefault((role, band.minimum, band.maximum), []).append(position)
    for (role, lo, hi), slots in groups.items():
        pool = sorted(
            [p for p in catalog if p.role == role and lo <= p.overall_rating <= hi],
            key=lambda p: p.id,
        )
        candidates: list[tuple[int, tuple[int, ...]]] = []
        for indices in combinations(range(len(pool)), 5):
            if valid_offer([pool[i] for i in indices]):
                candidates.append((sum(1 << i for i in indices), indices))
        failed: set[tuple[int, int, int]] = set()

        def search(
            start: int,
            used: int,
            count: int,
            pool: list[DraftProfile] = pool,
            candidates: list[tuple[int, tuple[int, ...]]] = candidates,
            failed: set[tuple[int, int, int]] = failed,
        ) -> list[tuple[int, ...]] | None:
            if count == 0:
                return []
            key = (start, used, count)
            if key in failed or len(pool) - used.bit_count() < count * 5:
                return None
            for index in range(start, len(candidates)):
                mask, indices = candidates[index]
                if not mask & used:
                    rest = search(index + 1, used | mask, count - 1)
                    if rest is not None:
                        return [indices, *rest]
            failed.add(key)
            return None

        solution = search(0, 0, len(slots))
        if solution is None:
            raise ValueError(f"No complete disjoint tradeoff allocation for {role} rated {lo}–{hi}")
        for position, chosen in zip(slots, solution, strict=True):
            allocation[position] = [pool[i].id for i in chosen]
    validate_allocation(list(catalog), allocation)
    return tuple(tuple(group) for group in allocation)


def shuffled_allocation(allocation: list[list[str]], rng: Random) -> list[list[str]]:
    result = [list(group) for group in allocation]
    for role in dict.fromkeys(ROLES):
        for minimum in (78, 90):
            positions = [
                i for i, r in enumerate(ROLES) if r == role and rating_band(i).minimum == minimum
            ]
            groups = [result[i] for i in positions]
            rng.shuffle(groups)
            for i, group in zip(positions, groups, strict=True):
                rng.shuffle(group)
                result[i] = group
    return result
