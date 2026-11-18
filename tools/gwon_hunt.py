"""권사 시안: 사냥 장면 캡처(폰 세로 390px). python3 tools/gwon_hunt.py [출력폴더]"""
import asyncio, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T
from playwright.async_api import async_playwright
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else '/home/claude/report/gwon_proto'); OUT.mkdir(parents=True, exist_ok=True)

async def main():
    async with async_playwright() as p:
        b = await T.launch(p)
        ctx = await b.new_context(viewport={'width': 390, 'height': 780}, device_scale_factor=2)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await T.fresh(pg)
        await T.signup(pg, 'gwonproto', 'abcd', '권사시안', 'musa')
        await pg.evaluate("() => { const G = window.__game; G.quiet = true; G.closePage && G.closePage(); G.S.level = 30; G.setStage(12); G.refreshStats(); document.getElementById('rotClose') && document.getElementById('rotClose').click(); }")
        for tag, sx, br, force in [('주먹_남', 'm', 1, 3), ('주먹_여', 'f', 1, 3), ('발차기_남', 'm', 2, 4), ('발차기_여', 'f', 2, 4)]:
            await pg.evaluate("([sx, br, f]) => { window.__gwonProto = {sx, br, force: f}; const G = window.__game; G.hero.dead = false; G.hero.hp = G.ST.maxHp; }", [sx, br, force])
            ok = False
            for _ in range(400):   # 용사가 몬스터 바로 앞에서 싸우는 순간까지 기다린다
                st = await pg.evaluate("() => { const G = window.__game, h = G.hero; h.hp = G.ST.maxHp; const t = h.target; return t && !h.moving && h.dir === 'right' ? 1 : 0; }")
                if st: ok = True; break
                await pg.wait_for_timeout(150)
            await pg.evaluate("() => { const h = window.__game.hero; h.hurt = 0; }")
            await pg.screenshot(path=str(OUT / f'3_사냥_{tag}.png'))
            r = await pg.evaluate("() => { const G = window.__game, c = G.cam, e = document.getElementById('cv').getBoundingClientRect(), k = e.width / c.vw; return {x: e.left + (G.hero.x - c.x) * k, y: e.top + (G.hero.y - c.y) * k}; }")
            clip = {'x': max(0, r['x'] - 70), 'y': max(0, r['y'] - 85), 'width': 140, 'height': 120}
            await pg.screenshot(path=str(OUT / f'3_사냥_{tag}_확대.png'), clip=clip)
            from PIL import Image
            im = Image.open(OUT / f'3_사냥_{tag}_확대.png'); im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(OUT / f'3_사냥_{tag}_확대.png')
            print(tag, ok)
        print('오류', errs)
        await b.close()
asyncio.run(main())
