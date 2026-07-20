import type { Weights } from "./score";

export interface PillarMeta {
  key: keyof Weights;
  label: string;
  description: string;
}

// Single source of truth for pillar labels + descriptors, in display order.
// Used by the weight controls, the settings page, and the match score bars.
export const PILLARS: PillarMeta[] = [
  {
    key: "mandate",
    label: "Mandate",
    description: "Sector fit and size sweet-spot — is the company in the fund's box?",
  },
  {
    key: "strategy",
    label: "Strategy",
    description:
      "Deal-type fit — buyout, growth, turnaround or roll-up — given the company's ownership and stage.",
  },
  {
    key: "value_creation",
    label: "Value creation",
    description:
      "Does the fund bring what this company needs — capital, sector expertise, buy-and-build?",
  },
];
