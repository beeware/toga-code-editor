# Deferred minors

Findings from the per-task and final reviews that were parked rather than fixed. None block merge.

## Documentation

- README: the `uv build --wheel` block follows a block that ends in `cd examples/editor`; say it runs from the repository root.
- README: the usage snippet has an unused `import toga`.
- README: the token-kind list omits `TEXT`; add a clause that `TEXT` is never styled.
- README: doesn't mention that the example pins the wheel filename and version, and the example's `pyproject.toml` comment says `uv build` where the README says `uv build --wheel`.
- README: "the rest of the layout stays put" for the Android keyboard lacks the edge-to-edge caveat (`ADJUST_RESIZE` is deprecated since API 30 and ignored under enforced edge-to-edge on Android 15 with target SDK 35+).

## Packaging and CI

- `pyproject.toml`: no upper bound on `toga-core`, while the spec says the package supports a pinned range; add `< 0.6` or reword the limitation.
- CI is one job with two steps while the plan's constraint wording says two jobs; the brief mandated one job, so this is wording only.

## Interface (`code_editor.py`)

- `_pending_rehighlight` is untyped (`asyncio.Task | None`).
- Construction calls `set_highlights` up to three times (value, theme, language); measured negligible, worth watching on real backends.
- An exception inside `_rehighlight()` raised from the debounce task is only reported when the task is collected; a done callback would surface it immediately.
- `DEFAULT_THEME` is a mutable module dict returned by `editor.theme`; `MappingProxyType` would prevent cross-editor mutation.

## Highlighting (`highlighting.py`)

- The token-table comment is muddled; reword to "most-specific first; anything unmatched, including bare `Name`, is `TEXT`".
- `language_for_filename` converts with `str(path)`; `os.fspath(path)` is the correct conversion for an arbitrary `PathLike`.
- `Style.color` is annotated `Color | str` but is always a `Color` after `__post_init__`.
- A zero-length span would raise `IllegalArgumentException` with `SPAN_EXCLUSIVE_EXCLUSIVE` on Android; no lexer produces one today; a `span.end > span.start` check in `merge_spans` closes it for all backends.

## Tests

- Nothing pins `Operator.Word` → `KEYWORD` precedence; adding `and` to the snippet would.
- The debounce test doesn't pin cancel behavior; assert `_pending_rehighlight is None` after a programmatic `value =` that follows `simulate_change()`.

## macOS (`cocoa_code_editor.py`)

- `smartInsertDeleteEnabled` and `richText` are still on; pasted rich text keeps attributes the re-highlight never resets. Overriding `paste:` with `pasteAsPlainText:` is the conventional fix.
- `draw_line_numbers` passes a view-space visible rect as container coordinates while adding `inset.height`; harmless with the zero default inset, inconsistent.
- `utf16_line_starts` runs over the whole text on every keystroke and the full range is repainted on every pause; measured at 8 ms for 5000 lines, will lag on very large files.

## iOS (`iOS_code_editor.py`)

- `gutter_label` allocates an `NSMutableDictionary` and `NSAttributedString` per visible line per draw; cache the attributes and invalidate in `set_font` (same on macOS).
- `constrain_placeholder_label` copies Toga's four constraints to keep one handle; could pick the leading constraint out of `native.constraints` after `super()`.
- The `base_font is not None` guards are inconsistent with the macOS sibling; keep everywhere or note why iOS differs.
- `rebuild_attributes` guards the `UIFont` but not the descriptor; `fontDescriptorWithSymbolicTraits` can return nil for a custom font without a bold or italic face.
- Emoji inside styled runs rendered as boxes in the iOS 26.3 simulator; closed as environmental (Toga's stock widget shows the same), still owed a physical-device check, including CJK and Cyrillic in bold and italic runs.

## Android (`android_code_editor.py`)

- `set_highlights` doesn't repost the gutter updater; a bold or italic `StyleSpan` can reflow text without a size or text change, mostly with proportional fonts.
- Each keystroke posts an uncoalesced gutter `Runnable`; `removeCallbacks` before `post` would coalesce them. Span removal and re-add is one JNI call each.
- The gutter color is a one-time snapshot of the hint color; the gutter `TextView` could also be marked not important for accessibility.
- `self.spans` is stored but never read (brief-mandated), and the "next change will post again" comment is stale now that the layout listener exists.
- `TogaGutterTouchListener` has no automated test; the Android backend is emulator-verified only.
- The keyboard-resize default was verified on API 31 only; verify on an API 35+ emulator.

## Example app (`examples/editor`)

- `SAMPLES.iterdir()` is unfiltered; a stray `.DS_Store` would raise on `read_text`.
- The Android section hard-codes the wheel filename and version, so a version bump breaks the Android build and a stale wheel deploys old code silently.
- The two-row toolbar also applies on desktop; could be conditional on platform.
