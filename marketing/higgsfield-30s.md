# Sigil — 30-second launch clip · Higgsfield production pack

**Audience:** developers · **Angle:** trust ("AI writes the code; Sigil makes
sure it can't lie") · **Sound:** captions-only, add a music bed in post ·
**Format:** 1080×1920 vertical (social) — a 1920×1080 landscape variant is noted
per shot · **Total:** 30.0 s across 6 shots (~5 s each, Higgsfield's clip length).

How to use: in Higgsfield, create each shot as one generation. Paste the
**Prompt**, set the **Motion** preset (Higgsfield's camera-motion menu) and the
**5s** duration, generate, then stitch the 6 clips in any editor and burn in the
**Caption** text. Brand + music notes at the bottom. Seed images you already
have (the hero page / plots) are listed under "Seed" to use image-to-video for
tighter brand control.

---

## Brand lock (use in every shot)

- **Palette:** near-black navy background `#07090f`; primary cyan `#5eead4`;
  secondary violet `#a78bfa`; warning amber `#fbbf24`; alert red `#fb7185`;
  off-white text `#e8ecf4`.
- **Look:** dark, premium, high-contrast, subtle film grain, soft volumetric
  glow, faint grid/particles. Monospace for code/hashes, clean sans for taglines.
- **Energy:** confident and kinetic but not frantic — let each beat land.
- **Logo/wordmark:** "SIGIL" in a bold gradient (white → cyan → violet).

---

## Shot 1 — The hook (0.0–5.0 s)

- **Caption (big, center):** "Your AI just wrote 400 lines."
  then snap to → "Do you trust them?"
- **Prompt:** *Cinematic dark tech scene, a dense wall of glowing monospace code
  scrolling fast on a near-black navy screen, cyan and violet syntax highlights,
  subtle film grain and bloom, shallow depth of field, the code blurring at the
  edges, ominous calm. Premium developer-tool aesthetic.*
- **Motion:** **Slow Push-In** (Dolly In) — drift toward the code wall.
- **Why:** states the stakes every dev feels.
- **Landscape note:** widen the code wall to fill 16:9.
- **Seed (optional):** a screenshot of the hero page's lifted-code terminal.

## Shot 2 — The hidden risk (5.0–10.0 s)

- **Caption:** "It snuck in a network call you never asked for."
  small tag appears: `requests.get(...)  →  !net`
- **Prompt:** *A single line of code lights up red-amber inside the scrolling
  code, a glowing tendril of light branches off it toward a network/cloud icon,
  warning glow pulsing, the rest of the code dims to navy. Tense, cinematic,
  high contrast, particles drifting.*
- **Motion:** **Whip Pan** into the highlighted line, then settle.
- **Why:** the concrete danger — hidden side effects in AI code.

## Shot 3 — The wall goes up (10.0–15.0 s)

- **Caption:** "Sigil checks effects before the build." → big stamp: "REJECTED"
- **Prompt:** *A luminous cyan geometric barrier/forcefield snaps into existence
  across the screen, blocking the red tendril mid-reach; the offending line
  freezes; a sharp 'REJECTED' seal stamps in red over a clean call-chain readout
  in monospace. Decisive, powerful, satisfying snap of light.*
- **Motion:** **Crash Zoom** out as the barrier forms (impact feel).
- **Why:** the product's core promise, made visceral. Static effect budget = a
  wall the AI cannot cross.

## Shot 4 — The verified loop (15.0–21.0 s)

- **Caption:** "Write the goal. The AI fills it in. Nothing ships unverified." →
  small: "sheet → expand → patch → verify ✓"
- **Prompt:** *Four glowing nodes connected in a loop —
  sheet · expand · patch · verify — pulsing cyan light traveling around the
  cycle, a small green check igniting on 'verify', clean holographic UI over
  navy, content-addressed hash strings (#a4c2) floating and locking into place.
  Elegant, futuristic, trustworthy.*
- **Motion:** **Orbit / Arc** around the loop.
- **Why:** shows the workflow without UI screenshots; the check = trust.

## Shot 5 — The proof (21.0–26.0 s)

- **Caption (stat slam, one at a time):** "6.0× less context" · "0 effects
  missed" · "every patch verified"
- **Prompt:** *Bold numeric stats slamming onto screen one by one in cyan and
  white over a dark grid, a constellation of small glowing hash-nodes forming a
  network behind them, a subtle bar/line chart rising, crisp kinetic typography,
  premium data-driven look.*
- **Motion:** **Build Up** (fast cuts / punch-ins on each stat).
- **Why:** measured credibility for a technical audience.
- **Seed (optional):** the hero `docs/img/bench-tests.svg` or reduction chart.

## Shot 6 — Logo + CTA (26.0–30.0 s)

- **Caption:** wordmark "SIGIL" → tagline "Code an AI can't quietly get wrong."
  → CTA line: "Python · R · MCP · open the hero page"
- **Prompt:** *The word 'SIGIL' resolves from a swirl of hash-particles into a
  crisp white-to-cyan-to-violet gradient wordmark, centered on deep navy, a
  single calm glow pulse, particles settling. Confident, clean, end-card energy.*
- **Motion:** **Slow Pull-Out** (Dolly Out) settling to a still hero frame.
- **Why:** brand lock + call to action.

---

## Music & sound (add in post; Higgsfield clips are silent here)

- Dark synthwave / minimal techno bed, ~120 BPM, building tension to shots 3 & 5.
- Sound-design accents: a deep "thunk" on REJECTED (shot 3), a soft chime on the
  verify check (shot 4), staccato hits on each stat (shot 5). Works muted too —
  captions carry it.

## Caption styling

- Sans, heavy weight, off-white `#e8ecf4`; keywords in cyan `#5eead4`, warnings
  in red `#fb7185`. Code/hashes in monospace. Keep ≤ 7 words on screen at once.
  Center-safe for vertical; lower-third for landscape.

## Stitch order & timing

1 (5s) → 2 (5s) → 3 (5s) → 4 (6s) → 5 (5s) → 6 (4s) = **30s**. Hard cuts on the
beat; a 4-frame cyan flash transition into shots 3 and 6 for punch.

## If you'd rather not hand-stitch

The repo already ships a fully-rendered explainer (`video/`, Remotion) and a live
animated hero (`site/index.html`). This Higgsfield pack is the *marketing* cut —
shorter, punchier, brand-forward — to run as a paid/social ad.
