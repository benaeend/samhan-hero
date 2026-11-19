"""발열·배터리 측정 도구(2026-11 절전 그리기 작업에서 만듦). 빌드된 index.html의 사본에 시간 재는 코드만 끼워 헤드리스 크롬으로 돌려,
프레임당 게임 코드 시간·브라우저 전체 CPU(%)·그리기 호출 수·DOM 갱신 수를 잰다. 원본은 건드리지 않는다.

사용(다른 시험과 겹치면 숫자가 흔들리니 잠금을 잡고):
  flock /tmp/samhan-test.lock python3 tools/perf_probe.py late            # 후반 저장 가로 사냥 60초
  flock /tmp/samhan-test.lock python3 tools/perf_probe.py late --mode on  # 그리기 방식(off=부드럽게/auto/on=절전)을 정해서
  작업 이름: new(새 캐릭터) late(후반 사냥) tab(후반+수련 메뉴 열림) raid(레이드) portrait(세로) sleep(절전 화면) title(로그인 화면) tabs(탭별 갱신 시간) all
환경: PERF_INDEX=<index.html 경로> 로 다른 판(예: git show 로 꺼낸 옛 판)을 재서 전후 비교
옵션: --mode off|auto|on  --secs 60  --count(그리기 호출·DOM 수 세기: 느려지니 CPU 숫자와 따로)
결과 JSON·캡처는 /tmp/samhan-perf/out/ 에. 이 환경(화면 없는 크롬, 그래픽 칩 없음)의 숫자는 방향·순위만 믿을 것(실기기는 다름).
주의: 5% 안쪽 차이는 같은 조건 두 번 재도 나오는 흔들림이다.
"""
import asyncio, json, os, sys, time, threading, functools, shutil
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from playwright.async_api import async_playwright
ROOT = Path(__file__).resolve().parent.parent; HERE = Path(__file__).resolve().parent; WORK = Path('/tmp/samhan-perf'); SITE = WORK / 'site'; OUT = WORK / 'out'; SITE.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
SIMD = ROOT / 'docs' / 'patch-sea' / 'sim'
INJ0 = """if (window.__perfOpt){ const O = window.__perfOpt;
 if (O.hudDiv){ const f = updateHud; let n = 0; updateHud = function(){ if (n++ % O.hudDiv === 0) f(); }; }
 if (O.renderDiv){ const f = render; let n = 0; render = function(){ if (n++ % O.renderDiv === 0) f(); }; }
 if (O.skipPage){ const f = render; render = function(){ const pg = document.querySelector('#page'); if (pg && !pg.hidden && !document.body.classList.contains('portrait')) return; f(); }; }
}
"""
INJ = INJ0 + "if (window.__perfNames){ for (const n of window.__perfNames){ try { eval(n + ' = window.__perfWrap(' + JSON.stringify(n) + ', ' + n + ')'); } catch (e) { (window.__perfMiss = window.__perfMiss || []).push(n); } } }\n"
MARK = "if (location.search.indexOf('simtest') >= 0){"

def make_site(name, patches=()):
    src = Path(os.environ.get('PERF_INDEX') or ROOT / 'index.html').read_text(encoding='utf-8')   # PERF_INDEX=다른 index.html 로 이전 판과 비교
    assert src.count(MARK) == 1
    src = src.replace(MARK, INJ + MARK)
    for a, b in patches:
        assert src.count(a) == 1, (a, src.count(a))
        src = src.replace(a, b)
    (SITE / name).write_text(src, encoding='utf-8')

class H(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin'); self.send_header('Cross-Origin-Embedder-Policy', 'require-corp'); self.send_header('Cache-Control', 'no-store')
        super().end_headers()
    def log_message(self, *a): pass

def serve():
    srv = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(H, directory=str(SITE)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{srv.server_address[1]}/'

def proc_cpu(root_pid):
    """브라우저와 그 자식 프로세스 전부의 CPU 초(종류별)"""
    kids = {}
    for p in os.listdir('/proc'):
        if not p.isdigit(): continue
        try:
            s = open(f'/proc/{p}/stat').read(); r = s.rsplit(')', 1)[1].split()
            kids[int(p)] = (int(r[1]), (int(r[11]) + int(r[12])) / os.sysconf('SC_CLK_TCK'))
        except Exception: pass
    out = {}
    def typ(pid):
        try: c = open(f'/proc/{pid}/cmdline').read().replace('\0', ' ').split()
        except Exception: return '?'
        for a in c:
            if a.startswith('--type='): return a[7:] + ('/' + [x for x in c if x.startswith('--utility-sub-type=')][0].split('.')[-1] if any(x.startswith('--utility-sub-type=') for x in c) else '')
        return 'browser'
    def walk(pid):
        if pid in kids:
            t = typ(pid); out[t] = out.get(t, 0) + kids[pid][1]
        for k, (pp, _) in kids.items():
            if pp == pid: walk(k)
    walk(root_pid)
    return out

async def find_browser_pid():
    # 내 파이썬 프로세스의 자손 가운데 --type 없는 크롬(= 브라우저 본체)
    pp = {}
    for p in os.listdir('/proc'):
        if not p.isdigit(): continue
        try: pp[int(p)] = int(open(f'/proc/{p}/stat').read().rsplit(')', 1)[1].split()[1])
        except Exception: pass
    me = os.getpid(); best = None
    for p in pp:
        try: c = open(f'/proc/{p}/cmdline').read()
        except Exception: continue
        if 'headless' in c and '--type=' not in c and '--remote-debugging' in c:
            x = p
            while x in pp and x != me and x > 1: x = pp[x]
            if x == me: best = max(best or 0, p)
    return best

def others():
    n = 0; me = os.getpid()
    for p in os.listdir('/proc'):
        if p.isdigit():
            try:
                c = open(f'/proc/{p}/cmdline').read()
                if '--type=renderer' in c: n += 1
            except Exception: pass
    return n - 1

SETUP_LATE = """([save]) => { const G = window.__game; G.noFork = true; G.noInh = true; G.gateOff = true;
  Object.assign(G.S, G.mergeState(JSON.parse(save))); const S = G.S; if (S.world >= 3 && G.refineInherit) G.refineInherit();
  S.inv.potion = 9999; S.inv.elixir = 9999; S.inv.mana = 9999; G.refreshStats(); G.setStage(S.stage); return {w:S.world, st:S.stage, lv:S.level, cls:S.cls}; }"""
KEEP = """() => { const G = window.__game; window.__keep = {cut:0, modal:0}; window.__keepT = setInterval(() => {
  if (G.cut){ window.__keep.cut++; const b = document.querySelector('#cutSkip'); if (b) b.click(); }
  const m = document.querySelector('#modal'); if (m && !m.hidden){ window.__keep.modal++; const b = document.querySelector('#modal .btn.primary') || document.querySelector('#modal-btn-0'); if (b) b.click(); }
}, 1000); }"""

async def run(base, name, site='base.html', vp=(844, 390), dsf=2, opt=None, save=None, tab=None, raid=False, secs=60, throttle=0, trace=False, count=False, sleep=False, title=False, mode=None):
    opt = dict(opt or {}); opt['count'] = count
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--no-sandbox'])
        pid = None
        for _ in range(20):
            pid = await find_browser_pid()
            if pid: break
            await asyncio.sleep(0.2)
        ctx = await b.new_context(viewport={'width': vp[0], 'height': vp[1]}, device_scale_factor=dsf, service_workers='block')
        await ctx.add_init_script("window.__samhanOnline = {url: ''}; window.__perfOpt = " + json.dumps(opt) + ";")
        if mode: await ctx.add_init_script("try { localStorage.setItem('samhan-lite', '" + mode + "'); } catch (e) {}")
        await ctx.add_init_script(path=str(HERE / 'perf_probe_harness.js'))
        page = await ctx.new_page(); errs = []
        page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(base + site + '?simtest'); await page.wait_for_timeout(1000)
        await page.click('#lg-tab-signup'); await page.fill('#lg-id', 'perf'); await page.fill('#lg-pw', '1234'); await page.fill('#lg-pw2', '1234'); await page.click('#modal-btn-0')
        await page.wait_for_selector('#mTitle:has-text("캐릭터 고르기")'); await page.click('#modal-btn-0'); await page.wait_for_selector('#cc-name')
        await page.fill('#cc-name', '측정용사'); await page.click('#cc-musa'); await page.click('#modal-btn-1')
        await page.wait_for_function('() => window.__game.session && document.querySelector("#modal").hidden'); await page.wait_for_timeout(1500)
        await page.evaluate('() => { const b = document.querySelector("#cutSkip"); if (window.__game.cut && b) b.click(); }')
        await page.evaluate('() => document.body.dispatchEvent(new PointerEvent("pointerdown", {bubbles: true}))')   # 소리 켜기(진짜 플레이처럼)
        info = None
        if save: info = await page.evaluate(SETUP_LATE, [json.dumps(json.loads((SIMD / save).read_text(encoding='utf-8')))])
        await page.evaluate(KEEP)
        if raid: info = await page.evaluate("() => { const G = window.__game; G.S.raid.tk = 3; const n = G.raidUnlocked ? G.raidUnlocked() : 1; const ok = G.startRaid(Math.max(0, n - 1)); if (G.raid && G.raid.boss){ G.raid.boss.hp = G.raid.boss.maxHp = 1e300; } return {ok, n, label:G.raid && G.raid.info.label, allies:G.raid && G.raid.allies.length}; }")
        if tab: await page.evaluate("([t]) => window.__game.buildTab(t)", [tab])
        if sleep: info = await page.evaluate('() => window.__game.sleepEnter()')
        if title: await page.reload(); await page.wait_for_timeout(1500)
        await page.wait_for_timeout(4000)   # 안정되기를 기다림
        cdp = await ctx.new_cdp_session(page); await cdp.send('Performance.enable')
        if throttle: await cdp.send('Emulation.setCPUThrottlingRate', {'rate': throttle})
        if trace: await b.start_tracing(page=page, categories=['devtools.timeline', 'disabled-by-default-devtools.timeline', 'cc', 'gpu', 'blink', 'viz'])
        m0 = {x['name']: x['value'] for x in (await cdp.send('Performance.getMetrics'))['metrics']}; c0 = proc_cpu(pid); t0 = time.time()
        await page.evaluate('() => window.__perfReset()')
        await page.wait_for_timeout(secs * 1000)
        r = await page.evaluate('() => window.__perfGet()')
        c1 = proc_cpu(pid); t1 = time.time(); m1 = {x['name']: x['value'] for x in (await cdp.send('Performance.getMetrics'))['metrics']}
        if trace: (OUT / f'{name}.trace.json').write_bytes(await b.stop_tracing())
        st = await page.evaluate("() => { const G = window.__game, S = G.S; return {keep:window.__keep, title:!!document.querySelector('#title') && !document.querySelector('#title').hidden, sleeping:document.body.classList.contains('sleeping'), mobs:G.mobs ? G.mobs.length : null, raid:!!G.raid, tab:document.querySelector('#page') && !document.querySelector('#page').hidden, world:S.world, stage:S.stage, level:S.level, kills:S.rec && S.rec.kills, aud:G.aud && G.aud.ctx && G.aud.ctx.state, cvs:[...document.querySelectorAll('canvas')].map(c => [c.id, c.width, c.height]), dpr:devicePixelRatio, nodes:document.querySelectorAll('*').length, anim:document.getAnimations().map(a => (a.animationName || a.transitionProperty || '?') + '@' + (a.effect && a.effect.target ? (a.effect.target.id || a.effect.target.className) : '?'))}; }")
        await page.screenshot(path=str(OUT / f'{name}.png'))
        wall = t1 - t0
        r.update(name=name, info=info, state=st, errs=errs[:5], wall=wall, cpu={k: round((c1.get(k, 0) - c0.get(k, 0)) / wall * 100, 1) for k in c1}, cdp={k: round((m1[k] - m0[k]) / wall * 1000, 2) for k in ('ScriptDuration', 'LayoutDuration', 'RecalcStyleDuration', 'TaskDuration')}, counts={k: round((m1[k] - m0[k]) / wall, 1) for k in ('LayoutCount', 'RecalcStyleCount')}, heap=m1['JSHeapUsedSize'], load=os.getloadavg()[0], others=others())
        (OUT / f'{name}.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
        await b.close()
        print(name, 'fps', round(r['frames'] / r['sec'], 1), 'loop ms', round(r['mean'], 3), 'p95', round(r['p95'], 2), 'cpu', r['cpu'], 'sum', round(sum(r['cpu'].values()), 1), 'cdp', r['cdp'], 'state', st, 'miss', r['miss'], 'errs', errs[:2], 'load', r['load'], 'others', r['others'], flush=True)
        return r

async def tabs(base, save):
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2, service_workers='block')
        await ctx.add_init_script("window.__samhanOnline = {url: ''}; window.__perfOpt = {};"); await ctx.add_init_script(path=str(HERE / 'perf_probe_harness.js'))
        page = await ctx.new_page(); await page.goto(base + 'base.html?simtest'); await page.wait_for_timeout(1000)
        await page.click('#lg-tab-signup'); await page.fill('#lg-id', 'perf'); await page.fill('#lg-pw', '1234'); await page.fill('#lg-pw2', '1234'); await page.click('#modal-btn-0')
        await page.wait_for_selector('#mTitle:has-text("캐릭터 고르기")'); await page.click('#modal-btn-0'); await page.wait_for_selector('#cc-name')
        await page.fill('#cc-name', '측정용사'); await page.click('#cc-musa'); await page.click('#modal-btn-1')
        await page.wait_for_function('() => window.__game.session && document.querySelector("#modal").hidden'); await page.wait_for_timeout(1500)
        await page.evaluate('() => { const b = document.querySelector("#cutSkip"); if (window.__game.cut && b) b.click(); }')
        await page.evaluate(SETUP_LATE, [json.dumps(json.loads((SIMD / save).read_text(encoding='utf-8')))]); await page.evaluate(KEEP)
        out = {}
        for t in ['grow', 'skill', 'gear', 'pet', 'quest', 'raid', 'shop', 'rec', 'bag', 'map', 'me', 'tower', 'pvp']:
            try:
                await page.evaluate("([t]) => window.__game.buildTab(t)", [t]); await page.wait_for_timeout(800)
                await page.evaluate('() => window.__perfReset()'); await page.wait_for_timeout(5000)
                r = await page.evaluate("() => { const r = window.__perfGet(); return {rp:r.fn.refreshPanel, nodes:document.querySelectorAll('#page *').length}; }")
                out[t] = {'calls': r['rp']['n'], 'ms': round(r['rp']['incl'] / max(1, r['rp']['n']), 3), 'max': round(r['rp']['max'], 2), 'nodes': r['nodes']}
            except Exception as e: out[t] = str(e)[:80]
            print(t, out[t], flush=True)
        (OUT / 'tabs.json').write_text(json.dumps(out, ensure_ascii=False)); await b.close()

async def main(args):
    mode = None; secs = None; count = False; which = []
    it = iter(args)
    for a in it:
        if a == '--mode': mode = next(it)
        elif a == '--secs': secs = int(next(it))
        elif a == '--count': count = True
        else: which.append(a)
    for f in ('manifest.webmanifest', 'sw.js'): shutil.copy(ROOT / f, SITE / f)
    for d in ('icons', 'vendor'):
        if not (SITE / d).exists(): shutil.copytree(ROOT / d, SITE / d)
    make_site('base.html')
    base = serve()
    L = 'save_musa_sea1.json'
    tag = '_' + (mode or 'def')
    def job(n, **kw):
        kw.setdefault('secs', secs or 60); kw['count'] = count or kw.get('count', False); kw['mode'] = mode
        return lambda: run(base, n + tag, **kw)
    jobs = {
      'tabs': lambda: tabs(base, L),
      'new': job('new'),
      'late': job('late', save=L),
      'tab': job('tab', save=L, tab='grow'),
      'raid': job('raid', save=L, raid=True),
      'portrait': job('portrait', save=L, vp=(390, 844), dsf=3),
      'sleep': job('sleep', save=L, sleep=True, secs=secs or 20),
      'title': job('title', title=True, secs=secs or 20),
    }
    if not which or which == ['all']: which = ['new', 'late', 'tab', 'raid', 'portrait', 'sleep', 'title']
    for w in which: await jobs[w]()

asyncio.run(main(sys.argv[1:]))
