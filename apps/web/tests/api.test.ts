import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { api, APIError, API_URL, mergeDecisionMatch, overs, strategySchema } from "@/lib/api";
import type { Match } from "@/lib/api";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("server state client", () => {
  it.each(["v3.0", "v3.1", "v3.2", "v3.3", "v3.4", "v3.5"] as const)(
    "routes %s through the three-mode contract",
    async (rulesetVersion) => {
      server.use(
        http.post(
          `${API_URL}/api/v1/matches/m/decisions`,
          async ({ request }) => {
            expect(await request.json()).toEqual({
              expectedRevision: 7,
              strategy: "AGGRESSIVE",
            });
            return HttpResponse.json({ id: "m", revision: 8, rulesetVersion });
          },
        ),
      );
      const session = {
        kind: "guest" as const,
        csrfToken: "csrf",
        revision: 0,
        googleEnabled: false,
      };
      const match = { id: "m", revision: 7, rulesetVersion } as Match;
      expect(
        (await api.decide(session, match, "AGGRESSIVE", "test-key")).revision,
      ).toBe(8);
      await expect(
        api.decide(session, match, "ATTACK", "test-key"),
      ).rejects.toThrow();
    },
  );
  it("retrieves sessions without browser storage", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/session`, () =>
        HttpResponse.json({
          kind: "guest",
          csrfToken: "token",
          revision: 0,
          googleEnabled: false,
        }),
      ),
    );
    expect((await api.session()).kind).toBe("guest");
    expect(localStorage.length).toBe(0);
  });
  it("sends the revision, credentials, csrf and idempotency key", async () => {
    server.use(
      http.post(`${API_URL}/api/v1/drafts`, async ({ request }) => {
        expect(request.credentials).toBe("include");
        expect(request.headers.get("x-csrf-token")).toBe("csrf");
        expect(request.headers.get("idempotency-key")).toBe("retry-key-201");
        expect(await request.json()).toEqual({ expectedRevision: 3 });
        return HttpResponse.json({
          id: "draft",
          revision: 0,
          slots: [],
          status: "DRAFTING",
          battingOrder: [],
          catalogVersion: "fictional-v1",
        });
      }),
    );
    const s = {
      kind: "guest" as const,
      csrfToken: "csrf",
      revision: 3,
      googleEnabled: false,
    };
    expect((await api.createDraft(s, "retry-key-201")).id).toBe("draft");
  });
  it("surfaces revision conflicts", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/drafts/x`, () =>
        HttpResponse.json({ detail: "State changed" }, { status: 409 }),
      ),
    );
    await expect(api.draft("x")).rejects.toEqual(
      new APIError(409, "State changed"),
    );
  });
  it("merges new decision events only into the preceding revision", () => {
    const previous = { revision: 2, events: [{ revision: 1 }, { revision: 2 }] } as Match;
    const next = { revision: 3, events: [{ revision: 3 }] } as Match;
    expect(mergeDecisionMatch(previous, next)?.events.map((event) => event.revision)).toEqual([
      1, 2, 3,
    ]);
    expect(mergeDecisionMatch(undefined, next)).toBeNull();
    expect(mergeDecisionMatch({ ...previous, revision: 1 }, next)).toBeNull();
    const fullResponse = { ...next, events: [...previous.events, ...next.events] } as Match;
    expect(mergeDecisionMatch(previous, fullResponse)?.events).toHaveLength(3);
  });
  it("formats legal balls and validates strategy values", () => {
    expect(overs(119)).toBe("19.5");
    expect(overs(120)).toBe("20.0");
    expect(strategySchema.safeParse("AGGRESSIVE").success).toBe(true);
    expect(strategySchema.safeParse("CHEAT").success).toBe(false);
    for (const old of ["PRESERVE", "ROTATE", "ATTACK", "ALL_OUT"])
      expect(strategySchema.safeParse(old).success).toBe(false);
  });
});
