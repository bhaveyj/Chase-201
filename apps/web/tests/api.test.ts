import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { api, APIError, API_URL, overs, strategySchema } from "@/lib/api";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("server state client", () => {
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
  it("formats legal balls and validates strategy values", () => {
    expect(overs(119)).toBe("19.5");
    expect(overs(120)).toBe("20.0");
    expect(
      strategySchema.safeParse({ intent: "ATTACK", riskFocus: "BALANCED" })
        .success,
    ).toBe(true);
    expect(
      strategySchema.safeParse({ intent: "CHEAT", riskFocus: "BALANCED" })
        .success,
    ).toBe(false);
  });
});
