---
name: design-system
description: Token-based design system — the shared visual contract for every FE slice. Color / typography / spacing / motion tokens; component contracts; theming (light / dark / brand); Storybook + visual regression baseline. Lives between `wireframing-prototyping` (which uses the system) and `stack-web-frontend` (which implements it).
---

# Design System


<!-- praxis:description:full -->
## Full description

Token-based design system — the shared visual contract for every FE slice. Color / typography / spacing / motion tokens; component contracts; theming (light / dark / brand); Storybook + visual regression baseline. Lives between `wireframing-prototyping` (which uses the system) and `stack-web-frontend` (which implements it). Use whenever new tokens or components are being introduced, when wireframing requires a component not yet in the system, or when establishing the design language for a new product.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: ux-and-design
domain: frontend
state: active
dependencies:
 - engineering-standards
triggers:
 - "introducing a new design language for a product"
 - "extending the system with new tokens or components"
 - "wireframes reference a component not yet in the system"
 - "setting up Storybook + visual regression for the project"
 - "evolving themes (dark mode, brand variants)"
outputs:
 - design tokens (color / typography / spacing / motion / sizing)
 - component contracts (props, states, variants per component)
 - Storybook stories per component
 - visual regression baseline (Chromatic / Percy / Playwright visual)
 - theme definitions (light / dark / brand)
consumers:
 - ux-designer (uses tokens + components in wireframes)
 - frontend-developer (implements components and uses tokens in code)
 - accessibility (audits components and tokens for a11y conformance)
 - wireframing-prototyping (consumes tokens for mid-fi wireframes)
references: []
```
<!-- praxis:metadata:end -->

The shared contract between design and implementation. Without it, every FE slice reinvents component styles and visual decisions; designers and developers debate inconsistencies that should never have arisen. With it, the system enforces consistency *by construction* — wireframes pull from the same components the code does.

The design system is a *product* the team maintains, not a one-off artifact. It evolves with the product.

## When this skill fires

- A new product is being designed; the system is being established from scratch.
- A wireframe needs a component that doesn't exist yet (extension trigger).
- The product is gaining a theme — dark mode, white-label brand, accessibility-optimized variant.
- A component needs revision based on accessibility or usability findings.
- The visual regression baseline is being established or refreshed.

## The system's layers

### Layer 1: Tokens

Tokens are the atomic, unstyled units. Colors are not "Blue 500" but `--color-primary-500: #3B82F6`. Spacing is not "16px" but `--spacing-4: 1rem`. Tokens have:

- A **name** in a consistent convention.
- A **value** for the default theme.
- **Variant values** per theme (dark mode, brand, etc.).
- A **purpose** (semantic, not visual — `--color-action-primary` not `--color-bright-blue`).

Token categories:

```
Color:
 --color-bg-primary, --color-bg-secondary, --color-bg-elevated
 --color-text-primary, --color-text-secondary, --color-text-muted
 --color-action-primary, --color-action-primary-hover, --color-action-primary-active
 --color-action-secondary, ...
 --color-status-success, --color-status-warning, --color-status-error
 --color-border-default, --color-border-emphasis

Typography:
 --font-family-sans, --font-family-mono, --font-family-display
 --font-size-xs, --font-size-sm, --font-size-base, --font-size-lg, --font-size-xl, ...
 --font-weight-regular, --font-weight-medium, --font-weight-semibold, --font-weight-bold
 --line-height-tight, --line-height-base, --line-height-relaxed

Spacing:
 --spacing-0, --spacing-1, --spacing-2, --spacing-3, --spacing-4, --spacing-6, ...
 (a consistent scale, often modular: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64)

Sizing:
 --radius-sm, --radius-md, --radius-lg, --radius-full
 --shadow-sm, --shadow-md, --shadow-lg

Motion:
 --duration-fast, --duration-base, --duration-slow
 --easing-default, --easing-enter, --easing-exit
```

Tokens are exported as JSON (the canonical source of truth) and consumed by:
- CSS custom properties at runtime.
- TypeScript types for compile-time safety.
- Figma / design tools via plugin or token-bridge.

Tools: Style Dictionary, Design Tokens W3C spec, framework-specific generators.

### Layer 2: Components

Components compose tokens into reusable UI units. Each component has:

- **A contract** — props (with TypeScript types), states (default, hover, active, disabled, loading, error, empty), variants (sizes, intents).
- **A reference implementation** — the canonical version using the chosen FE framework's primitives.
- **Accessibility expectations** — keyboard interaction, ARIA semantics, focus management.
- **Composition rules** — what can be nested inside it; what props it forwards.

baseline component set:

```
Layout: Box, Stack, Grid, Flex, Divider
Typography: Heading, Text, Code
Action: Button, IconButton, Link, Menu, MenuItem
Form: Input, Textarea, Select, Checkbox, Radio, Switch, Label, FormField
Feedback: Alert, Badge, Tooltip, Spinner, Skeleton
Navigation: Tabs, Breadcrumbs, Pagination, Navbar
Disclosure: Modal, Drawer, Popover, Accordion
Data display: Table, Card, List, Avatar
```

This is the *minimum*; product-specific components extend it.

### Layer 3: Patterns

Patterns are *compositions* of components for recurring use cases:

- **Empty state** (icon + heading + body + primary action).
- **Error state** (icon + heading + body + retry action).
- **Form layout** (consistent label/input/help/error positioning).
- **Confirmation dialog** (modal + heading + body + cancel/confirm).
- **Data fetching skeleton** (skeleton variants per content type).

Patterns are documented; they're not separate components (a confirmation dialog is just a Modal with specific contents), but they're the conventional way to assemble for the use case. Designers and developers refer to them by name.

### Layer 4: Themes

Themes are token-value overrides:

- **Light** (default).
- **Dark** — same token names, different values.
- **Brand** — for white-label products.
- **High contrast** — for accessibility.

The theme is applied at the root and cascades; components don't know which theme is active.

## The component contract format

Each component has a Storybook story file (`.stories.tsx` / `.stories.ts`) that doubles as documentation:

```typescript
// components/Button/Button.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta: Meta<typeof Button> = {
 title: 'Action/Button',
 component: Button,
 args: {
 variant: 'primary',
 size: 'md',
 children: 'Click me',
 },
 argTypes: {
 variant: { control: 'select', options: ['primary', 'secondary', 'ghost', 'destructive'] },
 size: { control: 'select', options: ['sm', 'md', 'lg'] },
 isLoading: { control: 'boolean' },
 isDisabled: { control: 'boolean' },
 },
};
export default meta;

export const Primary: StoryObj<typeof Button> = {};
export const Secondary: StoryObj<typeof Button> = { args: { variant: 'secondary' } };
export const Loading: StoryObj<typeof Button> = { args: { isLoading: true } };
export const Disabled: StoryObj<typeof Button> = { args: { isDisabled: true } };
// One story per significant state.
```

Each story renders the component in a specific state; Storybook generates the visual catalog.

## Visual regression

A baseline visual snapshot is captured per component story. On every PR that touches the design system or a component, the snapshot is compared:

- **No diff** — pass.
- **Intended diff** — reviewer approves the new baseline.
- **Unintended diff** — fail; investigate.

Tools: Chromatic (managed; integrates with Storybook), Percy (managed), Playwright Visual (self-hosted).

Visual regression catches the most common FE bug class: "I tweaked one component and broke another I didn't know used the same token." Without it, FE teams accumulate visual debt invisibly.

## Outputs

| Output | Location |
|---|---|
| Tokens (JSON source) | `design-system/tokens.json` (committed to repo) |
| Token-generated outputs (CSS, TS) | `design-system/dist/` (generated; gitignored or generated in CI) |
| Component implementations | `src/design-system/components/` |
| Storybook stories | colocated with components |
| Visual regression baselines | external (Chromatic) or `tests/visual-snapshots/` (self-hosted) |
| Documentation | Storybook itself; auto-generated from stories + component contracts |

## Mode handling (G/B)

**Greenfield.** Establish the baseline set; build components as wireframes demand them.

**Brownfield.** The existing product has implicit design decisions encoded in scattered CSS. Extract tokens from the current product (audit `.repo-intel/` for color/spacing patterns); document the inferred system in `.project/semantic/design-system-as-is.md`; then incrementally migrate: new components built against the explicit system, old components migrated as their owning slices touch them.

## Working with the system

- The UX Designer references tokens and existing components in wireframes; flags missing components for the system to grow.
- The Frontend Developer implements *only against* the design-system components in product code; custom one-off styles are violations to flag.
- The Accessibility skill audits components when they're added (color contrast, ARIA, keyboard support).
- Visual regression runs per PR; failures gate merge unless explicitly approved as intended.

## What this skill does not do

- Choose the frontend framework — that's `frontend-architecture` (which influences the component implementation).
- Design specific screens — that's `wireframing-prototyping`.
- Validate the design with users — that's `user-research`.
- Define brand identity — usually a separate brand-design exercise upstream of this skill.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Design system is over-engineering for early-stage." | A minimal design system (12 tokens + 8 components) is a day of work and prevents months of divergence. |
| "Visual token names are clearer." | They lock you to the current visual. Semantic names (`action-primary`) survive rebrands without code changes. |
| "Components are designer territory." | They have a designer-authored spec AND an engineer-authored implementation. Cross-functional, not single-owner. |
| "We can iterate the design system later." | Components proliferate without one. Migration cost grows superlinearly. |
| "MUI / Chakra / Radix is our design system." | Those are component libraries. Your design system is the tokens + composition rules on top. |
| "Storybook is the design system." | Storybook is documentation. The design system is the contract; Storybook surfaces it. |
| "Accessibility lives in the component." | Yes, baked in. The system + every component documents the a11y story. |

## Verification

You are done when:

- [ ] Design tokens defined: color, typography, spacing, radius, shadow, motion, breakpoints.
- [ ] Token naming is semantic (`color-action-primary`), not visual (`color-bright-blue`).
- [ ] Component library covers: button, input, select, modal, dialog, table, card, layout primitives.
- [ ] Each component has: spec, code, a11y story, usage examples.
- [ ] Storybook (or equivalent) deployed for the team.
- [ ] Component versioning policy documented.
- [ ] Contribution path documented (how to propose / change components).
- [ ] Accessibility verified per component (per `accessibility`).

Evidence to check:
- A new FE engineer can build a screen from existing components without writing new ones.
- A rebrand can be tested by changing only token values.

## Anti-patterns

- Tokens with visual names (`--color-bright-blue`) rather than semantic (`--color-action-primary`). When the brand evolves, every reference must change.
- One-off styles in product code that bypass the system. Cumulative drift.
- Component proliferation — five button variants that should be one with a prop. Audit and consolidate.
- Storybook stories that don't cover the component's states (only the default; missing hover/disabled/loading/error). Visual regression then misses regressions in those states.
- A "design system" that's only Figma libraries with no code-level enforcement. Inconsistency between design tool and runtime accumulates.
