# AudioEnhancerMAX Design Contract

## Signal Console

AudioEnhancerMAX is a local audio workstation, not a generic AI dashboard. Its interface should feel precise, calm, and inspectable: graphite work surfaces, violet for decisions, cyan for live signal state, and status colors reserved for outcomes that need attention.

This contract is the source of truth for product UI, public documentation, and visual evidence. The runnable reference is [docs/design-preview.html](docs/design-preview.html).

## Product principles

1. **Signal before decoration.** Prioritize the audio, measurement, next action, and resulting evidence.
2. **Local-first must be visible.** Show where processing occurs and when data can leave the Mac.
3. **Expert control, plain language.** Keep advanced capability available without making the default path cryptic.
4. **Claims need a confidence type.** Separate measurements, estimates, listening judgments, and research candidates.
5. **Density with calm.** Workstation views may be compact, but spacing, hierarchy, and alignment must prevent visual noise.

### Voice

Use short, factual sentences and active verbs. Name the action and consequence: “Normalize to −16 LUFS,” “Source audio stays on this Mac,” or “Estimated true peak: −1.1 dBTP.” Avoid superlatives, anthropomorphic AI language, vague promises, and unsupported “studio quality” claims.

## Foundation tokens

The values below mirror `frontend/css/style.css`. Change the application tokens first; update this document and the preview in the same pull request.

### Color

| Role | Token | Value | Use |
| --- | --- | --- | --- |
| Canvas | `--bg-primary` | `#080a0c` | Main application background |
| Shell | `--bg-secondary` | `#0c0f11` | Navigation and fixed chrome |
| Raised surface | `--bg-tertiary` | `#14181c` | Selected and elevated regions |
| Panel | `--bg-card` | `#101418` | Work panels and grouped controls |
| Panel hover | `--bg-card-hover` | `#151a1f` | Interactive surface hover |
| Input | `--bg-input` | `#0b0e11` | Form and data-entry surfaces |
| Decision | `--accent-primary` | `#7457d9` | Primary actions, selection, edit state |
| Decision bright | `--accent-primary-light` | `#a791ff` | Text and focus-adjacent emphasis |
| Live signal | `--accent-secondary` | `#16bdd1` | Meters, progress, connected/live state |
| Live signal bright | `--accent-secondary-light` | `#4dd8e8` | Small high-contrast signal details |
| Confirmed | `--success` | `#10b981` | Completed and verified outcomes |
| Caution | `--warning` | `#f59e0b` | Review required; never decoration |
| Failure | `--error` | `#ef4444` | Errors and destructive consequences |
| Informational | `--info` | `#3b82f6` | Neutral system information |
| Primary text | `--text-primary` | `#eef2f5` | Headings, values, active labels |
| Secondary text | `--text-secondary` | `#aab3bb` | Body copy and explanations |
| Tertiary text | `--text-tertiary` | `#78838d` | Metadata only; check contrast at small sizes |

Violet means a person can decide or change something. Cyan means the system is live, measuring, or progressing. Green means an outcome is confirmed. Amber and red must not be used as decorative accents. Never encode state by color alone; pair it with text, shape, or an icon.

### Type

Use Inter when it is already bundled by the product, followed by `-apple-system`, `BlinkMacSystemFont`, and `sans-serif`. Do not add a remote font dependency to the local app.

- Page title: 32-40 px, 700, line-height 1.1.
- Section title: 20-24 px, 650-700, line-height 1.25.
- Body: 15-16 px, 400-500, line-height 1.55-1.65.
- UI label: 12-14 px, 600, line-height 1.3.
- Eyebrow/status: 11-12 px, 700, uppercase, `0.08em` letter spacing.
- Measurements, hashes, timestamps, and logs: `ui-monospace`, SFMono-Regular, Menlo, monospace with tabular numbers.

Sentence case is the default. Reserve all caps for compact categories, never paragraphs or buttons.

### Space, shape, and depth

- Spacing follows a 4 px base: `4, 8, 12, 16, 24, 32, 48`.
- Application gutters: 16 px compact, 24 px standard, 32 px spacious.
- Radii: 5 px small, 6 px standard, 8 px large. Do not turn every control into a pill.
- Default border: 1 px `#252b31`; interactive hover: `#3a444d`.
- Use `0 1px 2px rgba(0,0,0,.35)` for small lift and `0 8px 24px rgba(0,0,0,.26)` for overlays.
- Avoid ambient glow. A restrained cyan or violet halo is acceptable only to identify an active signal or current decision.

### Focus and motion

Every interactive control must expose a visible `:focus-visible` state: a 2 px cyan outline with at least 2 px offset. Keyboard focus must never depend on a color change inside the control.

Use the existing 150 ms, 250 ms, and 400 ms motion timings. Motion should explain a state transition, progress, expansion, or completion, not decorate idle screens. Honor `prefers-reduced-motion: reduce` by removing non-essential animation and smooth scrolling.

## Layout

### Application workspace

- Keep navigation stable and the primary task visible without horizontal scrolling.
- Use a narrow persistent rail on wide screens and a disclosure/navigation sheet below the compact breakpoint.
- Place the current file, processing state, and primary action in the first scan path.
- Group controls by consequence rather than by implementation module.
- Preserve alignment between labels, values, meters, and evidence so changes are easy to compare.

### Documentation and marketing

Use more white space than the application. Alternate concise editorial explanation with concrete proof: screenshots, measurements, compatibility, or limitations. Avoid repeating identical feature cards and decorative dashboard mockups.

### Breakpoints

- **≥ 1024 px:** persistent navigation and multi-column work area.
- **640-1023 px:** compact navigation; two columns only when content remains readable.
- **< 640 px:** one-column flow, 16 px gutters, full-width primary controls, and no clipped tables or charts.

Do not merely shrink the desktop layout. Reorder content so task, state, and action remain first.

## Interface patterns

### Navigation

The active destination uses a cyan edge or marker plus stronger text. Violet remains available for an explicit mode or decision inside the page. Icons require text labels in primary navigation.

### Buttons and controls

- Primary button: violet fill, concise verb, one per decision area.
- Secondary button: graphite surface and visible border.
- Destructive button: red only when the consequence is real and stated.
- Disabled controls retain legible labels and explain why they are unavailable when the reason is not obvious.
- Sliders show the current numeric value and unit; toggles use positive labels such as “Preserve source.”

### Panels

A panel needs a title, purpose, and relationship to the task. Avoid grids of identical cards. Use panels to group controls, compare states, or hold evidence, not to decorate empty space.

### Status and proof surfaces

Status chips are compact supporting metadata, not the only status signal. Pair them with a plain-language sentence and, where applicable, a timestamp or measured value. A proof surface should identify the method, result, confidence type, and next review action.

### Waveforms and audio data

- Waveforms are cyan on graphite; selections or edit decisions are violet.
- Show a time axis, scale, or named metric when the visual is used as evidence.
- Keep the source and processed views visually comparable.
- Clipping, threshold exceedance, or missing samples use semantic warning/error markers plus text.
- Never use a decorative waveform to imply analysis that was not performed.

## Evidence language

Every quality or capability claim in the UI, release material, or generated report should use one of these labels:

| Label | Meaning | Example |
| --- | --- | --- |
| **Measured** | Directly calculated from the current artifact with a stated method | “Measured integrated loudness: −16.0 LUFS” |
| **Estimated** | Derived by an approximation with known limits | “Estimated true peak: −1.1 dBTP” |
| **Subjective** | Human listening judgment or preference | “Subjective review: voice sounds more present” |
| **Research candidate** | Experimental path that is not a shipped or validated capability | “Research candidate: streaming source separation” |

Never present an estimate as a measurement, a listening preference as a fact, or a roadmap experiment as a released feature.

## Accessibility checklist

- Semantic heading order and landmarks are intact.
- All actions are keyboard reachable in a logical order.
- Focus is visible against every surface.
- Labels, errors, progress, and status do not rely on color alone.
- Body and control text meet WCAG AA contrast; large measurements remain readable at 200% zoom.
- Dynamic progress has an accessible name and appropriate live-region behavior.
- Charts and waveforms have a text summary or accessible description.
- Touch targets are at least 44 × 44 px where touch use is expected.
- The layout works at 320 px width and with reduced motion enabled.

## Do / don't

| Do | Don't |
| --- | --- |
| Use cyan for observable signal state | Use cyan and violet interchangeably |
| Put a unit beside every audio measurement | Show unexplained scores or percentages |
| State local/cloud boundaries at the decision point | Hide external processing in legal copy |
| Use a single dominant action per region | Fill every panel with competing CTAs |
| Show limitations beside evidence | Turn caveats into low-contrast footnotes |
| Use compact, square-cornered workstation controls | Apply glass blur, glow, or pill shapes everywhere |
| Preserve the source and make edits reversible | Imply an irreversible edit is “smart” by default |

## Prompt for future agents

> Design this AudioEnhancerMAX surface in the **Signal Console** language. Preserve the graphite foundation and existing token values. Use violet only for decisions, cyan for live signal or measurement, green for confirmed success, and amber/red for real cautions or failures. Keep workstation layouts dense but calm, use square 5-8 px radii, visible keyboard focus, semantic HTML, responsive task-first reflow, and reduced-motion support. Label product claims as Measured, Estimated, Subjective, or Research candidate. Avoid generic glassmorphism, excessive glow, identical card grids, unsupported quality claims, and remote runtime dependencies.

## Inspiration and originality

The document structure follows the emerging `DESIGN.md` convention and was informed by the [VoltAgent awesome-design-md catalog](https://github.com/VoltAgent/awesome-design-md). AudioEnhancerMAX's Signal Console identity, token values, product language, and UI rules are original to this project; reference products are not a source of copied brand assets, proprietary typography, layouts, or marketing copy.
