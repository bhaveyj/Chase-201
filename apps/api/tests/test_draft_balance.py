import random
from collections import Counter

import pytest
from sqlalchemy import select
from test_api import draft, filled_draft, mutate

from chase201.catalog import balanced_fictional_players
from chase201.config import get_settings
from chase201.draft_rules import draft_offers, rating_band
from chase201.models import Draft, DraftOffer, Idempotency, Player


def test_rating_bands_always_offer_a_complete_unique_xi():
    catalog = [
        Player(id=p.id, role=p.role, overall_rating=p.overallRating)
        for p in balanced_fictional_players()
    ]
    for seed in range(100):
        offers = draft_offers(catalog, random.Random(seed))
        assert len(offers) == 11 and all(len(pool) == 5 for pool in offers)
        assert len({p.id for pool in offers for p in pool}) == 55
        for position, pool in enumerate(offers):
            band = rating_band(position)
            assert all(band.minimum <= p.overall_rating <= band.maximum for p in pool)
        strongest = [max(pool, key=lambda p: p.overall_rating) for pool in offers]
        assert Counter(p.role for p in strongest if p.overall_rating > 85) == {
            "BATTER": 1,
            "ALL_ROUNDER": 1,
        }
        assert sum(p.overall_rating for p in strongest) <= 2 * 92 + 9 * 85


async def test_draft_exposes_rating_limits_without_private_attributes(client):
    d = await draft(client)
    assert d["selectionRuleset"] == "balanced-v1"
    for position, slot in enumerate(d["slots"]):
        band = rating_band(position)
        assert (slot["minimumRating"], slot["maximumRating"], slot["ratingLabel"]) == (
            band.minimum,
            band.maximum,
            band.label,
        )
        assert all(band.minimum <= p["overallRating"] <= band.maximum for p in slot["options"])


async def test_insufficient_rated_catalog_fails_without_partial_draft(
    client, database, monkeypatch
):
    from test_api import guest

    s = await guest(client)
    monkeypatch.setattr(get_settings(), "catalog_version", "fictional-v1")
    response = await mutate(client, "POST", "/api/v1/drafts", {"expectedRevision": s["revision"]})
    assert (
        response.status_code == 503 and "Catalog needs five disjoint" in response.json()["detail"]
    )
    async with database() as db:
        assert await db.scalar(select(Draft)) is None
    assert (await client.get("/api/v1/session")).json()["revision"] == s["revision"]


async def test_cannot_select_a_second_star_even_if_an_offer_is_inserted(client, database):
    d = await draft(client)
    core = d["slots"][1]
    star = d["slots"][0]["options"][0]["id"]
    async with database() as db, db.begin():
        db.add(DraftOffer(slot_id=core["id"], player_id=star))
    response = await mutate(
        client,
        "PUT",
        f"/api/v1/drafts/{d['id']}/selections/{core['id']}",
        {"expectedRevision": d["revision"], "playerId": star},
    )
    assert response.status_code == 422 and "78–85" in response.json()["detail"]
    assert (await client.get(f"/api/v1/drafts/{d['id']}")).json()["revision"] == d["revision"]


@pytest.mark.parametrize("stage", ["order", "confirm", "match"])
async def test_rating_caps_rechecked_at_each_team_boundary(client, database, stage):
    d = await filled_draft(client)
    order = [s["selectedPlayerId"] for s in d["slots"]]
    if stage != "order":
        response = await mutate(
            client,
            "PUT",
            f"/api/v1/drafts/{d['id']}/batting-order",
            {"expectedRevision": d["revision"], "playerIds": order[::-1]},
        )
        assert response.status_code == 200  # Stars may bat anywhere.
        d = response.json()
    if stage == "match":
        response = await mutate(
            client, "POST", f"/api/v1/drafts/{d['id']}/confirm", {"expectedRevision": d["revision"]}
        )
        assert response.status_code == 200
        d = response.json()
    async with database() as db, db.begin():
        player = await db.get(Player, order[1])
        player.overall_rating = 90
    if stage == "order":
        response = await mutate(
            client,
            "PUT",
            f"/api/v1/drafts/{d['id']}/batting-order",
            {"expectedRevision": d["revision"], "playerIds": order},
        )
    elif stage == "confirm":
        response = await mutate(
            client, "POST", f"/api/v1/drafts/{d['id']}/confirm", {"expectedRevision": d["revision"]}
        )
    else:
        response = await mutate(
            client,
            "POST",
            "/api/v1/matches",
            {"draftId": d["id"], "expectedRevision": d["revision"]},
        )
    assert response.status_code == 422 and "78–85" in response.json()["detail"]


async def test_saved_open_draft_keeps_its_original_selection_rules(client, database):
    d = await draft(client)
    core = d["slots"][1]
    player_id = core["options"][0]["id"]
    async with database() as db, db.begin():
        saved = await db.get(Draft, d["id"])
        saved.selection_ruleset = "open-v1"
        player = await db.get(Player, player_id)
        player.overall_rating = 94
    response = await mutate(
        client,
        "PUT",
        f"/api/v1/drafts/{d['id']}/selections/{core['id']}",
        {"expectedRevision": d["revision"], "playerId": player_id},
    )
    assert response.status_code == 200
    assert response.json()["selectionRuleset"] == "open-v1"
    assert response.json()["slots"][1]["maximumRating"] == 100


async def test_pre_update_draft_receipts_can_still_be_retried(client, database):
    import copy

    d = await draft(client)
    slot = d["slots"][0]
    path = f"/api/v1/drafts/{d['id']}/selections/{slot['id']}"
    body = {"expectedRevision": d["revision"], "playerId": slot["options"][0]["id"]}
    original = await mutate(client, "PUT", path, body, "old-draft-receipt")
    assert original.status_code == 200
    async with database() as db, db.begin():
        receipt = await db.scalar(select(Idempotency).where(Idempotency.key == "old-draft-receipt"))
        saved = copy.deepcopy(receipt.response)
        saved.pop("selectionRuleset")
        for row in saved["slots"]:
            for field in ("ratingLabel", "minimumRating", "maximumRating"):
                row.pop(field)
        receipt.response = saved
    response = await mutate(client, "PUT", path, body, "old-draft-receipt")
    assert response.status_code == 200
    assert response.json()["selectionRuleset"] == "open-v1"
    assert response.json()["revision"] == original.json()["revision"]
