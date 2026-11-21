# 초월의 경지 속도 재기: 수미산 끝 저장(save_<직업>_ind3.json)을 Lv.700으로 올려 두고 구간마다 이어 돌리며 경지 단·단계·힘을 찍는다.
# 사용: sim_realm.py <직업> <최대 시간> <구간 시간> [열쇠=값 …]   예) sim_realm.py musa 40 5
# 주의: 저장은 5부 끝(Lv.600·45단계) 용사라 실제 Lv.700 용사(약 140시간 뒤, 장비·능력치가 더 쌓임)보다 힘이 약하다 → 힘의 벽이 있다면 실제보다 일찍 온다.
import asyncio, json, sys, time, os
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import test_game as T
from playwright.async_api import async_playwright
cls = sys.argv[1]; hours = float(sys.argv[2]); seg = float(sys.argv[3])
over = {}
for a in sys.argv[4:]:
    k, v = a.split('='); over[k] = float(v)
save = json.loads((T.ROOT/'docs'/'patch-sea'/'sim'/f'save_{cls}_ind3.json').read_text(encoding='utf-8'))
save['level'] = 700; save['exp'] = 0; save['expBank'] = 0
if os.environ.get('REALM_STAGE'):   # 실제 Lv.700 용사는 수미산 230~269단계에 서 있다 → 그 단계에서 시작(힘 부족은 over powK=…로 메움)
    st = int(os.environ['REALM_STAGE']); save['stage'] = st; save['maxStage'] = st; save['best']['s10'] = max(save['best'].get('s10', 0), st)
save = json.dumps(save, ensure_ascii=False)
SAVE_FILE = os.environ.get('SIM_SAVE')
if SAVE_FILE and os.path.exists(SAVE_FILE): save = open(SAVE_FILE, encoding='utf-8').read()
async def main():
    global save
    t0 = time.time(); done = 0.0; marks = {}
    async with async_playwright() as p:
        b = await T.launch(p)
        page = await (await b.new_context()).new_page()
        while done < hours:
            await T.fresh(page)
            opts = {'dt':0.2, 'marks':[int(seg*60)], 'load':save}
            if over: opts['over'] = over
            await page.evaluate(T.SIM, [seg*60, cls, opts])
            info = await page.evaluate("() => { const G = window.__game, S = G.S; return {save:JSON.stringify(S), lv:S.level, rl:S.trans.lv, rx:S.trans.exp / (S.trans.lv < G.TRANS.realmMax ? G.realmNeed(S.trans.lv) : 1), st:S.stage, best:S.best.s10, gate:G.bossGate().why||'', atk:G.ST.atk, hp:G.ST.maxHp, shard:S.trans.shard, bank:S.expBank, gl:G.gateLv()}; }")
            save = info.pop('save')
            if SAVE_FILE: open(SAVE_FILE, 'w', encoding='utf-8').write(save)
            done += seg
            r = info['rl'] + info['rx']
            marks[round(done, 2)] = round(r, 2)
            print(f'{cls} {done:.1f}h 경지 {info["rl"]}단+{info["rx"]:.2f} (평균 {done / max(r, 0.01):.2f}h/단) Lv{info["lv"]} 문Lv{info["gl"]} st{info["st"]} best{info["best"]} atk={info["atk"]:.3g} 조각{info["shard"]} 모음{info["bank"]:.1f} 문="{info["gate"]}" [{time.time()-t0:.0f}s]', flush=True)
        await b.close()
    print('MARKS', json.dumps(marks))
asyncio.run(main())
