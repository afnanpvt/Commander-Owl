# Commander Owl brand

## Idea
A calm, watchful owl that keeps an eye on your Claude sessions and powers the laptop down when they finish. The mascot is the product's voice: it is quiet when things are idle, busy when Claude is working, and alert when a power action is counting down.

## Logo and mascot
- **Mascot:** the 3D owl in the dashboard hero is always on and has no setting to turn it off. It is built in code (Three.js), so its colours come from the same tokens below. `commander-owl-mascot.svg` (navy body, cream eyes, chest chevron) is the flat version: the header mark, and the fallback if WebGL is unavailable.
- **Mark:** `commander-owl.svg`, the power-eye owl. Use for favicons and repository avatars.
- **Clear space:** keep at least one eye-width of space on every side.
- **Minimum size:** 24 px for the mark, 40 px for the mascot. Below that, use the mark, not the mascot.
- **Do not:** recolour the eyes, add shadows or gradients, rotate the mascot, or place it on a busy photo.

## Colour
| Token | Hex | Use |
|---|---|---|
| `--ink` | `#1b2430` | Primary text, mascot body, primary buttons |
| `--cream` | `#f4f1ea` | Page background, mascot eyes |
| `--paper` | `#fbfaf6` | Cards and raised surfaces |
| `--amber` | `#e0a84a` | The single accent: countdowns, cancel, warnings |
| `--ok` | `#3f7d5c` | Working sessions |

Dark theme swaps the cream and ink values and keeps the amber accent. Amber is the only attention colour; do not add red for warnings. Amber text needs the dark amber ink (`#5c3d08`) for contrast.

## Type
- **Interface:** Geist, falling back to the system UI font.
- **Numbers and paths:** Geist Mono, so countdowns and session times line up.
- Headings use tight tracking (`-0.02em` and below). Body text stays at normal tracking.

## Motion
- Only transform and opacity are animated, plus the 3D owl's pose.
- The mascot breathes slowly when idle, blinks, and looks side to side when working. During a countdown it shakes slightly.
- When the system asks for reduced motion, the owl moves less. This follows the operating system setting; the app has no motion option of its own.
- Springs: default ease is `cubic-bezier(.2,.8,.2,1)`. No bounce on settings controls.

## Voice
- Short, plain sentences. Say what will happen and when: "Hibernate in progress", "Cancel now if you still need the machine."
- Never use exclamation marks for system events.
- Name sessions by their conversation title. Fall back to the folder only when there is no title.

## Trademark note
The owl concept sits near a well-known mascot's shape. Run a trademark and image search before a public launch, and keep the power-eye mark as the primary logo.
