"""Production smoke: run explicitly after deployment; creates one guest draft and match."""

import argparse
import uuid

import httpx

from chase201.draft_rules import SIMPLE_SELECTIONS, rating_band


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    with httpx.Client(base_url=args.api, headers={"Origin": args.origin}, timeout=30) as client:
        client.get("/health").raise_for_status()
        session = client.get("/api/v1/session").json()
        client.headers["X-CSRF-Token"] = session["csrfToken"]

        def write(method: str, path: str, body: dict) -> dict:
            response = client.request(
                method, path, json=body, headers={"Idempotency-Key": str(uuid.uuid4())}
            )
            response.raise_for_status()
            return response.json()

        session = write("POST", "/api/v1/guest-sessions", {"expectedRevision": 0})
        client.headers["X-CSRF-Token"] = session["csrfToken"]
        draft = write("POST", "/api/v1/drafts", {"expectedRevision": session["revision"]})
        assert draft["selectionRuleset"] in SIMPLE_SELECTIONS
        assert len(draft["slots"]) == 11
        assert len({p["id"] for s in draft["slots"] for p in s["options"]}) == 55
        for position, slot in enumerate(draft["slots"]):
            band = rating_band(position, draft["selectionRuleset"])
            minimum, maximum = band.minimum, band.maximum
            assert len(slot["options"]) == 5
            assert all(minimum <= p["overallRating"] <= maximum for p in slot["options"])
            for player in slot["options"]:
                assert (
                    not {
                        "battingRating",
                        "battingPlaystyle",
                        "battingControl",
                        "battingRotation",
                        "battingPower",
                    }
                    & player.keys()
                )
        for slot in draft["slots"]:
            draft = write(
                "PUT",
                f"/api/v1/drafts/{draft['id']}/selections/{slot['id']}",
                {"expectedRevision": draft["revision"], "playerId": slot["options"][0]["id"]},
            )
        draft = write(
            "PUT",
            f"/api/v1/drafts/{draft['id']}/batting-order",
            {
                "expectedRevision": draft["revision"],
                "playerIds": [s["selectedPlayerId"] for s in draft["slots"]],
            },
        )
        draft = write(
            "POST", f"/api/v1/drafts/{draft['id']}/confirm", {"expectedRevision": draft["revision"]}
        )
        match = write(
            "POST",
            "/api/v1/matches",
            {"draftId": draft["id"], "expectedRevision": draft["revision"]},
        )
        assert match["rulesetVersion"] == "v3.4"
        for _ in range(100):
            if match["state"]["status"] != "LIVE":
                break
            assert [a["strategy"] for a in match["strategyAssessments"]] == [
                "DEFENSIVE",
                "BALANCED",
                "AGGRESSIVE",
            ]
            risks = [a["wicketProbability"] for a in match["strategyAssessments"]]
            if match["state"]["free_hit"]:
                assert risks == [0, 0, 0]
            else:
                assert 0 < risks[0] < risks[1] < risks[2] < 1
            match = write(
                "POST",
                f"/api/v1/matches/{match['id']}/decisions",
                {
                    "expectedRevision": match["revision"],
                    "strategy": "BALANCED",
                },
            )
        state = match["state"]
        assert state["status"] in {"LOST", "TIED"}
        assert state["runs"] <= 200
        assert state["approaches_used"] == ["BALANCED"]
        assert state["runs"] < match["target"]
        assert (
            sum(b["runs"] for b in state["batting"]) + state["wides"] + state["no_balls"]
            == state["runs"]
        )
        print(
            f"Smoke passed: {draft['catalogVersion']} · {match['id']} · {state['status']} · {state['runs']}/{state['wickets']}"
        )


if __name__ == "__main__":
    main()
