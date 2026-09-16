"use client";

import { Check, CircleDot, Shield, TrendingUp, Zap } from "lucide-react";
import type { Match, V2Strategy as Strategy } from "@/lib/api";

const plans = [
  {
    value: "PRESERVE",
    title: "Preserve",
    description: "Settle in. Protect your wicket.",
    icon: Shield,
  },
  {
    value: "ROTATE",
    title: "Rotate",
    description: "Find singles, twos and threes.",
    icon: TrendingUp,
  },
  {
    value: "BALANCED",
    title: "Balanced",
    description: "Play the ball on its merits.",
    icon: CircleDot,
  },
  {
    value: "ATTACK",
    title: "Attack",
    description: "Seek boundaries. Accept the risk.",
    icon: Zap,
  },
  {
    value: "ALL_OUT",
    title: "All-out Attack",
    description: "Swing big. Risk a collapse.",
    icon: Zap,
  },
] as const;

export function V2Plans({
  strategy,
  assessments,
  disabled,
  onChange,
}: {
  strategy: Strategy;
  assessments: Match["strategyAssessments"];
  disabled: boolean;
  onChange: (value: Strategy) => void;
}) {
  return (
    <fieldset disabled={disabled}>
      <legend>Batting plan</legend>
      <div className="plan-grid legacy-plan-grid">
        {plans.map(({ value, title, description, icon: Icon }) => {
          const assessment = assessments?.find(
            (item) => item.strategy === value,
          );
          return (
            <label
              key={value}
              className={`plan-card ${strategy === value ? "selected" : ""}`}
            >
              <input
                type="radio"
                name="strategy"
                value={value}
                aria-label={title}
                checked={strategy === value}
                onChange={() => onChange(value)}
              />
              <div className="plan-title">
                <Icon size={20} />
                <strong>{title}</strong>
                {strategy === value && (
                  <Check
                    className="plan-selected"
                    size={14}
                    aria-hidden="true"
                  />
                )}
              </div>
              <span className="plan-description">{description}</span>
              {assessment && (
                <dl className="plan-bands">
                  <div>
                    <dt>Scoring</dt>
                    <dd>{assessment.scoring}</dd>
                  </div>
                  <div>
                    <dt>Boundaries</dt>
                    <dd>{assessment.boundary}</dd>
                  </div>
                  <div>
                    <dt>Wicket risk</dt>
                    <dd>{assessment.wicketRisk}</dd>
                  </div>
                </dl>
              )}
            </label>
          );
        })}
      </div>
      <p className="plan-context-note">
        These bands describe the next delivery against the current bowler. They
        update as the chase changes.
      </p>
    </fieldset>
  );
}
