# PaperTrace branding and English copy QA

Scope: the selected second brand concept and English service copy, applied to the existing frontend. The paper reader layout, report structure and assessment calculations are outside this change.

Capture filenames below identify local QA evidence retained with the development task; the captures are not published application assets.

Source visual truth: `reference.png` (1536 × 1024).

Implementation: the local development preview, using an existing saved assessment without another model run.

## Comparison history

1. Desktop capture: `desktop-reader.png` (1440 × 960 CSS/pixels, 1×). Header lockup capture: `header-lockup.png` (128 × 28). The transparent asset's gutters are framed in CSS, retaining the icon/wordmark proportions and letterforms.
2. Narrow captures: `mobile-390.png` (390 × 844) and `mobile-320.png` (320 × 740), same completed-report state. At 320 px the full wordmark leaves insufficient space for the assessment tab strip. **[P2]** Use the same icon alone below 381 px and retain the accessible PaperTrace home label; recapture before passing.

3. Applied the compact-brand fix below 381 px, retaining the same image and accessible name. Post-fix evidence: `mobile-320-final.png`. At 320 px the brand occupies 37 px including its separator, leaving 91 px for the horizontally scrollable assessment tabs. Document width remains 320 px. The new-assessment control, tabs, History, copy and export remain reachable. No actionable P0/P1/P2 brand findings remain.

## Full and focused visual comparison

Combined evidence: `comparison-final.png`.
The comparison was rendered in the browser from `comparison.html`, putting the selected source and actual application capture in the same image. It includes the full reference, the existing real-report page, the two lockups at the same 128 × 28 CSS size enlarged 4× for inspection, and actual 16/32/48 px icon samples.

The source is a brand concept board, not a complete replacement app screen. Only its brand identity and compact header placement are the visual target. The source's enlarged toolbar was normalized to the existing 40 px app header; unrelated app typography and layout were retained. Desktop capture is 1440 × 960 at 1×. The source is 1536 × 1024. The implementation detail is a 128 × 28 screenshot enlarged for comparison; its raster interpolation is not treated as a design mismatch against the high-resolution source. Sharpness was also checked in the native-size application capture.

## Required fidelity surfaces

- **Fonts/typography:** the supplied PaperTrace wordmark is retained as image artwork, with the selected casing, weight and spacing. It does not depend on a substitute font loading. Existing product text keeps its original fonts.
- **Spacing/layout:** the lockup is framed at 128 × 28 px, proportionally reduced to 110 × 24 on narrow screens, and shown as its 28 px icon below 381 px. The subtle separator follows the selected concept. No stretching or toolbar height change.
- **Colors/tokens:** the artwork preserves the selected blue identity on the existing pale-blue chrome; the separator uses the existing line token. Existing content colors are unchanged.
- **Image quality:** transparent PNG assets load with their expected natural dimensions. No opaque white tile is visible. Icon, folded corner, two text strokes and round anchor remain recognizable at native sizes. Favicon samples at 16/32/48 px were viewed together in the comparison. CSS framing removes the horizontal asset's transparent gutters from the rendered layout.
- **Copy/content:** the home link, document title/description, report heading, helper UI and guide/server identity all say PaperTrace. Tagline: “Follow the evidence.” The slogan is available on the brand tooltip, matching the compact header treatment rather than adding a new page section.

## Interaction and implementation checks

- Brand home link navigates from the existing report to the submission page.
- Existing report opens and Paper/Report switching remains functional; report heading uses PaperTrace.
- Help panel opens/closes and its visible guide and prompt labels use PaperTrace. The helper service was restarted with the new identity; no model question was submitted.
- Browser title and favicon link point to the new brand. Brand accessible name is `PaperTrace home`, including icon-only mode.
- Browser console: no errors/warnings in the final inspected application state or comparison page.
- Frontend tests, including English-copy and assistant regressions: 96 passed. Lint, production build, assistant guide check and diff whitespace check passed. Final production build includes the responsive correction.

## English copy verification

- Reproduced Chinese validation notes in saved quality reports and confirmed their English equivalents on the rendered report. Page corrections, evidence IDs and verification status retain their meaning.
- Checked the quality report, combined printable document, saved failure messages, current credibility paper/report views and unknown progress-step fallback.
- Assistant responses use English regardless of input language. Offline integration tests cover historical Chinese assistant turns and rejected Chinese output; no real model calls were needed.
- Original source quotations, author metadata and numerical assessment results remain intact. The display compatibility layer does not rewrite stored assessments.

## Follow-up polish

- **[P3]** The production PNGs are generated extractions of the selected concept, not an original vector master. Minor curve/edge differences become apparent when greatly magnified; native-size header and favicon rendering were accepted. The standalone mark has a slightly lower visual center in its canvas, without clipping at the checked sizes.
- Existing report layout issues at very narrow widths and existing icon-only control labels are outside this branding change; this is not a whole-product accessibility or report-layout certification.

## Implementation checklist

- [x] Add selected mark/wordmark assets and favicon.
- [x] Replace visible product naming and metadata.
- [x] Correct narrow-screen navigation crowding.
- [x] Compare selected reference with real browser captures.
- [x] Run existing checks and preserve the working preview.

final result: passed
