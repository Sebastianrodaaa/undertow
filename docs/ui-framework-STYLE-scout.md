# Finance Bento UI framework (Sebastian, 2026-11-25): mandatory for every Devin build; replaces the Pinterest refs
Source: React client component "Finance Bento" (by vasnev.art credit badge) pasted by Sebastian in the DEV room. The paste was cut off mid-CSS (at `.vb-badge:h`), so only the part below is captured.

## Principles
- A single-file React client component; charts drawn with plain DOM + SVG inside an effect; no chart or UI dependencies.
- Dark bento grid of rounded cards; data comes from a typed `data` prop (real data only, never mock).
- Responsive: 12-column grid at >=1200px, reflow at <=1199px, <=767px, <=520px.

## Tokens
- Font: Geist (UI), Geist Mono (numbers, deltas, chips), tabular-nums; antialiased.
- Page/card bg #000, text #fff; --t2 rgba(255,255,255,.56); --t3 rgba(255,255,255,.38); --hair rgba(255,255,255,.14).
- Accent --acc #E8FF1F (electric lime): solid accent tile, deltas, focus ring.
- Series colors: #FFFFFF, #A9B2FF (periwinkle), #FFB37A (apricot).
- Ease --ease cubic-bezier(.32,.72,0,1).
- Radius: cards 28px; segmented control 14px/11px; chips 11px.

## Layout
- Top bar 44px: h1 28px/700/-.03em with a muted 15px subtitle span, segmented range control (active = white pill, dark text), round 40px avatar.
- Grid gap 14px. Row heights: hero 376px, KPI 168px, lower row 330px.
- Spans: hero chart 8 + gauge 4; four KPI tiles of 3; lower row 5 + 4 + 3.

## Card styles
- `.card`: 28px radius, overflow hidden, inset rim highlight (inset 0 1px 0 rgba(255,255,255,.2)); entrance fade + 14px rise + .985 scale over .7-.9s.
- Glow cards: blurred colored core (blur 60px) behind content.
- `.glass`: rgba(255,255,255,.06) bg, 1px rgba(255,255,255,.12) border, backdrop blur 20px.
- `.solid`: accent lime bg, dark text.
- Inner padding 22px 24px.

## Type scale
- Card title 18px/600/-.02em; caps label 11.5px/600 uppercase .06em tracking in --t2; big number 40px/200/-.04em tabular; delta 12.5px Geist Mono in accent; muted 12.5px --t3.
- Chips: 22px tall, black 85% bg, Geist Mono 11px.
- Legend: 8px dots, 12px labels.
- Tooltip: fixed, rgba(14,14,16,.92), 14px radius, blur 16px, mono values.

## Brief rule
Each project keeps this framework (structure, tokens, type, card styles, motion) and maps its own real data and visuals onto bento cards. The visual may fill the hero card, with KPI tiles carrying real result numbers.
