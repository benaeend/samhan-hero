# 구간(seg 시간)마다 저장을 이어받아 돌리고 진행을 바로 찍는다. 사용: post2.py <직업> <최대시간> <구간시간> '<opts json>' [멈출 레벨]
import asyncio, json, sys, time
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import test_game as T
from playwright.async_api import async_playwright
cls = sys.argv[1]; hours = float(sys.argv[2]); seg = float(sys.argv[3]); over = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
stop = int(sys.argv[5]) if len(sys.argv) > 5 else 700
SIMD = T.ROOT/'docs'/'patch-sea'/'sim'
save = (SIMD/f'save_{cls}_ind3.json').read_text(encoding='utf-8')
import os
SAVE_FILE = os.environ.get('SIM_SAVE')   # 구간마다 저장을 이 파일에 써 두면, 멈춰도 거기서 이어 돌릴 수 있다
if SAVE_FILE and os.path.exists(SAVE_FILE): save = open(SAVE_FILE, encoding='utf-8').read()
async def main():
    global save
    t0 = time.time(); done = 0.0; firstAll = {}
    async with async_playwright() as p:
        b = await T.launch(p)
        page = await (await b.new_context()).new_page()
        while done < hours:
            await T.fresh(page)
            opts = {'dt':0.2, 'marks':[int(seg*60)], 'load':save}
            opts.update(over)
            r = await page.evaluate(T.SIM, [seg*60, cls, opts])
            info = await page.evaluate("() => { const G = window.__game, S = G.S; const q = G.mainQuest(); return {save:JSON.stringify(S), q:S.quest.main, lv:S.level, exp:S.exp/G.expNeed(S.level), st:S.stage, best:S.best.s10, gate:G.bossGate().why||'', gems:S.gems, gemsAll:(S.rec&&S.rec.gems)||0, atk:G.ST.atk, hp:G.ST.maxHp, tr:S.transShard||0}; }")
            save = info.pop('save')
            if SAVE_FILE: open(SAVE_FILE, 'w', encoding='utf-8').write(save)
            for k, v in r['first'].items():
                if isinstance(v, (int, float)) and k.startswith('L10:') and k not in firstAll: firstAll[k] = round(done + v/60, 1)
            done += seg
            line = r['log'][-1] if r['log'] else ''
            import re
            m = re.search(r'보석 ([0-9.]+[만억]?)', line)
            print(f'{cls} {done:.0f}h Lv{info["lv"]}+{info["exp"]:.2f} st{info["st"]} best{info["best"]} q{info["q"]} gemsEarned={m.group(1) if m else "?"} atk={info["atk"]:.3g} hp={info["hp"]:.3g} gate={info["gate"]} [{time.time()-t0:.0f}s]', flush=True)
            if info['lv'] >= stop: break
        await b.close()
    print('FIRST', json.dumps({k:v for k, v in firstAll.items() if int(k[4:]) % 5 == 0}, ensure_ascii=False), flush=True)
    open(f'/tmp/max700/end_{cls}_{sys.argv[6] if len(sys.argv) > 6 else "a"}.json', 'w').write(save)
asyncio.run(main())
