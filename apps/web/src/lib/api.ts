import createClient from "openapi-fetch";
import { z } from "zod";
import type { paths, components } from "./api.generated";

export type Session = components["schemas"]["SessionView"];
export type Draft = components["schemas"]["DraftView"];
export type Match =
  components["schemas"]["MatchView"] | components["schemas"]["SavedMatchView"];
export type Player = components["schemas"]["PlayerSummary"];
export type V2Strategy =
  components["schemas"]["V2StrategyDecision"]["strategy"];
export type Strategy = components["schemas"]["StrategyDecision"]["strategy"];
export type LegacyStrategy = Pick<
  components["schemas"]["LegacyStrategyDecision"],
  "intent" | "riskFocus"
>;
export const strategySchema = z.enum(["DEFENSIVE", "BALANCED", "AGGRESSIVE"]);
export const v2StrategySchema = z.enum([
  "PRESERVE",
  "ROTATE",
  "BALANCED",
  "ATTACK",
  "ALL_OUT",
]);
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class APIError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const client = createClient<paths>({
  baseUrl: API_URL,
  credentials: "include",
  // Retrying a lost response uses the very same request, revision, and idempotency key.
  fetch: async (request: Request) => {
    const retry = request.clone();
    try {
      return await fetch(request);
    } catch {
      return fetch(retry);
    }
  },
});

function unwrap<T>(result: {
  data?: T;
  error?: unknown;
  response: Response;
}): T {
  if (result.data !== undefined) return result.data;
  const detail = (result.error as { detail?: unknown })?.detail;
  throw new APIError(
    result.response.status,
    typeof detail === "string"
      ? detail
      : "That request could not be completed. Please try again.",
  );
}

const headers = (session: Session, key: string) => ({
  "x-csrf-token": session.csrfToken,
  "idempotency-key": key,
});

export const api = {
  session: async () => unwrap(await client.GET("/api/v1/session")),
  guest: async (s: Session, key = crypto.randomUUID()) =>
    unwrap(
      await client.POST("/api/v1/guest-sessions", {
        body: { expectedRevision: 0 },
        headers: headers(s, key),
      }),
    ),
  logout: async (s: Session) =>
    unwrap(
      await client.POST("/api/v1/auth/logout", {
        body: { expectedRevision: s.revision },
        headers: headers(s, crypto.randomUUID()),
      }),
    ),
  createDraft: async (s: Session, key = crypto.randomUUID()) =>
    unwrap(
      await client.POST("/api/v1/drafts", {
        body: { expectedRevision: s.revision },
        params: { header: headers(s, key) },
      }),
    ),
  draft: async (id: string) =>
    unwrap(
      await client.GET("/api/v1/drafts/{draft_id}", {
        params: { path: { draft_id: id } },
      }),
    ),
  select: async (
    s: Session,
    d: Draft,
    slot: string,
    player: string,
    key: string,
  ) =>
    unwrap(
      await client.PUT("/api/v1/drafts/{draft_id}/selections/{slot_id}", {
        params: {
          path: { draft_id: d.id, slot_id: slot },
          header: headers(s, key),
        },
        body: { expectedRevision: d.revision, playerId: player },
      }),
    ),
  order: async (s: Session, d: Draft, playerIds: string[], key: string) =>
    unwrap(
      await client.PUT("/api/v1/drafts/{draft_id}/batting-order", {
        params: { path: { draft_id: d.id }, header: headers(s, key) },
        body: { expectedRevision: d.revision, playerIds },
      }),
    ),
  confirm: async (s: Session, d: Draft, key: string) =>
    unwrap(
      await client.POST("/api/v1/drafts/{draft_id}/confirm", {
        params: { path: { draft_id: d.id }, header: headers(s, key) },
        body: { expectedRevision: d.revision },
      }),
    ),
  createMatch: async (s: Session, d: Draft, key: string) =>
    unwrap(
      await client.POST("/api/v1/matches", {
        body: { draftId: d.id, expectedRevision: d.revision },
        params: { header: headers(s, key) },
      }),
    ),
  match: async (id: string) =>
    unwrap(
      await client.GET("/api/v1/matches/{match_id}", {
        params: { path: { match_id: id } },
      }),
    ),
  decide: async (
    s: Session,
    m: Match,
    strategy: Strategy | V2Strategy | LegacyStrategy,
    key: string,
  ) =>
    unwrap(
      await client.POST("/api/v1/matches/{match_id}/decisions", {
        params: { path: { match_id: m.id }, header: headers(s, key) },
        body: {
          expectedRevision: m.revision,
          ...(typeof strategy === "string"
            ? {
                strategy: (m.rulesetVersion === "v3.0" ||
                m.rulesetVersion === "v3.1" ||
                m.rulesetVersion === "v3.2" ||
                m.rulesetVersion === "v3.3" ||
                m.rulesetVersion === "v3.4"
                  ? strategySchema
                  : v2StrategySchema
                ).parse(strategy),
              }
            : strategy),
        },
      }),
    ),
  history: async (offset = 0) =>
    unwrap(
      await client.GET("/api/v1/me/matches", {
        params: { query: { offset, limit: 20 } },
      }),
    ),
};

export const overs = (balls: number) => `${Math.floor(balls / 6)}.${balls % 6}`;
export const roleLabel: Record<string, string> = {
  BATTER: "Batter",
  WICKETKEEPER: "Wicketkeeper",
  ALL_ROUNDER: "All-rounder",
  BOWLER: "Bowler",
};
