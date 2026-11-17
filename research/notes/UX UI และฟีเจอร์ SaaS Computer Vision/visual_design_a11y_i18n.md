# Visual Design, Accessibility and Thai i18n for LabelDesk (CV/ML SaaS)

Research date: 2026-10-31. Scope: visual language, WCAG 2.2 AA, dashboard component patterns, Thai typography and i18n, perceived performance for long ML jobs, and (added) the Liquid Glass and Material 3 Expressive style direction. Tier labels in Inferences: **[MUST]**, **[SHOULD]**, **[DIFF]** (differentiator).

## 1. Visual design of leading CV/ML tools (themes, density, typography, class colours, status colours, data-viz)

### Takeaway
There are few primary sources on competitors' visual language. The documented facts are: Roboflow Annotate offers both a light and a dark scheme, Linear builds its themes in the perceptually uniform LCH space from three inputs (including a contrast input that gives high-contrast themes), and class colours should come from algorithmic maximum-distinctness palettes (Glasbey) or CVD-safe sets (Okabe-Ito). Confusion matrices conventionally use viridis.

### Cited Findings
- Roboflow Annotate has had two colour schemes, light mode and dark mode, since its 2023 launch post. Users switch between them with a toggle at the bottom left of the annotation tool. — [Roboflow blog, "Improving Collaboration and Productivity"](https://blog.roboflow.com/annotation-updates/) (2023, older than the preferred window)
- Linear rebuilt its theme generation in LCH instead of HSL because LCH is perceptually uniform ("a red and a yellow color with lightness 50 will appear roughly equally light"). Each theme went from 98 hand-set variables to 3 inputs: base colour, accent colour and contrast. The same generator now produces the main light and dark themes. — [Linear, "How we redesigned the Linear UI"](https://linear.app/now/how-we-redesigned-the-linear-ui)
- Linear's contrast input can generate very high-contrast themes for accessibility. LCH also helps with elevation layers such as background, panels, dialogs and modals. — [Linear](https://linear.app/blog/how-we-redesigned-the-linear-ui)
- Background technique: dark mode through inverted lightness variables works better in LCH because LCH lightness is perceptually meaningful. — [Lea Verou, 2021](https://lea.verou.me/2021/03/inverted-lightness-variables/) (2021, older)
- Most hand-picked categorical palettes hold fewer than about 25 colours. Glasbey et al. (2007) choose each new colour to be as perceptually different as possible from the colours already chosen, within an allowed colour space. — [colorcet: Glasbey colormaps for categorical data](https://colorcet.holoviz.org/user_guide/Categorical.html)
- The original Glasbey paper measures distance with a Euclidean metric in CIE-LAB to build maximally distinct colour sets for unordered labels in categorical images. — [Glasbey et al., Strathprints](https://strathprints.strath.ac.uk/30312/) (2007, older but foundational)
- The MIT-licensed `glasbey` Python library can constrain lightness and chroma ranges, extend an existing palette such as `tab10`, seed a palette from given colours, and refine it by hill-climbing. `create_block_palette` makes groups of related hues for hierarchical classes. — [glasbey docs](https://glasbey.readthedocs.io/en/latest/creating_palettes.html); [block palettes](https://glasbey.readthedocs.io/en/stable/creating_block_palettes.html)
- Okabe and Ito designed their palette for Color Universal Design so that most people with red–green deficiency can tell the colours apart. Wong popularised it in "Points of view: Color blindness", Nature Methods 8:441 (2011), DOI 10.1038/nmeth.1618. — [factoextra_palette docs](https://rdrr.io/cran/factoextra/man/factoextra_palette.html); [discovr okabe_ito_pal](https://rdrr.io/cran/discovr/man/okabe_ito_pal.html)
- An R palette study found that Okabe-Ito performs "even better", particularly for deuteranope viewers. — [Zeileis & Murrell, "Coloring in R's Blind Spot", arXiv 2303.04918](https://arxiv.org/pdf/2303.04918) (2023)
- Okabe-Ito includes, among others, #0072B2 (blue), #E69F00 (orange) and #009E73 (bluish green). It is an 8-colour set that includes black. — [cvdsafe on PyPI](https://pypi.org/project/cvdsafe/) (full hex list not verified against the primary jfly source)
- scikit-learn's `ConfusionMatrixDisplay` uses `cmap='viridis'` by default, from version 1.0 through the current docs. — [scikit-learn ConfusionMatrixDisplay](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ConfusionMatrixDisplay.html)
- Sama's annotation tool lets annotators adjust brightness and contrast with keyboard shortcuts and lists all shortcuts in the Help menu. Image adjustment is an established canvas feature. — [Sama docs: brightness and contrast](https://docs.sama.com/brightness-and-contrast-updated) (date unclear)

### Inferences
- **[MUST]** Ship both a light and a dark theme from day one. Roboflow already does, and a dark canvas surround is the norm in image tools. Keep the image's own pixels untouched; theme only the chrome around it.
- **[MUST]** Assign class colours from a fixed, deterministic palette keyed by class index, not random hues. Use Okabe-Ito (8 colours) for the first classes, then extend with Glasbey (seeded with Okabe-Ito) for projects with many classes. Never rely on colour alone: show the class name label or chip on hover or selection (see WCAG 1.4.1 in section 2).
- **[SHOULD]** Generate tokens in OKLCH/LCH with Tailwind v4 (which uses OKLCH natively), following Linear's base, accent and contrast approach. A high-contrast theme is then nearly free.
- **[SHOULD]** Use a sequential, perceptually uniform map (viridis) for confusion matrices and heatmaps, and a categorical palette for per-class training curves, so they match the ML conventions users know from scikit-learn and matplotlib.
- **[DIFF]** Per-class colour override, a CVD simulation preview of the class palette, and a canvas brightness, contrast and opacity control panel.

### Gaps
- I found no primary documentation of the visual systems of V7, Encord, Labelbox, Weights & Biases or Hugging Face (typography, density, status colours). The searches returned only aggregator pages. The report writer should not claim specifics about them.
- I found no published research comparing dark and light annotation canvases for labelling accuracy or fatigue.
- I found no primary source on status-colour conventions specific to ML job states.

## 2. Accessibility: WCAG 2.2 AA, canvas annotation challenges, vendor VPATs

### Takeaway
WCAG 2.2 has been a W3C Recommendation since 5 October 2023. Its new AA criteria hit annotation tools directly: 2.5.7 Dragging Movements requires a single-pointer alternative to drag-to-draw, 2.5.8 sets 24×24 px minimum targets for dense toolbars, and 2.4.11 forbids focus hidden under sticky panels. Non-text contrast (1.4.11, 3:1) applies to UI controls, focus and selection states, and chart graphics. I could not find a published VPAT/ACR for any CV labelling vendor.

### Cited Findings
- WCAG 2.2 became a W3C Recommendation on 5 October 2023. It adds 9 success criteria and removes 4.1.1 Parsing as obsolete. — [W3C: What's New in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)
- New criteria and levels: 2.4.11 Focus Not Obscured (Minimum) AA; 2.4.12 Focus Not Obscured (Enhanced) AAA; 2.4.13 Focus Appearance AAA (minimum indicator size, 3:1 change of contrast); 2.5.7 Dragging Movements AA (single-pointer alternative unless dragging is essential); 2.5.8 Target Size (Minimum) AA; 3.2.6 Consistent Help A; 3.3.7 Redundant Entry A; 3.3.8 Accessible Authentication (Minimum) AA; 3.3.9 Accessible Authentication (Enhanced) AAA. — [W3C](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)
- 2.5.8: pointer targets must be at least 24×24 CSS px. Exceptions cover adequate spacing, inline text, and an equivalent control elsewhere that meets the size. The AAA criterion 2.5.5 uses 44 px. — [WebAIM WCAG 2.2 checklist](https://webaim.org/standards/wcag/wcag22); [Deque](https://dequeuniversity.com/resources/wcag-2.2)
- 2.4.11: a keyboard-focused component must not be entirely hidden by author-created content, such as sticky headers or overlays. — [W3C](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)
- Some secondary sources mislabel the levels. One puts 2.4.11 at Level A. Use the W3C documents. — [Deque summary noting sources](https://dequeuniversity.com/resources/wcag-2.2); [W3C](https://w3.org/WAI/standards-guidelines/wcag/new-in-22/)
- 1.4.11 Non-text Contrast (AA): user interface components and meaningful graphics, including charts and icons, need 3:1 contrast against adjacent colours. Visual cues for states such as selected and focused also need 3:1. Decorative graphics are exempt. — [W3C Understanding 1.4.11 (WCAG 2.2)](https://w3.org/WAI/WCAG22/Understanding/non-text-contrast)
- The whiteboard SDK tldraw states that it is WCAG 2.2 AA compliant, with screen reader support and keyboard navigation of canvas shapes. This is a reference point for canvas accessibility, but tldraw is not an annotation vendor. — [tldraw accessibility](https://tldraw.dev/features/composable-primitives/accessibility)
- Webflow shipped keyboard navigation of canvas elements in its builder. This is a precedent for making a visual canvas operable by keyboard. — [Webflow updates](https://webflow.com/updates/keyboard-navigate-canvas-elements-in-build-mode)
- An ACR is the completed VPAT (an ITI template). Buyers use it to assess conformance, and a WCAG 2.2 edition exists (VPAT 2.5Rev, February 2025). — [VPAT 2.5Rev WCAG Feb 2025 template](https://design.sis.gov.uk/VPAT2.5Rev_WCAG_February2025.docx); [accessible.org VPAT checklist](https://accessible.org/vpat-requirements-checklist/)
- A search for a Labelbox VPAT/ACR returned no Labelbox document. — [search result set, see the VPAT checklist](https://accessible.org/vpat-requirements-checklist/) (negative finding)

### Inferences
- **[MUST]** Meet WCAG 2.2 AA for all non-canvas UI: dashboards, tables, forms and auth. That means 4.5:1 body text contrast (WCAG baseline), 3:1 for controls and focus rings, visible focus never hidden under sticky toolbars or toasts, 24×24 px minimum hit area for toolbar icons, and no cognitive-test login (3.3.8; prefer passkeys or OAuth and allow password paste).
- **[MUST]** 2.5.7 for the canvas: every drag action needs a click-based alternative. Draw a box by click-click on two corners, draw a polygon by clicking each vertex, and move or resize with arrow keys (Shift for larger steps) and numeric X/Y/W/H inputs in the side panel.
- **[MUST]** The canvas must be keyboard operable. Use Tab or `[`/`]` to cycle annotations, Delete to remove, number keys for class assignment, and provide a shortcut cheat sheet like Sama's Help menu. Mirror the canvas state into an accessible DOM list of annotations (class, coordinates, status) that screen readers can use. Canvas pixels themselves are not accessible.
- **[SHOULD]** Selected and hovered annotation outlines need 3:1 against the image. Use a double stroke (dark outer, light inner) so the outline holds up on any image content.
- **[DIFF]** Publish a WCAG 2.2 ACR (VPAT 2.5) for LabelDesk. No CV labelling competitor was found publishing one, so it would set LabelDesk apart in enterprise and public-sector procurement.

### Gaps
- No ACRs, VPATs or accessibility statements were found for Roboflow, V7, Encord, Labelbox or CVAT. Absence in search results does not prove they don't exist.
- No authoritative W3C guidance was found specifically on accessible image-annotation canvases. The Understanding document for 2.5.7 was not fetched.
- No research was found on screen-reader use of bounding-box annotation.

## 3. Design-system patterns for data-heavy dashboards

### Takeaway
The only design-system specifics I verified come from Carbon. It uses skeleton states, not inline loading, for full-page loads. Inline loading is for actions inside tables, buttons and modals, with errors surfacing as inline notifications. Carbon ships a `DataTableSkeleton` component. Guidance from Atlassian, Primer, Material 3 and shadcn/ui was not retrieved.

### Cited Findings
- Carbon inline loading must not be used for full-page loads; use skeleton states instead. Inline loading can appear inside a table, after clicking a primary or secondary button, or inside a modal. In the error state, an inline notification or form error handling should appear. — [Carbon: Inline loading usage](https://carbondesignsystem.com/components/inline-loading/usage/)
- Carbon React provides `DataTableSkeleton` alongside form skeleton components. — [Carbon React loading/progress docs (tessl mirror)](https://tessl.io/registry/tessl/npm-carbon--react/files/docs/loading-progress.md)
- Carbon has separate Pattern pages for Empty states, Loading and Notifications, plus a Data table component page. — [Carbon Design System](https://www.carbondesignsystem.com/search)

### Inferences
- **[MUST]** Every list or table view needs four designed states: loading (a skeleton matching the final layout), empty (explanation plus a primary action, e.g. "Upload images"), error (an inline message with retry), and populated.
- **[MUST]** Use row virtualisation for image grids and annotation tables with thousands of rows, and keep filters and sort in the URL so views can be shared.
- **[SHOULD]** A command palette (Cmd/Ctrl+K) for navigation and actions, in the style of Linear and other dev tools. Keyboard-first is consistent with the canvas shortcut model.
- **[SHOULD]** Toasts only for non-blocking confirmations. Put errors that need action inline (the Carbon pattern), and never place a toast over the focused element (WCAG 2.4.11).
- **[SHOULD]** Base components on shadcn/ui (Radix primitives, Tailwind) for a React 19 + Tailwind v4 stack. This is an inference from the stack fit; it was not verified against shadcn docs in this pass.

### Gaps
- Atlassian, GitHub Primer, Material 3 and shadcn/ui guidance on tables, filters, toasts and empty states was not retrieved within the tool budget. The report writer should source these separately before citing them.
- Carbon's Data table, Empty states and Notifications pages were not fetched in full.

## 4. Thai internationalisation: fonts, line height, line breaking, mixed text, numbers and dates

### Takeaway
Thai has no spaces between words (spaces separate phrases), stacks marks above and below the base consonant, and has native digits. W3C's Thai layout document is still a draft with many empty sections. For UI fonts, IBM Plex Sans Thai (looped and loopless) and Anuphan (a loopless Thai companion to IBM Plex Sans, by Cadson Demak, OFL) pair naturally with a Plex-based Latin UI. `Intl.Segmenter` (Baseline) supports Thai word segmentation for truncation and selection. Thai locales default to the Buddhist Era (+543) unless `-u-ca-gregory` is set.

### Cited Findings
- The W3C "Thai Script Resources" (thai-lreq) is a Group Note Draft dated 20 March 2026, edited by Richard Ishida and not endorsed by W3C. Its sections on line breaking (8.1), segmentation (6.2), line height (8.4), fonts (5.1) and data formats (7.7) mostly pose open questions or link out. — [W3C thai-lreq](https://www.w3.org/TR/thai-lreq/)
- "Spaces separate phrases, rather than words" in Thai, and "it can therefore be difficult to algorithmically detect syllable boundaries." — [W3C thai-lreq §2](https://www.w3.org/TR/thai-lreq/)
- Thai composite vowels can use up to 4 glyphs plus a tone mark, and glyphs can surround the base consonant on up to 3 sides. Thai has native digits, and they are commonly used. — [W3C thai-lreq §2](https://www.w3.org/TR/thai-lreq/)
- Thai justification adjusts space between phrases, with some adjustments to inter-character spacing. — [W3C thai-lreq (2024 draft)](https://www.w3.org/TR/2024/DNOTE-thai-lreq-20240705/)
- IBM Plex Thai includes a looped style (more familiar to older readers) and a loopless style (simplified, more relaxed), each in seven weights, free on Google Fonts. — [fontpad: IBM Plex Thai](https://www.fontpad.co.uk/?p=1772)
- Anuphan is a loopless Thai typeface by Mint Tantisuwanna at Cadson Demak, based on the Latin IBM Plex Sans. It is not a modification of IBM Plex Sans Thai. It is licensed under OFL. — [Cadson Demak / Anuphan GitHub](https://github.com/cadsondemak/Anuphan); [Google Fonts: Anuphan](https://fonts.google.com/specimen/Anuphan/about)
- A font designer had to adjust vertical metrics (which affect line spacing) to support Thai vowels and tone marks. Clipping is often a font-metric issue, not only a CSS one. — [Pattaya font notes, RightFont](https://rightfontapp.com/family/pattaya)
- Mis-anchored Thai tone marks in fonts are a known font-engineering problem. — [Glyphs forum: Problem of Thai marks](https://forum.glyphsapp.com/t/problem-of-thai-marks-tone-marks/375)
- `Intl.Segmenter` is Baseline across browsers and supports `granularity: "word"`. Thai text such as สวัสดีครับ segments into สวัสดี + ครับ, both marked `isWordLike`. — [web.dev: Intl.Segmenter is Baseline](https://web.dev/blog/intl-segmenter?hl=th); [lingo.dev example](https://lingo.dev/en/javascript-i18n/split-text-into-words)
- Thai word boundaries are contested even among linguists. Firefox's segmenter tests record ขนบนอก split as ขนบ + นอก, citing a Thai linguistics paper, so dictionary segmentation will sometimes differ from user expectations. — [Firefox Intl.Segmenter word tests](https://searchfox.org/firefox-main/source/js/src/tests/non262/Intl/Segmenter/word.js)
- Browsers break Thai lines at dictionary word boundaries under `word-break: normal`, and web-platform tests cover Thai `normal` and `keep-all` behaviour. — [W3C i18n tests: word-break results](https://www.w3.org/International/tests/html-css/line-break/results-word-break); [WPT css-text/word-break](https://searchfox.org/firefox-main/source/testing/web-platform/tests/css/css-text/word-break)
- Neural Thai word segmenters exist (AttaCut), which is relevant if server-side segmentation (search, tokenising labels) is needed. — [AttaCut, arXiv 1911.07056](https://arxiv.org/pdf/1911.07056) (2019, older)
- Thai locales default to Buddhist Era year numbering. ICU output: `th-u-ca-gregory` gives "29 ก.ย. 2020" while `th-u-ca-buddhist` gives 2563. — [Java supported calendars technote](https://www.eecs.yorku.ca/teaching/docs/java/technotes/guides/intl/calendar.doc.html); [W3C i18n list: Thai Buddhist calendar](https://lists.w3.org/Archives/Public/public-i18n-archive/2020JulSep/0611.html)
- Platforms that apply the Thai locale display BE years (+543) by default, which confuses users who expect CE. — [Mendix forum](https://community.mendix.com/link/space/app-development/questions/144408)

### Inferences
- **[MUST]** Font stack: Latin `IBM Plex Sans` (or Inter) with Thai `IBM Plex Sans Thai` or `Anuphan` (loopless, modern UI voice) as the second family, plus `Noto Sans Thai` as fallback. Self-host with `unicode-range` subsetting so English-only pages don't download Thai glyphs.
- **[MUST]** Give Thai text more line height than Latin, because of stacked marks above and below. Start at about 1.5–1.6 for body text (an inference; no source tested specific values) and avoid `overflow: hidden` with tight fixed heights on text containers, buttons, table cells and badges. Run visual QA with strings such as ปั่นป่วน and ญู/ฐู.
- **[MUST]** Never truncate Thai with naive `slice()`. Use CSS `text-overflow: ellipsis` or `Intl.Segmenter` (grapheme or word) so marks are not split from base consonants. Keep `word-break: normal` for Thai (avoid `break-all`).
- **[MUST]** Dates: format with `Intl.DateTimeFormat`. For a developer tool, default the Thai UI to Gregorian years (`th-TH-u-ca-gregory`) and offer BE as a user preference. Test in the target browser and Node runtime, because the region-qualified tag behaviour was not verified.
- **[SHOULD]** Use Arabic digits (0–9) for metrics, counts and IDs even in the Thai UI, because ML metrics and code contexts expect them. Use `font-variant-numeric: tabular-nums` in tables. Thai digits are "commonly used" in some contexts, but metric tables are not one of them (inference).
- **[SHOULD]** Mixed Thai and English: keep technical terms (mAP, epoch, bounding box, class) in English inside Thai sentences, and test layouts with Thai strings, which are often longer or shorter than English.
- **[DIFF]** Thai-aware search and label tokenising (Intl.Segmenter client-side, or a server-side segmenter) for class names and dataset search.

### Gaps
- No authoritative source gives a recommended CSS line-height for Thai UI text. W3C §8.4 is empty.
- No source compared the readability of IBM Plex Sans Thai, Noto Sans Thai and Sarabun for UI. Sarabun was not researched in this pass.
- The behaviour of `th-TH-u-ca-gregory` specifically in V8/SpiderMonkey/JSC was not verified from MDN or the ECMA-402 spec.
- Whether browser CSS line breaking and `Intl.Segmenter` share the same ICU Thai dictionary was not confirmed.

## 5. Performance perception and responsiveness for long-running ML jobs

### Takeaway
Nielsen's 0.1 s, 1 s and 10 s limits (from 1993, which NN/g says still hold) set the feedback rules. Under 1 s needs no loader. From 1–10 s, show an indeterminate indicator or skeleton. Beyond 10 s, show a percent-done indicator and let users leave. Skeleton screens fit full-page loads and must match the real layout. Training jobs lasting minutes to hours need a background-job pattern, not a waiting screen.

### Cited Findings
- Response-time limits: 0.1 s feels instantaneous and caused by the user; 1 s keeps flow of thought uninterrupted; 10 s is the limit for keeping attention. Between 1 and 10 s, users "feel at the mercy of the computer". The limits date from 1993 and NN/g says they still hold. — [NN/g: Website Response Times](https://nngroup.com/articles/website-response-times/); [NN/g video: 3 response time limits](https://www.nngroup.com/videos/3-response-time-limits-interaction-design/)
- For longer delays, use a percent-done indicator. For short waits, an animation signals the wait will soon end. — [NN/g response-time topic](https://www.nngroup.com/topic/response-time/)
- Nielsen also describes UX time scales from 0.1 s up to 100 years. — [Jakob Nielsen, "Time Scales of UX"](https://jakobnielsenphd.substack.com/p/time-scale-ux?open=false)
- A skeleton screen is a placeholder for full-page loads that reduces perceived loading time. NN/g describes three types: static-content-and-image, animated, and frame-display. If a page loads in under 1 s, no skeleton or spinner is needed. Skeletons do not replace performance optimisation. — [NN/g: Skeleton Screens 101](https://nngroup.com/articles/skeleton-screens/); [NN/g video: Skeleton vs progress bars vs spinners](https://www.nngroup.com/videos/skeleton-screens-vs-progress-bars-vs-spinners/)
- Skeletons that misrepresent the coming content or its position disorient users. — [Tim Kadlec, "Effective Skeleton Screens"](https://timkadlec.com/remembers/2020/11/skeleton-screens/) (2020, older)
- Carbon: skeletons for full-page loads, inline loading for in-context actions. — [Carbon inline loading](https://carbondesignsystem.com/components/inline-loading/usage/)

### Inferences
- **[MUST]** Canvas interactions (draw, select, pan, zoom, class change) must respond within 0.1 s. Apply them optimistically on the client and sync in the background, with visible rollback and a toast on failure.
- **[MUST]** Show skeletons matching the layout for dataset grids, the project dashboard and the model page. Show no loader for under 1 s (delay the loader by about 300–500 ms to avoid flashes; the threshold value is an inference).
- **[MUST]** Long jobs (auto-label with SAM, export, training) run as background jobs. Show a persistent job tray or indicator with determinate progress (images processed out of total, epoch out of total), elapsed time and ETA. Users can navigate away, and completion is announced through a toast plus an `aria-live="polite"` region, and optionally email.
- **[SHOULD]** Show partial results while jobs run: stream auto-label predictions as each image finishes, and draw live loss and mAP curves during training. This turns waiting into monitoring.
- **[DIFF]** Cancel and resume for jobs, plus cost and time estimates before a job starts ("~12 min on GPU worker, 4,300 images").

### Gaps
- NN/g's full "Skeleton Screens 101" text was not fetched. Its date and any quantitative results are unconfirmed.
- No 2025–2026 empirical research on optimistic UI or on perceived wait for multi-minute ML jobs was found.

## 6. (Scope addition) "Liquid Glass" web style plus Material 3 Expressive and dynamic colour: what they are, how to build them on the web, their accessibility cost, and where glass belongs in a CV tool

### Takeaway
Apple's Liquid Glass (announced 9 June 2025) is a translucent, refracting material for the **controls and navigation layer**, not for content. It drew sustained legibility criticism (NN/g, developers, press), and Apple toned it down during the iOS 26 betas. On the web it can be approximated with `backdrop-filter: blur() saturate()` everywhere and SVG `feDisplacementMap` refraction only in Chromium. It is GPU-costly, and translucent surfaces have no fixed contrast ratio. Material 3 Expressive and Material dynamic colour (HCT and tonal palettes in `material-color-utilities`) offer a contrast-aware way to generate a rich, premium palette. The right combination for LabelDesk: Material-style tonal tokens for colour, glass limited to floating chrome, and solid surfaces for the canvas, tables and charts.

### Cited Findings
**Apple Liquid Glass: definition and intent**
- Announced 9 June 2025. Apple describes it as a "translucent material [that] reflects and refracts its surroundings". It uses "real-time rendering and dynamically reacts to movement with specular highlights". Controls and navigation, including "tab bars and sidebars", are "crafted from Liquid Glass", with the goal to "bring greater focus to content". — [Apple Newsroom, 9 June 2025](https://www.apple.com/newsroom/2025/06/apple-introduces-a-delightful-and-elegant-new-software-design/)
- Apple's HIG has a Materials page covering Liquid Glass, but its text could not be retrieved (the page is rendered client-side). Its specific guidance on regular and clear variants is not cited here. — [Apple HIG: Materials](https://developer.apple.com/design/human-interface-guidelines/materials)

**Documented usability and accessibility criticism**
- NN/g (Raluca Budiu), "Liquid Glass Is Cracked, and Usability Suffers in iOS 26": the result is "light, airy — and often invisible". The article cites the established principle that anything placed on top of something else becomes harder to see, and criticises tab-bar categories "crammed into each other" and new patterns replacing conventions. — [NN/g](https://nngroup.com/articles/liquid-glass) (full text not fetched; points taken from excerpts and coverage such as [anderegg.ca](https://anderegg.ca/2025/10/12/nielsen-norman-group-on-ios-26-usability))
- Developers raised legibility concerns at iOS 26 launch. One noted that Liquid Glass cannot control what passes behind it, which creates legibility problems over busy content. — [9to5Mac, 15 Sep 2025](https://9to5mac.com/2025/09/15/ios-26-officially-launches-today-but-some-developers-arent-sure-it-should/)
- Apple reduced the transparency of navigation bars, buttons and tabs in a later iOS 26 beta. — [mezha.ua on beta 3](https://mezha.ua/en/news/ios-26-liquid-glass-beta-3-303201/amp/); [PhoneArena](https://www.phonearena.com/news/liquid-glass-returns-to-ios-26-toned-down-but-with-original-vision_id172532). Apple discussed its legibility measures at launch. — [MobileSyrup, June 2025](https://mobilesyrup.com/2025/06/10/how-apple-is-making-sure-liquid-glass-as-legible-as-possible/)
- A "Tinted" option that tones down the glass was reported in iOS 26.1 beta 4. — [Gulf News](https://gulfnews.com/technology/companies/apple-yields-tinted-control-in-ios-261-beta-4-tones-down-liquid-glass-after-backlash-1.500315176) (less authoritative)
- Some users reported legibility problems even with Reduce Transparency on. — [Kottke thread](https://kottke.org/25/09/0047552-im-usually-pretty-go-with) (anecdotal)

**Web implementation, browser support and performance**
- Recipe: translucent background (e.g. `rgba(255,255,255,0.12)`), `backdrop-filter: blur(16px) saturate(180%)` with the `-webkit-` prefix, a 1px border at about 0.28 alpha with a brighter top edge, and an inset top highlight (the "specular" edge). Typical ranges are blur 12–30px and saturate 140–200%. Blur does nothing without a colourful or textured backdrop. — [BuildMVPFast, "Liquid Glass on the Web", 16 Aug 2026](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)
- Refraction: `backdrop-filter: url(#lens) blur(2px) saturate(160%)` with an SVG `feDisplacementMap`. Only Chromium supports it; Safari has an open WebKit bug, and Firefox passes `@supports` but renders nothing, so it needs a UA-gated, three-rung fallback (solid, then frosted, then refraction). — [BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026); [DEV: 6 ways to build Liquid Glass](https://dev.to/devyatov/liquid-glass-on-the-web-6-ways-to-build-it-with-css-and-svg-3m07)
- Chromatic aberration is usually done with three displacement passes, one per RGB channel. `feDisplacementMap` moves pixels without changing brightness, and the SVG filter must be in the same document, so shadow DOM breaks it. — [DEV](https://dev.to/devyatov/liquid-glass-on-the-web-6-ways-to-build-it-with-css-and-svg-3m07); [liquid-glass wiki](https://github.com/deepika-builds/liquid-glass/wiki)
- Safari does not resolve CSS custom properties inside `-webkit-backdrop-filter`, so values must be hard-coded. — [BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)
- Performance: `backdrop-filter` re-composites everything behind the element every frame. Guidance: never animate blur radius (animate opacity), keep blur under about 20px on large surfaces, use at most 3–4 glass layers per viewport, use `will-change` sparingly (VRAM cost), and expect possible scroll jank in Firefox. Test on a mid-tier Android while scrolling. No measured benchmarks were given. — [BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)

**Accessibility media queries**
- `prefers-reduced-transparency` is experimental and not Baseline: Chrome and Edge 119+ support it, Safari does not. Firefox status conflicts: web-features lists it as unsupported, while Mozilla bug 1736914 shows an implementation (reportedly behind a disabled pref). — [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-transparency); [web-features explorer](https://web-platform-dx.github.io/web-features-explorer/features/prefers-reduced-transparency); [Bugzilla 1736914](https://bugzil.la/1736914); [BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)
- Recommended pattern: make the solid, high-contrast surface the default, and add glass only inside `@media (prefers-reduced-transparency: no-preference)`. Add a 2px border under `prefers-contrast: more`. Translucent surfaces have no fixed contrast ratio, so put a semi-solid layer under text and check WCAG contrast against the worst-case backdrop. — [BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)

**Where glass belongs**
- "Glass is chrome, never content." Use it for nav bars, sidebars, modals and command palettes, where text is short and large. Avoid it for data-dense content, tables and numeric dashboards, because contrast shifts as the backdrop moves. — [BuildMVPFast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)
- Apple itself scopes Liquid Glass to controls and navigation in order to focus on content. — [Apple Newsroom](https://www.apple.com/newsroom/2025/06/apple-introduces-a-delightful-and-elegant-new-software-design/)

**Material 3 Expressive and dynamic colour**
- M3 Expressive (announced May 2025) is reported to rest on 46 studies with more than 18,000 participants, using eye tracking, surveys, focus groups and usability tests. Participants reportedly recognised key UI elements up to 4× faster. These figures come from press coverage, not the Google primary source. — [Dezeen, 28 May 2025](https://www.dezeen.com/2025/05/28/google-ushers-in-age-of-expressive-interfaces-with-material-design-update/amp/); [Droid-Life](https://www.droid-life.com/2025/05/05/material-3-expressive-might-be-the-future-of-android-design/); [Design Compass](https://designcompass.org/en/2025/05-1tp-3tea/15/material-3-expressive/)
- `material-color-utilities` (MCU) is the set of algorithms that powers M3 dynamic colour. HCT is based on CAM16 hue and chroma plus L* tone, accounting for viewing conditions. A tonal palette varies only in tone. Dynamic colour derives 5 key colours, which give the 5 foundational tonal palettes of a scheme. — [MCU README](https://chromium.googlesource.com/external/github.com/material-foundation/material-color-utilities/+/91da30d89e70c3dc9575ec71a1ebe8874d881f29/README.md)
- MCU dynamic colour supports contrast adjustment that preserves intended chroma, and background-aware colours adjust to raise or lower contrast. The codebase has ColorSpec2025 and ColorSpec2026 revisions. — [MCU dynamic_color.dart](https://github.com/material-foundation/material-color-utilities/blob/051ed9a15be6a4d4b4774d2edec1ee3d64e9f771/dart/lib/dynamiccolor/dynamic_color.dart); [MCU commits](https://chromium.googlesource.com/external/github.com/material-foundation/material-color-utilities/+/4578d0a1d40f1d17f1ca6f34cc9c484bea8f0a9d)
- Linear's comparable approach generates themes in LCH from base, accent and contrast inputs (see section 1). — [Linear](https://linear.app/now/how-we-redesigned-the-linear-ui)

### Inferences
- **[MUST]** Ship solid surfaces by default and treat glass as progressive enhancement. Gate glass behind `@supports (backdrop-filter: blur(1px))` and `prefers-reduced-transparency: no-preference`, add a user setting ("Reduce transparency") because Safari ignores the media query, and add stronger borders under `prefers-contrast: more`. Glass is never allowed to break WCAG 1.4.3 or 1.4.11, so test text contrast against the worst-case backdrop.
- **[MUST]** No glass on the annotation canvas, its class-label overlays, the dense data tables, the confusion matrices or the training charts. Translucency there changes the perceived image and box colours and destabilises contrast, which defeats accurate labelling and reading charts.
- **[SHOULD]** Use glass where it helps. Good candidates: the top app bar and sidebar over a subtle gradient or mesh background, the floating canvas toolbar and zoom controls (a heavier, more opaque tint, at least about 0.85 alpha over images, so icons stay at 3:1), the command palette, modals and sheets, and the job-progress tray. Limit to 3–4 glass layers per viewport and never animate blur.
- **[SHOULD]** Use frosted blur plus saturate as the cross-browser baseline. SVG refraction and chromatic aberration, Chromium-only, belong at most on marketing pages or the hero; skip them in the app (JS UA gating, shadow-DOM limits, GPU cost on labellers' laptops).
- **[SHOULD]** For the Google-style rich palette, generate tokens with `@material/material-color-utilities` (TypeScript) from one brand seed. Use `SchemeTonalSpot` or the more vivid `SchemeVibrant`/`SchemeExpressive` variants for the brand, export primary, secondary, tertiary, neutral and neutral-variant tonal palettes as Tailwind v4 `@theme` CSS variables (convert to OKLCH), and use MCU's contrast level (0, 0.5, 1.0) for standard, medium and high-contrast themes. Keep class colours (Okabe-Ito or Glasbey) separate from the brand palette so brand hues never collide with label colours on the canvas.
- **[DIFF]** A user-selectable accent seed, with the whole UI re-tinting through MCU at runtime as in Material You, plus an automatic high-contrast mode. Combined with restrained glass chrome, this gives the premium look without sacrificing labelling accuracy.

### Gaps
- Apple's HIG Materials text (regular and clear variants, dimming guidance, exact wording on Reduce Transparency and Increase Contrast) could not be fetched. Cite it only after manual verification.
- The full NN/g Liquid Glass article was not fetched. No quantitative study on Liquid Glass legibility was found.
- No measured web performance benchmarks (FPS or GPU memory) for `backdrop-filter` or SVG refraction were found. The guidance above is practitioner advice.
- No primary Google source (m3.material.io or the Google Design blog) was retrieved for the M3 Expressive research figures. Whether Expressive changes the HCT and dynamic colour algorithm (vs. ColorSpec2025/2026) is unconfirmed.
- No source evaluates glass UIs specifically in data-heavy or annotation tools. The "chrome, never content" rule comes from one 2026 practitioner article plus Apple's own scoping.
