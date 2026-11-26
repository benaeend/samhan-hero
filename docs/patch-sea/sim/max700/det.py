# 같은 씨앗·멈춘 시계로 돌리면 결과가 글자까지 같은지 보는 도구. 사용: det.py <index.html 경로> <직업> <시간> <끝 저장 이름(ind2 등)>
import asyncio, json, sys, hashlib
sys.path.insert(0, '/home/claude/wt-p2-max/tools')
import test_game as T
from pathlib import Path
from playwright.async_api import async_playwright
index = Path(sys.argv[1]); cls = sys.argv[2]; hours = float(sys.argv[3]); tag = sys.argv[4]
save = (T.ROOT/'docs'/'patch-sea'/'sim'/f'save_{cls}_{tag}.json').read_text(encoding='utf-8')
INIT = """(() => { let s = 123456789; Math.random = () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return ((s >>> 0) % 4294967296) / 4294967296; };
  const T0 = 1795000000000; let t = T0; const RD = Date; Date.now = () => t; performance.now = () => t - T0;
  window.Date = class extends RD { constructor(...a){ if (a.length) super(...a); else super(t); } static now(){ return t; } }; })();"""
async def main():
    async with async_playwright() as p:
        b = await T.launch(p)
        ctx = await b.new_context(); await ctx.add_init_script(INIT)
        page = await ctx.new_page()
        url = index.as_uri() + '?simtest'
        await page.goto(url); await page.evaluate("() => { try { localStorage.clear(); } catch(e){} Storage.prototype.setItem = function(){}; }"); await page.goto(url); await page.wait_for_timeout(800)
        r = await page.evaluate(T.SIM, [hours*60, cls, {'dt':0.2, 'marks':[int(hours*60)], 'load':save}])
        st = await page.evaluate("() => { const S = window.__game.S; return JSON.stringify([S.level, S.exp, S.stage, S.maxStage, S.gold, S.gems, S.quest.main, S.up, S.expBank]); }")
        await b.close()
    print(hashlib.md5(st.encode()).hexdigest(), st[:300])
asyncio.run(main())
