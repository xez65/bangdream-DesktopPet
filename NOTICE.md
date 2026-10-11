# Asset notice / 素材声明

## What is not covered by the MIT license

Everything under `assets/` except the two JSON manifests is **derived third-party artwork**, not
original work by this repository's author:

| path | origin |
|---|---|
| `assets/clips/**/*.webp` | 2,166 frames baked from Live2D models and motion/expression sets of a *Bang Dream! It's MyGO!!!!! / Ave Mujica* character, through an offline Unity/Cubism capture pipeline. The 1024² sources are not in this repository. |
| `assets/app.ico`, `assets/icon_candidate_subject.png`, `assets/icon_candidate_centred.png` | the application icon, cropped from a character image held by the author; the two candidates are the same subject cropped differently. |
| `assets/clips.json` | technical manifest: crop box, fps, WebP settings, and the sha256 of the source index the pack was built from. No artwork. |
| `assets/text/lines.json` | spoken lines, original text written for this project. |

The characters, the artwork and the underlying Live2D models belong to the rights holders of the
BanG Dream! franchise and to the illustrators and redistributors whose material the sources came from.
Publishing them here as part of a personal hobby project does not transfer any rights, and the MIT
license in `LICENSE` is deliberately limited to the code.

## Attribution carried over from the source sets

One of the motion/expression source folders on the author's machine carried the note
「在视频当中使用请 @冲矢明逸」 — a request to credit **冲矢明逸** when those motions are used in
video. That request is passed along here; it is not a license grant.

## What you may and may not do

- You may run this locally, study it, and fork the code.
- You may **not** treat `assets/clips/` or the icon as free material to redistribute, repackage,
  sell, train on, or ship inside your own project.
- If you build your own pet from this chassis, replace `assets/clips/`, `assets/clips.json` and
  `assets/app.ico` with artwork you have the right to distribute. The only files that name this
  character are `src/petcore/clip_manifest.py` (slugs, labels, motion pools) and
  `assets/text/lines.json` (lines); everything else reads from them.

## Takedown

If you hold rights to any asset here and want it removed, open an issue — the repository is a personal
hobby build and will be taken down or have the asset removed on request.
