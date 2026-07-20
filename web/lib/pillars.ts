import type { Weights } from "./score";

// Default pillar weights, mirroring the backend DEFAULT_WEIGHTS in
// app/services/matching/score.py. Used as the initial client-side weighting.
export const DEFAULT_WEIGHTS: Weights = {
  mandate: 0.4,
  strategy: 0.35,
  value_creation: 0.25,
};

export interface PillarMeta {
  key: keyof Weights;
  label: string;
  // At-a-glance meaning of the pillar.
  description: string;
  // How the 0–100 score is actually derived — shown on hover.
  how: string;
}

// Single source of truth for pillar labels, descriptions and calculation notes,
// in display order. Used by the weight controls, the settings page, and the
// match score bars.
export const PILLARS: PillarMeta[] = [
  {
    key: "mandate",
    label: "Mandate",
    description: "Sector fit and size sweet-spot — is the company in the fund's box?",
    how: "Average of two 0–100 signals: how well the company's size sits in the fund's bands (EBITDA, revenue or check size, with rough estimates filled in where figures aren't disclosed), and the model's read on how central the company's sector is to the fund's thesis.",
  },
  {
    key: "strategy",
    label: "Strategy",
    description:
      "Deal-type fit — buyout, growth, turnaround or roll-up — given the company's ownership and stage.",
    how: "The model rates 0–100 how well the company's deal situation — ownership, deal stage and growth trajectory — matches the fund's playbook.",
  },
  {
    key: "value_creation",
    label: "Value creation",
    description:
      "Does the fund bring what this company needs — capital, sector expertise, buy-and-build?",
    how: "The model rates 0–100 how well the fund's capabilities serve this company's specific needs.",
  },
];
