"""4부 바다 진행 시뮬(물의 신화 5단계에서 만듦): 3부 끝 저장에서 이어 동해에 건너가 46장부터 이야기 끝까지 돌리고 이정표 표를 찍는다.

사용: python3 tools/sim_sea4.py <직업: musa|jagaek|sulsa|doin> [최대 시간=40] [덮어쓰기 JSON]
- 출발점: docs/patch-sea/sim/save_<직업>_end.json(3부 끝, Lv.500, 4차 전직). 끝나면 save_<직업>_sea1.json(첫째 바다 끝)을 남긴다(다음 바다·5부 시뮬과 곤륜 진 기준의 출발점).
- 덮어쓰기 예: '{"sea1":{"e0":133},"expk5":0.9,"over":{"JOB5_REF":8}}' — 빌드 없이 수치를 바꿔 본다(tools/test_game.py SIM의 opts).
- 빌드된 index.html 을 쓴다(먼저 python3 tools/build.py). 40시간에 실제 2~3분, 코어 하나.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

cls = sys.argv[1]
hours = float(sys.argv[2]) if len(sys.argv) > 2 else 40
over = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
SIMD = T.ROOT / 'docs' / 'patch-sea' / 'sim'
save = (SIMD / f'save_{cls}_end.json').read_text(encoding='utf-8')
ANCHOR = "if (opts.snapQ && !('q' in snaps)"
SIM = T.SIM.replace(ANCHOR,
    "if (!('sea' in first) && G.S.world >= 5) first.sea = Math.round(t / 60);\n"
    "    if (G.S.quest.main >= G.MAIN_Q.length && !G.raid) { snaps.sea1 = JSON.stringify(G.S); first.END = Math.round(t / 60); break; }\n"
    "    " + ANCHOR)
assert SIM != T.SIM


async def main():
    t0 = time.time()
    async with async_playwright() as p:
        b = await T.launch(p)
        page = await (await b.new_context()).new_page()
        await T.fresh(page)
        marks = list(range(120, int(hours * 60) + 1, 120))
        opts = {'dt': 0.2, 'marks': marks, 'load': save, 'raidlog': True}
        opts.update(over)
        r = await page.evaluate(SIM, [hours * 60, cls, opts])
        info = await page.evaluate("() => { const G = window.__game, S = G.S; return {n:G.MAIN_Q.length, p3:G.PART3_END, q:S.quest.main, lv:S.level, st:S.maxStage, job:S.job, w:S.world, atk:G.ST.atk, hp:G.ST.maxHp, pw:G.power(G.ST)}; }")
        await b.close()
    for line in r['log']:
        print(line[:150])
    f = r['first']
    hh = lambda k: f'{f[k] / 60:.1f}' if k in f else '-'
    print(f"\n[{cls}] 동해 도착 {hh('sea')}h · " + ' · '.join(f"Lv{lv} {hh('L5:' + str(lv))}h" for lv in (502, 505, 507, 509, 511, 513, 514, 516)))
    print('  단계: ' + ' · '.join(f"{s} {hh('5:' + str(s))}h" for s in (4, 8, 11, 14, 17, 21, 24, 27, 31, 33, 35, 37, 40, 45, 50)))
    print(f"  5차 전직 {hh('J5')}h(실패 {f.get('JF5', 0)}번) · 이야기: " + ' · '.join(f"Q{q} {hh('Q' + str(q))}h" for q in range(info['p3'], info['n'] + 1, 2)))
    for x in r.get('raids', []):
        if x['w'] >= 5 and x['k'] in ('d0', 'd1', 'd2', 'job'):
            print(f"  레이드 {x['k']}: {x['dur']}초 {'승' if x['win'] else '패'} (Lv{x['lv']} · {x['st']}단계 · 기준 {x['ref']})")
    end = f.get('END')
    print(f"  끝: {'%.1f시간' % (end / 60) if end else '못 닿음'} · 지금 이야기 {info['q']}/{info['n']} · Lv{info['lv']} · {info['st']}단계 · 전직 {info['job']} · 걸린 시간 {time.time() - t0:.0f}초")
    for k, v in r['snaps'].items():
        if k == 'sea1':
            (SIMD / f'save_{cls}_sea1.json').write_text(v, encoding='utf-8')
            print('  저장:', SIMD / f'save_{cls}_sea1.json')


asyncio.run(main())
