"""Export a README preview and provenance manifest from a completed video run."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image
from make_video import Film


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path('media'))
    args=parser.parse_args()
    folder=args.directory
    evidence=json.loads((folder/'continuity_demo.json').read_text())
    film=Film(evidence,720,900)
    film.frame(19).save(folder/'poster.png')
    # Replay the same actual 72-hour scenario in eight seconds, with a two-second
    # final hold. Global palette avoids unstable colors between GIF frames.
    frames=[film.frame(7+21*i/63) for i in range(64)]
    palette=frames[-1].quantize(colors=64)
    frames=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
    frames[0].save(folder/'preview.gif',save_all=True,append_images=frames[1:],
                   duration=[125]*63+[2125],loop=0,optimize=False,disposal=2)
    result=evidence['reports'][1]['result']['heldout']
    b=result['means']['baseline']['weighted_unresolved_hours']
    o=result['means']['optimized']['weighted_unresolved_hours']
    reduction=100*(b-o)/b
    ci=result['baseline_minus_optimized']
    maximum=max(b,o)
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 420" role="img" aria-labelledby="title description">
<title id="title">Continuity allocation: measured comparison</title>
<desc id="description">64 synthetic sites, 128 available crews, 16 held-out replications. Even allocation {b:.1f} versus optimized {o:.1f} mean weighted unresolved incident-hours. Lower is better.</desc>
<rect width="1000" height="420" rx="16" fill="#0c1423"/>
<g font-family="Arial,sans-serif" fill="#f0f4fa">
<text x="40" y="50" font-size="28">Same crew budget. Measured allocation tradeoffs.</text>
<text x="40" y="86" font-size="19" fill="#b1c0d3">64 sites · 128 crews · 72 hours · 16 held-out replications</text>
<text x="40" y="142" font-size="22">Even allocation</text><text x="960" y="142" text-anchor="end" font-size="22">{b:,.0f}</text>
<rect x="40" y="158" width="{920*b/maximum:.1f}" height="34" rx="4" fill="#ffbb66"/>
<text x="40" y="238" font-size="22">Optimized allocation</text><text x="960" y="238" text-anchor="end" font-size="22">{o:,.0f}</text>
<rect x="40" y="254" width="{920*o/maximum:.1f}" height="34" rx="4" fill="#58dcc1"/>
<text x="40" y="335" font-size="23">{reduction:.1f}% reduction in mean weighted unresolved incident-hours</text>
<text x="40" y="370" font-size="18" fill="#b1c0d3">Paired reduction 95% interval: [{ci['lower_95']:,.0f}, {ci['upper_95']:,.0f}] weighted hours</text>
<text x="40" y="401" font-size="17" fill="#b1c0d3">Independent synthetic study. This metric is not asset uptime.</text>
</g></svg>'''
    (folder/'comparison.svg').write_text(svg,encoding='utf-8')
    paths=['continuity_demo.mp4','continuity_demo.json','continuity_demo.srt',
           'preview.gif','poster.png','comparison.svg']
    manifest={'provenance':evidence['provenance'],
              'assets_sha256':{name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
                               for name in paths},
              'video':evidence['video'], 'seed':evidence['seed']}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
    rev=evidence['provenance']['source_commit']
    (folder/'README.md').write_text(f'''# Generated continuity visuals

Source revision: [{rev}](https://github.com/tmummidi/Refueling/tree/{rev}).

[Watch or download the 60-second MP4](continuity_demo.mp4) · [Evidence](continuity_demo.json) · [Source and asset fingerprints](manifest.json)

![Synchronized replay of one held-out scenario](preview.gif)

![Measured 64-site comparison](comparison.svg)

The 8-site replay is one held-out simulation. The 64-site chart summarizes 16
independent replications. These are synthetic incidents, not employer systems.
The video is silent with captions. Its source is in the main branch's visuals/
directory. This branch is regenerated after verified model/renderer changes;
commits preserve previous visual releases. Do not edit generated files here.
''')
    print('Created preview.gif, poster.png, comparison.svg, and manifest.json')


if __name__=='__main__':main()
