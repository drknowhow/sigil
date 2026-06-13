# marketing/ — Sigil promo assets

- **higgsfield-30s.md** — full 30-second launch-clip production pack for
  [Higgsfield](https://higgsfield.ai): 6-shot storyboard with per-shot visual
  prompt, camera-motion preset, caption, timing, brand lock, and music notes.
  Developer audience, trust angle, captions-only.
- **higgsfield-prompts.txt** — the same 6 shots as a fast copy-paste sheet
  (prompt + motion + caption per shot).
- **captions.srt** — burn-in caption track timed to the 30s cut.

Workflow: generate each shot in Higgsfield (paste prompt, set motion preset +
5s), stitch the 6 clips, drop a synthwave music bed, burn in `captions.srt`.
For brand-tight shots, seed image-to-video with the hero page (`site/index.html`)
or the benchmark plots (`docs/img/*.svg`).

Already in the repo for other channels: a rendered explainer (`video/`,
Remotion) and the live animated hero page (`site/index.html`).
