# Design System — "Stacks" (working name)

## Why this direction

The last several iterations of this app (Omniscient's neon glassmorphism,
then Nexus's flat dark gray-on-black) are different color schemes wrapped
around the same underlying formula: dark canvas, one sans-serif doing
every job, one saturated accent, rounded pill badges, glowing borders.
That formula is what every AI-chat-adjacent product defaults to — it
reads as "generic AI tool," not as this product.

This app's actual subject is documents, excerpts, and citations. The
direction below leans into that instead of fighting it: an **editorial
archive** aesthetic — closer to a well-typeset library catalog or a
scholarly footnote system than a tech dashboard. Concretely different on
every axis that made the last two skins feel like variations on one
theme:

| Axis | Omniscient / Nexus | Stacks |
|---|---|---|
| Canvas | Black / near-black | Warm paper (light) |
| Type | One sans-serif for everything | Serif for reading content, sans for chrome, mono for system data |
| Accent | Neon cyan / saturated blue | Single muted terracotta |
| Shape | Rounded pills, glass panels | Hairline rules, sharp-cornered index cards |
| Elevation | Glow, blur, drop shadow | Flat — a top border stripe or a hairline, never a shadow |
| Citation treatment | Bracketed number, chat-style | Footnote-style dotted underline + superscript |
| Confidence | Progress bar / percentage | A bordered "stamp" |

If a future dark mode is wanted, it should be an inverted reading mode
(deep ink-blue paper, warm off-white text) — not a return to
black-with-neon-accent, which is the exact sameness this direction
exists to break from.

## 1. Color palette

| Token | Hex | Usage |
|---|---|---|
| `--color-canvas` | `#F5F0E6` | Page background |
| `--color-surface` | `#FBF8F1` | Main content area (slightly lighter than canvas) |
| `--color-surface-sunken` | `#EFE8D8` | Sidebar, source panel (slightly darker than canvas) |
| `--color-surface-card` | `#FDFBF6` | Index cards (source excerpts, document rows) |
| `--color-ink` | `#2A2521` | Primary text |
| `--color-ink-secondary` | `#6B6255` | Secondary text, labels |
| `--color-ink-muted` | `#A69C8C` | Placeholders, timestamps, metadata |
| `--color-border` | `#DCD3C4` | Default hairline |
| `--color-border-strong` | `#C7BBA8` | Emphasized divider |
| `--color-accent` | `#A8462B` | Links, active states, citation markers, primary actions |
| `--color-accent-tint` | `#F0DCD2` | Accent-tinted backgrounds (rare — used sparingly) |
| `--color-success` | `#3F6B4A` | Verified / supported / high confidence |
| `--color-success-tint` | `#E3EDE1` | Success background fill |
| `--color-warning` | `#A67C1F` | Low confidence, needs review |
| `--color-warning-tint` | `#F5ECD3` | Warning background fill |
| `--color-danger` | `#8C2F1D` | Errors, unsupported citations |
| `--color-danger-tint` | `#F5E1DC` | Danger background fill |

**Rules:**
- One accent color, used deliberately. Terracotta means "this is
  interactive or this is a citation" — nothing else uses it.
- Success/warning/danger are always paired with their tint for
  backgrounds and the solid color for text/borders on top of it — never
  the solid color as a large fill.
- No gradients. No drop shadows. Elevation is communicated by a hairline
  border or a top border stripe (see Components), never by shadow or
  blur.

## 2. Typography

Three families, each with one job:

| Role | Family | Where |
|---|---|---|
| Reading content | **Lora** (serif) | Generated answers, quoted excerpts, document titles |
| Interface chrome | System sans (`-apple-system, "Segoe UI", sans-serif`) | Nav labels, buttons, form inputs, body UI text |
| System / metadata | **IBM Plex Mono** | Chunk IDs, timestamps, confidence scores, source filenames, section labels |

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
```

**Why this pairing:** the serif on the answer text is what makes this
feel like reading something rather than chatting with a bot — it's the
single biggest lever for the "completely different" ask, because no
competing AI-chat UI sets its main content in serif. The mono family
does double duty: it makes system data (confidence numbers, chunk
metadata) visually distinct from prose, and it reads as "precise
instrument" rather than "decorative."

**Sizes:** body/UI 13–14px, answer text 16px at 1.75 line-height (serif
needs more line-height than sans to stay readable), metadata/mono
11–12px with `letter-spacing: 0.05em` on uppercase labels, sidebar brand
wordmark 17px italic serif.

**Weights:** 400 and 500 for nearly everything; 600 reserved for the
brand wordmark only. Never bold body text — use the accent color or a
border treatment for emphasis instead.

## 3. Shape language

- **Sharp or barely-rounded corners** (`border-radius: 4–6px` at most,
  0 on index cards). This is a paper-and-ink aesthetic, not an app-icon
  aesthetic — heavy rounding fights that.
- **Hairline borders (1px), never shadows.** Every panel, card, and
  divider is a `1px solid var(--color-border)` line. This is the
  single most load-bearing rule for avoiding drift back toward "generic
  SaaS dashboard."
- **A top border stripe (3px, accent color) marks a card as
  source/reference material** — source excerpt cards and document rows
  in the knowledge base both get this. It's the one place a saturated
  accent color appears as a fill rather than text/border.

## 4. Iconography

Minimal to none. Where the current app uses icons (folder for knowledge
base, clock for history, chart for insights), prefer short text labels
or a single small serif initial/glyph instead — icon fonts read as
"generic app," and this direction is explicitly avoiding that register.
If icons are unavoidable (e.g. a send/submit action), use a thin-stroke
line icon at 16–18px, `color: var(--color-ink-secondary)`, never filled.

## 5. Core components

**Navigation rail** — sidebar background `--color-surface-sunken`. Active
item gets a 2px left border in `--color-accent`, not a filled
background pill. Inactive items are plain text in `--color-ink-secondary`.
Log out sits at the bottom in `--color-accent` (not a semantic "danger"
red — logging out isn't an error).

**Buttons** — text-only or hairline-bordered, never filled, except for
the single primary action per screen (e.g. submitting a question), which
gets `1px solid var(--color-accent)` and accent-colored text — still no
fill. Verb-first labels, sentence case: "Ask", "Upload documents", "Mark
accurate."

**Inputs** — no boxed input fields. A question input is a baseline rule
(`border-bottom: 1px solid var(--color-border)`) under italic serif
placeholder text, not a bordered box. This mirrors a library card
catalog's blank line more than a chat app's text field.

**Citation markers** — the cited phrase itself gets
`border-bottom: 1px dotted var(--color-accent)`; a small superscript
number in mono immediately follows, in accent color. Clicking either
opens the corresponding source card. This replaces the bracketed `[1]`
chat-style marker with an actual footnote convention.

**Confidence indicator ("the stamp")** — a bordered rectangle, uppercase
mono text with letter-spacing, colored by tier (`--color-success` /
`--color-warning` / `--color-danger`), with a very slight rotation
(`transform: rotate(-2deg)`) for a rubber-stamp feel. Text reads
"Verified · high confidence" / "Needs review · low confidence" rather
than a bare number — the number itself lives one click away in an
expandable detail row (retrieval / coverage / completeness), in mono,
each rounded to two decimals.

**Source / document cards** — `--color-surface-card` background, 1px
border, 3px accent top stripe. Filename in mono, section heading in
italic serif (small, muted), excerpt in serif body text inside quote
marks, a small bordered "Supported" / "Unsupported" tag in success or
danger color at the bottom.

**Empty states** — plain serif italic sentence, muted ink color, no
illustration. "Nothing indexed yet." reads better in this system than an
icon-and-headline empty state pattern.

**Loading state** — a thin horizontal rule that fills left-to-right in
accent color (like ink spreading along a line), not a spinner. Reserve
spinners for genuinely indeterminate waits only.

**Error state** — same card treatment as everything else, top stripe in
`--color-danger` instead of accent, message in plain sans (not serif —
errors are system speech, not document content).

## 6. Motion

Minimal and functional only: the loading-rule fill, a fade when a source
card expands, a subtle border-color transition on hover. No easing
tricks, no bounce, no glow pulses. Motion here should feel like turning
a page, not like a tech demo.

## 7. Accessibility

- `--color-ink` (`#2A2521`) on `--color-surface` (`#FBF8F1`) exceeds
  12:1 contrast — comfortably passes AAA for body text.
- `--color-ink-secondary` on `--color-surface-sunken` should be spot
  checked at implementation time; if it falls under 4.5:1, darken
  `--color-ink-secondary` rather than lightening the sunken surface (the
  surface hierarchy is load-bearing for the "sidebar vs. main vs. card"
  distinction).
- Never rely on the stamp's color alone to convey confidence tier — the
  text label ("high confidence" / "needs review") is the primary signal;
  color reinforces it.
- Dotted citation underlines must remain visible against the serif text
  at 1px — verify at the actual rendered font size, not just in this
  mockup.

## 8. Implementation starter

Drop-in replacement for the neon `@theme` block currently in
`apps/web/src/index.css`:

```css
@theme {
  --color-canvas: #F5F0E6;
  --color-surface: #FBF8F1;
  --color-surface-sunken: #EFE8D8;
  --color-surface-card: #FDFBF6;

  --color-ink: #2A2521;
  --color-ink-secondary: #6B6255;
  --color-ink-muted: #A69C8C;

  --color-border: #DCD3C4;
  --color-border-strong: #C7BBA8;

  --color-accent: #A8462B;
  --color-accent-tint: #F0DCD2;

  --color-success: #3F6B4A;
  --color-success-tint: #E3EDE1;
  --color-warning: #A67C1F;
  --color-warning-tint: #F5ECD3;
  --color-danger: #8C2F1D;
  --color-danger-tint: #F5E1DC;

  --font-serif: 'Lora', serif;
  --font-sans: -apple-system, 'Segoe UI', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
}

html, body, #root {
  background-color: var(--color-canvas);
  color: var(--color-ink);
  font-family: var(--font-sans);
}
```

And in `apps/web/index.html`, replace the existing Inter/JetBrains Mono
font links with the Lora/IBM Plex Mono pair shown in section 2.

## 9. Do / Don't

| Do | Don't |
|---|---|
| Hairline borders | Drop shadows, glow, blur |
| One accent color, used sparingly | Multiple saturated accent colors |
| Serif for content the user reads | Sans-serif for everything |
| Sharp/barely-rounded corners | Rounded pill badges |
| Text-only or hairline buttons | Filled gradient buttons |
| Flat, paper-colored canvas | Black or near-black canvas |
| Footnote-style citations | Chat-bubble `[1]` badges |
| A bordered "stamp" for confidence | A progress bar or raw percentage as the primary signal |

If a future screen doesn't fit anywhere in this document, the fallback
question is: "would this choice look at home in a library catalog, or
in a tech dashboard?" If the answer is dashboard, it's the wrong choice
for this app.
