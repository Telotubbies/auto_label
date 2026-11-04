# Annotation Editor UX/UI in CV Labeling SaaS (image + video) — patterns, HCI research, performance

Research date: 2026-10-31. Sources are official docs or the original papers unless marked otherwise. Papers from before 2023 are flagged [OLDER] but are still the standard HCI references. Doc pages carry no "last updated" date unless one is noted.

---

## Q1. Editor layout and interaction patterns across the platforms

### Takeaway
All the major editors converge on the same core: single-letter tool hotkeys (B/P/S, V/F/E and so on), arrow keys to move between images, Ctrl/Cmd+Z undo, an object list with hide/lock/occluded/z-order toggles, display-only brightness/contrast, copy/propagate to the next frames, and a video timeline with keyframes plus linear interpolation. Since 2025, SAM 2/SAM 3 tracking has been added to that timeline. A competitive editor needs this whole baseline. The remaining differences are in AI-assist depth and in hotkey customization.

### Cited Findings

**Roboflow Annotate (hotkey scheme)**
- Tool hotkeys: `b` Bounding Box, `p` Polygon, `d` Drag/Select, `s` Smart Polygon, `n` Mark Null. Holding `meta` temporarily switches between Drag/Select and Box/Polygon. — [Roboflow keyboard shortcuts](https://docs.roboflow.com/annotate/use-roboflow-annotate/keyboard-shortcuts)
- Zoom: `+`/`-`, `0` = fit to viewport, `1` = 100%. `meta+plus/minus/0` zooms the editor and overrides browser zoom. — [Roboflow keyboard shortcuts](https://docs.roboflow.com/annotate/use-roboflow-annotate/keyboard-shortcuts)
- Left/right arrows = previous/next image. `shift+a` adds the image to the dataset, or opens "Submit for Review" when review is enabled. `meta+z` undo, `meta+shift+z` redo. — [Roboflow keyboard shortcuts](https://docs.roboflow.com/annotate/use-roboflow-annotate/keyboard-shortcuts)
- Class picker with an annotation selected: up/down arrows cycle classes, `enter` confirms, `esc` cancels (a newly drawn box is deleted), and `backspace` deletes once the text field is empty. Review mode: `a` approve, `r` reject. — [Roboflow keyboard shortcuts](https://docs.roboflow.com/annotate/use-roboflow-annotate/keyboard-shortcuts)
- Right-clicking any bounding box offers "Convert to Smart Polygon". "Convert to Smart Mask" re-runs Smart Polygon on each selection to refine the mask. — [Roboflow Smart Polygon docs](https://docs.roboflow.com/annotate/ai-labeling/enhanced-smart-polygon-with-sam) (search-snippet level; page not fully fetched)
- The shortcuts page does not mention brightness, hide/lock or repeat-previous. — [Roboflow keyboard shortcuts](https://docs.roboflow.com/annotate/use-roboflow-annotate/keyboard-shortcuts)

**CVAT (objects sidebar, image settings, propagate)**
- Object-level controls: Lock `L` (prevents modification), Occluded `Q` (dashed border), Pinned (no drag), Visibility toggle, z-order "to background" `-`/`_` and "to foreground" `+`/`=`, Remove `Del`/`Shift+Del`, Copy `Ctrl+C`→`Ctrl+V`, Merge `M`, Group `G`. — [CVAT annotation editor docs](https://docs.cvat.ai/docs/annotation/annotation-editor/_print/)
- **Propagate (`Ctrl+B`)** copies an object forward or backward across N frames. This is CVAT's "copy annotations to the next image/frame" pattern. — [CVAT annotation editor docs](https://docs.cvat.ai/docs/annotation/annotation-editor/_print/)
- Image settings adjust **Brightness, Contrast, Saturation and Gamma** plus a grid overlay (cell size, color, opacity) and a reset button. The adjustments are display-only and do not modify the files. — [CVAT annotation editor docs](https://docs.cvat.ai/docs/annotation/annotation-editor/_print/)
- Polygon point context menu: "Delete point" and "Set start point". Settings: "Automatic bordering" and "Intelligent polygon cropping". Mask editing: Join and Slice tools; brushing tools. — [CVAT annotation editor docs](https://docs.cvat.ai/docs/annotation/annotation-editor/_print/)
- Shortcuts are user-customizable under Settings → Shortcuts (changelog). Frame-navigation defaults changed between versions: older docs use D/F for previous/next frame, newer ones C/V. — [CVAT changelog: keyboard shortcut customization](https://www.cvat.ai/resources/changelog/keyboard-shortcut-customization); [CVAT interface docs](https://docs.cvat.ai/docs/manual/basics/cvat-annotation-interface/_print)
- Older user guide [OLDER, unofficial mirror]: v/c step back/forward by a configurable "Player Step" (default 10). Tracks are created in Interpolation mode and keyframes are interpolated between. — [CVAT user guide mirror](https://github.com/rkshuai/cvat/blob/master/cvat/apps/documentation/user_guide.md); [LearnOpenCV CVAT guide](https://learnopencv.com/a-closer-look-at-cvat-perfecting-your-annotations/)

**V7 Darwin (brush, edit, video)**
- Edit tool `V`, Brush `F`, Eraser `E`; `[`/`]` change brush tip size. `Enter` commits a brush edit and creates a keyframe. — [V7 Brush Tool](https://docs.v7labs.com/docs/the-brush-tool); [V7 Interpolation docs](https://docs.v7labs.com/docs/use-interpolation-in-video-and-dicom)
- Video: `,`/`.` step frames, `Space` plays. — [V7 Video Labeling Guide](https://docs.v7labs.com/docs/video-labeling-guide) (search-snippet level)
- Editing an object on one frame creates a keyframe, and clicking a keyframe in the timeline jumps to it. "Interpolate" is on by default. Interpolating tools: Auto-Annotate, SAM, Polygon, Brush, Bounding Box, Ellipse, Polyline, Keypoint, Keypoint Skeleton. — [V7 Interpolation docs](https://docs.v7labs.com/docs/use-interpolation-in-video-and-dicom)
- Video re-prompting pattern: move the rough box on a later frame and click **Rerun** to regenerate the polygon there. **Clear** drops stale corrections. — [V7 Interpolation docs](https://docs.v7labs.com/docs/use-interpolation-in-video-and-dicom)

**Encord (video)**
- Interpolation needs manual labels on at least two non-consecutive frames. `Shift+I` interpolates between the first and last labeled frames. Interpolated labels get a fixed 99% confidence, which separates them from human labels. — [Encord interpolation](https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-interpolation)
- SAM 2 tracking: `Shift+T` (or right-click → Track forwards/backwards). The default range is 30 frames, adjustable in Editor Settings. `Shift+A` toggles SAM mode. The docs say SAM 2 handles tracking and SAM 3 handles object labeling. Shape-support tables conflict between doc versions (e.g. polygon tracking marked unsupported in one). — [Encord SAM 2 video tracking](https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-sam2-video-tracking); [Encord SAM](https://docs.encord.com/docs/annotate-sam)

**SuperAnnotate / Supervisely / Labelbox / Label Studio**
- SuperAnnotate Magic Select (SAM): click a segment to create an instance. "Clip mode" stops instances from overlapping. Alt switches between Magic Select layers. — [SuperAnnotate Magic Select](https://doc.superannotate.com/docs/magic-select-sam)
- Supervisely: per-class hotkeys and colors are set when the class is created. Mouse wheel zooms; modifier+drag pans. — [Supervisely Smart Tool](https://docs.supervisely.com/labeling/labeling-tools/smart-tool.md)
- Label Studio: maintainers acknowledged browser slowdowns with many pre-labeled polygons, and its UI is described as targeting "dozens to hundreds" of regions. — [Label Studio issue #4026](https://github.com/heartexlabs/label-studio/issues/4026); [label-studio-frontend issue #299](https://github.com/humansignal/label-studio-frontend/issues/299)

### Inferences
- The must-have hotkey layer is: single-letter tool keys, arrow-key navigation, Ctrl/Cmd+Z/Shift+Z, Enter/Esc to confirm or cancel, number or arrow class switching, `[`/`]` brush size, and Del. Both Roboflow and CVAT bind "fit vs 100%" zoom. LabelDesk should copy Roboflow's single-letter scheme because users migrating from Roboflow will expect it, and should support remapping (CVAT does).
- Display-only brightness/contrast/gamma is table stakes, and doing it with a GPU CSS filter is cheap (see Q4).
- Object list with Lock/Hide/Occluded/z-order is must-have for dense scenes. "Propagate to next N frames/images" is a should-have for image sequences.
- Video: a keyframe timeline plus linear interpolation is must-have if video ships. SAM-based "track forward N frames" with a configurable range is the 2025-26 norm (Encord, CVAT), and LabelDesk's SAM 3.1 makes it a near-free differentiator. Marking machine-generated frames with a different confidence (Encord's 99%) is a good pattern for review.

### Gaps
- Labelbox editor docs (hotkeys, layer panel, SAM) were not retrieved. No primary source was found.
- Label Studio hotkey list and its SAM/SAM 2 ML-backend UX were not fetched in detail (a Label Studio SAM 2 tutorial exists: [Label Studio SAM2 tutorial](https://labelstud.io/learningcenter/how-to-build-a-labeling-tool-for-sam2-interactive-precision-segmentation-with-prompt-refinement-in-label-studio/)).
- CVAT's current official shortcuts page returned 404. Undo/redo keys and the keyframe key were not confirmed from primary docs.
- No primary source was found for polygon vertex add (midpoint drag) or polygon smoothing/simplification sliders on any platform.

---

## Q2. How click-to-segment (SAM-style) is presented, and measured effects

### Takeaway
The pattern is now standard everywhere: left click = positive point, right or Shift click = negative point, an optional box prompt, iterate until the mask looks right, then commit with Enter/Space/N. Most tools offer mask→polygon conversion as well. SAM 3 adds "segment all similar" from one example box (Supervisely) and text-concept prompts. Measured speed-ups come mostly from Meta's SAM data engine (34→14 s per mask) and from domain studies. Vendors publish no latency figures.

### Cited Findings
- **CVAT interactors:** left click adds positive points, right click adds negative points. Negative-point support and the maximum number of points depend on the model. Positive points alone usually suffice. Finish with Done or `Shift+N`/`N`. — [CVAT AI tools](https://docs.cvat.ai/docs/manual/advanced/ai-tools)
- CVAT SAM 3 (Jan 2026 blog): positive/negative clicks or boxes → mask → accept. — [CVAT SAM 3 blog](https://www.cvat.ai/resources/blog/sam-3-image-segmentation)
- CVAT SAM 2 video tracker: make a mask on frame 0 with the Interactor, convert it to a polygon and then to a Track, and run "SAM 2 Tracker" for N frames. The blog says this was limited to On-Prem paid tiers at the time. — [CVAT SAM 2 video blog](https://www.cvat.ai/blog/video-annotation-sam-2)
- **Supervisely Smart Tool:** a box prompt (two clicks, about 10% padding recommended; Alt+drag/Alt+arrows to nudge) + left-click positive, Shift+left-click negative, Alt+click removes a point, SPACE finalizes. Brush/pen add or remove areas afterwards. The ID button switches model (RITM, SAM, custom). **SAM 3 "reference bounding box prompt":** box one example and it masks all visually similar instances. — [Supervisely Smart Tool](https://docs.supervisely.com/labeling/labeling-tools/smart-tool.md)
- **Roboflow Smart Select with SAM 3 (Nov 2025 changelog):** click an object for a mask, click outside the highlighted region to expand it, click inside the edges to tighten it. That is an implicit positive/negative decided by click position relative to the current mask, with no modifier key. Enhanced Smart Polygon runs SAM in the browser. — [Roboflow changelog: SAM 3 in Smart Select](https://docs.roboflow.com/changelog/explore-by-month/november-2025/use-sam-3-in-smart-select); [Roboflow Smart Polygon](https://docs.roboflow.com/annotate/ai-labeling/enhanced-smart-polygon-with-sam)
- **Encord:** `Shift+A` toggles SAM mode (or the wand icon next to a class). Tracking is a separate `Shift+T` action. — [Encord SAM](https://docs.encord.com/docs/annotate-sam)
- **V7:** the Auto-Annotate/SAM box is re-runnable ("Rerun"), and corrections can be cleared. — [V7 Interpolation docs](https://docs.v7labs.com/docs/use-interpolation-in-video-and-dicom)
- **Measured speed (SAM paper, Kirillov et al., ICCV 2023):** in the SA-1B data engine, average time per mask fell from 34 s to 14 s as the model improved. 14 s is 6.5× faster than COCO mask annotation and only 2× slower than extreme-point box labeling. — [Segment Anything (arXiv 2304.02643)](https://arxiv.org/pdf/2304.02643)
- Domain study (agriculture, 2026): SAM 2 on image sequences took 1.6 s/mask vs 9.7 s/mask for manual polygons. This is a different domain and tooling. — [PMC12872900](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12872900/)
- Interactive-segmentation predecessor [OLDER]: Polygon-RNN++ (CVPR 2018) needed 50% fewer annotator clicks on Cityscapes in interactive mode. — [Acuna et al. CVPR 2018](https://openaccess.thecvf.com/content_cvpr_2018/html/Acuna_Efficient_Interactive_Annotation_CVPR_2018_paper.html)

### Inferences
- Must-have: click + / − (left/right, also Shift-click for trackpads), a box prompt, a live mask preview with undo per point, Enter/Space to commit, Esc to discard, and auto mask→polygon with an adjustable simplification tolerance (CVAT exposes "number of points in polygon approximation").
- Roboflow's position-aware click (outside = expand, inside = shrink) cuts down on modifiers. It is worth offering as the default with explicit +/- as a fallback.
- Differentiator for LabelDesk: a SAM 3.1 text/concept prompt ("all screws") and an example-box "find all similar" (Supervisely only offers this with SAM 3). The 7B VLM can then suggest the class label for each mask, which takes class picking off the critical path.
- Latency: no vendor publishes numbers. Running the image encoder once per image (server side) and the prompt decoder per click (client or fast server) is implied by "SAM runs in browser" (Roboflow). That makes it worth showing an "encoding image…" state on load and then near-instant per-click previews.

### Gaps
- No public vendor data on click-to-mask latency, hover-mask preview (hover-to-preview before click), or SLA. Hover preview behavior was not documented by any vendor fetched.
- No controlled study comparing SAM-assisted vs manual polygon *quality* (IoU) in a commercial UI was found beyond the SAM paper and the agricultural study.

---

## Q3. HCI / CV research on annotation interfaces

### Takeaway
The research has moved from asking humans to draw (boxes at 7-42 s each, polygons) toward asking them to verify, click extreme points, or correct machine proposals. Each step brings reported 3-9× speed-ups at similar quality. The design principle for LabelDesk is to make the human the corrector of SAM/VLM output, not the drawer.

### Cited Findings
- **Su, Deng, Fei-Fei. "Crowdsourcing Annotations for Visual Object Detection." HCOMP @ AAAI 2012** [OLDER]: drawing boxes is significantly harder and slower than answering multiple-choice questions. Used for more than 1M ImageNet images. — [Stanford PDF](https://cs.stanford.edu/groups/vision/pdf/bbox_submission.pdf); [dblp](https://dblp1.uni-trier.de/rec/conf/hcomp/SuDF12.html)
  - The commonly quoted "42 s per box" is cited this way by later papers ([Russakovsky et al. CVPR 2015](https://ai.stanford.edu/~olga/papers/RussakovskyCVPR15.pdf) gives a range of "7 s to 42 s"; [arXiv 1807.03142](https://arxiv.org/pdf/1807.03142)). I did not verify the figure in the 2012 PDF itself, so treat the attribution as secondhand.
- **Russakovsky, Li, Fei-Fei. "Best of Both Worlds: Human-Machine Collaboration for Object Annotation." CVPR 2015** [OLDER]: human-machine collaboration for box annotation. — [mlanthology](https://mlanthology.org/cvpr/2015/russakovsky2015cvpr-best); [PDF](https://ai.stanford.edu/~olga/papers/RussakovskyCVPR15.pdf)
- **Papadopoulos, Uijlings, Keller, Ferrari. "We Don't Need No Bounding-Boxes: Training Object Class Detectors Using Only Human Verification." CVPR 2016** [OLDER]: annotators verify machine-proposed boxes. Total annotation time drops 6-9× on PASCAL VOC 2007. — [CVF open access](https://openaccess.thecvf.com/content_cvpr_2016/html/Papadopoulos_We_Dont_Need_CVPR_2016_paper.html)
- **Papadopoulos, Uijlings, Keller, Ferrari. "Extreme Clicking for Efficient Object Annotation." ICCV 2017** [OLDER]: clicking the top/bottom/left/right-most points takes about 7 s per box, about 5× faster than drawing, with equal box quality and equal detector performance. The 4 boundary points also improve GrabCut segmentation. — [CVF](https://openaccess.thecvf.com/content_iccv_2017/html/Papadopoulos_Extreme_Clicking_for_ICCV_2017_paper.html); [arXiv 1708.02750](https://arxiv.org/pdf/1708.02750)
- **Hata, Krishna, Fei-Fei, Bernstein. "A Glimpse Far into the Future: Understanding Long-term Crowd Worker Quality." CSCW 2017** [OLDER]: about 9M AMT annotations. Workers were "extremely stable in their quality over the entire period", which contradicts the simple fatigue-decline assumption. — [arXiv 1609.04855 (ar5iv)](https://ar5iv.labs.arxiv.org/html/1609.04855)
- **Acuna, Ling, Kar, Fidler. "Efficient Interactive Annotation of Segmentation Datasets with Polygon-RNN++." CVPR 2018** [OLDER]: vertex-based output that humans can correct, where a fixed vertex re-predicts the rest. 50% fewer clicks, +10% absolute automatic mIoU on Cityscapes. — [CVF](https://openaccess.thecvf.com/content_cvpr_2018/html/Acuna_Efficient_Interactive_Annotation_CVPR_2018_paper.html); [project page](https://www.cs.toronto.edu/polyrnn)
- **Andriluka, Uijlings, Ferrari. "Fluid Annotation: A Human-Machine Collaboration Interface for Full Image Annotation." ACM Multimedia 2018** [OLDER]: starts from Mask R-CNN proposals. The annotator relabels, adds or removes regions in a single pass and chooses what and in which order to fix. About 3× less time than LabelMe at similar quality. Limits: manual tools give more accurate boundaries, and class disagreement is the main source of differences. — [arXiv 1806.07527](https://arxiv.org/abs/1806.07527); [Google AI blog](https://ai.googleblog.com/2018/10/fluid-annotation-exploratory-machine.html); [DOI](https://www.doi.org/10.1145/3240508.3241916)
  - Follow-up: "Panoptic Image Annotation with a Collaborative Assistant" (Uijlings et al.). — [arXiv 1906.06798](https://arxiv.org/pdf/1906.06798v3)
- **Ling, Gao, Kar, Chen, Fidler. "Fast Interactive Object Annotation with Curve-GCN." CVPR 2019** [OLDER]: predicts all polygon/spline vertices at once with a GCN. The preprint reports 29.3 ms automatic and 2.6 ms interactive inference, 10× and 100× faster than Polygon-RNN++ (preprint figures). — [CVF](https://openaccess.thecvf.com/content_CVPR_2019/html/Ling_Fast_Interactive_Object_Annotation_With_Curve-GCN_CVPR_2019_paper.html); [arXiv 1903.06874](https://arxiv.org/abs/1903.06874v1)
- **Kirillov et al. "Segment Anything." ICCV 2023**: the data engine's per-mask time fell from 34 s to 14 s (see Q2). — [arXiv 2304.02643](https://arxiv.org/pdf/2304.02643)
- Fatigue: a 2025 arXiv paper proposes worktime/throughput metadata as fatigue proxies. Another study interleaves gold items to detect drops over time (emotion labels). Vendor blogs (Pareto) recommend breaks and rotation but cite no controlled data. — [arXiv 2503.21000](https://arxiv.org/html/2503.21000v2); [Burmania et al. 2016](https://msp.utdallas.edu/publications/Burmania_2016_2.pdf); [Pareto blog](https://pareto.ai/blog/annotation-fatigue-why-human-data-quality-declines-over-time)

### Inferences
- The tiers map onto the research. **Must:** correction UX over model proposals (Fluid Annotation, We Don't Need No Boxes). **Should:** verify-only review mode (accept/reject at speed, as Roboflow's `a`/`r`). **Differentiator:** whole-image pre-annotation by SAM 3.1 text prompts + VLM, with the annotator triaging in a single pass, which is Fluid Annotation built with 2025 models.
- Extreme-click (4 points → box + mask seed) could be a cheap alternative box tool that also seeds SAM.
- Since class disagreement dominated errors in Fluid Annotation, invest in the class picker: search, hotkeys, VLM-suggested class, and class descriptions/examples.
- Fatigue: the evidence for quality decline is weak (Hata 2017), so gold/honeypot items and throughput monitoring matter more than forced breaks.

### Gaps
- No recent (2024-2026) CHI/UIST controlled study of SAM-era annotation UIs was found within the search budget. A targeted CHI/UIST search is recommended.
- The 42 s/box primary source was not verified.

---

## Q4. Performance engineering for large images and many objects in web canvas editors

### Takeaway
The documented techniques are a few Konva layers (static image vs editable shapes), `listening(false)` and viewport culling for off-screen shapes, GPU CSS filters for brightness/contrast instead of per-pixel canvas filters, and pyramid tiling (OpenSeadragon-style) with a WebGL overlay for gigapixel images. Vendors document hundreds of regions as the comfortable limit for Konva/SVG-style editors. Beyond that, WebGL plus spatial indexing is the route.

### Cited Findings
- **Konva official performance guidance:** cost scales with scene complexity, redraw frequency, pixel count and hit detection. Separate static from changing content into layers, but keep the layer count small because each layer creates a scene canvas and a hit canvas. Use `listening(false)` on non-interactive nodes, and hide nodes outside the viewport in large scenes. — [Konva canvas performance](https://konvajs.org/docs/posts/canvas-performance.html)
- **Labelbox engineering post (2019, author Anton Lavrenov / Konva)** [OLDER]: React + Konva, with separate layers for the image and the regions. Opacity uses `destination-out` composite so overlaps don't blend colors (0.8 opacity, 1 when selected). Konva `Brighten` filters need `.cache()` and run on the CPU per pixel. Setting CSS `canvas.style.filter = brightness(...)` runs on the GPU and "works MUCH faster, even for very large images" (qualitative, no numbers). — [Labelbox blog](https://labelbox.com/blog/case-study-image-labeling-with-javascript/)
- **Label Studio:** maintainers acknowledged browser performance problems when a task has many pre-labeled polygons, with no simple fix. Its Enterprise UI is described as aimed at dozens to hundreds of regions. — [Label Studio issue #4026](https://github.com/heartexlabs/label-studio/issues/4026); [label-studio-frontend #299](https://github.com/humansignal/label-studio-frontend/issues/299)
- **Gigapixel tiling:** OpenSeadragon streams pyramidal tiles on demand and has WebGL/Canvas/HTML drawers. — [OpenSeadragon package](https://openapps.pro/packages/openseadragon). Histopathology patent filings describe regular-grid tiles per pyramid level so only viewport tiles load, with GPU memory depending on display resolution rather than image size, and note that OpenSeadragon may not hold 60 FPS, making WebGL the faster option (patent claims, not benchmarks). — [USPTO 11443408](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11443408)
- **Annota (OpenSeadragon + PixiJS/WebGL + R-tree index)** claims 10,000+ annotations at 60 FPS. This is a vendor claim from a low-adoption package. — [Annota on socket.dev](https://socket.dev/npm/package/annota/overview/0.10.9)

### Inferences
- **Must:** a single static image layer + one shapes layer + one transient "tool/preview" layer (SAM mask preview goes here so per-click redraws don't repaint everything). CSS-filter brightness/contrast. `listening(false)` on the background. A virtualized object list (react-window style) once there are more than about 100 objects.
- **Should:** viewport culling and an R-tree hit index once there are more than about 500 shapes. Render masks as a single bitmap layer (RLE→ImageData) rather than as thousands of polygon nodes.
- **Differentiator:** tiled/pyramid loading for images over about 8k px (drone, PCB/IC-defect, which is LabelDesk's own domain) with a WebGL renderer for overlays.

### Gaps
- No documentation was found on how CVAT (SVG-based canvas), V7, Encord or Roboflow render large images or many objects, or on their object-count limits. These are inferred or unknown.
- No independent benchmark of Konva vs PixiJS vs deck.gl for annotation overlays was found.
- No vendor documentation was found on virtualized object lists.
