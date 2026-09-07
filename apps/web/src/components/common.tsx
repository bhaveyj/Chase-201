"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  CircleDot,
  LoaderCircle,
  LogOut,
} from "lucide-react";
import { api, APIError, API_URL } from "@/lib/api";

export function useSession() {
  return useQuery({ queryKey: ["session"], queryFn: api.session });
}

export function Header() {
  const path = usePathname();
  const router = useRouter();
  const { data: session } = useSession();
  const client = useQueryClient();
  const logout = useMutation({
    mutationFn: () => api.logout(session!),
    onSuccess: () => {
      client.clear();
      router.push("/play");
      router.refresh();
    },
  });
  return (
    <header className="header">
      <Link href="/" className="brand" aria-label="Chase 201 home">
        <span className="brand-icon">
          <CircleDot size={23} />
        </span>
        CHASE<span className="brand-number">201</span>
        <span className="edition">CRICKET, IN YOUR HANDS</span>
      </Link>
      <nav aria-label="Main navigation">
        <Link href="/play" aria-current={path === "/play" ? "page" : undefined}>
          Play
        </Link>
        <Link
          href="/history"
          aria-current={path === "/history" ? "page" : undefined}
        >
          Match history
        </Link>
        {session?.kind === "user" ? (
          <button
            className="icon-button"
            aria-label="Sign out"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
          >
            <LogOut size={18} />
          </button>
        ) : (
          <span className="guest-badge">
            <span /> Guest friendly
          </span>
        )}
      </nav>
      {logout.error && <span role="alert">Sign out failed. Try again.</span>}
    </header>
  );
}

export function Footer() {
  return (
    <footer>
      <Link href="/" className="footer-brand">
        CHASE 201
      </Link>
      <span>One target. A thousand ways to get there.</span>
      <span>20 OVERS · YOUR CALL</span>
    </footer>
  );
}

export function Loading({
  label = "Getting the field ready…",
}: {
  label?: string;
}) {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={28} />
      <p>{label}</p>
    </div>
  );
}

export function ErrorPanel({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  const expired = error instanceof APIError && error.status === 401;
  return (
    <div role="alert" className="error-panel">
      <strong>
        {expired
          ? "Let’s get you back in the game."
          : "That didn’t go through."}
      </strong>
      <p>{error instanceof Error ? error.message : "Please try again."}</p>
      {expired ? (
        <Link className="text-link" href="/play">
          Return to the lobby <ArrowRight size={16} />
        </Link>
      ) : (
        retry && (
          <button className="text-link" onClick={retry}>
            Try again <ArrowRight size={16} />
          </button>
        )
      )}
    </div>
  );
}

export function GoogleLink({
  label = "Continue with Google",
}: {
  label?: string;
}) {
  const { data } = useSession();
  return data?.googleEnabled ? (
    <a
      className="button secondary"
      href={`${API_URL}/api/v1/auth/google/start`}
    >
      <span className="google-g">G</span>
      {label}
      <ArrowUpRight size={18} />
    </a>
  ) : (
    <p className="subtle">
      Google sign-in will be available when configured. You can play as a guest
      now.
    </p>
  );
}

export function Steps({ current }: { current: number }) {
  return (
    <ol className="steps" aria-label="Match setup">
      {["Draft your XI", "Set the order", "Chase 201"].map((step, i) => (
        <li
          key={step}
          className={current === i ? "current" : current > i ? "done" : ""}
          aria-current={current === i ? "step" : undefined}
        >
          <span>{current > i ? "✓" : `0${i + 1}`}</span>
          {step}
        </li>
      ))}
    </ol>
  );
}
