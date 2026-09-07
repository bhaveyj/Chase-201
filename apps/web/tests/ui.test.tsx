import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { ErrorPanel, Steps } from "@/components/common";
import { APIError } from "@/lib/api";
import { useUI } from "@/lib/ui-store";

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
  useUI.getState().setStrategy({ intent: "ATTACK" });
  useUI.getState().editOrder("draft", ["a", "b"]);
  expect(useUI.getState().strategy.intent).toBe("ATTACK");
  expect(useUI.getState()).not.toHaveProperty("match");
  expect(useUI.getState()).not.toHaveProperty("session");
  expect(localStorage.length).toBe(0);
});
