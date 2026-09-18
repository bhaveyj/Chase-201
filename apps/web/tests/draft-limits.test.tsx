import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { DraftLimits } from "@/components/draft-limits";
import type { Draft } from "@/lib/api";

function draft(real: boolean): Draft {
  const roles = [
    "BATTER",
    "BATTER",
    "BATTER",
    "BATTER",
    "BATTER",
    "WICKETKEEPER",
    "ALL_ROUNDER",
    "ALL_ROUNDER",
    "BOWLER",
    "BOWLER",
    "BOWLER",
  ];
  return {
    id: "draft",
    revision: 0,
    status: "DRAFTING",
    battingOrder: [],
    catalogVersion: real ? "real-players-v2" : "fictional-v4",
    selectionRuleset: real ? "real-players-v1" : "simple-v1",
    slots: roles.map((role, position) => {
      const star = position === 0 || position === 6;
      const specialist = real && (role === "WICKETKEEPER" || role === "BOWLER");
      return {
        id: String(position),
        role,
        position,
        options: [],
        selectedPlayerId: null,
        ratingLabel: star
          ? "Star player"
          : specialist
            ? "Specialist"
            : "Core player",
        minimumRating: star ? 90 : real ? 75 : 78,
        maximumRating: real ? (star || specialist ? 100 : 89) : star ? 92 : 85,
      };
    }),
  };
}

it("shows real-player limits and counts core and specialist selections separately", () => {
  const view = draft(true);
  const { rerender } = render(<DraftLimits draft={view} />);
  expect(screen.getByLabelText("XI rating limits")).toHaveTextContent(
    "One batter and one all-rounder rated 90–100. Five core players rated 75–89. A keeper and three bowlers rated 75–100.",
  );
  expect(screen.getByText("Core players")).toHaveTextContent("0/5");
  expect(screen.getByText("Specialists")).toHaveTextContent("0/4");
  view.slots.forEach((slot) => {
    slot.selectedPlayerId = `player-${slot.id}`;
  });
  rerender(<DraftLimits draft={view} />);
  expect(screen.getByText("Core players")).toHaveTextContent("5/5");
  expect(screen.getByText("Specialists")).toHaveTextContent("4/4");
});

it("preserves the limits displayed for saved fictional drafts", () => {
  render(<DraftLimits draft={draft(false)} />);
  expect(screen.getByLabelText("XI rating limits")).toHaveTextContent(
    "One batter and one all-rounder rated 90–92. Nine players rated 78–85.",
  );
  expect(screen.getByText("Core players")).toHaveTextContent("0/9");
  expect(screen.queryByText("Specialists")).toBeNull();
});
