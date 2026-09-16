import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { ErrorPanel, Steps } from "@/components/common";
import { APIError } from "@/lib/api";
import { useUI } from "@/lib/ui-store";
import { BattingPlans, LegacyPlans } from "@/components/batting-plans";
import { V2Plans } from "@/components/v2-plans";
import type { Match } from "@/lib/api";
import {
  PlayerAttributes,
  attributeDescription,
} from "@/components/player-attributes";

it("retains five original plans for v2 saves", () => {
  render(
    <V2Plans
      strategy="ATTACK"
      assessments={[]}
      disabled={false}
      onChange={vi.fn()}
    />,
  );
  expect(screen.getAllByRole("radio")).toHaveLength(5);
  expect(screen.getByRole("radio", { name: "Attack" })).toBeChecked();
  expect(screen.queryByRole("radio", { name: "Aggressive" })).toBeNull();
});

it("selects one plan and refreshes contextual bands without resetting the choice", async () => {
  const onChange = vi.fn();
  const assessments: Match["strategyAssessments"] = [
    {
      strategy: "AGGRESSIVE",
      scoring: "High",
      boundary: "High",
      wicketRisk: "Moderate",
      wicketProbability: 0.071,
    },
  ];
  const { rerender } = render(
    <BattingPlans
      strategy="BALANCED"
      assessments={assessments}
      disabled={false}
      onChange={onChange}
    />,
  );
  expect(screen.getAllByRole("radio")).toHaveLength(3);
  await userEvent.click(screen.getByRole("radio", { name: "Aggressive" }));
  expect(onChange).toHaveBeenCalledWith("AGGRESSIVE");
  rerender(
    <BattingPlans
      strategy="AGGRESSIVE"
      assessments={[
        {
          ...assessments[0],
          wicketRisk: "None (free hit)",
          wicketProbability: 0,
        },
      ]}
      disabled={false}
      onChange={onChange}
    />,
  );
  expect(screen.getByRole("radio", { name: "Aggressive" })).toBeChecked();
  expect(screen.getByText("0% · None")).toBeVisible();
  rerender(
    <BattingPlans
      strategy="AGGRESSIVE"
      assessments={assessments}
      disabled={true}
      onChange={onChange}
    />,
  );
  expect(screen.getByRole("radio", { name: "Defensive" })).toBeDisabled();
});

it("formats exact next-delivery percentages and free-hit risk for all three modes", () => {
  const assessments: Match["strategyAssessments"] = [
    {
      strategy: "DEFENSIVE",
      scoring: "Low",
      boundary: "Low",
      wicketRisk: "Very low",
      wicketProbability: 0.01949,
    },
    {
      strategy: "BALANCED",
      scoring: "Moderate",
      boundary: "Moderate",
      wicketRisk: "Low",
      wicketProbability: 0.052,
    },
    {
      strategy: "AGGRESSIVE",
      scoring: "High",
      boundary: "High",
      wicketRisk: "High",
      wicketProbability: 0.1087,
    },
  ];
  const { container, rerender } = render(
    <BattingPlans
      strategy="BALANCED"
      assessments={assessments}
      disabled={false}
      onChange={vi.fn()}
    />,
  );
  const cards = container.querySelectorAll(".plan-card");
  expect(cards[0]).toHaveTextContent("Wicket risk: 1.9% · Very low");
  expect(cards[1]).toHaveTextContent("Wicket risk: 5.2% · Low");
  expect(cards[2]).toHaveTextContent("Wicket risk: 10.9% · High");
  rerender(
    <BattingPlans
      strategy="BALANCED"
      assessments={assessments.map((a) => ({
        ...a,
        wicketProbability: 0,
        wicketRisk: "None (free hit)",
      }))}
      disabled={false}
      onChange={vi.fn()}
    />,
  );
  expect(screen.getAllByText("0% · None")).toHaveLength(3);
});

it("shows one Batting bar for simple cards and preserves historical attributes", () => {
  const player = {
    id: "p",
    name: "Ari Vale",
    role: "BATTER" as const,
    overallRating: 90,
    battingRating: 86,
  };
  const { container, rerender } = render(<PlayerAttributes player={player} />);
  expect(screen.getByText("Batting")).toBeVisible();
  expect(container.querySelectorAll(".attribute-track")).toHaveLength(1);
  expect(container.querySelector("i")).toHaveStyle({ width: "86%" });
  expect(screen.queryByText("Anchor")).toBeNull();
  expect(screen.queryByText("Control")).toBeNull();
  expect(attributeDescription(player)).toBe(", Batting 86 out of 100");
  const historical = {
    ...player,
    battingPlaystyle: "Anchor" as const,
    battingControl: 90,
    battingRotation: 76,
    battingPower: 62,
  };
  rerender(<PlayerAttributes player={historical} />);
  expect(screen.getByText("Anchor")).toBeVisible();
  expect(container.querySelectorAll(".attribute-track")).toHaveLength(3);
  expect(screen.queryByText("Batting")).toBeNull();
  expect(attributeDescription(historical)).toContain(
    "Control 90, Rotation 76, Power 62",
  );
});

it("retains the original controls for saved matches", () => {
  render(
    <LegacyPlans
      strategy={{ intent: "ROTATE", riskFocus: "BALANCED" }}
      disabled={false}
      onChange={vi.fn()}
    />,
  );
  expect(screen.getByRole("radio", { name: "Rotate" })).toBeChecked();
  expect(screen.getByRole("radio", { name: "Balanced" })).toBeChecked();
  expect(screen.getAllByRole("radio")).toHaveLength(6);
});

it("provides recovery from an expired guest session", async () => {
  render(<ErrorPanel error={new APIError(401, "Your session has expired")} />);
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Your session has expired",
  );
  const recovery = screen.getByRole("link", { name: /Return to the lobby/ });
  await userEvent.tab();
  expect(recovery).toHaveFocus();
  expect(recovery).toHaveAttribute("href", "/play");
});
it("announces the current setup step", () => {
  render(<Steps current={1} />);
  expect(screen.getByText("Set the order")).toHaveAttribute(
    "aria-current",
    "step",
  );
});
it("keeps only transient edits in the UI store", () => {
  useUI.getState().setStrategy("AGGRESSIVE");
  useUI.getState().editOrder("draft", ["a", "b"]);
  expect(useUI.getState().strategy).toBe("AGGRESSIVE");
  expect(useUI.getState()).not.toHaveProperty("match");
  expect(useUI.getState()).not.toHaveProperty("session");
  expect(localStorage.length).toBe(0);
});
