import Link from "next/link";
export default function NotFound() {
  return (
    <section className="page-width">
      <p className="eyebrow">OUTSIDE THE BOUNDARY</p>
      <h1>Nothing to field here.</h1>
      <Link className="button primary" href="/play">
        Return to the pavilion
      </Link>
    </section>
  );
}
