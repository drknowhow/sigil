Hi — Oskar here (my AI assistant did the legwork and reproductions). I read Sigil end to end, ran the suite and the benchmarks, and poked at the core idea. The engineering is genuinely impressive and the honesty in `docs/limitations.md` is rare. This issue is about one concrete, fixable defect plus a related framing point — both aimed at the thing Sigil is actually selling.

A quick vocabulary note so nothing below is opaque, since the terms are CS jargon, not chemistry:

- **Token** — the unit a language model is billed and sized in. Roughly a word-fragment; `fetch_prices` might be 2–3 tokens. "Saving tokens" = the agent reads/writes less, so it's cheaper and fits more in its working memory.
- **AST** (abstract syntax tree) — the structured, parsed form of code: the *meaning* (this is a function, these are its arguments, it returns x) with the surface text (spacing, comments) stripped out. Sigil hashes this.
- **Lossless / lossy** — lossless means you can reconstruct the original exactly; lossy means some of it is gone for good. (Same distinction as PNG vs JPEG.)

---

## Part 1 — The bug: `expand` silently discards comments and docstrings

When an agent works through Sigil, it reads code back via `expand(hash, form="source")`. I expected that to return the function as written. It returns a **de-commented, reformatted reconstruction** instead — the docstring and every comment are gone, not just hidden from the fingerprint but unrecoverable from the store.

### Reproduce it

```bash
cat > /tmp/probe.py <<'PY'
# a leading comment explaining intent
def fetch_prices(tickers, start, end):
    """Fetch prices for tickers between start and end.

    Multi-line docstring with detail the author cared about.
    """
    result = {}          # inline comment, idiosyncratic spacing
    for t in tickers:
        result[t] = _get(t, start, end)
    return result
PY

python3 - <<'PY'
from sigil.harness.core import Harness
import tempfile
h = Harness(tempfile.mkdtemp())
h.lift("/tmp/probe.py")
ref = next(l.split()[0] for l in h.sheet().splitlines() if "fetch_prices" in l)
print(h.expand(ref, form="source"))
PY
```

What comes back:

```python
def fetch_prices(tickers, start, end):
    result = {}
    for t in tickers:
        result[t] = _get(t, start, end)
    return result
```

The comment, the **entire docstring**, and the formatting are gone.

### Why this is more than cosmetic

There are two different meanings of "lossless," and Sigil only has the first:

- **Semantically lossless** — the reconstructed code *does the same thing*. ✅ Sigil is solidly this.
- **Text-lossless** — you get back *what the author wrote*. ❌ Sigil is not this.

For a tool whose whole premise is **human–AI collaboration**, the docstring is the most important thing on the page: it's the function's *intent* — the "why," in the author's own words. An agent that can only ever see the de-commented projection has been handed the code with the reasoning torn off. (Think of it as handing a collaborator your method section with every "we did X *because* Y" deleted — the steps survive, the judgment doesn't.)

The README says "formatting, comments and docstrings never change it [the hash]." That sentence is true and correct about the *fingerprint*. But a reader naturally infers that the comments are *kept* somewhere and the hash just ignores them for identity purposes. They aren't kept. That gap between what's implied and what happens is the heart of this issue.

### A fix that keeps the design intact

Store the **original source bytes** alongside the canonical/IR object (keyed by the same hash). Then:

- `expand(form="source")` returns the **original text** — comments, docstring, formatting and all.
- The canonical/IR form still does all the hashing, patching, and verification exactly as today. The fingerprint stays stable because it's still computed over the canonical form, not the bytes.

One honest wrinkle: once an agent *edits* a function through an AST patch, the original comments can't always be re-attached to the changed code. That's fine — just be explicit about it:

- functions the agent **hasn't touched** expand to original source (the common case, and the one that matters most for reading/understanding);
- functions it **has** patched expand to the canonical projection, clearly labeled as such (e.g. `; projected from patched AST — original comments not preserved`).

That single change closes the gap for almost all real reading, and the `?`/provisional honesty convention you already use everywhere extends naturally to it.

---

## Part 2 — A framing point: where the token savings actually come from

This part isn't a bug — it's about how Sigil is described. The tagline (and the spec's "10×+") frame the win as **"lossless token compression via a terser language."** When I measured it, that phrase turns out to bundle three separate claims, and the savings come from none of the three. Naming the real mechanism makes the project *more* defensible, not less — so I think it's worth correcting in the docs.

**Claim A — "a terser language."** The one place the language could save tokens is the pretty math glyphs (`∧ ≤ ≠`), which the printer emits by default. But models chop text into tokens in a way that punishes non-ASCII symbols. Measured with a real tokenizer:

| written as | tokens | written as | tokens |
|---|---|---|---|
| `and` | **1** | `∧` | **2** |
| `<=` | **1** | `≤` | **2** |
| `!=` | **1** | `≠` | **2** |

So the canonical (glyph) form is *more* expensive than plain ASCII, not less. And the `.sg` form overall is *longer* than the equivalent Python, because it adds contracts and effect rows. The language is not where tokens are saved.

**Claim B — "compression."** Not in the technical sense. A digest-sheet line —

```
#9407 fetch_prices(tickers, start, end) -> ? !unsafe?
```

— is not a squeezed-down version of the function from which you could rebuild it. It's an **index card**: name, arguments, effects, and a fingerprint. The actual body is filed away and fetched only when needed. This is the same move as keeping a one-line index in your lab notebook and pulling the full protocol from the binder only when you actually run it — you carry less *day to day*, but you haven't compressed any single protocol. The saving is "don't carry what you aren't using this turn," which is real and valuable but is a different thing from compression.

**The actual lever (and it's a good one).** The token win is two mechanisms working together:

1. **Content addressing makes "unchanged" provable.** Because a function's fingerprint only moves when its meaning changes, the index sheet is *byte-for-byte identical* turn after turn. Models can keep an unchanged chunk of input in a cheap **prompt cache** — but only if it's exactly identical each time. Content addressing is what guarantees that. This is the single cleverest thing in the design.
2. **Edits are small structured deltas** (patch operations) instead of whole-file rewrites.

Stable, cacheable index + tiny edits = the compounding savings. That's the honest story, and it's a strong one. Worth noting the corollary: the **contracts and effects** — arguably the most valuable part of Sigil — *add* information; they're the opposite of compression. The best part of the project is not compressing anything, and that's fine.

**Why bother fixing the words.** Two reasons:

- The honest framing survives scrutiny; "lossless compression via a terser language" invites exactly the three measurements above and loses all three.
- It points at the experiment that would actually prove Sigil's worth: take one real agent coding task and run it two ways — **(a) Sigil's sheet + patch protocol**, vs **(b) plain Python kept in a prompt cache + an ordinary patch tool** — and compare the real token bill. If Sigil wins, my bet is the win is the **contracts and effects** (catching bad edits), not terseness or compression. Either way that result tells you where to invest next.

---

None of this dents the core: content-addressed, contract-checked code for agents is a genuinely good idea, and the build quality is high. Part 1 is a real defect I'd fix; Part 2 is a relabeling that I think makes the pitch stronger. Happy to dig into either — and the cache-vs-Sigil A/B in Part 2 is something I'd be glad to help design.
