# Visual simulation and video

The README's animation and downloadable film are generated from this repository's
actual SimPy model and allocation code. Neither the event timeline nor the
headline reduction is hand-authored. The 60-second video matches the public
LinkedIn demonstration format: setup, paired replay, evaluation, stress, evidence.

## Watch

- [Animated replay](https://github.com/tmummidi/Refueling/blob/visual-assets/preview.gif)
- [60-second captioned MP4](https://github.com/tmummidi/Refueling/blob/visual-assets/continuity_demo.mp4)
- [Results and event logs](https://github.com/tmummidi/Refueling/blob/visual-assets/continuity_demo.json)
- [Source revision and file hashes](https://github.com/tmummidi/Refueling/blob/visual-assets/manifest.json)

## Windows

From the repository root, with Python 3.12 installed:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install . -r visuals/requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s visuals -v
.\.venv\Scripts\python.exe visuals/make_video.py --output media/continuity_demo.mp4
Start-Process .\media\continuity_demo.mp4
```

On Linux/macOS replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.
Create the environment with `python3.12 -m venv .venv`.

The default film is 1080 x 1350, 24 fps, 60 seconds, silent with on-screen text.
An optional `--audio narration.wav` attaches your recording. The narration
outline is in [narration.txt](narration.txt). No API keys or GPU are required.
FFmpeg is provided by the pinned imageio-ffmpeg dependency.

Quick rendering check:

```powershell
.\.venv\Scripts\python.exe visuals/make_video.py --width 720 --fps 2 --duration 2 --output media/continuity_demo.mp4
```

This compresses the five-scene story into two seconds; it is a smoke test, not
the final video. Use the default settings for a complete film.

Create the README animation, results graphic, and provenance manifest after
rendering the complete video:

```powershell
.\.venv\Scripts\python.exe visuals/build_media.py --directory media
.\.venv\Scripts\python.exe visuals/verify_media.py --directory media
```

## How the visuals stay synchronized

1. Install the core package from the same checkout (`pip install .`), not a
   separately pinned old release.
2. Run the model on independent training, evaluation, and stress seed streams.
3. Replay the first held-out 8-site scenario under both allocations. Both receive
   the same incidents; the scenario is not selected for a favorable result.
4. Recompute the separate 64-site, 16-replication result and its paired interval.
5. Record hashes of the imported model modules, visual scripts, dependencies,
   and every published asset, alongside the source Git commit.
6. CI checks the original scientific tests and replay equivalence on Linux and
   Windows. On main, the visuals workflow rebuilds media and publishes it to the
   `visual-assets` branch using an ordinary, reversible Git commit.

The Actions workflow runs on source, test, dependency, and visual workflow changes.
An unrelated README edit does not require a new film. Existing media stays visible
if a new build fails; check the linked source revision and workflow status for
freshness. No promise of instantaneous synchronization is made.

## Reading the replay correctly

- Crew occupancy is shown as busy / assigned. Waiting squares are capped at 12
  per site; the numeric count includes all waiting incidents.
- The plot counts waiting plus in-service incidents and uses common axes.
- Half-hour samples draw the plot; instantaneous state counts use exact events.
- The 8-site replay and the 64-site repeated evaluation are different experiments.
- Stress doubles the arrival intensity in a separate held-out scenario while
  retaining the original allocation; it is not a mid-run shock.
- Unresolved incident-hours are not availability, asset downtime, or monetary
  savings. No employer data, topology, or claimed employer impact is used.
- Queue behavior can be worse at some sites or times under the optimized policy.
  The replay preserves this rather than forcing every view to look better.

## Dependencies and attribution

The renderer uses Pillow (HPND) and imageio-ffmpeg (BSD). Their bundled FFmpeg
and libx264 components retain their respective licensing requirements. We do
not commit executable binaries. Fonts are loaded from the local operating
system; CI uses DejaVu Sans. Renderer code is covered by the repository MIT license.
