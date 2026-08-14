# 01 — Widen reader + book metrics

Status: resolved

Type: task

## What

Update `web/player.html` CSS:

- `--reader-width` ≈ book measure (max ~46–48rem / ~68–70ch; higher `vw` so mid-width desktops aren’t capped early)
- `#text`: ~1.4rem / line-height ~1.78
- Lightly adjust `main` and `.dock` padding for the wider stage
- Keep `@media (max-width: 860px)` behavior as-is (mobile deferred); only avoid regressing the mid breakpoint harder than needed

## Done when

Desktop reader matches the spec acceptance; theme and chrome unchanged.

## Answer

Updated `web/player.html`:
- `--reader-width: clamp(28rem, 62vw, 48rem)` (mid breakpoint 42rem max)
- `#text`: 1.4rem / line-height 1.78; title/section-heading lightly scaled
- `main` / `.dock` padding/gap nudged
- Copied to `output_audio/player.html` for local serve
