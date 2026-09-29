"""Render a reproducible, captioned continuity simulation film.

No API keys, AI-generated simulation frames, or network calls at render time.
The core model is imported from the pinned Refueling package (see requirements).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import time

for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(key, '1')

import numpy as np
import simpy
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
from continuity.cli import DEFAULT, run
from continuity.simulation import generate, evaluate

BG = '#0c1423'
CARD = '#152237'
LINE = '#30425b'
INK = '#f0f4fa'
MUTED = '#b1c0d3'
AMBER = '#ffbb66'
TEAL = '#58dcc1'
RED = '#ff818c'


def trace(jobs_by_site, allocation, horizon=72.0):
    """Instrument the same SimPy FIFO queue used by the model.

    Preserve unfinished service as end=None; no fabricated completions.
    Inclusive horizon agrees with continuity.simulation.simulate.
    """
    if len(jobs_by_site) != len(allocation):
        raise ValueError('One crew count per site is required')
    sites = []
    for jobs, crews in zip(jobs_by_site, allocation):
        if int(crews) != crews or crews < 0:
            raise ValueError('Crew counts must be nonnegative integers')
        env = simpy.Environment()
        rows = [dict(arrival=j.arrival, duration=j.repair_hours,
                     weight=j.weight, start=None, end=None) for j in jobs]
        resource = simpy.Resource(env, int(crews)) if crews else None

        def process(row):
            yield env.timeout(row['arrival'])
            with resource.request() as request:
                yield request
                row['start'] = float(env.now)
                yield env.timeout(row['duration'])
                row['end'] = float(env.now)

        if crews:
            for row in rows:
                env.process(process(row))
            env.run(until=np.nextafter(float(horizon), np.inf))
        sites.append(rows)
    return sites


def state(rows, hour):
    arrived = [r for r in rows if r['arrival'] <= hour]
    waiting = sum(r['start'] is None or r['start'] > hour for r in arrived)
    active = sum(r['start'] is not None and r['start'] <= hour
                 and (r['end'] is None or r['end'] > hour) for r in arrived)
    done = sum(r['end'] is not None and r['end'] <= hour for r in arrived)
    loss = sum(max(0., min(hour, r['end'] if r['end'] is not None else hour)
                       - r['arrival']) * r['weight'] for r in arrived)
    return dict(waiting=waiting, active=active, done=done, loss=float(loss),
                arrived=len(arrived))


def totals(sites, hour):
    values = [state(rows, hour) for rows in sites]
    return {k: sum(v[k] for v in values) for k in values[0]}


def build_evidence(seed):
    configs = [dict(DEFAULT, seed=seed, sites=n, budget=2*n,
                    train_seeds=4, test_seeds=16) for n in (8, 64)]
    reports = []
    for config in configs:
        start = time.perf_counter()
        result = run(config)
        reports.append(dict(config=config, result=result,
                            measured_runtime_seconds=time.perf_counter()-start))
    demo = reports[0]['result']
    # Deterministic first held-out seed; never choose a visually favorable run.
    scenes = {}
    for label, seed_key, intensity in [('normal', 'test_seeds', 1.),
                                       ('stress', 'stress_seeds', 2.)]:
        scenario_seed = demo[seed_key][0]
        jobs = generate(scenario_seed, 8, 72., intensity)
        scenes[label] = {'seed': scenario_seed, 'intensity': intensity}
        for policy, key in [('even', 'baseline_allocation'), ('optimized', 'allocation')]:
            events = trace(jobs, demo[key])
            observed = totals(events, 72.)
            expected = evaluate(jobs, demo[key], 72., 6.)
            if not np.isclose(observed['loss'], expected['weighted_unresolved_hours']):
                raise AssertionError('Replay disagrees with the core loss metric')
            if observed['done'] != expected['completed']:
                raise AssertionError('Replay disagrees with the completion count')
            scenes[label][policy] = events
    return {'provenance': provenance(), 'python': platform.python_version(),
            'platform': platform.platform(), 'seed': seed,
            'scope': 'Independent synthetic study; no employer data or impact claims',
            'reports': reports, 'scenes': scenes}


def provenance():
    """Fingerprint the imported model and renderer, including local edits."""
    import continuity
    root = Path(__file__).resolve().parents[1]
    try:
        revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,
                                           text=True,stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git','status','--porcelain', '--',
                     'src/continuity','visuals','pyproject.toml'],cwd=root,text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None
    model_dir = Path(continuity.__file__).resolve().parent
    files = {f'src/continuity/{p.name}':hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(model_dir.glob('*.py'))}
    for p in sorted(Path(__file__).parent.glob('*.py')):
        files[f'visuals/{p.name}'] = hashlib.sha256(p.read_bytes()).hexdigest()
    for relative in ('pyproject.toml','visuals/requirements.txt'):
        p=root/relative
        if p.is_file(): files[relative]=hashlib.sha256(p.read_bytes()).hexdigest()
    return {'source_commit':revision, 'working_tree_modified':dirty,
            'source_sha256':files,
            'versions':{name:importlib.metadata.version(name) for name in
                        ('numpy','scipy','simpy','Pillow','imageio-ffmpeg')}}


def find_font(explicit=None):
    paths = [explicit] if explicit else []
    paths += [r'C:\Windows\Fonts\arial.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              '/System/Library/Fonts/Supplemental/Arial.ttf']
    for p in paths:
        if p and Path(p).is_file():
            return str(p)
    return None


class Film:
    """Draw in a 1080 x 1350 design space, scaled to requested resolution."""
    def __init__(self, evidence, width=1080, height=1350, font=None):
        self.e = evidence
        self.width, self.height = width, height
        self.scale = width / 1080
        self.font_path = find_font(font)
        self.fonts = {}
        self.curves = {}
        for label, scene in evidence['scenes'].items():
            grid = np.linspace(0,72,145)
            series = []
            for policy,color in [('even',AMBER),('optimized',TEAL)]:
                values = [totals(scene[policy],float(t)) for t in grid]
                series.append((color,np.array([v['waiting']+v['active'] for v in values])))
            self.curves[label] = (grid,series)

    def f(self, size):
        size = max(10, round(size*self.scale))
        if size not in self.fonts:
            self.fonts[size] = (ImageFont.truetype(self.font_path, size)
                                if self.font_path else ImageFont.load_default(size=size))
        return self.fonts[size]

    def box(self, rect, fill=CARD, outline=None, radius=16):
        self.d.rounded_rectangle(tuple(round(v*self.scale) for v in rect),
                                 radius=round(radius*self.scale), fill=fill,
                                 outline=outline, width=max(1, round(self.scale)))

    def text(self, xy, text, size=28, color=INK, anchor=None):
        self.d.text(tuple(round(v*self.scale) for v in xy), str(text),
                    font=self.f(size), fill=color, anchor=anchor)

    def line(self, points, fill=LINE, width=2):
        self.d.line([(round(x*self.scale), round(y*self.scale)) for x,y in points],
                    fill=fill, width=max(1, round(width*self.scale)))

    def header(self, chapter, headline, subline):
        self.text((52,38), 'REFUELING  /  DECISION SYSTEMS', 23, TEAL)
        self.text((1028,38), chapter, 22, MUTED, 'ra')
        self.text((52,93), headline, 43)
        self.text((52,158), subline, 25, MUTED)

    def caption(self, first, second):
        self.box((40,1168,1040,1270), '#202e44')
        self.text((540,1191), first, 28, INK, 'ma')
        self.text((540,1230), second, 25, MUTED, 'ma')

    def bars(self, rect, baseline, optimized):
        x,y,w = rect
        maximum = max(baseline, optimized, 1.)
        for index, (name,value,color) in enumerate([
                ('EVEN ALLOCATION',baseline,AMBER), ('OPTIMIZED',optimized,TEAL)]):
            yy=y+index*145
            self.text((x,yy),name,25,color)
            self.text((x+w,yy),f'{value:,.0f}',30,INK,'ra')
            self.box((x,yy+52,x+w,yy+101),BG,radius=7)
            self.box((x,yy+52,x+max(2,w*value/maximum),yy+101),color,radius=7)

    def replay(self, hour, label):
        scene = self.e['scenes'][label]
        demo = self.e['reports'][0]['result']
        self.text((52,215),f'SIMULATED TIME  {hour:05.1f} / 72 h',29)
        self.text((1028,219),f'8 sites  |  16 crews available',23,MUTED,'ra')
        for x, policy, allocation, color in [
                (40,'even',demo['baseline_allocation'],AMBER),
                (554,'optimized',demo['allocation'],TEAL)]:
            self.box((x,274,x+486,919))
            self.text((x+22,294), 'EVEN ALLOCATION' if policy=='even' else 'OPTIMIZED',27,color)
            self.text((x+22,338),f'{sum(allocation)} crews assigned',22,MUTED)
            self.text((x+22,378),'SITE     CREWS BUSY     WAITING INCIDENTS',17,MUTED)
            for i, rows in enumerate(scene[policy]):
                st=state(rows,hour)
                yy=419+i*55
                self.text((x+22,yy),f'{i+1:02}',25)
                self.text((x+100,yy),f"{st['active']} / {allocation[i]}",25,color)
                visible=min(st['waiting'],12)
                for j in range(visible):
                    xx=x+209+j*15
                    self.box((xx,yy+6,xx+10,yy+25),color,radius=2)
                # Count labels are authoritative; squares are capped for legibility.
                self.text((x+462,yy),st['waiting'],25,INK,'ra')
            t=totals(scene[policy],hour)
            self.text((x+22,874),f"Completed: {t['done']}   Unfinished: {t['active']+t['waiting']}",21,MUTED)
        self.text((52,944),'BACKLOG OVER TIME  /  waiting + in service',21,MUTED)
        grid,series=self.curves[label]
        upper=max(1,max(float(vals.max()) for _,vals in series))
        self.line([(83,982),(83,1110),(1010,1110)])
        self.text((70,978),f'{math.ceil(upper)}',18,MUTED,'ra')
        self.text((70,1096),'0',18,MUTED,'ra')
        for color,values in series:
            mask=grid<=hour
            points=[(83+t/72*927,1110-v/upper*122) for t,v in zip(grid[mask],values[mask])]
            if len(points)>1:self.line(points,color,4)
        for t in [0,24,48,72]:
            self.text((83+t/72*927,1120),f'{t}h',18,MUTED,'ma')

    def frame(self, seconds):
        self.im=Image.new('RGB',(self.width,self.height),BG)
        self.d=ImageDraw.Draw(self.im)
        if seconds<7:
            self.header('01 / THE DECISION','Same resources. Different decisions.','Allocate repair crews before a 72-hour incident horizon.')
            self.box((40,244,1040,798))
            self.text((540,285),'SIMULATION + OPTIMIZATION',27,TEAL,'ma')
            for x,big,small in [(210,'8','sites in replay'),(540,'16','available crews'),(870,'72h','planning horizon')]:
                self.text((x,395),big,86,INK,'ma');self.text((x,502),small,26,MUTED,'ma')
            self.text((540,640),'Uneven incident demand creates uneven queues.',30,INK,'ma')
            self.text((540,696),'Where should the same crew budget go?',30,INK,'ma')
            self.text((540,888),'Simulate staffing options. Optimize the allocation.',30,TEAL,'ma')
            self.text((540,944),'Evaluate on independent incident scenarios.',28,MUTED,'ma')
            self.caption('Equal staffing sounds reasonable.','But some sites accumulate incidents faster than others.')
        elif seconds<30:
            self.header('02 / PAIRED REPLAY','Identical incidents. Shared clock.','One held-out scenario; both policies receive the same incidents.')
            self.replay(min(72,(seconds-7)/21*72),'normal')
            self.caption('Watch where work accumulates under each allocation.','Each square is a waiting incident; numeric counts include overflow.')
        elif seconds<41:
            r=self.e['reports'][1]['result']; h=r['heldout'];m=h['means']
            b=m['baseline']['weighted_unresolved_hours'];o=m['optimized']['weighted_unresolved_hours']
            reduction=100*(b-o)/b;ci=h['baseline_minus_optimized']
            self.header('03 / EVALUATION','Measure across independent runs.','64 sites  |  128 available crews  |  16 held-out replications')
            self.box((40,250,1040,1099))
            self.text((80,285),'MEAN WEIGHTED UNRESOLVED INCIDENT-HOURS',25,MUTED)
            self.bars((80,350,920),b,o)
            self.text((540,683),f'{abs(reduction):.1f}% '+('lower' if reduction>=0 else 'higher'),72,TEAL,'ma')
            self.text((540,785),'Compared with even allocation',28,INK,'ma')
            self.text((80,885),f"Paired mean reduction: {ci['mean']:,.0f} weighted hours",27)
            self.text((80,936),f"95% interval: [{ci['lower_95']:,.0f}, {ci['upper_95']:,.0f}]",27,MUTED)
            self.text((80,1002),'Sampling uncertainty; not all model uncertainty.',23,MUTED)
            self.caption('A replay explains behavior. Repeated runs evaluate it.','This metric measures unresolved incidents, not asset uptime.')
        elif seconds<54:
            self.header('04 / STRESS TEST','Double the incident arrival intensity.','Allocation stays fixed; this is a separate held-out stress scenario.')
            self.replay(min(72,(seconds-41)/11*72),'stress')
            self.caption('Better allocation still has a capacity limit.','The stress run shows the remaining backlog under both policies.')
        else:
            self.header('05 / REPRODUCE','Inspect the decision. Rerun the evidence.','Independent implementation with synthetic incidents.')
            self.box((40,260,1040,1050))
            for yy,num,title,detail in [
                (310,'01','SIMULATE','SimPy queues and heterogeneous incident demand'),
                (475,'02','ALLOCATE','Mixed-integer optimization with a free solver'),
                (640,'03','VERIFY','Held-out scenarios, paired intervals, stress tests')]:
                self.text((80,yy),num,40,TEAL)
                self.text((170,yy),title,33)
                self.text((170,yy+62),detail,24,MUTED)
            self.text((540,891),'github.com/tmummidi/Refueling',37,TEAL,'ma')
            self.text((540,961),'Code. Assumptions. Tests. Reproducible results.',25,MUTED,'ma')
            self.caption('A decision system should make its tradeoffs inspectable.','The model, evaluation, and failure cases are public.')
        self.line([(40,1300),(1040,1300)],LINE,2)
        self.text((40,1311),'INDEPENDENT SYNTHETIC STUDY  /  NOT EMPLOYER RESULTS',18,MUTED)
        return self.im


def captions():
    return [(0,7,'Equal staffing sounds reasonable.\nBut sites accumulate incidents at different rates.'),
            (7,30,'Same incidents. Same crew budget.\nWatch the queues under each allocation.'),
            (30,41,'Evaluate across independent runs.\nUnresolved incident-hours are not asset uptime.'),
            (41,54,'Double incident arrival intensity.\nBetter allocation still has a capacity limit.'),
            (54,60,'Inspect the code, assumptions, and evidence.\ngithub.com/tmummidi/Refueling')]


def stamp(seconds):
    ms=round(seconds*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('output/continuity_demo.mp4'))
    p.add_argument('--width',type=int,default=1080)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--duration',type=float,default=60.)
    p.add_argument('--seed',type=int,default=20260929)
    p.add_argument('--font',help='Optional path to a TrueType font')
    p.add_argument('--audio',type=Path,help='Optional narration file; padded or trimmed to video length')
    p.add_argument('--evidence-only',action='store_true')
    args=p.parse_args()
    if args.width<540 or args.width%8 or args.fps<1 or args.duration<=0:
        p.error('width must be >=540 and divisible by 8; fps and duration must be positive')
    if args.audio and not args.audio.is_file():p.error('Audio file not found')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    print('Running core model and verifying event replay...',flush=True)
    evidence=build_evidence(args.seed)
    evidence['video']={'width':args.width,'height':args.width*5//4,
                       'fps':args.fps,'duration':args.duration,'audio':bool(args.audio)}
    args.output.with_suffix('.json').write_text(json.dumps(evidence,indent=2,allow_nan=False))
    if args.evidence_only:return
    film=Film(evidence,args.width,args.width*5//4,args.font)
    for sec in [3,19,35,50,57]:
        film.frame(sec).save(args.output.parent/f'preview-{sec:02}.png')
    frames=round(args.duration*args.fps)
    temp=args.output.with_name(args.output.stem+'.silent.mp4') if args.audio else args.output
    writer=imageio_ffmpeg.write_frames(str(temp),(film.width,film.height),fps=args.fps,
        codec='libx264',pix_fmt_in='rgb24',pix_fmt_out='yuv420p',
        output_params=['-crf','20','-preset','fast','-movflags','+faststart'],
        macro_block_size=2,ffmpeg_log_level='error')
    writer.send(None)
    try:
        for i in range(frames):
            writer.send(np.asarray(film.frame(i/frames*60)))
            if i%(args.fps*5)==0:print(f'Rendered {i}/{frames} frames',flush=True)
    finally:writer.close()
    if args.audio:
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(temp),'-i',str(args.audio),
            '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-af','apad',
            '-t',str(frames/args.fps),'-movflags','+faststart',str(args.output)],check=True)
        temp.unlink()
    factor=args.duration/60
    srt='\n\n'.join(f'{i}\n{stamp(a*factor)} --> {stamp(b*factor)}\n{text}'
                      for i,(a,b,text) in enumerate(captions(),1))+'\n'
    args.output.with_suffix('.srt').write_text(srt,encoding='utf-8')
    print(f'Created {args.output.resolve()}',flush=True)


if __name__=='__main__':main()
