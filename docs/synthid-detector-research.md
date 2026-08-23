# SynthID local detector research

> Research archive for the hunt for a local, keyless SynthID pixel detector.
> Not a statement of current product capability. Shipped behavior:
> [supported signals](supported-signals.md) and
> [known limitations](known-limitations.md).
>
> Sister pages: [classifier models](synthid-classifiers.md),
> [SynthID mark removal](synthid-removal-research.md),
> [mechanism reference](synthid.md). Dated measurements live in the
> [chronological plan](synthid-detector-removal-plan.md).

## Result

The local OpenAI SynthID detector hunt closed 2026-08-20. Google has no
public payload decoder. Nothing in this project reproduces one.

The mark behaves like a keyed spread-spectrum residual: a content-adaptive
`x' = x + g(x)` with a paired decoder (DeepMind patent family, optional
secret in intermediate layers, encoder/decoder ensembles that do not
recognize each other). Without that pair, the residual sits under the
scene. Keyless energy, TrustMark transfer, L1 distillation, a flat-field
stamp, and a 16-32 band student all failed to read the official oracle
contrast on photographs.

S4, 2026-08-15: the two providers are not doing the same thing. Cross-image
correlation of the folded residual is high for Google (tile16 pos-pos
`+0.326`, chance `0.036`) and at chance for OpenAI (`+0.032`). Google
shares one fixed phase-coherent pattern, also present in its controls at
about half the amplitude. OpenAI shares nothing, which is what a
content-dependent post-hoc encoder produces. Comb experts that work on
Google therefore cannot be reused as an OpenAI watermark detector.

M2, 2026-08-15, re-verified 2026-08-16: Google unwatermarked pairs cannot
be minted. `imagen-*` ids 404 from the model garden. `gemini-*-image`
rejects `addWatermark` (`Cannot find field`). Current Gemini API docs
state that all generated images include a SynthID watermark. There is no
encoder-off Google path.

What the product uses for the *watermark* is signed provenance and
`verify-openai-synthid`. The periodic-lattice expert is research-only under
`scripts/synthid_runtime/` and is not called from `identify` or the CLI.
Lineage measurements of that expert are in
[classifier models](synthid-classifiers.md).

## Closed detector routes

| Route | Close | Why |
| --- | --- | --- |
| Wavelets / FFT / cepstrum as a single-image detector | 2026-08-09 | TrustMark proxy: 318-d wavelet/spectral summary AUC 0.653 and 0 TPR at a clean calibration cut. Complex FFT maps AUC 0.516. Spatial RGB still won |
| `aloshdenny/reverse-SynthID` V3 phase codebook | 2026-08-09 | Pickle-free numeric audit. 5/5 Google positives, 0/194 then-available negatives. Discovery only: not 0.1% FPR, no same-provider hard negatives |
| `aloshdenny/reverse-SynthID` V4 | 2026-08-13 | Commit `b110836`. Better-of-two profiles: 141/355 Google positives and 191/499 controls. Frozen 1,000 Open Images: 386 accepted. Paired AUC 0.517. Threshold sits 0.02 above chance phase similarity |
| `cebeuq/Synthid-Bypass` as a local decoder | 2026-08-13 | 12 public before/after diffusion pairs. Fixed carrier 10/12 before, 0/12 after. Gemini Verify still saw SynthID on two `before` files the carrier missed. Reconstruction removal, not a payload read |
| S4: one content-independent pattern for both providers | 2026-08-15 | Google has a shared phase-coherent tile. OpenAI is at chance. See Result |
| M2: mint Google encoder-off pairs | 2026-08-15 | No current Google path emits an unwatermarked image. See Result |
| U1: one feature space for both providers | 2026-08-15 | Transfer 0.535 and 0.469 |
| Hand statistics vs a perceptually masked keyed mark (M1b) | 2026-08-15 | At equal RMS, fixed 0.670, keyed 0.669, keyed+masked 0.546. Masking, not keying, defeats hand features |
| Decoder-substitution / foreign VAE as a verified negative | 2026-08-17 | OpenAI oracle stayed `detected` at 22.3 dB. Attacking a positive does not mint a labelled negative |
| `aoxo/reverse-synthid` as extra Google templates | 2026-08-19 | Hugging Face dump scored against the frozen era bank. Extra family means raised foreign scores instead of isolating a mark |
| Origin-locked lattice as SynthID | 2026-08-16 | Two-pixel crop kills it; published SynthID keeps 99.97% TPR under aggressive crop. See classifiers for `google_lineage_renderer` |
| Keyless energy in 16-32 px | 2026-08-20 | L1 AUC 0.53; official decoder reads phase structure, not energy |
| TrustMark / open-encoder transfer | 2026-08-20 | E3 leave-one-encoder-out at chance on TrustMark (0.505 ridge, 0.510 conv) |
| L1 distillation of oracle bits | 2026-08-20 | Geometry-only AUC 0.78-0.83 beats pixel 124-d (0.64). ChatGPT export and `opened` C2PA predict `not_detected`. Inside 1254x1254, permutation p=0.45 |
| Flat 16-32 matched filter | 2026-08-21 | Leave-one-out residual correlation 0.645 on gray flats; 0.007-0.025 on COCO photo residuals. L1 AUC 0.70 was a size confound (size-matched 0.59 / 0.44) |
| `gpt-image-1` as encoder-off pair | 2026-08-21 | Does not stamp. `gpt-image-2` does |
| CNN on raw L1 bits | 2026-08-21 | Do not train. Labels are export geometry and presentation, not the mark |
| 128-photo causal wavelet student on the flat template | 2026-08-21 | Photo 16-32 jam flips only at a=24 / 18.6 dB (`a*_photo < 0.53` failed). A student cannot beat a matched filter if the photo-domain mark is that quiet |
| Photo 16-32 amplitude without the flat-arm template | 2026-08-23 | 11 COCO `gpt-image-2` edits plus the red-dot pair. Residual is the camera JPEG resized onto the edit raster, top-left 32 px dropped. Median 16-32 residual RMS 12.2, same order as 8-16 (9.0) and 32-64 (16.3). On the five tightest pairs (full residual RMS < 16): 16-32 median 2.69, still ~24x the 0.11 flat stamp and not louder than 8-16 (3.81). The photo residual does not isolate a 16-32 codeword |
| Sort-by-luma 1D chroma stego | 2026-08-23 | Flat LOO 0.914 but a luma-order shuffle is already 0.792. COCO plus tiny noise: 0.642 vs shuffle 0.640. The sort invents the correlation |
| Retinex / local-gain then 16-32 LOO | 2026-08-23 | 0.742 vs plain 16-32 LOO 0.752 on the same eight gray flats. No new carrier |
| Distant 16-32 patch coupling | 2026-08-23 | Near lag 0.13 of a tile: -0.013. Far lag ~500 px: +0.054. No nonlocal lock |
| Bispectrum of the 16-32 ring | 2026-08-23 | Degenerate: 1.0 on flats and 1.0 on COCO. Not a statistic |
| Length-255 m-sequence vs 16x16 fold | 2026-08-23 | Max abs corr 0.059. Chance for n=255 is `1/sqrt(255) ≈ 0.063` |
| Row-as-audio pitch peak | 2026-08-23 | Peak-to-mean 51 on flats, 46 on COCO noise residuals. Shared FFT peakiness, not a pitch |
| 16x16 origin search of the flat 16-32 template on photos | 2026-08-23 | Zero-shift NCC 0.006-0.024, best of 256 shifts 0.013-0.026. Origin is not hiding a lock |

## Information budget on photographs (2026-08-21)

On 11 `gpt-image-2` photo edits, the flat-derived 16-32 template at full
amplitude against per-image whitening has median `d' = 0.93` (range
0.68-2.46). That is a best-case single-image AUC of about 0.75 even with a
perfect, perfectly aligned template. A P5 gate (FPR 0.1%, TPR 90%) needs
`d' >= 4.37`. The deficit is 4.7x in amplitude, 13.4 dB, *unless* the
photo-domain mark is louder than the flat measurement. Titration said it
is not: fish 16-32 additive jam stays `detected` through a=16 / 21.9 dB.

2026-08-23, without using that flat stamp as `G`: the aligned photo
residual in 16-32 is redraw, not a codeword. Median RMS 12.2 across 12
pairs; 2.69 on the five tightest. Neighboring octaves are as loud.
`.local-eval/synthid/prc-oklab-attack-2026-08-15/photo-band-amplitude-2026-08-23.json`.

Do not report an AUC from those 11 pairs as a detector result. With n=11
the standard error on AUC is about 0.12. Notes:
`.local-eval/synthid/prc-oklab-attack-2026-08-15/agent-detector-claude.md`.

## External literature (surveyed 2026-08-23)

Primary sources, not abstracts. Each row is mapped onto a closed or open
route in this campaign. Mechanism detail stays in
[synthid.md](synthid.md). Removal papers are on
[mark removal](synthid-removal-research.md). Classifier papers are on
[classifier models](synthid-classifiers.md).

### Official mark, not a public decoder

| Source | What it is | Map to this campaign |
| --- | --- | --- |
| Gowal et al., [arXiv:2510.09263](https://arxiv.org/abs/2510.09263) | Post-hoc encoder `f` / decoder `g`. Detection logit is not payload recovery. SynthID-O (partner variant) 136 bits at 512x512. TPR at 0.1% FPR 99.98% aggregated, 99.97% on the hardest spatial crop+resize. Trains against sampled semantics-preserving transforms, including weak VAE regeneration. Production decoder unpublished | Matches the architecture we treat as keyed `x' = x + g(x)`. Explains why a two-pixel crop kills `pipeline_lattice` but not the official oracle, and why a 22.3 dB foreign VAE still reads `detected` |
| DeepMind [US12094474B1](https://patents.google.com/patent/US12094474B1/en) and continuation [US20250149048A1](https://patents.google.com/patent/US20250149048A1/en) | Residual U-Net encoder, separate decoder, optional key, encoder/decoder ensembles that need not recognize each other | Constraint, not a recipe. Ensemble non-recognition is why one recovered Google tile cannot be reused as an OpenAI detector (S4) |
| Dathathri et al., [Nature 634:818-823 (2024)](https://www.nature.com/articles/s41586-024-08025-4) | SynthID-Text: tournament sampling of LLM tokens, open-source | Different system. Image/audio/video remain proprietary |
| OpenAI, [advancing content provenance](https://openai.com/index/advancing-content-provenance/) (2026-05-19, audio 2026-07-31) and [content provenance API](https://developers.openai.com/api/docs/guides/content-provenance) | ChatGPT / API / Codex images carry C2PA plus SynthID. Audio from 2026-07-31. `POST /v1/content_provenance_checks`. `not_detected` does not rule out another vendor | This is the oracle. C2PA and SynthID are independent entries. Do not abuse the endpoint as an adaptive reverse-engineering loop |

### Keyless presence detectors in the literature

| Source | Claim | Caveat against our gates |
| --- | --- | --- |
| Ao et al., [arXiv:2603.06723](https://arxiv.org/abs/2603.06723) (AWPD / FSNet, SAFE@CVPR 2026) | Leave-one-algorithm-out presence detection. SynthID held out: FSNet Acc 0.894 / F1 0.886, ResNet-50 Acc 0.845 / F1 0.812, ConvNeXt V2 Acc 0.866. LSB and Patchwork both fail below 60%. Hypothesis: modern invisible marks share dense high-frequency spectral anomalies | UniFreq Table 3: SynthID is 2,000 images, all AIGC, zero photographs, from `imagen-4.0-fast-generate-001` only, resized to 256x256. No OpenAI. No 0.1% FPR. Closest published analog to E3/L1 distillation. Our TrustMark leave-one-encoder-out was chance (0.505 ridge). Their high-frequency commonality is the same energy that L1 failed to read as an OpenAI payload |
| `aloshdenny/reverse-SynthID` V3/V4; Google to [The Verge, 2026-04-14](https://www.theverge.com/ai-artificial-intelligence/911579/google-synthid-ai-watermarking-system-reverse-engineered) | Spectral codebook from averaged Gemini flats. Spokesperson Myriam Khan: "It is incorrect to say this tool can systematically remove SynthID watermarks." The author also said the bypass confuses the decoder rather than deleting a payload | Our pickle-free V4 audit: paired AUC 0.517, frozen Open Images 386/1000 accepted. Not 0.1% FPR |
| Krawetz, [Hacker Factor "Reversing SynthID"](https://www.hackerfactor.com/blog/index.php?/archives/1092-Reversing-SynthID.html) and ["Meta's Un-Stable Signature"](https://hackerfactor.com/blog/index.php?/archives/1098-Metas-Un-Stable-Signature.html) | Gemini chat TPR closer to 1/20 than the paper's 99.97%. Detector weak on flats. reverse-SynthID field accuracy ~70% vs the author's 90% | Gemini-app chat is not the OpenAI provenance API. Our gray `gpt-image-2` flats are `detected` on the official OpenAI oracle. Do not mix the two verifiers |
| vitotitto LAB-a logistic (community, tiny holdout) | Reported 97.7% AUC on 20/20 | Not a P5 gate. Ignore as a detector claim |

### Different embedding loci (not post-hoc SynthID)

These papers are often cited as if they were SynthID. They are not.

| Source | Locus | Why it is not this mark |
| --- | --- | --- |
| Gunn, Zhao, Song, [arXiv:2410.07369](https://arxiv.org/abs/2410.07369) (PRC, ICLR 2025) | Pseudorandom error-correcting code in the *initial diffusion latent* | Cryptographic undetectability is a latent-code property. SynthID-Image is applied after the VAE has already decoded pixels. Our OKLab "PRC-style" noise was a category error |
| Francati et al., [arXiv:2509.10577](https://arxiv.org/abs/2509.10577) (EuroS&P 2026) | Crop-and-resize flipped about half of PRC latent signs and blocked belief-propagation decode | Confirms PRC is origin-locked in latent space. Matches why a 2 px shift kills `pipeline_lattice` and does not kill OpenAI SynthID |
| Fernandez et al. Stable Signature; Wen et al. Tree-Ring | Fine-tuned VAE decoder, or ring constraints on initial noise | In-generation. Google's paper is explicit that SynthID-Image does not modify the generator |
| TrustMark ([arXiv:2311.18297](https://arxiv.org/abs/2311.18297)), HiDDeN, StegaStamp | Open post-hoc encoder/decoder pairs | Transfer from these is E3: chance on TrustMark. WAVES ([arXiv:2401.08573](https://arxiv.org/abs/2401.08573)) stress-tests this family, not production SynthID |

Do not train a student on AWPD's Imagen-only 256 crop and call it an
OpenAI SynthID detector. That would repeat L1's contamination: a
generator/size cue, not a payload.

### Adjacent literature, not SynthID

These papers are the published versions of the wild hypotheses and of
Model 1. They detect *something else*: a camera pipeline, a generator
fingerprint, an open watermark, or steganography. None of them is a
keyless OpenAI payload decoder.

**Classical spread-spectrum and open neural marks**

| Source | What it is | Map |
| --- | --- | --- |
| Cox, Kilian, Leighton, Shamoon, IEEE TIP 1997 | i.i.d. Gaussian vector in perceptually significant spectral components. Informed detector. Collusion-resistant by construction | Ancestor of keyed CDMA. Our length-255 m-sequence vs 16x16 fold was at chance because we did not have the key, and because OpenAI is content-adaptive, not a fixed Gold code |
| Zhu et al., HiDDeN, ECCV 2018 | Joint encoder / noise layer / decoder | Open pair. AWPD leave-one-out Acc 0.985. Transfer to SynthID is E3 |
| Tancik, Mildenhall, Ng, StegaStamp, 2020 | 100 bits at 400x400, trained through print-scan | Open pair. Survives recapture. WAVES: TPR at 1% FPR collapses from 1.00 to 0.01 under regeneration |
| Wen et al., [arXiv:2305.20030](https://arxiv.org/abs/2305.20030) (Tree-Ring, NeurIPS 2023) | Pattern in the *initial diffusion noise*, recovered by DDIM inversion | In-generation, origin-locked in latent Fourier space. Crop-invariant by design. Not post-hoc SynthID |
| Fernandez et al., Stable Signature, ICCV 2023 | Fine-tune the LDM VAE decoder so every decode carries a bit string | In-generation. Gowal is explicit that SynthID-Image does not modify the generator |
| Lin and Juarez, [arXiv:2506.10502](https://arxiv.org/abs/2506.10502) (USENIX 2025) | Public-knowledge attack that removes Tree-Ring | Confirms Tree-Ring is a different object with a different kill |

**Steganalysis as a presence detector**

Fridrich and Kodovsky Spatial Rich Models (TIFS 2012) and Boroumand,
Chen, Fridrich SRNet (TIFS 2018) detect sub-bit-per-pixel spatial
stego by high-pass residuals, with pooling disabled in the front of
SRNet so the weak signal is not averaged away. AWPD cites both and
says they drift on modern deep / generative marks. That matches our
wavelet/FFT single-image detector (AUC 0.653, 0 TPR at a clean cut)
and the 16-32 energy miss on photographs: a residual energy detector
without the matching key is steganalysis of a mark that was trained
not to look like LSB.

**Generator fingerprints in the Fourier domain**

Corvi, Cozzolino, Poggi, Nagano, Verdoliva,
[arXiv:2304.06408](https://arxiv.org/abs/2304.06408) (CVPRW 2023):
GAN, diffusion, and VQ-GAN images show spectral peaks and anomalous
autocorrelation; real vs synthetic differ in mid-high radial and
angular power. reverse-SynthID averaged Gemini flats and called the
peak a watermark codebook. Corvi's result says many generators leave
*some* peak. Our V4 Open Images 386/1000 is what a generator-fingerprint
detector looks like when you calibrate it as if it were a payload.

Yao and Juarez, [arXiv:2512.11771](https://arxiv.org/abs/2512.11771)
("Smudged Fingerprints"): 14 fingerprinting methods across RGB,
frequency, and learned features; removal attacks >80% white-box, >50%
black-box. A fingerprint you can see without a key is a fingerprint
you can wipe without a key.

### Image investigation and data hiding (any method)

These are not SynthID papers. They are the rest of the toolkit: how
people hide bits in pictures, and how people tell a picture was
touched. Several of our wild hypotheses already had a published form
here.

Hiding is not one problem. Cover modification (change an existing
image), coverless / generative (sample an image that already carries
the bits), and signed metadata (C2PA) fail under different attacks.

**Cover modification, classical**

| Source | Hide how | Detect / limit |
| --- | --- | --- |
| LSB, Patchwork (Bender et al., IBM SJ 1996) | Flip low bits, or luminance of random pixel pairs | AWPD Acc < 0.60. Sparse or ±1 amplitude. SRNet / FSNet average it away |
| Westfeld F5 (2001), Fridrich nsF5 | JPEG DCT coefficients, matrix embedding | Histogram attacks on F5; nsF5 was the shrinkage fix. Domain is the codec, not a mid-band residual |
| Pevny, Filler, Bas HUGO (2010); Holub and Fridrich WOW (2012); Holub, Fridrich, Denemark UNIWARD (IH&MMSec 2013 / EURASIP 2014) | Content-adaptive costs, bits placed in texture via syndrome-trellis codes (Filler, IH 2011) | The modern spatial/JPEG floor. Distortion is *designed* to look like the cover. A 16-32 energy detector is the wrong statistic |
| Cox et al. 1997 | Spread-spectrum in significant DCT | Keyed. Already mapped above |

**Cover modification, neural (hide a whole image, not 32 bits)**

| Source | What it does | Map |
| --- | --- | --- |
| Baluja, NeurIPS 2017, "Hiding Images in Plain Sight" | Full-resolution secret image distributed across all bits of a same-size cover | Capacity is the point. Not robust, not keyed provenance. HiDDeN later added a noise layer so the secret survives JPEG |
| Jing et al., HiNet, ICCV 2021 | Invertible neural net: hide and recover as one bijection | High-capacity lossless-ish hiding. Recovery needs the exact inverse, not an official oracle |
| Yang et al., PRIS, [arXiv:2309.13620](https://arxiv.org/abs/2309.13620) | Invertible net plus robustness modules | Same family, trained through distortion |

A HiNet-style student on OpenAI pairs would learn the *edit*, not a
SynthID codeword. That is the L1 contamination again.

**Coverless / generative hiding**

The cover is never modified because there is no cover. The sampler
emits an image whose latents already encode the message.

| Source | Locus | Map |
| --- | --- | --- |
| Yang et al., Gaussian Shading, [arXiv:2404.04956](https://arxiv.org/abs/2404.04956) (CVPR 2024) | Map bits onto Gaussian latents indistinguishable from ordinary noise. Recover by DDIM inversion | Sibling of Tree-Ring / PRC. Training-free, performance-lossless *for the generator*. Not a post-hoc pixel stamp |
| Peng et al., StegaDDPM (ACM MM 2023) and later LDStega | Bits in the diffusion sampling distribution | Spatial SRNet is the wrong detector (NS-DSer, [arXiv:2602.10219](https://arxiv.org/abs/2602.10219): move steganalysis into noise space) |
| CRoSS, Pulsar, MDDM | Message-to-noise projections | Same locus. A pixel scramble does not invert the sampler |

**Passive forensics (the picture was touched, no secret assumed)**

| Source | Cue | Map |
| --- | --- | --- |
| Krawetz, "A Picture's Worth", 2007 (ELA) | Re-JPEG at lower quality, subtract | Already measured: COCO 3.13, s1 1.97, gray stamp 0.49. Codec history, not a payload. Farid publicly called ELA as likely to mislabel originals as it is to catch edits |
| Farid, IEEE TIFS 2009, JPEG ghosts | Difference energy vs a sweep of JPEG qualities; spliced regions ghost at their original Q | Untested here. The remaining JPEG check after ELA. Only defined on quantized JPEG |
| Popescu and Farid, TR2004-515 | Copy-move via duplicated regions | Not generation, not a watermark |
| Popescu and Farid, IEEE TSP 2005 | Resampling periodic correlations | Affine search cousin. A rotated SynthID residual is a different question |
| Wang et al., DIRE, [arXiv:2303.09295](https://arxiv.org/abs/2303.09295) (ICCV 2023) | Diffusion reconstruction error: generated images reconstruct, cameras do not | Model 1 sibling, needs a diffusion model. Inverse of our VAE round-trip: there the mark survived 22.3 dB; here the *error map* is the feature |
| Wang, Wang, Zhang, Owens, Efros, [arXiv:1912.11035](https://arxiv.org/abs/1912.11035) (CVPR 2020, CNNDetect) | One ProGAN classifier, heavy JPEG/crop aug, transfers to many CNNs | Ancestor of "train on one generator". Ojha showed the sink-class failure once diffusion arrived. We required Firefly for that reason |

C2PA is the non-pixel stack: a signed manifest, stripped by
`metadata --remove`. Durable Content Credentials (spec 2.4) add a
soft binding that can re-link a stripped file to a repository. That
is provenance, not hiding.

Do not train on ELA, JPEG ghosts, DIRE, or a HiNet reconstruction and
name the score SynthID.

### Waveforms that can live in a picture

A mark is a function on the pixel lattice. The literature does not
use one wave. It picks a basis whose symmetries match the attack it
fears, then hides a keyed coefficient vector in that basis. Cartesian
16-32 is one shell. Polar, scale, and diffraction are different
shells.

**Standing waves on a rectangle.** DFT / DCT / DST. A 2-D sinusoid
`cos(2π(ux + vy)/N)`. JPEG lives here. Our octave scramble destroys
one annular *radius* of these frequencies, not one orientation. A
Gabor packet is the same sinusoid windowed in space.

**Circular and log-radial waves.** Functions of `(r, θ)`, not
`(x, y)`.

| Basis | Wave | Invariance it buys |
| --- | --- | --- |
| Fourier-Mellin / log-polar (Ó Ruanaidh and Pun, Signal Processing 1998) | `r^{iα} exp(ikθ)` after a DFT magnitude | Rotation and scale become translations |
| Logarithmic radial harmonics (IH 2002) | Same family, added in pixels, detected by complex correlation | RST without going through the unstable log-polar resample |
| Polar harmonic transforms: PCET, PCT, PST | `exp(±i2π n r²)` and polar cos/sin | Rotation. Moments, not a dense codebook |
| Zernike / pseudo-Zernike | Orthogonal polynomials on the disk, radial part related to Bessel | Rotation. Classical moment watermark |
| Circular chirp (SPIE 6072, 2006) | Polar map of a 1-D chirp onto a ring | JPEG (tune chirp rate) plus rotation (the ring) |
| Tree-Ring (Wen 2023) | Concentric rings in the *latent* Fourier plane | Crop/flip by construction. Not a pixel wave |

Our prepared polar 16-32 scramble is the attack on this family: keep
the Cartesian octave energy, randomize angle. If the official decoder
still reads `detected`, the OpenAI mark is not a polar harmonic. If it
flips near 25.6 dB, angular structure mattered.

**Scale chirps.** Hyperbolic / Mellin monomials (arXiv:1208.5842):
real 1-D Mellin patterns tiled in 2-D, detected after a Radon-like
projection. Affine search of a 16-32 template is the cheap version.
Not yet run.

**Directional packets.** Dual-tree complex wavelets (approximate
analytic wave), Gabor/Morlet, ridgelets, curvelets, shearlets,
contourlets, bandelets. Multiplicative spread-spectrum on curvelet
coefficients is a published detector-design paper, not a SynthID
decoder. Our wavelet summary AUC 0.653 already said a *generic*
packet energy is not the OpenAI payload.

**Optical diffraction, actual wave physics.**

| Transform | What the wave is | Map |
| --- | --- | --- |
| Fresnel | Quadratic phase `exp(iπ r² / λz)`, a radial chirp. Energy concentrates with distance | Holographic watermarks embed the diffracted field, not the picture |
| Fractional Fourier | Rotation of the time-frequency plane. Order is an extra key | Extra key space on top of DFT |
| Double random phase encoding (Réfrégier and Javidi, Optics Letters 1995) | Random phase at input *and* Fourier plane. Ciphertext is stationary white noise | Closest optical analog of a keyed `x' = x + g(x)` that looks like noise without both screens |
| Cascaded Fresnel / CGH | Two holograms at different depths | Hardware key. Not a pixel residual we can match-filter |

A Fresnel/FrFT student without the distance or the fractional order
is another unmatched filter.

**Cyclostationary and clock-warped waves.** Periodic clock change
(Martin, Chabert, Lacaze, EUSIPCO 2005) turns a stationary host into
a cyclostationary one by a periodic time warp. Our H2 multiplicative
cyclostationarity test already put official positives *below*
controls. Do not rerun the same statistic in a new basis and call it
new evidence.

**How to read a candidate wave.** Name the coordinates `(x,y)` vs
`(r,θ)` vs `log r`, the generating function (sinusoid, chirp,
Bessel, Zernike), additive vs multiplicative, and the symmetry it
claims. Then pick one attack that kills that symmetry and one that
should not. Cartesian 16-32 scramble, polar 16-32 scramble, 2 px
shift, and a small rotation are the four cheap probes. Shift already
left OpenAI `detected`. Polar scramble is prepared. Affine/rotation
search is not.

## Still open or incomplete

- Google: no public payload decoder and no usable programmatic oracle.
  The Gemini app remains quota-limited. Vertex was 403.
- `chatgpt-image-latest` encoder-off pairs: `models.retrieve` returns the
  id, `images.generate` is 403 until the organization is verified
  (re-checked 2026-08-23). `gpt-image-2` remains the working pair mint.
- Adding unmarked context (frame, pad, hstack, collage) to hunt a
  residual is a presentation gate, not a mark statistic. Those rungs
  belong with identity and layout below, and with
  [mark removal](synthid-removal-research.md).
- Camera-to-ChatGPT "unchanged crop" pairs are dirty counterfactuals.
  The instructed edit redraws; aligned PSNR on the frame pair was
  16.6 dB. Compare pixels only after registration and a frozen residual
  bound, as in the `gpt-image-2` red-dot row.

A Gemini app caption that an image "looks like a photograph" is not a
SynthID verdict. Use the provider pixel check or signed provenance.

## Wild hypotheses

Battery 2026-08-23, no official oracle. Local numbers:
`.local-eval/synthid/prc-oklab-attack-2026-08-15/wild-hypotheses-2026-08-23.json`.
Prepared attack rasters wait in `wild-attacks-2026-08-23/` for a later
verifier window. Jacobian / adaptive queries against
`verify-openai-synthid` stay out: the endpoint forbids reverse-engineering.

### Tested locally, not a mark

| Hypothesis | Result |
| --- | --- |
| Chroma ordered by luma is a 1D payload | Correlation is an artifact of the sort |
| Mark is `g(x)` of a Retinex envelope | LOO unchanged vs the raw 16-32 residual |
| Nonlocal patch agreement in 16-32 | Far patches are not coupled |
| Quadratic phase coupling (bispectrum) | Statistic saturates on camera images too |
| CDMA Gold / m-sequence in the 16x16 fold | At chance for length 255 |
| Rows as a pitched waveform | COCO noise has the same peak-to-mean |
| The photo mark is the flat stamp at an unknown 16-phase | Exhaustive shift does not lift NCC |
| Self-keyed predictor from a 16 px luma thumb | Already 0.48 vs L1, 0.50 vs COCO (`self-keyed.json`) |
| Global multiplicative cyclostationarity (H2) | Official positives below controls, 2026-08-14 |

### Not a watermark, might still be an AI-vs-camera extra

| Hypothesis | Result |
| --- | --- |
| Absence of camera PRNU | Gray `gpt-image-2` highpass RMS 0.25 vs COCO 14.6, that is missing texture, not a missing sensor. A Wiener PRNU residual on photographs is still open as a Model 1 sibling, not as SynthID |
| JPEG ELA | Flat 0.49, s1 1.97, COCO 3.13. Compression history, not a payload |

### Still crazy, not yet measured

- Content-locked affine search (small rotation plus 16-32 NCC), not origin-locked. Published analog: Fourier-Mellin / log-radial harmonics (Ó Ruanaidh and Pun 1998). Polar 16-32 scramble is the remover twin, already rastered at 25.6 dB.
- CFA presence as a camera vote (Bayer as a *detector* feature, the inverse of the remover arm). Published analog: Zhong, Xu, Zou [arXiv:2601.22778](https://arxiv.org/abs/2601.22778) (DCCT). Farid's 2005 CFA-interpolation test is the classical form.
- Wavelet Wiener PRNU on `gpt-image-2` photo edits versus Kodak. Published analog: Klier and Baier, DFRWS EU 2026, PCE vs smartphone fingerprints (ChatGPT-5 FPR 100% until a center crop).
- PNG Paeth / filter-byte residual after a lossless rewrite.
- Double-JPEG ghosting as an export fingerprint. Farid TIFS 2009. ELA already failed as a payload; the ghost sweep is the remaining codec check, JPEG-only.
- Face-gated 16-32: maybe the encoder spends budget off faces.
- Baker-map / area-preserving scramble of the mid band.
- Print-scan (physical).
- Nested open watermark plus SynthID.
- Mark in ICC / cICP / gamma, not in pixels. Strip-and-reencode already used for the oracle path; a pixel-preserving ICC rewrite is the remaining check.
- Encoder ensemble that does not recognize itself (patent). Untestable without that pair.
- Photon-shot / Poisson-domain embedding.
- CLIP-space watermark. Would show up as Model 1, not as a payload.

Do not train on official decoder bits beyond the frozen L1 study. Do not
mint a 128-photo student on the flat stamp. The information budget and
the 2026-08-23 residual measurement both say the photo-domain mark is
under the scene.

## Oracle and seeds

Official `POST /v1/content_provenance_checks`, metadata stripped, pixels
preserved. Raw files stay gitignored under
`.local-eval/synthid/prc-oklab-attack-2026-08-15/`.

| Seed | Path | Size |
| --- | --- | --- |
| s1 | `originals/2026-05-31/31e55ea8a4de42029659654a80814630_src.png` | 1024x1536 |
| s2 | `originals/2026-05-31/37ae95821a3447c78f94e56bdebf0c88_src.png` | 1024x1536 |
| s3 | `originals/2026-07-10/d76f35fee69e4531865e88b786fa52e5_src.png` | 1086x1448 |

All three `detected` before attacks.

## Source-matched pairs (2026-08-21)

`gpt-image-2` (ChatGPT Images 2.0) can mint encoder-on/off pairs.
`chatgpt-image-latest` still 403 on generate (org verification),
re-checked 2026-08-23; retrieve of the model id succeeds.

| Input | C2PA | Oracle | Aligned PSNR |
| --- | --- | --- | ---: |
| Camera JPEG 960x1280 | none | not_detected | - |
| ChatGPT UI + frame 1086x1448 | watermarked.unbound | detected | 16.6 dB (redraw) |
| `gpt-image-1` edit, high fidelity, red dot | created, converted only | not_detected | 30.9 dB |
| `gpt-image-2` edit, red dot 1024x1536 | watermarked.unbound | detected | 28.2 dB |

The `gpt-image-2` photo residual is broadband (std 9.1), not a 16-32 stamp.
COCO `gpt-image-2` edits: 11/12 `watermarked.unbound`, one safety block.

Solid gray/white through `gpt-image-2` "reproduce exactly" is
`watermarked.unbound`. Gray 128 at 1024x1536: PSNR 41.9 dB vs the flat,
source `not_detected`, output `detected`. Other gray levels 32-220: PSNR
38-49 dB. Eight gray 1024x1536 residuals, leave-one-out correlation after
highpass: 0.645 (shuffle 0). That shared stamp does not transfer to COCO
photo residuals (0.007-0.025).

## Presentation gate versus residual

An official `not_detected` is not one event. Collage, photo-pad, two-panel
self-concat, and 8x8 scramble can be a *presentation gate* (this upload is
not a single photograph). Blur sigma 7 and in-band 16-32 destruction sit on
the single-photo manifold and are residual damage; those belong in
[mark removal](synthid-removal-research.md).

Do not train a surrogate on mixed collage misses if the goal is a mark
student.

Identity (s1, 2026-08-19): JPEG q80/q20, crop 2 px, crop 8 px, keep 0.75
and 0.50, rot90, rotate 5, flip, grayscale all stay `detected`.

Token / layout (s1): each quadrant at 512x768 `detected`; `hstack` and
`vstack` of marked\|marked `not_detected`; 4x4 tile scramble `detected`;
8x8 `not_detected`. Two copies of a detecting image still miss. Tomography
3x3: all nine cells `not_detected` (a 1/9 window is below support).

Preprocess E1 (s1): stretch 2x `detected`; centre-crop of marked\|marked
hstack back to native `detected`; 0.20x pixels on a native-size white
canvas `not_detected` (the same 0.20x file uploaded alone was `detected`).

## L1 is not a mark task

A missing `watermarked.unbound` assertion is not a clean negative. On
2026-08-16 the official verifier called 65 of 94 OpenAI rows without that
assertion `detected` (69%), with 9 of 9 interleaved health positives
detected so the endpoint was answering. Google's own API emits watermarked
images with no assertion, per its documentation. Corpus AUCs that treat
"no assertion" as unmarked rest on a negative class that is roughly
two-thirds positive.

Control-only 283 rows: 203 detected, 80 not_detected. Forward-temporal
nested ridge on 124 pixel features: AUC 0.649 / 0.641. Geometry-only:
0.781 / 0.826. All 21 `claim_generator=ChatGPT` controls are
`not_detected`. C2PA `opened`: 24/24 `not_detected`. Inside 1254x1254,
mean-feature permutation p=0.45.

OpenAI-supervised ridge on 16-32 band-passed `image_features`:
forward-temporal AUC 0.53 vs L1 `not_detected`, 0.95 vs COCO, 0.97 vs COCO
after a 2 px crop. The student learns OpenAI-versus-photo and still does
not see the oracle mark contrast.

## Product remainder for the watermark

Signed provenance (`identify`) and `verify-openai-synthid` (remote, explicit
upload). A research lattice miss is not a clean SynthID negative.
