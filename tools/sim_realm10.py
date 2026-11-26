# 초월의 경지 단 10마다 저장을 남기며 이어 돌린다(경지 시험 세기 재기용, 2026-11-26).
# 사용: sim_realm10.py <직업> <시작 저장.json> <최대 시간> <구간 시간> <저장 폴더> [열쇠=값 …]
#   예) sim_realm10.py musa docs/patch-sea/sim/max700/end_musa_a.json 130 2 /tmp/realm_saves
#   빠르게: TRANS.realmBase=0.17 (경지가 4배 빨리 오름 — 장비가 덜 큰 만큼 힘이 낮게 잰다는 점에 주의)
# 경지가 10·20·…단을 처음 넘은 구간 끝에서 <저장 폴더>/<직업>_r<단>.json 을 남기고, 진행 줄을 찍는다. 멈추면 같은 명령으로 이어 돌린다(<직업>_cur.json).
import asyncio, json, sys, time, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T
from playwright.async_api import async_playwright
cls, start, hours, seg, outd = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), Path(sys.argv[5])
over = {}
for a in sys.argv[6:]:
    k, v = a.split('='); over[k] = float(v)
outd.mkdir(parents=True, exist_ok=True)
cur = outd / f'{cls}_cur.json'
save = (cur if cur.exists() else Path(start)).read_text(encoding='utf-8')
meta = outd / f'{cls}_meta.json'
M = json.loads(meta.read_text()) if meta.exists() else {'done': 0.0, 'marks': {}}
async def main():
    global save
    t0 = time.time()
    async with async_playwright() as p:
        b = await T.launch(p)
        page = await (await b.new_context()).new_page()
        while M['done'] < hours:
            await T.fresh(page)
            opts = {'dt': 0.2, 'marks': [int(seg * 60)], 'load': save}
            if over: opts['over'] = over
            await page.evaluate(T.SIM, [seg * 60, cls, opts])
            info = await page.evaluate("() => { const G = window.__game, S = G.S; return {save:JSON.stringify(S), lv:S.level, rl:S.trans.lv, rx:S.trans.exp / (S.trans.lv < G.TRANS.realmMax ? G.realmNeed(S.trans.lv) : 1), st:S.stage, atk:G.ST.atk, hp:G.ST.maxHp, shard:S.trans.shard}; }")
            save = info.pop('save'); cur.write_text(save, encoding='utf-8')
            M['done'] += seg
            r = info['rl'] + info['rx']
            for m in range(10, 101, 10):
                if r >= m and str(m) not in M['marks']:
                    M['marks'][str(m)] = round(M['done'], 2); (outd / f'{cls}_r{m}.json').write_text(save, encoding='utf-8')
            meta.write_text(json.dumps(M)); 
            print(f'{cls} {M["done"]:.1f}h 경지 {info["rl"]}단+{info["rx"]:.2f} Lv{info["lv"]} st{info["st"]} atk={info["atk"]:.3g} hp={info["hp"]:.3g} 조각{info["shard"]} 표시={M["marks"]} [{time.time()-t0:.0f}s]', flush=True)
            if info['rl'] >= 100: break
        await b.close()
asyncio.run(main())
