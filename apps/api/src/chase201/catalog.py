import argparse
import asyncio
import json
import random
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chase201.draft_rules import ROLES
from chase201.models import CatalogVersion, Player, SimulationProfile
from chase201.profile_defaults import expanded_profile

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
    db.add(
        CatalogVersion(
            id=data.version, source=data.source, license=data.license, approved=data.approved
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
    ):
        if not await db.get(CatalogVersion, version):
            await import_catalog(
                db,
                CatalogImport(
                    version=version,
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
