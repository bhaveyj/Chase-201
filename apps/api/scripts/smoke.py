"""Production smoke: run explicitly after deployment; creates one guest draft and match."""

import argparse
import statistics
import uuid
from time import perf_counter

import httpx

from chase201.draft_rules import SIMPLE_SELECTIONS, rating_band


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument(
        "--strategy", choices=["DEFENSIVE", "BALANCED", "AGGRESSIVE"], default="BALANCED"
    )
    args = parser.parse_args()
    decision_timings: list[dict[str, float]] = []
    decision_wall_times: list[float] = []
    retries = 0
    with httpx.Client(base_url=args.api, headers={"Origin": args.origin}, timeout=30) as client:
        client.get("/health").raise_for_status()
        client.head("/health").raise_for_status()
        session = client.get("/api/v1/session").json()
        client.headers["X-CSRF-Token"] = session["csrfToken"]

        def write(method: str, path: str, body: dict) -> dict:
            nonlocal retries
            started = perf_counter()
            key = str(uuid.uuid4())
            for attempt in range(3):
                try:
                    response = client.request(
                        method, path, json=body, headers={"Idempotency-Key": key}
                    )
                except httpx.TransportError:
                    if attempt == 2:
                        raise
                    retries += 1
                    continue
                if response.status_code in {502, 503, 504} and attempt < 2:
                    retries += 1
                    continue
                break
            if path.endswith("/decisions"):
                decision_wall_times.append((perf_counter() - started) * 1000)
                timing_header = response.headers.get("Server-Timing", "")
                decision_timings.append(
                    {
                        name.strip(): float(duration)
                        for item in timing_header.split(",")
                        if ";dur=" in item
                        for name, duration in [item.split(";dur=", 1)]
                    }
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
        assert match["rulesetVersion"] == "v3.5"
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
                    "strategy": args.strategy,
                },
            )
        state = match["state"]
        assert state["status"] in {"WON", "LOST", "TIED"}
        assert state["approaches_used"] == [args.strategy]
        assert (state["runs"] >= match["target"]) == (state["status"] == "WON")
        assert (
            sum(b["runs"] for b in state["batting"]) + state["wides"] + state["no_balls"]
            == state["runs"]
        )
        print(
            f"Smoke passed: {match['rulesetVersion']} · {draft['catalogVersion']} · {args.strategy} · {match['id']} · {state['status']} · {state['runs']}/{state['wickets']}"
        )
        if decision_wall_times:
            metrics = sorted({name for sample in decision_timings for name in sample})
            summary = [
                f"wall median={statistics.median(decision_wall_times):.0f}ms max={max(decision_wall_times):.0f}ms"
            ]
            summary.extend(
                f"{name} median={statistics.median(sample[name] for sample in decision_timings if name in sample):.0f}ms"
                for name in metrics
            )
            print(
                f"Decision timings ({len(decision_wall_times)} requests, {retries} retries): "
                + ", ".join(summary)
            )


if __name__ == "__main__":
    main()
