# Finance Bento UI Framework (Sebastian, 2026-11-25)

Mandatory UI framework for every Devin build, replacing the retired Pinterest UI references.
Source: React client component "Finance Bento" pasted by Sebastian in the DEV team room (`finance-bento.tsx`). Note: the pasted component was cut off in the room transcript mid-CSS (at `@media (m` and `.vb-badge:h`) and before the end of `mount()`, so this spec documents all recovered tokens, grid rules, card styles, typography, and behavior, and builds should faithfully extend this design language.

## Core Principles
- Single-file React client component (`"use client"`) or plain DOM + SVG inside an effect (`useEffect`); no third-party UI or chart libraries.
- Projects keep this framework's structure, tokens, typography, card styles, and motion, and only change tile content to fit their real data and live demo.
- Real data only (typed `data` prop); never mock data.

## Canvas, Colors & Tokens
- Canvas & card background: `#000` (`padding: 20px 22px 22px`, outer `.fpb-c` radius `28px`).
- Text hierarchy: `--t1: #fff`, `--t2: rgba(255,255,255,.56)`, `--t3: rgba(255,255,255,.38)`, hairline `--hair: rgba(255,255,255,.14)`.
- Primary accent (`--acc`): `#E8FF1F` (electric lime) — used for solid accent cards, deltas, and focus rings (`outline: 2px solid var(--acc); outline-offset: 2px`).
- Secondary series colors: `#FFFFFF`, `#A9B2FF`, `#FFB37A`.
- Easing (`--ease`): `cubic-bezier(.32,.72,0,1)`.

## Grid & Responsive Breakpoints
- Top bar (`height: 44px`, `margin-bottom: 16px`): `h1` (`28px`, `font-weight: 700`, `letter-spacing: -.03em`, `flex: 1`) with muted subtitle `span` (`15px`, `font-weight: 500`, `color: var(--t3)`), segmented pill toggles, and optional `40px` circular avatar (`box-shadow: 0 0 0 2px rgba(255,255,255,.18)`).
- 12-column CSS Grid (`grid-template-columns: repeat(12, minmax(0, 1fr))`, `gap: 14px`).
- Row heights: `.h1 { height: 376px }` (hero + gauge), `.h2 { height: 168px }` (KPI tiles), `.h3 { height: 330px }` (lower row).
- Default desktop spans (`>=1200px`): hero `span 8`, gauge `span 4`, four KPI tiles `span 3` each, lower row `span 5` + `span 4` + `span 3`.
- Responsive breakpoints: `1199px`, `767px`, `520px` (at `<=1199px`: hero `span 12`, gauge `span 6; grid-row: span 2; height: auto`, KPIs `span 6`, lower row `span 12` + `span 6` + `span 6`; extend cleanly down through `767px` and `520px` to single-column stacking on mobile).

## Card Styles & Effects
- Base `.card`: `28px` radius, `position: relative`, `overflow: hidden`, inner content `.in-c` (`padding: 22px 24px`, `z-index: 2`).
- Inset rim highlight (`.card .rim`): `box-shadow: inset 0 1px 0 rgba(255,255,255,.2), inset 0 0 0 1px rgba(255,255,255,.06); pointer-events: none; z-index: 9`.
- Blurred glow cores behind charts (`.g` + `.core`): `position: absolute; left: 10%; right: 10%; top: 16%; bottom: -6%; border-radius: 90px; filter: blur(60px)`.
- Glass cards (`.glass`): `background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.12); backdrop-filter: blur(20px)` (`.rim` hidden on glass).
- Solid accent cards (`.solid`): `background: var(--acc)` (`#E8FF1F`), dark text `color: #0b0b0c`, `.cap` at `rgba(0,0,0,.55)`, `.rim` with `inset 0 1px 0 rgba(255,255,255,.5)`.
- Staggered card entrance: initial `opacity: 0; transform: translateY(14px) scale(.985)`, transitioning over `opacity .7s ease, transform .9s var(--ease)` with `transitionDelay = (i * 60) + 'ms'` once `.in` is added after `document.fonts.ready`.

## Typography & Controls
- UI font: `Geist, ui-sans-serif, system-ui, -apple-system, sans-serif` (`-webkit-font-smoothing: antialiased`).
- Numeric / mono font: `"Geist Mono", monospace` with `font-variant-numeric: tabular-nums`.
- Type scale:
  - Card title (`.ttl`): `18px`, `font-weight: 600`, `letter-spacing: -.02em`.
  - Uppercase captions (`.cap`): `11.5px`, `font-weight: 600`, `letter-spacing: .06em`, `text-transform: uppercase`, `color: var(--t2)`.
  - Huge thin figures (`.big`): `40px`, `font-weight: 200`, `letter-spacing: -.04em`, `line-height: 1`, `tabular-nums`.
  - Deltas (`.delta`): `12.5px`, `font-weight: 600`, `"Geist Mono"`, `color: var(--acc)`, `letter-spacing: -.02em`.
  - Muted metadata (`.muted`): `12.5px`, `font-weight: 500`, `color: var(--t3)`.
- Segmented pill toggles (`.seg`): `padding: 3px; gap: 2px; border-radius: 14px; background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.12)`. Buttons: `height: 28px; min-width: 44px; padding: 0 12px; border-radius: 11px; font: 600 12.5px Geist,sans-serif`; active `[aria-pressed="true"]`: `background: #fff; color: #0b0b0c`.
- Chips (`.chip`): `height: 22px; padding: 0 9px; border-radius: 11px; background: rgba(0,0,0,.85); color: #fff; font: 600 11px "Geist Mono",monospace`.
- Legends (`.legend`): `12px`, `font-weight: 500`, `color: var(--t2)`, `8px` circular dot markers.
- Fixed glass tooltips (`.tip`): `position: fixed; z-index: 50; pointer-events: none; background: rgba(14,14,16,.92); border: 1px solid rgba(255,255,255,.12); border-radius: 14px; padding: 9px 11px; font-size: 12px; backdrop-filter: blur(16px); box-shadow: 0 12px 30px -10px rgba(0,0,0,.6)`.
