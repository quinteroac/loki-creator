# AGENTS.md

## UI Development Guidelines

For any change or creation related to the user interface (UI), you **must** follow the design system defined in [`DESIGN.md`](./DESIGN.md). This includes, but is not limited to:

- **Colors**: Use only the palette tokens defined in DESIGN.md (brand-coral, brand-magenta, brand-blue, canvas, ink, charcoal, slate, steel, stone, muted, surface, hairline, etc.). Never introduce arbitrary colors.
- **Typography**: Use **DM Sans** as the primary font family (with Inter, Helvetica Neue, Helvetica, Arial as fallbacks). Follow the hierarchy table for size, weight, line-height, and letter-spacing per token.
- **Buttons**: Pill-shaped (`rounded-full`). Black-pill for primary CTAs, outline-pill for secondary.
- **Cards**: 32px corner softening for vibrant gradient product cards; 16px corner softening for quiet documentation cards.
- **Layouts**: Respect the established patterns (e.g., 3-column documentation layout with left sidebar, center prose, right TOC).
- **Spacing & Sizing**: Follow the scale and rhythm defined in DESIGN.md.
- **Iconography**: Use the specified icon system and styling.
- **Components**: Match the existing component patterns (modals, tabs, inputs, badges, banners, etc.) as described in DESIGN.md.

Before implementing any UI work, open and review [`DESIGN.md`](./DESIGN.md) to ensure full compliance with the design system.

## General Workflow

1. Read and understand the relevant sections of [`DESIGN.md`](./DESIGN.md).
2. Identify which design tokens, components, and patterns apply to the task.
3. Implement the UI change using only the specified design system elements.
4. If the design system does not cover a needed element, fall back to the closest existing pattern and flag the gap for design review.
