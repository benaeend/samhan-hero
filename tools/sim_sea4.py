"""4부 바다 진행 시뮬(물의 신화 5·7단계): 바다 하나를 처음부터 그 바다 이야기 끝까지 돌리고 이정표 표를 찍는다.

사용: python3 tools/sim_sea4.py <직업: musa|jagaek|sulsa|doin> [최대 시간=40] [덮어쓰기 JSON] [출발점: end|sea1|sea2 (기본 end)]
- 출발점 end = docs/patch-sea/sim/save_<직업>_end.json(3부 끝) → 동해(46~52장)를 돌리고 save_<직업>_sea1.json 을 남긴다.
  sea1 → 남쪽 바다(53~59장) → save_<직업>_sea2.json, sea2 → 깊은 바다(60~67장) → save_<직업>_sea3.json(4부 끝, 5부 시뮬·바다 진 기준의 출발점).
- 덮어쓰기 예: '{"over":{"SEA2.e0":160,"EXP_K.6":0.03,"gateOff":true}}' — 빌드 없이 수치를 바꿔 본다(tools/test_game.py SIM의 opts). "nosave":true 면 저장을 남기지 않는다.
  "from":"<저장 파일>" 이면 그 저장에서 시작한다(「4부부터 시작」 캐릭터의 진행을 볼 때 — 저장은 남기지 않음).
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
start = sys.argv[4] if len(sys.argv) > 4 else 'end'
W = {'end': 5, 'sea1': 6, 'sea2': 7, 'sea3': 8, 'ind1': 9, 'ind2': 10}[start]          # 이번에 도는 바다·천축(세계 번호)
OUT = {5: 'sea1', 6: 'sea2', 7: 'sea3', 8: 'ind1', 9: 'ind2', 10: 'ind3'}[W]
nosave = bool(over.pop('nosave', False))
SIMD = T.ROOT / 'docs' / 'patch-sea' / 'sim'
src = over.pop('from', None)   # 다른 저장 파일에서 시작(예: 「4부부터 시작」 캐릭터) — 이때는 저장을 남기지 않는다
save = Path(src).read_text(encoding='utf-8') if src else (SIMD / f'save_{cls}_{start}.json').read_text(encoding='utf-8')
nosave = nosave or bool(src)
ANCHOR = "if (opts.snapQ && !('q' in snaps)"
SIM = T.SIM.replace(ANCHOR,
    "if (!('sea' in first) && G.S.world >= opts.seaW) first.sea = Math.round(t / 60);\n"
    "    if (G.S.quest.main >= opts.stopQ && !G.raid) { snaps.out = JSON.stringify(G.S); first.END = Math.round(t / 60); break; }\n"
    "    " + ANCHOR)
assert SIM != T.SIM


async def main():
    t0 = time.time()
    async with async_playwright() as p:
        b = await T.launch(p)
        page = await (await b.new_context()).new_page()
        await T.fresh(page)
        ends = await page.evaluate("() => { const G = window.__game; return {5:G.PART4A_END, 6:G.PART4B_END, 7:G.PART4_END, 8:G.PART5A_END, 9:G.PART5B_END, 10:G.MAIN_Q.length, n:G.MAIN_Q.length, q0:{5:G.PART3_END, 6:G.PART4A_END, 7:G.PART4B_END, 8:G.PART4_END, 9:G.PART5A_END, 10:G.PART5B_END}, cap:G.LV_CAP}; }")
        stopQ = ends[str(W)] if ends[str(W)] and ends[str(W)] > 0 else ends['n']
        marks = list(range(120, int(hours * 60) + 1, 120))
        opts = {'dt': 0.2, 'marks': marks, 'load': save, 'raidlog': True, 'seaW': W, 'stopQ': stopQ}
        opts.update(over)
        r = await page.evaluate(SIM, [hours * 60, cls, opts])
        info = await page.evaluate("() => { const G = window.__game, S = G.S; return {n:G.MAIN_Q.length, q:S.quest.main, lv:S.level, st:S.maxStage, job:S.job, w:S.world, atk:G.ST.atk, hp:G.ST.maxHp, pw:G.power(G.ST), mem:S.mem ? S.mem.p : null, aw2:S.aw2 ? [S.aw2.q, !!S.aw2.got] : null}; }")
        await b.close()
    for line in r['log']:
        print(line[:150])
    f = r['first']
    hh = lambda k: f'{f[k] / 60:.1f}' if k in f else '-'
    lv0, lv1 = ends['cap'][W - 1], ends['cap'][W]
    print(f"\n[{cls}] {start} → 세계 {W} 도착 {hh('sea')}h · " + ' · '.join(f"Lv{lv} {hh(f'L{W}:{lv}')}h" for lv in range(lv0 + 2, lv1 + 1, 2)))
    print('  단계: ' + ' · '.join(f"{s} {hh(f'{W}:{s}')}h" for s in (4, 8, 11, 14, 17, 21, 24, 27, 31, 33, 35, 37, 40, 45, 50, 60)))
    q0 = ends['q0'][str(W)]
    print(f"  5차 전직 {hh('J5')}h(실패 {f.get('JF5', 0)}번) · 6차 전직 {hh('J6')}h(실패 {f.get('JF6', 0)}번) · 이야기: " + ' · '.join(f"Q{q} {hh('Q' + str(q))}h" for q in range(q0, stopQ + 1, 2)))
    print(f"  환생의 기억 {info['mem']}(진 {f.get('MF', 0)}번) " + ' '.join(f"M{k} {hh('M' + str(k))}h" for k in (4, 8, 12)) + f" · 초각성기 2 {info['aw2']} " + ' '.join(f"A{k} {hh('A' + str(k))}h" for k in (1, 3, 5)))
    for x in r.get('raids', []):
        if x['w'] == W and (str(x['k'])[:1] in ('d', 'n', 'x', 'r', 'c', 'u') or x['k'] == 'job'):
            print(f"  레이드 {x['k']}: {x['dur']}초 {'승' if x['win'] else '패'} (Lv{x['lv']} · {x['st']}단계 · 기준 {x['ref']})")
    end = f.get('END')
    print(f"  끝: {'%.1f시간' % (end / 60) if end else '못 닿음'} · 지금 이야기 {info['q']}/{info['n']}(멈춤 {stopQ}) · Lv{info['lv']} · {info['st']}단계 · 전직 {info['job']} · 전투력 {info['pw']:.3g} · 걸린 시간 {time.time() - t0:.0f}초")
    if 'out' in r['snaps'] and not nosave:
        (SIMD / f'save_{cls}_{OUT}.json').write_text(r['snaps']['out'], encoding='utf-8')
        print('  저장:', SIMD / f'save_{cls}_{OUT}.json')


asyncio.run(main())
