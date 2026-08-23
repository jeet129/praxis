# Design tooling — the fallback chain (free-first)

Companion to `frontend-design/SKILL.md`. Design tools raise the quality
ceiling; this skill's text-only discipline is the floor that works on every
harness with zero dependencies. Use the highest tier available to the
project; never hard-depend on any of them.

## The chain

| Tier | Tool | Cost | What it gives the factory |
|---|---|---|---|
| 1 | **Official Figma MCP** (Dev Mode) | Figma Dev seat (~$12–15/mo) or Full seat; free Starter is ~6 MCP calls/month — not usable | Design context as source of truth: variables, components, auto-layout; canvas write-back (beta). Highest fidelity for design→code |
| 2a | **Community Figma context MCP** (e.g. Framelink Figma-Context-MCP) | Free — uses a personal access token on the free Figma plan | Layout/style/component extraction from files you own; no Dev Mode extras, no write-back |
| 2b | **Penpot** (open-source design tool) + community MCP | Free, self-hostable | Full design tool ownership; smaller ecosystem, rougher MCP maturity |
| 3 | **Generation tools** — Google Stitch (free), v0 / Magic Patterns (free tiers with credits) | Free tiers workable for a few screens per slice | Generate 2–3 professional screen candidates in the UX phase; human picks direction at the UX gate; chosen design becomes the FE reference. Magic Patterns honors an uploaded design system |
| 4 | **Component baseline** — shadcn/ui + Radix with a token-driven theme (tweakcn-style); daisyUI / Park UI / HeroUI as alternatives | Free | Professionally designed primitives as the composition floor; the token theme is what prevents the default look |
| 5 | **This skill, text-only** | Free | The two-pass plan + anti-generic critique + quality floor. Always on, every harness |

Paid upgrades worth considering when budget exists: Figma Dev seat (tier 1),
Tailwind Plus / Untitled UI for the component baseline.

## Verification/screenshot tooling (pairs with any tier)

- **Playwright** (or Playwright MCP where the harness supports it): capture
  implemented screens at 2–3 viewports including empty/loading/error states;
  screenshots become gate evidence for the visual-review pass and the input
  to this skill's self-critique loop.
- **Storybook** (free): per-component states, the natural screenshot target.
- Screenshot diffing (Playwright snapshots) once a look is approved — turns
  visual REGRESSIONS into a machine-verifiable check usable in task `verify`
  commands and drive mode.

## How the tiers plug into the workflow

- **UX phase (Phase B):** tier 1/2 — ux-designer reads (or writes) real
  designs and extracts tokens. Tier 3 — generate candidates, gate on human
  choice. All tiers — emit/extend `design-tokens.json` as the contract
  artifact FE tasks depend on.
- **Implementation:** frontend/mobile developer consumes the design
  reference (frame, export, or plan) + tokens; tier 4 provides the
  primitives; tier 5 governs every choice the reference doesn't pin.
- **Review:** screenshots + the design plan are the evidence; the reviewer
  scores against `design-craft.md`'s calibration and the brief.

## Selection

`delivery-planner` characterization: when `has_frontend` (or mobile) is
true, record the project's design tier in the charter (which MCPs are
connected, which accounts exist). Harness note: Figma MCP support is
first-class on Claude Code/Cursor; check current status on Codex —
tier 2a/3 work anywhere the tool has network access, tiers 4/5 work
everywhere including fully offline.

Pricing/capability claims current as of 2026-07; re-verify before relying
on a tier's free limits.
