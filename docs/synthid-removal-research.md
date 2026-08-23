# SynthID mark removal research

> Research archive for pixel-only SynthID removal, not diffusion
> regeneration. Not a statement of current product capability. Shipped
> invisible removal is lossy regeneration:
> [known limitations](known-limitations.md).
>
> Sister pages: [SynthID local detector](synthid-detector-research.md),
> [classifier models](synthid-classifiers.md),
> [mechanism reference](synthid.md).

## Result

The quality-preserving OpenAI SynthID remover hunt closed 2026-08-20.
Bayer, VNG demosaic, upscale-then-Bayer, barrel distortion, and scanline
jitter closed 2026-08-22: they leave the official oracle `detected`.

Working residual kills on photographs cost about 19-24 dB:

- 16-32 px phase scramble (s1 24.6 dB, fish 24.3 dB, s2 19.0 dB)
- Gaussian blur sigma 7 (23.8 dB), holds 3/3 versus sigma 6
- Additive 16-32 jam only at a=24 / 18.6 dB, worse than scramble

JPEG q5, noise sigma 16, grayscale, rot90, flip, 5°, downscale 0.20x,
median 7, posterize 4, VAE round-trip, and white pad to 40% linear stay
`detected`. Elastic warp is not a stable kill (s3 still `detected` at
22.0 dB).

The product remainder is diffusion regeneration (`qwen-zimage` /
`sdxl-zimage`), which does not decode and delete a payload. Defeating the
verifier does not restore forensic deniability; see
[synthid.md](synthid.md#23-removal-attacks-and-forensic-detectability).

Official `not_detected` on collage, photo-pad, and two-panel layouts is a
presentation gate, not residual damage. Those rungs are in
[detector research](synthid-detector-research.md).

## Closed quiet removers

| Attack | Close | Notes |
| --- | --- | --- |
| Quality-preserving photo remover | 2026-08-20 | Every residual `not_detected` that is not a collage is below usable quality |
| Additive in-band jam as a quiet remover | 2026-08-21 | Fish flips only at 18.6 dB; 4-8 px at the same PSNR stays `detected` |
| Bayer bilinear / VNG / upscale-Bayer | 2026-08-22 | s1/s2 still `detected`; VNG on s2 is dirtier than scramble (18.5 vs 19.0 dB) and the mark remains |
| Barrel k1=0.06 and scanline ±0.8 px | 2026-08-22 | s1/s2 `detected` even at 14-20 dB barrel |
| TrustMark-style micro-warp | 2026-08-21 | 0.25 px / 32 dB still 100% detect on TrustMark P; OpenAI elastic ~21 dB unreplicated |

Oracle: `verify_openai_synthid` after AI-metadata strip. Seeds s1, s2, s3
as in [detector research](synthid-detector-research.md). Raw files:
`.local-eval/synthid/prc-oklab-attack-2026-08-15/`.

## Band that actually carries the mark

Phase-randomize one octave at a time, preserve energy (E2, s1, replicated
p16_32 on s2 and s3):

| Octave (period px) | Verdict |
| --- | --- |
| 2-4 | detected |
| 4-8 | detected |
| 8-16 | detected |
| 16-32 | not_detected |
| 32-64 | detected |
| 64-128 | detected |

Destroying only 16-32 px periods silences the official decoder. The
lattice band 8-16 px does not. On a marked gray flat the same scramble is
51.1 dB `not_detected` because the band is almost empty. On a photograph
the band holds the scene (24.3 dB). Replacing native 16-32 with a
2x-pyramid prediction is 48.4 dB and still `detected`.

Fish additive jam, luma RMS `a`:

| Band | a | PSNR | Verdict |
| --- | ---: | ---: | --- |
| 16-32 | 0.06-4.0 | 51.2-33.6 | detected |
| 16-32 | 8 | 27.7 | detected |
| 16-32 | 16 | 21.9 | detected |
| 16-32 | 24 | 18.6 | not_detected |
| 4-8 | 16 | 21.9 | detected |
| 4-8 | 24 | 18.6 | detected |

Preregistered close `a*_photo < 0.53` failed (`a* > 16`).

## Bayer and geometry (2026-08-22)

Frozen one-pass batch. Lattice scores on these OpenAI sources are already
`indeterminate` and are not the label. s3 and the fish photo were queued
after an OpenAI 429.

| Attack | s1 PSNR / oracle | s2 PSNR / oracle |
| --- | --- | --- |
| source | detected | detected |
| Bayer bilinear | 32.7 detected | 28.4 detected |
| Bayer VNG | 25.0 detected | 18.5 detected |
| upscale 1.15 then Bayer | 33.9 detected | 29.8 detected |
| barrel k1=0.06 | 19.9 detected | 14.2 detected |
| scanline ±0.8 px | 31.5 detected | 26.7 detected |
| shift 2 px | 23.1 detected | (429, not submitted) |
| 16-32 phase scramble | 24.6 not_detected | 19.0 not_detected |

Camera pipeline and mild geometry do not hit the decoder basis. A 2 px
shift, which kills `pipeline_lattice`, left s1 `detected`.
`.local-eval/synthid/prc-oklab-attack-2026-08-15/bayer-geometry-2026-08-22/`.

## Attack ladders (OpenAI oracle)

Pilot 2026-08-17 (n=3): JPEG q40, 0.5x, noise8+jpeg85, 0.35x+jpeg50 all
`detected` (s2 0.35x+jpeg50 at 20.1 dB still detected).

Kill and flip (s1), then replication 3/3:

| Rung | s1 | s2 | s3 |
| --- | --- | --- | --- |
| blur sigma 6 | detected | detected | detected |
| blur sigma 7 | not_detected | not_detected | not_detected |
| keep 0.50 linear | detected | detected | detected |
| keep 0.40 linear | not_detected | not_detected | not_detected |
| elastic ~24 dB | detected 24.6 | detected 17.9 | detected 26.1 |
| elastic ~21 dB | not_detected 20.8 | not_detected 14.8 | detected 22.0 |
| pad white 40% linear | detected | detected | detected |
| hstack with photo | not_detected | not_detected | not_detected |
| blend 25% marked | detected | detected | detected |
| inset native 1:1 on 2x photo | not_detected | not_detected | not_detected |
| JPEG q5 | detected | detected | detected |

Holds on 3/3: blur 6 vs 7, crop keep 0.50 vs 0.40, white pad 40%
`detected`, hstack `not_detected`, blend 25% `detected`, JPEG q5
`detected`. Elastic at ~21 dB does not hold. Crop keep-0.40 and hstack
are presentation or support, not a quiet residual wipe.

Surround: photo fill at the white-pad geometries is `not_detected` on
3/3; white pad at those sizes was `detected`. Unmarked photo strip flips
between 25% width (`detected`) and 35% (`not_detected`). Photo frame 15%
each side is `not_detected` on 3/3; 12% does not hold.

## Product remainder for removal

Invisible removal in this package regenerates through `qwen-zimage` or
`sdxl-zimage`. It is lossy. There is no shipped pixel-only OpenAI or
Google SynthID wipe. Do not add Bayer or geometry as remover arms.
