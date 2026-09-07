"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <section className="page-width">
      <h1>A break in play.</h1>
      <p>
        Something went wrong loading this page. Your saved match is still on the
        server.
      </p>
      <button className="button primary" onClick={reset}>
        Try again
      </button>
    </section>
  );
}
