import json
import random
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy import func, select
from test_api import draft, guest, match, mutate

from chase201.catalog import (
    REAL_CATALOG_VERSION,
    CatalogImport,
    import_catalog,
    real_players,
    seed_real,
)
from chase201.config import Settings, get_settings
from chase201.draft_rules import REAL_SELECTION, ROLES, draft_offers, rating_band
from chase201.models import CatalogVersion, DraftOffer, Player, SimulationProfile


@pytest.fixture
async def real_catalog(database, monkeypatch):
    async with database() as db, db.begin():
        await seed_real(db)
    monkeypatch.setattr(get_settings(), "catalog_version", REAL_CATALOG_VERSION)


def test_default_catalog_is_real(monkeypatch):
    monkeypatch.delenv("CATALOG_VERSION", raising=False)
    assert Settings(_env_file=None).catalog_version == REAL_CATALOG_VERSION


def test_roster_preserves_every_supplied_identity_role_and_rating():
    supplied = json.loads((Path(__file__).parent / "fixtures/user-player-ratings.json").read_text())
    players = real_players()
    by_name = {p.name: p for p in players}
    assert len(players) == len(by_name) == len({p.id for p in players}) == 200
    assert len(supplied) == 141 and len({p["name"] for p in supplied}) == 139
    for row in supplied:
        assert (by_name[row["name"]].role, by_name[row["name"]].overallRating) == (
            row["role"],
            row["rating"],
        )
    assert Counter(p.role for p in players) == {
        "BATTER": 52,
        "WICKETKEEPER": 31,
        "ALL_ROUNDER": 55,
        "BOWLER": 62,
    }
    assert by_name["Jasprit Bumrah"].bowling_style == "PACE"
    assert by_name["Rashid Khan"].bowling_style == "SPIN"
    assert by_name["Sunil Narine"].bowling_style == "SPIN"


def test_all_200_players_are_reachable_in_unique_legal_offers():
    players = [Player(id=p.id, role=p.role, overall_rating=p.overallRating) for p in real_players()]
    seen = set()
    for seed in range(500):
        offers = draft_offers(players, random.Random(seed), REAL_SELECTION)
        assert len(offers) == 11 and all(len(group) == 5 for group in offers)
        assert len({p.id for group in offers for p in group}) == 55
        for position, group in enumerate(offers):
            band = rating_band(position, REAL_SELECTION)
            assert all(
                p.role == ROLES[position] and band.minimum <= p.overall_rating <= band.maximum
                for p in group
            )
            seen.update(p.id for p in group)
    assert seen == {p.id for p in players}


async def test_real_seed_is_idempotent_and_keeps_historical_catalogs(database, real_catalog):
    async with database() as db, db.begin():
        before = [
            (p.id, p.name, p.role, p.overall_rating)
            for p in (await db.scalars(select(Player).order_by(Player.id))).all()
        ]
        await seed_real(db)
        after = [
            (p.id, p.name, p.role, p.overall_rating)
            for p in (await db.scalars(select(Player).order_by(Player.id))).all()
        ]
        assert before == after
        assert await db.get(CatalogVersion, "fictional-v4") is not None
        version = await db.get(CatalogVersion, REAL_CATALOG_VERSION)
        assert version.selection_ruleset == REAL_SELECTION
        assert not version.approved
        assert (
            await db.scalar(
                select(func.count())
                .select_from(Player)
                .where(Player.catalog_id == REAL_CATALOG_VERSION)
            )
            == 200
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(SimulationProfile)
                .join(Player)
                .where(Player.catalog_id == REAL_CATALOG_VERSION)
            )
            == 200
        )


async def test_real_import_checks_role_tier_capacity_before_writing(database):
    async with database() as db, db.begin():
        data = CatalogImport(
            version="invalid-real-roster",
            source="test",
            license="test",
            selectionRuleset=REAL_SELECTION,
            players=[p.model_copy(update={"overallRating": 89}) for p in real_players()],
        )
        with pytest.raises(ValueError, match="five disjoint"):
            await import_catalog(db, data)
        assert await db.get(CatalogVersion, data.version) is None


async def test_real_draft_limits_and_private_profiles(client, real_catalog):
    view = await draft(client)
    assert view["catalogVersion"] == REAL_CATALOG_VERSION
    assert view["selectionRuleset"] == REAL_SELECTION
    for position, slot in enumerate(view["slots"]):
        band = rating_band(position, REAL_SELECTION)
        assert (slot["minimumRating"], slot["maximumRating"], slot["ratingLabel"]) == (
            band.minimum,
            band.maximum,
            band.label,
        )
        for player in slot["options"]:
            assert set(player) == {"id", "name", "role", "overallRating"}
            assert player["id"].startswith(f"{REAL_CATALOG_VERSION}:")
    # All supplied elite keepers and bowlers fit their specialist slots.
    assert rating_band(5, REAL_SELECTION).maximum == 100
    assert rating_band(8, REAL_SELECTION).maximum == 100


async def test_real_draft_rejects_a_star_in_a_core_slot(client, database, real_catalog):
    view = await draft(client)
    core = view["slots"][1]
    star_id = view["slots"][0]["options"][0]["id"]
    async with database() as db, db.begin():
        db.add(DraftOffer(slot_id=core["id"], player_id=star_id))
    response = await mutate(
        client,
        "PUT",
        f"/api/v1/drafts/{view['id']}/selections/{core['id']}",
        {"expectedRevision": view["revision"], "playerId": star_id},
    )
    assert response.status_code == 422 and "75–89" in response.json()["detail"]


async def test_real_xi_and_opponent_start_the_current_engine(client, real_catalog):
    view = await match(client)
    assert view["rulesetVersion"] == "v3.5"
    for side in ("team", "opponent"):
        assert len(view[side]) == 11
        assert all(p["id"].startswith(f"{REAL_CATALOG_VERSION}:") for p in view[side])
        assert Counter(p["role"] for p in view[side]) == Counter(ROLES)
        assert all(set(p) == {"id", "name", "role", "overallRating"} for p in view[side])


async def test_real_catalog_does_not_bypass_production_approval(client, real_catalog, monkeypatch):
    session = await guest(client)
    monkeypatch.setattr(get_settings(), "environment", "production")
    response = await mutate(
        client, "POST", "/api/v1/drafts", {"expectedRevision": session["revision"]}
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "The player catalog is not ready"
