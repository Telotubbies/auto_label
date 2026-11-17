# Visual override: keep the existing Liquid Glass look (owner, 2026-11-17)

The owner wants the glass design the app already ships to stay the standard. The v3 frames in this
folder decide **layout, information architecture, flows, states and copy**. They do **not** decide the
visual style.

Binding for every redesign and parity card:

1. Visual style comes from the running app: `apps/frontend/src/index.css` tokens (`--glass-tint`,
   `--glass-hi`, `--glass-edge`, `--glass-sheen`, `--glass-solid`, the HCT/Material colour roles) and the
   primitives in `apps/frontend/src/components/glass.tsx`. Reuse them; do not introduce the flat v3
   surfaces or a second token set.
2. Glass stays on chrome: top bar, rails, floating toolbars, sheets, popovers, overlays. The annotation
   canvas, dense tables and charts stay solid for legibility and performance.
3. Accessibility still binds: WCAG AA text contrast (the v3 pass found grey text at 11-12 px failing;
   use the darker text role), `prefers-reduced-transparency` falls back to `--glass-solid`, focus rings
   visible on glass.
4. Thai text uses a font with Thai glyphs (Anuphan / Noto Sans Thai), never Inter alone.
5. Where a v3 frame and the glass system disagree on colour, radius, blur or elevation, the glass
   system wins; where they disagree on layout or flow, the frame wins.

Features: implement everything in docs/research/roboflow-parity/PARITY.md and
docs/research/beyond-roboflow/BEYOND.md via the backlog cards, styled with the glass system.
