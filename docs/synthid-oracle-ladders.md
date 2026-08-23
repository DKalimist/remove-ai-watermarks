# OpenAI SynthID oracle ladders

> This page is a routing hub. The mixed 2026-08 campaign log was split by
> purpose on 2026-08-22. Numeric tables now live on the page for that
> purpose. Raw images stay gitignored under
> `.local-eval/synthid/prc-oklab-attack-2026-08-15/`.
>
> Seeds s1, s2, s3 are listed in
> [SynthID local detector research](synthid-detector-research.md).

| Page | Use it for |
| --- | --- |
| [SynthID local detector research](synthid-detector-research.md) | Hunt for a keyless local mark detector. Closed. |
| [Classifier models](synthid-classifiers.md) | Model 1 AI-versus-camera result, rejected provider CLIP, `pipeline_lattice` as google-lineage. |
| [SynthID mark removal research](synthid-removal-research.md) | Quiet-remover hunt. Closed except ~19-24 dB 16-32 scramble and blur sigma 7. |
| [Mechanism reference](synthid.md) | How SynthID works, provenance, robustness, regeneration. |
| [Chronological plan archive](synthid-detector-removal-plan.md) | Dated H-gates, corpora, and session notes in original order. |

## Where former sections went

| Former heading | Now |
| --- | --- |
| 2026-08-21 pairs, flats, L1 labels | [detector](synthid-detector-research.md) |
| Identity, token/layout, tomography, preprocess E1 | [detector](synthid-detector-research.md) (presentation gate) |
| L1 repair, L1 geometry, camera vs edit pair, E3 | [detector](synthid-detector-research.md) |
| CLIP-L photo vs AI, provider CLIP, union | [classifiers](synthid-classifiers.md) |
| 124-d three-class and binary AI | [classifiers](synthid-classifiers.md) |
| `pipeline_lattice` re-check, Spaces census | [classifiers](synthid-classifiers.md) |
| Attack / kill / flip / add / surround ladders | [removal](synthid-removal-research.md) |
| 16-32 titration, E2 scramble, Bayer and geometry | [removal](synthid-removal-research.md) |
| S4 provider split, M2 Imagen `addWatermark`, reverse-SynthID, Bypass | [detector](synthid-detector-research.md) |
| Photo `d'` budget 13.4 dB, 128-photo student, 16-32 residual without flat `G` | [detector](synthid-detector-research.md) |
| OKLab codeword replacement, add-context as presentation | [removal](synthid-removal-research.md) |
| Three-class OpenAI / Gemini / photo ask | [classifiers](synthid-classifiers.md) |
| Wild hypotheses 2026-08-23 (sort, CDMA, bispectrum, PRNU, affine-not-run) | [detector](synthid-detector-research.md) |
| Prepared polar / band-transplant / palette64 | [removal](synthid-removal-research.md) |
| External literature 2026-08-23 (Gowal, AWPD, PRC, Zhao, UnMarker, CtrlRegen, MarkNull, reverse-SynthID) | [detector](synthid-detector-research.md), [removal](synthid-removal-research.md), [classifiers](synthid-classifiers.md) |
| Adjacent literature, not SynthID (Cox, HiDDeN, StegaStamp, Tree-Ring, Ojha CLIP, Corvi Fourier, DCCT CFA, PRNU PCE) | [detector](synthid-detector-research.md), [classifiers](synthid-classifiers.md), [removal](synthid-removal-research.md) |
| Image investigation and data hiding (LSB, UNIWARD, Baluja, HiNet, Gaussian Shading, ELA, JPEG ghosts, DIRE, CNNDetect) | [detector](synthid-detector-research.md), [classifiers](synthid-classifiers.md) |
| Waveforms in a picture (DFT, Fourier-Mellin, Zernike, chirps, Fresnel, DRPE, cyclostationary) | [detector](synthid-detector-research.md) |
