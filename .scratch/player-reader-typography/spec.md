# Spec: Desktop reader typography (book measure)

## Goal

On desktop, the web player reader should read like a book: wider column (~60–70 characters), slightly larger body type, comfortable line-height. Keep the existing dark-green theme and layout chrome (sidebar, progress rail, dock).

## Decisions (from grilling)

- Pain: narrow text column (“столбик”), not overlapping lines
- Primary viewport for this slice: **desktop**
- Target feel: paper book — larger + air, ~60–70 characters
- Widen `--reader-width` only (sidebar/rail stay); do not collapse sidebar or remove rail
- Body: ~**1.4rem**, **line-height ~1.75–1.8** (replace 1.22 / 2.05)
- Mild tweaks to `main` / dock padding OK
- Theme, font families, palette unchanged
- **Mobile nav / drawer deferred** to a later ticket
- Out of scope: speed, hotkeys, bookmarks, localStorage, visual redesign

## Acceptance

- On a wide desktop (as in the user’s screenshot): reader is not a thin column; body text is comfortable to follow by eye
- Sidebar, progress rail, and dock remain in place without redesign
- Source of truth: `web/player.html` (copied to `OUT_DIR` on `make serve` / refresh-web)

## Out of scope

- Phone layout / chapter drawer
- Playback UX extras
- Restyle / new aesthetic
