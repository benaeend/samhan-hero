"""프레임 간격이 달라도(120·60·30·20fps 흉내) 같은 게임 시간 동안 처치·엽전·게임 시간이 같은지 재는 도구(2026-11 절전 그리기 작업).
진짜 loop()를 가짜 시각(rAF 대신 직접 호출)으로 돌린다. 장면은 메뉴 페이지로 가려 그리기는 건너뛰므로 빠르다.
사용: flock /tmp/samhan-test.lock python3 tools/perf_equiv.py [--index <index.html>] [--secs 600] [--trials 8] [--fps 120,60,30,20] [--mode off|auto|on] [--save]
  --save  후반 저장(docs/patch-sea/sim/save_musa_sea1.json, 동해 50단계) 대신 새 캐릭터 이승 15단계로 재려면 쓰지 않는다(기본은 이승 15단계)
같은 줄에 옛 판(git show 로 꺼낸 index.html)을 --index 로 넣으면 옛 loop(프레임 간격 = 걸음 크기)와 비교할 수 있다.
"""
import asyncio, functools, json, os, sys, threading, statistics as st
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from playwright.async_api import async_playwright
ROOT = Path(__file__).resolve().parent.parent; WORK = Path('/tmp/samhan-perf'); SITE = WORK / 'site'; SITE.mkdir(parents=True, exist_ok=True)
SIMD = ROOT / 'docs' / 'patch-sea' / 'sim'
MARK = "if (location.search.indexOf('simtest') >= 0){"
JS = r"""
async ([save, secs, trials, fpsList, mode]) => {
  const G = window.__game, S = G.S; G.quiet = true; G.noFork = true; G.noInh = true; G.gateOff = true; G.noNoti = true;
  if (mode) G.setDrawMode(mode);
  if (save){ Object.assign(S, G.mergeState(JSON.parse(save))); if (S.world >= 3 && G.refineInherit) G.refineInherit(); }
  else { S.level = 30; S.up.atk = 50; S.up.hp = 50; S.maxStage = 20; S.stage = 15; }
  S.mode = 'auto'; S.bossAuto = false; S.autoBoss = false; S.inv.potion = 9999; S.inv.elixir = 9999; S.inv.mana = 9999;
  G.refreshStats(); G.setStage(S.stage);
  window.requestAnimationFrame = () => 0; await new Promise(r => setTimeout(r, 300));   // 진짜 rAF 고리를 끊고 loop를 직접 부른다
  G.buildTab('grow');                                                                    // 메뉴로 장면을 가려 그리기 비용을 줄임(가로 화면)
  const save0 = JSON.stringify(S), out = {};
  const reset = () => { const d = JSON.parse(save0); for (const k of Object.keys(S)) if (!(k in d)) delete S[k]; Object.assign(S, d); G.refreshStats(); G.setStage(S.stage); };
  let T = performance.now() + 5e6;
  for (const fps of fpsList){
    out[fps] = [];
    for (let t = 0; t < trials; t++){
      reset(); window.__loop(T += 1000 / fps);            // 첫 호출(앞 시각과 차이가 커서 0.25초로 잘림)은 재기 전에 흘려보냄
      reset();
      const k0 = S.rec.kills, g0 = S.gold, p0 = S.rec.play, lv0 = S.level, e0 = S.exp;
      const frames = Math.round(secs * fps);
      for (let f = 0; f < frames; f++){
        window.__loop(T += 1000 / fps);
        if (f % 60 === 0){ const m = document.querySelector('#modal'); if (m && !m.hidden){ const b = document.querySelector('#modal .btn.primary') || document.querySelector('#modal-btn-0'); if (b) b.click(); } }
        if (f % 3000 === 0) await new Promise(r => setTimeout(r, 0));
      }
      out[fps].push({kills:S.rec.kills - k0, gold:S.gold - g0, play:+(S.rec.play - p0).toFixed(3), lv:S.level - lv0, exp:S.exp - e0, stage:S.stage});
    }
  }
  return out;
}
"""
async def main(a):
    opt = {'--index': str(ROOT / 'index.html'), '--secs': '600', '--trials': '8', '--fps': '120,60,30,20', '--mode': ''}
    it = iter(a); late = False
    for x in it:
        if x == '--late': late = True
        elif x in opt: opt[x] = next(it)
    src = Path(opt['--index']).read_text(encoding='utf-8')
    assert src.count(MARK) == 1
    (SITE / 'equiv.html').write_text(src.replace(MARK, "window.__loop = loop;\n" + MARK), encoding='utf-8')
    class H(SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(H, directory=str(SITE))); threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{srv.server_address[1]}/'
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width': 844, 'height': 390}, service_workers='block')
        await ctx.add_init_script("window.__samhanOnline = {url: ''};")
        page = await ctx.new_page(); errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(base + 'equiv.html?simtest'); await page.wait_for_timeout(800)
        await page.click('#lg-tab-signup'); await page.fill('#lg-id', 'perf'); await page.fill('#lg-pw', '1234'); await page.fill('#lg-pw2', '1234'); await page.click('#modal-btn-0')
        await page.wait_for_selector('#mTitle:has-text("캐릭터 고르기")'); await page.click('#modal-btn-0'); await page.wait_for_selector('#cc-name')
        await page.fill('#cc-name', '측정용사'); await page.click('#cc-musa'); await page.click('#modal-btn-1')
        await page.wait_for_function('() => window.__game.session && document.querySelector("#modal").hidden'); await page.wait_for_timeout(1200)
        await page.evaluate('() => { const b = document.querySelector("#cutSkip"); if (window.__game.cut && b) b.click(); }')
        save = json.dumps(json.loads((SIMD / 'save_musa_sea1.json').read_text(encoding='utf-8'))) if late else None
        r = await page.evaluate(JS, [save, int(opt['--secs']), int(opt['--trials']), [int(x) for x in opt['--fps'].split(',')], opt['--mode'] or None])
        print(('동해 50단계(후반)' if late else '이승 15단계(새 캐릭터를 키운 것)'), '판:', opt['--index'], '그리기 방식:', opt['--mode'] or '기본')
        base60 = None
        for fps, L in r.items():
            ks = [x['kills'] for x in L]; gs = [x['gold'] for x in L]; ps = [x['play'] for x in L]
            if fps == '60': base60 = st.mean(ks)
            print(f"  {fps:>3}fps  처치 평균 {st.mean(ks):7.1f} ±{st.pstdev(ks):5.1f}  엽전 평균 {st.mean(gs):.4g}  게임시간(S.rec.play) {min(ps)}~{max(ps)}  단계 {sorted(set(x['stage'] for x in L))}", flush=True)
        if base60:
            print('  60fps 대비 처치:', {fps: f"{(st.mean([x['kills'] for x in L]) / base60 - 1) * 100:+.1f}%" for fps, L in r.items()})
        if errs: print('  페이지 오류:', errs[:3])
        await b.close()
asyncio.run(main(sys.argv[1:]))
