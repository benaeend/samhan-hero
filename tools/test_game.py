"""빌드된 index.html을 헤드리스 크롬으로 열어 확인한다.

필요: pip install playwright && python3 -m playwright install chromium
사용:
  python3 tools/test_game.py          # 화면 캡처(tools/out/) + 오류 확인
  python3 tools/test_game.py --sim    # + 직업별 30분 빠른 진행 시뮬레이션(밸런스 확인)

주소 끝에 ?simtest 를 붙이면 게임이 window.__game 테스트 훅을 연다.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = (ROOT / 'index.html').as_uri() + '?simtest'
OUT = ROOT / 'tools' / 'out'

SIM = r"""
(args) => {
  const [minutes, cls] = args;
  const G = window.__game;
  G.setClass(cls);
  G.S.buyMode = 1;
  const dt = 0.05, steps = Math.round(minutes * 60 / dt);
  const marks = new Set([5, 10, 20, 30].map(m => Math.round(m * 60 / dt)));
  const log = [];
  let nextShop = 0, nextRetry = 60;
  const Wt = {atk:1, hp:1.3, crit:1.5, critDmg:1.8, aspd:1.5, regen:3};
  for (let i = 1; i <= steps; i++) {
    G.update(dt);
    const t = i * dt;
    if (t >= nextShop) {
      nextShop = t + 2;
      for (let g = 0; g < 400; g++) {
        let best = null, bs = Infinity;
        for (const k of Object.keys(Wt)) { const b = G.buyInfo(k); if (!b.n) continue; const sc = b.cost * Wt[k]; if (sc < bs) { bs = sc; best = k; } }
        let bsk = null, sc2 = Infinity;
        for (const sk of G.SKILLS) { const lv = G.S.skills[sk.key]; if (lv && lv < sk.max) { const c = G.skillCost(sk, lv) * 2; if (c < sc2) { sc2 = c; bsk = sk.key; } } }
        if (bsk && sc2 < bs) { if (!G.upgradeSkill(bsk)) break; }
        else if (best) { if (!G.buyStat(best)) break; }
        else break;
      }
      while (G.S.gems >= 450) G.summon(Math.random() < 0.5 ? 'weapon' : 'armor', 10);
      G.mergeAll('weapon'); G.mergeAll('armor'); G.equipBest('weapon'); G.equipBest('armor');
    }
    if (t >= nextRetry) { nextRetry = t + 60; G.S.autoBoss = true; }
    if (marks.has(i)) log.push(`${cls} ${Math.round(t / 60)}분: 스테이지 ${G.S.stage}, Lv ${G.S.level}, 처치 ${G.S.rec.kills}, 보스 ${G.S.rec.bosses}`);
  }
  return log;
}
"""


async def launch(p):
    try:
        return await p.chromium.launch(args=['--no-sandbox'])
    except Exception:
        for path in ('/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'):
            if os.path.exists(path):
                return await p.chromium.launch(executable_path=path, args=['--no-sandbox'])
        raise


async def fresh(page):
    await page.evaluate("() => { localStorage.clear(); Storage.prototype.setItem = function(){}; }")
    await page.goto(URL)
    await page.wait_for_timeout(800)


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await launch(p)
        ctx = await browser.new_context(viewport={'width': 390, 'height': 800}, device_scale_factor=2)
        page = await ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)))
        page.on('console', lambda m: errors.append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
        await page.goto(URL)
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(OUT / '1_직업선택.png'))
        await page.click('#cc-musa')
        await page.click('#modal-btn-0')
        await page.wait_for_timeout(5000)
        await page.screenshot(path=str(OUT / '2_플레이.png'))
        for i, st in enumerate([11, 21, 31, 41, 51]):
            await page.evaluate(
                f"() => {{ const G = window.__game; G.S.level = {st}; G.S.up.atk = {st} * 2; G.S.up.hp = {st} * 2;"
                f" G.setStage({st}); G.setClass(['musa','jagaek','doin','sulsa','jagaek'][{i}]); }}")
            await page.wait_for_timeout(3000)
            el = await page.query_selector('#scene')
            await el.screenshot(path=str(OUT / f'3_지역{i + 2}.png'))
        if '--sim' in sys.argv:
            for c in ['musa', 'jagaek', 'sulsa', 'doin']:
                await fresh(page)
                await page.evaluate("() => { const b = document.querySelector('#modal-btn-0'); if (b) b.click(); }")
                for line in await page.evaluate(SIM, [30, c]):
                    print(line)
        await browser.close()
    print(f'캡처: {OUT.relative_to(ROOT)}/')
    print('오류:', json.dumps(errors, ensure_ascii=False, indent=1) if errors else '없음')
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
