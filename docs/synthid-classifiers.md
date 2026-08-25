# Classifier models (research)

> Research archive for pixel classifiers that are *not* SynthID detectors.
> Not a statement of current product capability. Shipped behavior:
> [supported signals](supported-signals.md) and
> [known limitations](known-limitations.md).
>
> Sister pages: [SynthID local detector](synthid-detector-research.md),
> [SynthID mark removal](synthid-removal-research.md),
> [mechanism reference](synthid.md).

A classifier is reliable only when its name matches its errors, photographs
are the first negative, Firefly and PixelBin are in the test, and a watermark
claim uses an independent oracle. CLIP content embeddings and the 124-d
origin-locked residual bank are different features for different jobs.

## Result: Model 1, AI versus camera

Finetuned CLIP-L (`openai/clip-vit-large-patch14`), last two vision blocks,
224 letterbox, JPEG and mild crop, linear ridge. Train 5,221 AI plus 6,129
photos. Locked Open Images fresh never enters train. Operating point: 1%
FPR on disjoint `photo_dev_oi`.

| Cell | Value |
| --- | --- |
| Kodak | 0/24 |
| Open Images fresh FPR | 1.7% (n=3,000) |
| Exact-1024 Open Images FPR | 6% |
| AI-test TPR | 93.0% (n=1,905) |
| OpenAI | 93.2% |
| Gemini | 90.5% |
| Firefly | 94.0% |
| xAI | 96.1% |
| FLUX hold | 92.7% |

51 fresh false positives are mostly graphics, CGI, product cutouts, and
scans, not Gemini. Nobody in the sweep hit both ≤1% fresh FPR and ≥90%
TPR. This is AI-versus-camera, not SynthID, and it is not in `identify`.

Artifacts: `.local-eval/synthid/ai-photo-2026-08-22/`
(`comparison.json`, `probe-report-clip-l-ft.json`,
`probe-weights-clip-l-ft.npz`). Date cutoff 2026-07-23, seed 20260822.

### Rejected Model 1 variants

Same splits and `photo_dev_oi` 1% cut.

| Variant | Fresh FPR | Kodak | 1024 FPR | AI TPR | FLUX hold |
| --- | ---: | ---: | ---: | ---: | ---: |
| CLIP-L v2 | 0.017 | 0/24 | 0.04 | 0.877 | n/a |
| CLIP-L + FLUX extra | 0.016 | 0/24 | 0.05 | 0.861 | 0.707 |
| CLIP-H + FLUX extra | 0.014 | 0/24 | 0.02 | 0.812 | 0.913 |
| CLIP-L last-2-blocks finetune | 0.017 | 0/24 | 0.06 | **0.930** | **0.927** |
| DINOv2-giant 256 | 0.023 | 0/24 | 0.04 | 0.606 | 0.293 |

CLIP-H is the photo-FPR specialist (1.4% fresh, 2% at 1024) at 81% TPR and
is not the result. DINOv2-giant at 256 px is not usable.

v1 (CLIP-L, no Open Images in train) at a COCO-looking 0.5% cut accepted
13% of Open Images. Domain shift, not the 124 residual bank. v2 added
1,000 disjoint Open Images reserve photos to train and 500 as
`photo_dev_oi`; locked fresh stayed 1.7% FPR at 87.7% TPR before
finetune.

The 124-d residual bank is the wrong feature for "AI or not". At a
Kodak-safe cut it catches 60% Firefly and misses FLUX, NovelAI, Reve, and
most of TC260 and xAI. Do not train another ridge on that representation
for an AI-or-not claim.

Open, if this head is ever considered for a product cut: a graphics/CGI
abstain. CLIP treats non-camera imagery as generation; that is the remaining
error, not Gemini contamination.

### Wild extras, not SynthID

| Hypothesis | 2026-08-23 | Use |
| --- | --- | --- |
| Missing camera PRNU | Gray `gpt-image-2` highpass RMS 0.25 vs COCO 14.6 | Texture confound. A Wiener PRNU residual on *photographs* vs Model 1 errors is the real test |
| JPEG ELA | COCO 3.13, s1 1.97, gray stamp 0.49 | Export history, leaks PNG vs JPEG, not a provider |
| CFA / Bayer presence | Photo-edit ratio 0.117 vs camera 0.184 vs gray 0.588 | Weak camera vote, overlap. Inverse of the Bayer remover |
| Double-JPEG ghosts | s1 / gpt-image-2 / camera all min at Q90 | Codec, not a provider |
| Perfect-circle / text-edge rate | Circles/MP 385 vs 536, edge 0.052 vs 0.072 | Too noisy for abstain |
| Wiener PRNU on photographs | Edits 4.61 vs camera 8.05 | Donor JPEG texture leftover, not a missing sensor |
| PNG Paeth filter mix | gpt-image-2 PNG 99.9% Paeth vs camera 73% | Export fingerprint |

None of these should be named a SynthID score.

## External literature (surveyed 2026-08-23)

AWPD / FSNet ([arXiv:2603.06723](https://arxiv.org/abs/2603.06723)) is
the published "is there any invisible watermark" task. Leave-one-algorithm-out
SynthID Acc 0.894 is *not* Model 1 and *not* a payload decoder. UniFreq's
SynthID split is 2,000 Imagen-API AIGC crops at 256x256, no photographs,
no Firefly, no OpenAI. A head trained that way can pass as watermark
presence while actually reading generator/size texture, which is the L1
failure mode.

Model 1 remains AI-versus-camera on CLIP-L-ft. That is a published
task, not a watermark task. Adjacent papers:

| Source | Claim | Map to Model 1 |
| --- | --- | --- |
| Ojha, Li, Lee, [arXiv:2302.10174](https://arxiv.org/abs/2302.10174) (CVPR 2023, UnivFD) | A classifier trained to see "fake" treats unseen generators as the real sink. Frozen CLIP + nearest neighbor / linear probe generalizes better than a trained CNN | This is the architecture. We finetuned the last two CLIP-L vision blocks instead of freezing, and put Firefly and a locked Open Images fresh set in the gate |
| Cozzolino et al., [arXiv:2312.00195](https://arxiv.org/abs/2312.00195) | CLIP linear probe, few shots from one generator, holds on DALL-E 3 / Midjourney / Firefly | Firefly is the cell we required. Their paper is why Firefly belongs in the test, not as a surprise |
| Corvi et al., [arXiv:2304.06408](https://arxiv.org/abs/2304.06408) | Spectral peaks and mid-high power differences, GAN and diffusion | Generator fingerprint, not a payload. Explains why a Fourier codebook lights up Google *and* Open Images |
| Zhong, Xu, Zou, [arXiv:2601.22778](https://arxiv.org/abs/2601.22778) (DCCT) | Self-supervised color-channel prediction under a Bayer mask; theoretical gap between photo CFA correlations and AIGC | Local Bayer interpolation-error ratio: edits 0.117 vs camera 0.184. Weak vote, not a payload |
| Klier and Baier, DFRWS EU 2026 | AI noise is not predominantly additive. Standard PCE vs smartphone PRNU: FPR 61% Firefly Image 4, 100% ChatGPT 5. Center crop kills those false positives without hurting true camera matches | Do not call missing PRNU a SynthID score. If we ever add a Wiener residual, crop and a recorded PCE threshold come with it |
| Popescu and Farid, IEEE Trans. Signal Process. 2005 | CFA interpolation leaves neighbor correlations; splicing breaks them | Classical forgery localization, not generation detection |
| Wang, Wang, Zhang, Owens, Efros, [arXiv:1912.11035](https://arxiv.org/abs/1912.11035) (CVPR 2020, CNNDetect) | Classifier on ProGAN + JPEG/crop aug transfers to many CNNs | The "one generator is enough" claim. Ojha is the correction once diffusion exists |
| Wang et al., DIRE, [arXiv:2303.09295](https://arxiv.org/abs/2303.09295) (ICCV 2023) | Reconstruction error under a frozen diffusion model | SDXL float32 at 512. VAE RMS: camera 11.84, photo edit 9.89, s1 9.15, gray stamp 1.24. DDIM DIRE RMS: camera 33.0, s1 31.5, photo 30.9, gray 2.40. Texture rank, not a payload. Float16 DDIM NaN'd on MPS |

They do not substitute for `verify-openai-synthid`.

Krawetz's Gemini-chat TPR critique is a verifier-quality claim, not a
feature we can ship. [Lead Stories, 2026-07](https://leadstories.com/analysis/2026/07/google-gemini-synthid-detector-confuses-results-within-same-chat.html)
documented Gemini repeating the first file's SynthID verdict inside a
chat; Google said that was fixed 2026-07-16. The OpenAI provenance API is
a different endpoint.

## Provider names from pixels

With the keyless mark hunt still open, the adjacent ask was: given a file
with no metadata, is this OpenAI, Gemini, or not AI, with almost no
errors on camera photographs. That is this section. It is not a SynthID
detector. Firefly, PixelBin, and other generators have to sit in the
test, because a head that only sees OpenAI versus Gemini versus COCO
will call Firefly a provider.

Three-way `openai` / `google` / `other` on Model 1 embeddings fails the
Firefly gate. CLIP-L-ft test accuracy 0.53; Firefly 35/31/18. CLIP-H 0.57;
Firefly 36/33/15. OpenAI versus Gemini AUC on CLIP-L-ft is 0.845; on the
124-d lattice bank it is 0.989. They are two pipelines, not one class.

Collapsing OpenAI and Gemini into one pixel class versus other generators
does not fix that. Binary ridge AUC 0.686, TPR 75% at FPR 45%. Canva 98%,
Microsoft 75%, Firefly 68% leak into the union; FLUX HF hold stays out at
3%. Training the same union only against photographs recreates Model 1 with
a narrower train set (fresh FPR 2.1%, Firefly still 95%).

`provider-report-clip-l-ft.json`, `provider-union-report.json`.

### Strict abstention does not recover provider identity

An `unknown` class makes the claim narrower, but neither existing
representation has a useful high-precision operating point. A
leave-one-foreign-family-out ridge on the 124-d residual bank set each cut
above every calibration negative. Mean OpenAI recall fell to 1.3% and mean
Google recall to 4.4%, while a held-out foreign family was still attributed to
a provider up to 5.0% of the time and photographs were called OpenAI up to
0.52% of the time.

The CLIP-L-ft head has the same failure at a 0.1% calibration-negative cut.
On 400 disjoint queries per provider, OpenAI recall was 1.0% and Google recall
was 0.5%. It still called 1/11 held-out FLUX images OpenAI and 1/750 COCO
photographs OpenAI. Zero calibration false positives reduced both provider
recalls to zero. These are abstaining content classifiers, not precise source
finders.

A nonlinear head and local-neighbor decision do not expose a hidden provider
partition in the same embeddings. Across five balanced 768-128-3 MLP seeds,
strict test recall ranged from 0.5-7.0% for OpenAI and 0.75-1.0% for Google,
with 6-19 false attributions among 6,550 locked negatives. The best
calibration-selected `k=3` local-neighbor rule reached 0.5% OpenAI and 3.25%
Google recall and still called one TC260 image Google.

### Pixel finetuning learns the train split, not an exact provider boundary

The last two CLIP-L vision blocks were then finetuned directly for
`openai` / `google` / `unknown`: 9,063 fit images, 3,537 disjoint calibration
images, 400 balanced steps, and random JPEG 40-95, 85-100% crop, and mild blur.
Each provider cut was placed above every calibration negative. Calibration
recall was 4.3% OpenAI and 5.2% Google.

The time-disjoint locked result was 6/400 OpenAI and 10/400 Google. One Google
image and one TC260 image were called OpenAI. All 500 unseen-AI controls and
all 4,945 locked photographs stayed `unknown`, including 3,000 fresh Open
Images, but that photo specificity does not repair an AI-source error. An
oracle cut above both locked OpenAI errors leaves only 1/400 OpenAI; it is an
upper bound, not a valid post-test threshold. The model is not shippable.

The independent high-frequency route is already closed at the tested
capacity. A four-layer opponent-residual patch CNN reached AUC 0.44-0.56
against foreign generators, reversed to 0.15 on a fresh era, and accepted
95-100% of several held-out Firefly, Microsoft, fal.ai, and PixelBin families
at its photo-median threshold. It learned AI rendering versus photography,
not vendor identity.

### External surrogate and forensic-descriptor audit

The public
[`newideas99/gpt-image-synthid-detector`](https://github.com/newideas99/gpt-image-synthid-detector/tree/5495e09)
does not supply a causal SynthID contrast. Its negatives are lightly
regenerated positive images, so the trained ResNet/EfficientNet ensemble can
read the regeneration pipeline. On a blind 517-file local pilot, OpenAI versus
all AUC was 0.630. At the repository's 0.5 cut it retained 92/100 OpenAI and
accepted 307/417 negatives, including 104/120 Open Images, 26/30 COCO, 34/50
Google, and 8/10 Firefly. A later exact repeat on the hash-disjoint v7 challenge
retained 172/200 OpenAI but accepted 110/200 Google and 53/64 personal camera
photos. OpenAI-versus-camera AUC was 0.549. Even a post-test cut above every
camera retained only 14/200 OpenAI and still accepted 4/200 Google; that is an
upper bound, not a deployable threshold. Replaying the v11 rule on the same
rows showed no hybrid value: using that camera-safe post-test cut on `unknown`
rows rescued zero v11 OpenAI misses and introduced two Google-to-OpenAI errors.
Allowing it to override the Gemini branch still corrected zero OpenAI files
and introduced four Google-to-OpenAI errors. It is a visual-domain classifier,
not an independent confirmation signal.

The current [`aloshdenny/reverse-SynthID`](https://github.com/aloshdenny/reverse-SynthID/tree/b110836)
V4 codebook also adds no useful hybrid evidence. A pickle-free exact inference
repeat on v7 accepted 77/200 Google, 76/200 OpenAI, and 27/64 personal camera
files at its published 0.52 threshold. Google-versus-OpenAI/camera AUC was
0.510. Applied only to v11 `unknown` rows, that threshold would rescue 26
Google files while adding 2 OpenAI and 27 camera errors. A post-test cut above
every OpenAI and camera retained one additional Google file; 0.5% recall chosen
after opening the test is an upper bound, not a rule. The older V3 published
cut would add two v11 Google misses and no v7 errors, but it previously accepted
5/499 controls and 6/1,000 fresh Open Images. A 1%-recall OR rule with that
measured false-positive history is also rejected.

The public [`Ristellise/REGRET`](https://github.com/Ristellise/REGRET/tree/7d449034bf323987e7e608e7886e029ed20fd847)
SPAM model is another forensic descriptor, not a decoder. The audited pickle
contained only an sklearn pipeline, scaler, logistic regression, and numeric
numpy globals; inference used an exact restricted allowlist. At the published
0.5 cut it accepted 139/200 Google, 141/200 OpenAI, and 36/64 personal cameras.
Google-versus-camera AUC was 0.647 and OpenAI-versus-camera AUC was 0.614. A
post-test cut above those 64 cameras appeared to retain 22 Google and 2 OpenAI,
but a frozen extension rejected the tail: it accepted 47/500 new personal
cameras, 39/600 other photos, 10/75 BigGAN, 3/75 Midjourney, 14/75 SDXL, and
5/75 VQDM. Target-versus-all-controls AUC was 0.709. It adds no safe v11 rescue.

[`vordme2010/synthid-dataset`](https://github.com/vordme2010/synthid-dataset/tree/133a27088f6f4d695c79db9a1a70fa8e7fa3adad)
publishes a useful flat-field corpus but an invalid open-world classifier
contrast. Its Tier-1 matrix has 500 Gemini-flat positives and 1,500 synthetic,
spectrum-matched, or phase-scrambled negatives, with no real negative. The
33 features include noise scale and radial power as well as six hand-selected
carrier bins. Rebuilding the repository's seed-42 RBF SVM from the safe numeric
matrix, without loading joblib, accepted 1/200 current Google, 0/200 OpenAI, and
0/64 personal cameras on v7. Google-versus-camera AUC was 0.503 and the other
two AUCs were 0.497-0.504. The reported AUC above 0.999 measures the synthetic
negative recipe and flat renderer epoch; it cannot confirm the current source
finder or a SynthID payload.

[Forensic Self-Descriptions](https://github.com/ductai199x/Forensic-Self-Descriptions-CVPR25/tree/50f2eae)
(CVPR 2025) is a genuinely different representation: constrained prediction
residuals are summarized as a 960-d forensic descriptor. Its ready attribution
head is not usable here. Three current OpenAI files were all called `Real`,
while one Microsoft file was called `GPT-Image 1/1.5` at confidence 0.863.

A custom source head on a native 256-pixel center crop was more informative.
PCA-64 plus logistic regression, with each provider cut above every calibration
negative, gave OpenAI AUC 0.872 and 3/50 strict OpenAI recall with 0/388 test
false attributions. Its Google head failed on Bytedance, Canva, FLUX,
Microsoft, and an Open Images photograph. On a later unused-hash challenge the
OpenAI FSD head alone accepted 14/300 OpenAI, 3/300 TC260, and 3/90 PixelBin.
FSD is therefore an independent source cue, not a sufficient classifier and
not a watermark statistic.

### Rejected narrow two-signal cascades, 2026-08-23

The visible Gemini sparkle is absent from the target generation and is not a
feature or a gate. Two metadata-free intersections did survive a new challenge:

| Cascade | Development | Unused-hash challenge |
| --- | --- | --- |
| Google provider probability >= 0.8876249 **and** registered-v3 lattice >= 1.0 | 3/45 Google, 0/30 lattice-positive foreign files | 3/300 Google, 0/690 OpenAI/TC260/PixelBin |
| OpenAI provider probability >= 0.8822824 **and** FSD probability >= 0.9912320 | The two cuts were frozen independently | 3/300 OpenAI, 0/690 Google/TC260/PixelBin, 0/500 photographs |

The Google result is a low-recall intersection of a content head and an
origin-locked renderer lattice. A two-pixel crop destroys the lattice, so an
indeterminate result says nothing about SynthID. It is evidence for a narrow
Gemini/Imagen pipeline, not a public decoder.

All three OpenAI challenge positives were 1086x1448 RGB PNGs, the measured
ChatGPT export geometry. Thirty known non-OpenAI files at exactly 1086x1448
(TC260, Apple, Microsoft, Canva, Firefly, Google, and others) produced zero
first-gate positives. A scan of 1,194 unique files at that geometry with no
provider or platform label produced 29 pixel-gate candidates and four final
hybrid candidates. Three had only PNG image-data chunks; the fourth carried
generic DPI/orientation fields but no provider or provenance label. Visual
inspection found four plausible AI generations. They remain candidates, not
ground truth, until a held-out oracle or original source confirms them.

The full luma 16-32-pixel phase-ring head is not a third confirmation. It
rejected all three known and all four unlabeled OpenAI hybrid candidates while
accepting 3/30 known non-OpenAI same-geometry controls. Its global test AUC was
0.600 for OpenAI and it stays closed.

These cascades established that independent intersections could suppress the
observed false positives, but about 1% recall is not useful for the source-hunt
task. They are rejected as operating detectors. The FSD implementation and
weights are also research-only under CC BY-NC-SA 4.0.

Local artifacts: `lattice-pixel-hybrid-challenge.json`,
`fsd-openai-challenge-report.json`,
`unlabeled-1086x1448-openai-hybrid-candidates.json`. The research entry point
is `.local-eval/synthid/ai-photo-2026-08-22/hybrid_source_finder.py`.

### Canonical forensic source finder, 2026-08-23

An overlooked pixel representation materially improves the strict result. It
normalizes each file to 512x512, then extracts 1,794 metadata-free features
from opponent-color residuals: patch power and variation, phase coherence,
autocorrelation, low-bit correlations, and residual-error histograms. The
OpenAI branch intersects its canonical forensic score with a weak provider
pixel vote. The Gemini branch intersects a forensic/provider fusion with the
registered-v3 lattice. The visible Gemini sparkle remains excluded.

The single-scale cuts were frozen before a third hash-disjoint challenge. The
result was:

| Challenge cell | OpenAI candidate | Gemini candidate | Any candidate |
| --- | ---: | ---: | ---: |
| OpenAI | 51/300 | 1/300 | 52/300 (17.3%) |
| Google | 0/300 | 34/300 | 34/300 (11.3%) |
| Open Images photographs | 1/1,000 | 0/1,000 | 1/1,000 (0.1%) |
| TC260 | 0/7 | 0/7 | 0/7 |

For the requested union, 86/600 OpenAI-or-Google targets were found, 14.3%
recall instead of the rejected cascades' 1%. One OpenAI file crossed through
the Gemini branch, and one known photograph crossed through the OpenAI branch.
The seven remaining unused TC260 files are too few to establish specificity,
and no fresh PixelBin, Firefly, Microsoft, or other generator hashes remained
outside the earlier model and challenge manifests.

This v3 result established a strict source-candidate finder, not an exact
identifier or a SynthID decoder. It does not recover a payload, and an
`unknown` result says nothing about whether SynthID is present.

Local artifacts: `source-finder-v3-selection.json`,
`source-finder-v3-challenge.json`, `google-canonical-forensic.json`, and
`google-forensic-pixel-fusion.json`. The same local research entry point now
implements this rule without the FSD dependency.

### Multiscale strict finder, 2026-08-24

The 512x512 normalization was discarding usable scale-specific evidence. A
frozen union now takes the strongest OpenAI forensic response over 512, 640,
768, and native views, gated by the provider pixel head. The Google branch
takes the strongest forensic/provider fusion over 384, 512, 640, 768, and
native views, then requires the same registered-v3 lattice. Development on
the second and third challenges found 539/1,200 targets and 0/1,657
photograph/TC260 controls.

The views and cuts were written before opening a fourth challenge whose hashes
were disjoint from every model manifest and the first three challenges:

| Challenge cell | OpenAI candidate | Gemini candidate | Any candidate |
| --- | ---: | ---: | ---: |
| OpenAI | 92/300 | 11/300 | 103/300 (34.3%) |
| Google | 0/300 | 173/300 | 173/300 (57.7%) |
| Open Images photographs | 0/1,000 | 0/1,000 | 0/1,000 |
| TC260 | 1/25 | 0/25 | 1/25 |

For the requested union, the blind result is 276/600, 46.0% recall, with
1/1,025 non-target candidates. This is 3.2 times the single-scale v3 recall
and 46 times the rejected 1% cascades. The one false candidate is TC260, not a
camera photograph. Eleven OpenAI files crossed through the Gemini branch;
that is a provider-attribution error but still a correct hit for the declared
OpenAI-or-Google union.

This remains a source-candidate finder, not an exact identifier or a SynthID
decoder. Fresh unused paths from the other generator families were not
available for v4, so the 0.1% observed non-target rate is not an open-world
precision claim. Robustness to crop, resize, re-encoding, and screenshot
capture is also not established. Keep the models and paths in `.local-eval`;
do not add a runtime or public CLI until a new temporal challenge with fresh
foreign-generator families establishes positive precision.

Local artifacts: `source-finder-v4-selection.json`,
`source-finder-v4-rule.json`, `source-finder-v4-challenge.json`, and
`multiscale-forensic-development.json`. The local research entry point
implements the frozen multiscale rule and still uses no metadata or visible
sparkle.

A post-hoc OR over every per-view zero-development-error OpenAI cut is
rejected. It raised v4 OpenAI recall to 153/300 but also accepted 6/1,000
photographs and 3/25 TC260 controls. The apparent union of many individually
strict cuts was multiple-testing overfit, not additional independent evidence.

### Original-export hybrids, 2026-08-24

Three more hash-disjoint challenges tested whether multiscale fusion could be
made useful without metadata. The v5 ExtraTrees union improved exact provider
recall to 363/600 (60.5%) and provider-union recall to 373/600 (62.2%), but it
also accepted 8/1,000 photograph and foreign-generator controls. A revised
Google confirmation removed those eight development errors. Adding an
AI-versus-camera gate in v6 did not transfer: exact recall fell to 327/600
(54.5%), union recall was 341/600 (56.8%), and 2/500 previously unseen personal
camera photographs were called OpenAI.

The two camera errors exposed a stronger but narrower signal. Current OpenAI
exports in these sets are PNGs produced with adaptive scanline filters. The
camera errors were JPEGs, while the earlier TC260 error was a PNG encoded with
filter zero on every row. A strict PNG parser now requires a non-interlaced PNG
with at least one adaptive filter before the OpenAI branch can emit a result.
This reads the image container and pixels, not EXIF, C2PA, a filename, or a
visible label. It also changes the claim: a re-encoded OpenAI JPEG must abstain.

The complete frozen v7 rule reached 215/400 exact provider matches (53.8%) and
221/400 provider-union matches (55.3%) on a new challenge, with 0/64 new camera
controls. Its cells were 114/200 exact OpenAI and 101/200 exact Google. The PNG
gate repaired the observed specificity problem, but the old OpenAI forensic
head remained the recall bottleneck.

A subsequent v8 development hybrid trains an ExtraTrees OpenAI head on v4-v5
multiscale forensic scores, pixel probabilities, and PNG encoding structure.
Model selection used v6. The final 0.47 precision cut was chosen after v7 and a
known-origin local subset had been opened, so the following is a transfer
measurement, not another blind result:

| v7 cell under v8 development rule | OpenAI | Gemini | Unknown |
| --- | ---: | ---: | ---: |
| OpenAI | 190/200 | 3/200 | 7/200 |
| Google | 0/200 | 102/200 | 98/200 |
| Personal camera photographs | 0/64 | 0/64 | 64/64 |

That is 292/400 exact provider matches (73.0%) and 295/400 provider-union
matches (73.8%). On a metadata-free scan of 12,775 readable unique local files,
the precision rule emitted 131 OpenAI and 17 Gemini candidates. Filenames were
not model inputs. They were used only after scoring to audit a known-origin
development subset: 45/53 OpenAI and 16/29 Gemini were found, with no cross-
provider errors at the selected cut.

The remaining Google miss set contained two different export pipelines: PNG
and JPEG. A second development branch parses only JPEG codestream parameters,
including quantization tables, chroma sampling, and progressive encoding; it
explicitly skips APP0-APP15 and COM segments. Training one Google model per
encoding class on v4 and selecting zero-validation-error cuts on v5-v6 raised
the v11 transfer result to:

| v7 cell under v11 development rule | OpenAI | Gemini | Unknown |
| --- | ---: | ---: | ---: |
| OpenAI | 190/200 | 4/200 | 6/200 |
| Google | 0/200 | 126/200 | 74/200 |
| Personal camera photographs | 0/64 | 0/64 | 64/64 |

This is 316/400 exact provider matches (79.0%) and 320/400 provider-union
matches (80.0%). A separate 500-file personal-camera slice, unused by v4-v7
model or threshold selection, produced zero Google candidates. On the local
12,775-file scan, v11 emitted the same 131 OpenAI candidates and 106 Gemini
candidates. The known-origin audit did not improve beyond 45/53 OpenAI and
16/29 Gemini, so the extra 89 Gemini results remain unlabeled recall-mode
candidates rather than confirmed finds.

This is the best local source finder in the campaign, but it is still not a
SynthID detector, payload decoder, or open-world precision proof. The v8 rule
is post-hoc, and candidates outside the known-origin audit are not ground
truth. The OpenAI branch is intentionally scoped to original-style PNG
exports. The v8 148-candidate result is the precision mode; the v11
237-candidate result is a broader recall mode whose additional local results
lack ground truth. A new temporal blind challenge with new foreign generators
and PNG camera/editor controls is required before a runtime or public CLI is
justified.

Local artifacts: `source-finder-v7-selection.json`,
`source-finder-v7-challenge.json`, `source-finder-v8-rule.json`,
`source-finder-v8-openai-extra-trees.joblib`, and
`source-finder-v11-google-per-codec.joblib`. Private scan reports, paths,
labels, and image files remain outside the repository.

### Published few-shot attribution also fails the open-world gate

[OmniDFA](https://arxiv.org/abs/2509.25682) is a purpose-built few-shot source
attributor rather than a generic content embedding. Its published `part1`
checkpoint is the correct unseen-generator fold for DALL-E 2 and DALL-E 3:
those generators are in `part1` validation and absent from its training list.
The same checkpoint has seen Imagen, so its Google result is not a clean
unseen-Imagen benchmark; the OpenAI result is sufficient to reject the shared
runtime.

With 20 support images per provider and provider-specific similarity plus
margin cuts calibrated to zero false attributions over 160 negatives, a
content-hash-disjoint 745-image evaluation produced:

| Cell | Result |
| --- | ---: |
| OpenAI recall | 9/50 (18%) |
| Google recall | 4/50 (8%) |
| Microsoft called OpenAI | 3/15 (20%) |
| Kodak called OpenAI | 3/24 (12.5%) |
| Canva called Google | 1/15 (6.7%) |
| fal.ai called OpenAI | 1/15 (6.7%) |
| xAI called OpenAI | 1/15 (6.7%) |
| unseen Higgsfield called OpenAI | 1/11 (9.1%) |
| fresh Open Images / COCO false attributions | 0/100 / 0/50 |

Provider multimodality is not the missing fix. Choosing 1-10 spherical
prototypes only by calibration recall selected five: test recall fell to 16%
OpenAI and 4% Google, while false attributions remained on Firefly (2/15),
Kodak (2/24), Microsoft, ByteDance, TC260, and Made-with-AI samples.

Native files already fail, so JPEG, resize, crop, and screenshot variants were
not run for OmniDFA. Do not add a provider-attribution runtime or CLI from that
model. General exact OpenAI/Gemini identification remains unsupported. The
strict source finder above emits candidates; it does not read the SynthID
payload.

### 124-d lattice as pipeline ID, not a vendor CLIP head

Provider-class ridge on 124 native residual features (70/30 once, not a
watermark gate). OpenAI L1 n=285, Google corpus n=533, foreign n=218, COCO
n=289: OpenAI vs COCO 0.965; Google vs COCO 0.999; OpenAI vs Google 0.989;
OpenAI vs foreign 0.725; Google vs foreign 0.922. OpenAI vs Firefly-class
is the weak cell.

One-vs-rest: Google head at TPR 90% has FPR 0% vs COCO, 14% vs foreign, 2%
vs OpenAI. A Gemini-like pixel class is close to what `pipeline_lattice`
already is. An OpenAI-like pixel class on this bank would label Firefly as
OpenAI about half the time and is not shippable.

Three-class `openai` / `google` / `no_ai` on 2,000 catalog OpenAI, 2,000
catalog Google, and 1,936 COCO photos. Photo-first margin 0.50: openai
74.7%, google 78.9%, no_ai 99.8%; Kodak 24/24 `no_ai`. Other generators
are leakage, not classes:

| Platform | n | openai | google | no_ai |
| --- | ---: | ---: | ---: | ---: |
| Firefly | 106 | 37 | 27 | 42 |
| Microsoft | 117 | 39 | 22 | 56 |
| PixelBin | 90 | 14 | 46 | 30 |
| HuggingFace job | 82 | 3 | 62 | 17 |
| ByteDance C2PA | 86 | 5 | 35 | 46 |
| SD / Comfy | 120 | 30 | 11 | 79 |
| fal.ai | 98 | 11 | 18 | 69 |
| Made-with-AI tag | 115 | 4 | 32 | 79 |
| TC260 | 118 | 1 | 13 | 104 |
| xAI | 114 | 1 | 20 | 93 |
| Canva | 76 | 11 | 3 | 62 |
| Apple Clean Up | 114 | 1 | 23 | 90 |
| Aweme | 37 | 2 | 7 | 28 |
| FLUX | 11 | 0 | 0 | 11 |
| Reve | 10 | 0 | 0 | 10 |
| NovelAI | 9 | 0 | 0 | 9 |
| Higgsfield | 11 | 1 | 5 | 5 |

PixelBin and HuggingFace jobs lean `google` (shared renderer lineage).
FLUX, NovelAI, and Reve stay `no_ai`. Local probe:
`uv run python .local-eval/synthid/prc-oklab-attack-2026-08-15/classify_openai_gemini.py image.png`.

## Research lattice expert (google-lineage renderer)

Not a watermark and not in `identify`. `scripts/synthid_runtime/`
`detect_synthid` re-check on 628 frozen holdouts, seed 20260822, threshold
1.0.

| Family | n | detected | rate | max score |
| --- | ---: | ---: | ---: | ---: |
| Google / Gemini | 80 | 45 | 0.56 | 3.03 |
| Firefly | 84 | 15 | 0.18 | 3.00 |
| PixelBin | 80 | 11 | 0.14 | 2.48 |
| Microsoft | 60 | 2 | 0.03 | 2.40 |
| OpenAI | 80 | 1 | 0.01 | 1.38 |
| xAI | 40 | 1 | 0.03 | 1.26 |
| FLUX HF | 40 | 0 | 0 | 0.85 |
| TC260 | 40 | 0 | 0 | 0.97 |
| Kodak | 24 | 0 | 0 | 0.49 |
| Open Images fresh | 60 | 0 | 0 | 0.64 |
| COCO hold | 40 | 0 | 0 | 0.74 |

Firefly 18% and PixelBin 14% match the 2026-08-16 signed-foreign rates
(24% and 14%) in order of magnitude. Both Microsoft hits have issuer
`Microsoft, Google LLC`. A 2 px crop killed every sampled positive,
including Firefly and PixelBin. Google TPR 56% is mixed Spaces eras, not
the oracle-positive 147/148 cell. Honest name:
`google_lineage_renderer` = Gemini/Imagen + Firefly + PixelBin.

Registered-v3 photographic controls remain 0/5,993 Open Images and 0/2,366
COCO. Against 223 C2PA-named non-Google generators on 2026-08-16: 29
accepted (0.130), Firefly 0.241. `.local-eval/synthid/lattice-check-2026-08-22/`.

## Spaces catalog sizes (2026-08-21)

49,082 unique sha256. Unlabeled 24,832 rows are not photographs. Microsoft
127/279 and Firefly 64/210 also carry `synthid_from_provenance=true`, so
that flag is not an OpenAI-plus-Gemini class.

| Platform | n |
| --- | ---: |
| none / unlabeled | 24,832 |
| OpenAI | 11,722 (11,347 SynthID-from-provenance) |
| Google / Gemini | 6,875 (plus 94 Google C2PA without a named generator) |
| China AIGC TC260 (not a brand) | 3,610 |
| Microsoft | 279 |
| Meta-style Made-with-AI tag | 275 |
| Adobe Firefly | 210 |
| xAI | 179 |
| local SD / Comfy | 178 |
| ByteDance platform | 88 |
| fal.ai | 98 |
| Canva | 79 |
| ByteDance Aweme tag | 40 |
| Dreamina tag | 4 |
