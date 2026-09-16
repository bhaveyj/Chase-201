import argparse
import asyncio
import json
import random
from collections import Counter
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chase201.draft_rules import ROLES, SIMPLE_SELECTION, draft_offers
from chase201.models import CatalogVersion, Player, SimulationProfile
from chase201.profile_defaults import expanded_profile
from chase201.tradeoffs import TRADEOFF_SELECTION, DraftProfile, allocate

COMPOSITION = Counter(ROLES)


class ImportPlayer(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,50}$")
    name: str = Field(min_length=1, max_length=100)
    role: str
    overallRating: int = Field(ge=1, le=100)
    batting: float = Field(ge=1, le=100)
    bowling: float = Field(ge=1, le=100)
    batting_control: float | None = Field(default=None, ge=1, le=100)
    batting_rotation: float | None = Field(default=None, ge=1, le=100)
    batting_power: float | None = Field(default=None, ge=1, le=100)
    bowling_control: float | None = Field(default=None, ge=1, le=100)
    bowling_threat: float | None = Field(default=None, ge=1, le=100)
    bowling_style: Literal["PACE", "SPIN"] | None = None


class CatalogImport(BaseModel):
    version: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    source: str = Field(min_length=1, max_length=1000)
    license: str = Field(min_length=1, max_length=1000)
    approved: bool = False
    players: list[ImportPlayer]
    selectionRuleset: Literal["open-v1", "tradeoffs-v1", "simple-v1"] = "tradeoffs-v1"


async def import_catalog(db: AsyncSession, data: CatalogImport) -> None:
    if await db.get(CatalogVersion, data.version):
        raise ValueError("Catalog versions are immutable; choose a new version")
    ids = [p.id for p in data.players]
    counts = Counter(p.role for p in data.players)
    if len(ids) != len(set(ids)) or set(counts) != set(COMPOSITION):
        raise ValueError("Catalog requires unique IDs and exactly the four supported roles")
    # Disjoint offers make a complete XI possible regardless of earlier picks.
    if any(counts[role] < required * 5 for role, required in COMPOSITION.items()):
        raise ValueError(
            "Catalog needs at least 25 batters, 5 keepers, 10 all-rounders, 15 bowlers"
        )
    allocation: list[list[str]] = []
    if data.selectionRuleset == SIMPLE_SELECTION:
        # Validate role/tier capacity before writing any catalog rows.
        draft_offers(
            [Player(id=p.id, role=p.role, overall_rating=p.overallRating) for p in data.players],
            random.Random(0),
        )
    if data.selectionRuleset == TRADEOFF_SELECTION:
        if any(
            any(
                getattr(p, key) is None
                for key in ("batting_control", "batting_rotation", "batting_power")
            )
            for p in data.players
        ):
            raise ValueError(
                "Tradeoff catalogs require explicit Control, Rotation and Power profiles"
            )
        allocation = allocate(
            [
                DraftProfile(
                    f"{data.version}:{p.id}",
                    p.role,
                    p.overallRating,
                    (
                        cast(float, p.batting_control),
                        cast(float, p.batting_rotation),
                        cast(float, p.batting_power),
                    ),
                )
                for p in data.players
            ]
        )
    db.add(
        CatalogVersion(
            id=data.version,
            source=data.source,
            license=data.license,
            approved=data.approved,
            selection_ruleset=data.selectionRuleset,
            offer_allocation=allocation,
        )
    )
    await db.flush()
    for p in data.players:
        db.add(
            Player(
                id=f"{data.version}:{p.id}",
                catalog_id=data.version,
                name=p.name,
                role=p.role,
                overall_rating=p.overallRating,
            )
        )
    await db.flush()
    for p in data.players:
        attributes = expanded_profile(f"{data.version}:{p.id}", p.batting, p.bowling)
        attributes.update(
            {key: getattr(p, key) for key in attributes if getattr(p, key) is not None}
        )
        db.add(
            SimulationProfile(
                player_id=f"{data.version}:{p.id}",
                batting=p.batting,
                bowling=p.bowling,
                **attributes,
            )
        )


async def seed_fictional(db: AsyncSession) -> None:
    for version, players in (
        ("fictional-v1", fictional_players()),
        ("fictional-v2", balanced_fictional_players()),
        ("fictional-v3", tradeoff_fictional_players()),
        ("fictional-v4", simple_fictional_players()),
    ):
        if not await db.get(CatalogVersion, version):
            await import_catalog(
                db,
                CatalogImport(
                    version=version,
                    selectionRuleset=(
                        "simple-v1"
                        if version == "fictional-v4"
                        else "tradeoffs-v1"
                        if version == "fictional-v3"
                        else "open-v1"
                    ),
                    source="Original fictional development identities",
                    license="Project-owned fictional fixture. Not real players.",
                    players=players,
                ),
            )


def fictional_players() -> list[ImportPlayer]:
    rng = random.Random(201)
    first = [
        "Ari",
        "Dev",
        "Finn",
        "Ilan",
        "Jai",
        "Kian",
        "Leo",
        "Milo",
        "Nico",
        "Oren",
        "Ravi",
        "Sami",
        "Tavi",
        "Zev",
        "Remy",
    ]
    last = ["Ashford", "Vale", "Rowan", "Mercer", "Linden", "Hale", "Wren", "Corin"]
    players = []
    for i, role in enumerate(role for role, n in COMPOSITION.items() for _ in range(n * 5 + 5)):
        rating = rng.randint(68, 92)
        players.append(
            ImportPlayer(
                id=f"p{i:03}",
                name=f"{first[i % len(first)]} {last[i // len(first)]}",
                role=role,
                overallRating=rating,
                batting=rating if role != "BOWLER" else rating * 0.57,
                bowling=rating
                if role == "BOWLER"
                else rating * (0.90 if role == "ALL_ROUNDER" else 0.35),
            )
        )
    return players


def balanced_fictional_players() -> list[ImportPlayer]:
    """A new immutable catalog; old ratings/profiles remain available for saved games."""
    counts: Counter[str] = Counter()
    players = []
    for p in fictional_players():
        index = counts[p.role]
        counts[p.role] += 1
        star = p.role in {"BATTER", "ALL_ROUNDER"} and index < 5
        rating = 90 + index % 3 if star else 78 + (index * 3) % 8
        players.append(
            p.model_copy(
                update={
                    "overallRating": rating,
                    "batting": rating if p.role != "BOWLER" else rating * 0.57,
                    "bowling": rating
                    if p.role == "BOWLER"
                    else rating * (0.90 if p.role == "ALL_ROUNDER" else 0.35),
                }
            )
        )
    return players


def tradeoff_fictional_players() -> list[ImportPlayer]:
    """Role/tier owns the total; specialization redistributes that fixed budget.

    OVR includes role skills and is deliberately not a batting-attribute multiplier.
    Cohort tilts preserve the total and give every profile a visible weakness.
    """
    counts: Counter[str] = Counter()
    offsets = ((18, -2, -16), (14, 3, -17), (-12, 22, -10), (-16, -4, 20), (-10, -8, 18))
    result = []
    for p in balanced_fictional_players():
        index = counts[p.role]
        counts[p.role] += 1
        star = p.overallRating >= 90
        base = {"BATTER": 72, "WICKETKEEPER": 70, "ALL_ROUNDER": 69, "BOWLER": 44}[p.role] + (
            6 if star else 0
        )
        tilt = max(0, index // 5 - (1 if p.role in {"BATTER", "ALL_ROUNDER"} else 0))
        c, r, power = offsets[index % 5]
        attributes = (base + c + tilt, base + r - tilt, base + power)
        result.append(
            p.model_copy(
                update={
                    "batting": float(base),
                    "batting_control": float(attributes[0]),
                    "batting_rotation": float(attributes[1]),
                    "batting_power": float(attributes[2]),
                    "bowling_control": p.bowling,
                    "bowling_threat": p.bowling,
                    "bowling_style": "PACE" if index % 2 else "SPIN",
                }
            )
        )
    return result


def simple_fictional_players() -> list[ImportPlayer]:
    """New immutable batting ratings; OVR and all bowling inputs stay unchanged."""
    counts: Counter[tuple[str, bool]] = Counter()
    result = []
    for player in tradeoff_fictional_players():
        star = player.overallRating >= 90
        cohort = (player.role, star)
        base = {"BATTER": 80, "WICKETKEEPER": 78, "ALL_ROUNDER": 77, "BOWLER": 44}[player.role]
        batting = base + (6 if star else 0) + (-3, -1, 0, 1, 3)[counts[cohort] % 5]
        counts[cohort] += 1
        result.append(
            player.model_copy(
                update={
                    "batting": float(batting),
                    # Legacy storage columns have no archetypes and are never read by v3.1.
                    "batting_control": float(batting),
                    "batting_rotation": float(batting),
                    "batting_power": float(batting),
                }
            )
        )
    return result


async def main() -> None:
    from chase201.db import SessionFactory

    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()
    async with SessionFactory() as db, db.begin():
        if args.file:
            await import_catalog(
                db, CatalogImport.model_validate(json.loads(args.file.read_text()))
            )
        else:
            await seed_fictional(db)
        versions = (await db.scalars(select(CatalogVersion.id))).all()
        print(f"Available catalogs: {', '.join(versions)}")


if __name__ == "__main__":
    asyncio.run(main())
