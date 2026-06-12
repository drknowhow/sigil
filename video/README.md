# Sigil explainer — Remotion clip

A 75-second explainer of how Sigil works: the problem → lift → goals &
contracts → static effect budgets → the agent loop (sheet/expand/patch/verify)
→ the measured v1.0.0 results → outro. 1920×1080 @ 30fps; every number shown
is real (docs/cost-model.md, docs/STATUS.md).

```bash
npm install
npm run studio    # live preview + scrubbing in the browser
npm run render    # out/sigil-explainer.mp4 (needs Chrome/Chromium once)
npm run still     # out/poster.png — poster frame
```

Scene timings live in `src/SigilExplainer.tsx` (one line per scene); shared
design tokens in `src/theme.ts` match the project hero page.
