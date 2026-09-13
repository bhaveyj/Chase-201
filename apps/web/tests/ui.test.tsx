import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { ErrorPanel, Steps } from "@/components/common";
import { APIError } from "@/lib/api";
import { useUI } from "@/lib/ui-store";
import { BattingPlans, LegacyPlans } from "@/components/batting-plans";
import type { Match } from "@/lib/api";

it("selects one plan and refreshes contextual bands without resetting the choice", async () => {
  const onChange = vi.fn();
  const assessments: Match["strategyAssessments"] = [
    {
      strategy: "ATTACK",
      scoring: "High",
      boundary: "High",
      wicketRisk: "Moderate",
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
  expect(screen.getAllByRole("radio")).toHaveLength(5);
  await userEvent.click(screen.getByRole("radio", { name: "Attack" }));
  expect(onChange).toHaveBeenCalledWith("ATTACK");
  rerender(
    <BattingPlans
      strategy="ATTACK"
      assessments={[{ ...assessments[0], wicketRisk: "None (free hit)" }]}
      disabled={false}
      onChange={onChange}
    />,
  );
  expect(screen.getByRole("radio", { name: "Attack" })).toBeChecked();
  expect(screen.getByText("None (free hit)")).toBeVisible();
  rerender(
    <BattingPlans
      strategy="ATTACK"
      assessments={assessments}
      disabled={true}
      onChange={onChange}
    />,
  );
  expect(screen.getByRole("radio", { name: "All-out Attack" })).toBeDisabled();
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
  useUI.getState().setStrategy("ATTACK");
  useUI.getState().editOrder("draft", ["a", "b"]);
  expect(useUI.getState().strategy).toBe("ATTACK");
  expect(useUI.getState()).not.toHaveProperty("match");
  expect(useUI.getState()).not.toHaveProperty("session");
  expect(localStorage.length).toBe(0);
});
