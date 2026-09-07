import Link from "next/link";
import {
  ArrowRight,
  Crosshair,
  ListOrdered,
  SlidersHorizontal,
  Users,
  History,
} from "lucide-react";

export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="hero-field" aria-hidden="true">
          <div />
          <span />
        </div>
        <div className="hero-copy">
          <p className="eyebrow hero-badge">
            <span className="live-dot" /> THE CRICKET STRATEGY GAME
          </p>
          <div className="hero-wordmark" aria-label="Chase 201">
            CHASE<span>201</span>
          </div>
          <h1>
            One chase.
            <br />
            Every decision counts.
          </h1>
          <p className="hero-description">
            Build your XI. Back your instincts.
            <br />
            Can you chase down 201?
          </p>
          <div className="hero-actions">
            <Link className="button primary" href="/play">
              Play Chase 201 <ArrowRight size={20} />
            </Link>
            <a className="button secondary" href="#how-to-play">
              How to play
            </a>
          </div>
          <p className="hero-footnote">
            Free to play · No account needed · Your pace
          </p>
          <div className="hero-facts" aria-label="The challenge">
            <div>
              <strong>11</strong>
              <span>YOUR PLAYERS</span>
            </div>
            <div>
              <strong>20</strong>
              <span>OVERS TO PLAY</span>
            </div>
            <div>
              <strong>201</strong>
              <span>RUNS TO WIN</span>
            </div>
          </div>
        </div>
      </section>
      <section className="home-hub" aria-label="Your game">
        <p className="eyebrow">TAKE THE CREASE</p>
        <div className="hub-grid">
          <Link className="hub-card" href="/play">
            <span className="hub-icon">
              <Crosshair size={23} />
            </span>
            <span>
              <strong>The 201 challenge</strong>
              <small>A fresh draft. One target. All yours.</small>
            </span>
            <ArrowRight size={18} />
          </Link>
          <Link className="hub-card" href="/history">
            <span className="hub-icon blue">
              <History size={23} />
            </span>
            <span>
              <strong>Your match history</strong>
              <small>Every innings has a story.</small>
            </span>
            <ArrowRight size={18} />
          </Link>
        </div>
      </section>
      <section className="how-section" id="how-to-play">
        <div className="section-heading">
          <div>
            <p className="eyebrow">FROM FIRST PICK TO LAST BALL</p>
            <h2>Four steps. One unforgettable chase.</h2>
          </div>
        </div>
        <div className="how-grid">
          {[
            {
              n: "01",
              icon: Users,
              title: "Draft your XI",
              text: "Pick one of five players for every spot. Five batters, a keeper, two all-rounders and three bowlers.",
            },
            {
              n: "02",
              icon: ListOrdered,
              title: "Set the order",
              text: "Choose your openers and your finishers. Put every player where you need them.",
            },
            {
              n: "03",
              icon: SlidersHorizontal,
              title: "Make the calls",
              text: "Defend, rotate or attack. Adjust your risk as the target gets closer and the pressure builds.",
            },
            {
              n: "04",
              icon: Crosshair,
              title: "Bring it home",
              text: "In the final two overs, you call every delivery. Get to 201 and make the chase yours.",
            },
          ].map(({ n, icon: Icon, title, text }) => (
            <article key={n}>
              <div className="how-top">
                <span>{n}</span>
                <Icon size={23} />
              </div>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="home-finish">
        <p className="eyebrow">THE TARGET IS SET</p>
        <h2>
          Your XI. Your decisions.
          <br />
          <span>Your moment.</span>
        </h2>
        <Link className="button primary" href="/play">
          Start your chase <ArrowRight size={18} />
        </Link>
      </section>
    </>
  );
}
