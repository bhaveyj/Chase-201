"use client";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ShieldCheck, Timer, Users } from "lucide-react";
import { api } from "@/lib/api";
import { useUI } from "@/lib/ui-store";
import { ErrorPanel, GoogleLink, useSession } from "./common";
import { Pitch } from "./pitch";

export function Lobby({ authStatus }: { authStatus?: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useSession();
  const start = useMutation({
    mutationFn: async () => {
      let s = await queryClient.fetchQuery({
        queryKey: ["session"],
        queryFn: api.session,
        staleTime: 0,
      });
      if (s.kind === "anonymous") s = await api.guest(s);
      queryClient.setQueryData(["session"], s);
      const draft = await api.createDraft(s);
      useUI.getState().setActiveSlot(0);
      queryClient.setQueryData(["draft", draft.id], draft);
      await queryClient.invalidateQueries({ queryKey: ["session"] });
      router.push(`/draft/${draft.id}`);
    },
  });
  return (
    <section className="lobby page-width">
      <div>
        <p className="eyebrow">THE PAVILION</p>
        <h1>
          Ready,
          <br />
          <em>captain?</em>
        </h1>
        <p className="lead">
          A fresh XI. A target of 201.
          <br />
          Let’s see what you’re made of.
        </p>
        <div className="lobby-facts">
          <p>
            <Users size={18} /> Draft your team before every chase
          </p>
          <p>
            <Timer size={18} /> Play at your own pace
          </p>
          <p>
            <ShieldCheck size={18} /> Guest matches kept for 30 days
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => start.mutate()}
          disabled={start.isPending}
        >
          {start.isPending
            ? "Preparing your draft…"
            : session.data?.kind === "user"
              ? "Start a new chase"
              : "Play as guest"}
          <ArrowRight size={20} />
        </button>
        {(session.data?.activeMatchId || session.data?.activeDraftId) && (
          <p style={{ marginTop: 14 }}>
            <Link
              className="text-link"
              href={
                session.data.activeMatchId
                  ? `/match/${session.data.activeMatchId}`
                  : `/draft/${session.data.activeDraftId}`
              }
            >
              {session.data.activeMatchId
                ? "Resume your chase"
                : "Continue your draft"}
              <ArrowRight size={16} />
            </Link>
          </p>
        )}
        {authStatus && (
          <p className="subtle" role="status" style={{ marginTop: 16 }}>
            {authStatus === "cancelled"
              ? "Sign-in cancelled. Your guest game is still here."
              : "Google sign-in could not be completed. Try again or keep playing as a guest."}
          </p>
        )}
        <div className="sign-in-block">
          <p>Keep your cricket story.</p>
          <GoogleLink />
          <span className="subtle">
            Signing in saves this browser’s guest matches to your history.
          </span>
        </div>
        {start.error && (
          <ErrorPanel error={start.error} retry={() => start.mutate()} />
        )}
      </div>
      <div className="lobby-stage">
        <Pitch />
        <div className="lobby-score">
          <span>THE CHALLENGE</span>
          <strong>
            201 <small>to win</small>
          </strong>
          <p>120 legal balls. You’re in charge.</p>
        </div>
      </div>
    </section>
  );
}
