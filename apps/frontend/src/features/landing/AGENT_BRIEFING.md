# Landing build briefing (Task 18)

You own **one file**. Never edit `primitives.tsx`, `Landing.tsx`, `App.tsx`, `theme.ts`, `index.css`, `glass.tsx` or another section. Report a missing primitive instead of adding one.

## Visual language (all of it comes from Task 11 tokens — no hex, no new colours)
- Container `max-w-6xl px-5 sm:px-8`; section rhythm `py-20 sm:py-28 lg:py-32`.
- Display type: `font-semibold tracking-[-0.04em] leading-[0.98] [font-stretch:88%]` on IBM Plex Sans. Body `text-muted-foreground leading-relaxed`, max `max-w-2xl`.
- Surfaces: `rounded-2xl border bg-card`; use `.lift` for hover (translateY −2px + shadow). Radii: cards 2xl, small chips rounded-full/xl.
- Glass (`<Glass>`) is allowed on **nav, floating mini cards, MockWindow frame, CTA band** only. Everything else solid.
- Colour roles: `bg-primary text-primary-foreground`, `bg-accent text-accent-foreground` (= primary container), `bg-secondary text-secondary-foreground` (= secondary container), `bg-tertiary-container text-foreground`, `bg-muted`, `bg-card`. Status tokens only for real status.
- Original LabelDesk copy and visuals only. No reference-site text, logos, illustrations or brand colours. All mock UI is HTML/CSS/SVG.
- Icons: `lucide-react`, 16–20 px, `aria-hidden` unless they carry meaning.

## Primitives (`../primitives`)
`SectionShell` (section + container: `className`, `innerClassName`, `id`, `aria-labelledby`), `SectionHeading` (`id`, `tag`, `icon`, `title`, `intro`, `align`), `TagPill` (`icon`, `children`), `MockWindow` (`title`, `meta`, `children`, `bodyClassName`), `CornerMarks`, `DotGrid`, `Reveal` (`delay` ms).

## Non-negotiables
- Semantic landmarks: your root is the right element (`section` with `aria-labelledby` pointing at the h2 `id`; nav is inside a `header`; footer is `<footer>`). Headings descend h1 → h2 → h3, no skips.
- Text ≥ 4.5:1, UI borders/icons ≥ 3:1, visible `:focus-visible` (global outline — never remove it).
- Responsive at 375 / 768 / 1280 / 1440. Nothing overflows horizontally at 375.
- Motion: `Reveal` for entrances; only opacity/transform; reduced-motion is handled globally — also guard any JS parallax with `matchMedia('(prefers-reduced-motion: reduce)').matches`. Never animate blur. No auto-advancing content.
- Interactive controls are real `<button>`/`<a>` with accessible names; tabs use `role=tablist/tab/tabpanel`, `aria-selected`, arrow keys. Hero nav anchor links must point at existing ids: `#product`, `#models`, `#pricing`, `#docs`.
- Decorative layers get `aria-hidden`.

## Verify (one fix iteration allowed)
From `apps/frontend`, run `npm run dev -- --port <YOUR_PORT> --strictPort` in the background, then
`node scripts/landing-shot.mjs http://localhost:<YOUR_PORT>/__preview/<SECTION> ../../.superpowers/sdd/2026-10-31-labeldesk-v2/task-18-shots/section-<SECTION>-<light|dark>.png 1440 <light|dark>`
and `node scripts/landing-shot.mjs axe http://localhost:<YOUR_PORT>/__preview/<SECTION> 1440 <light|dark>`.
Look at both screenshots (1440 and 375). Fix what you see, re-shoot once, stop the server. axe must show 0 violations; colour-contrast incomplete must be hand-sampled and reported.
