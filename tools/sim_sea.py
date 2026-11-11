"""4부의 새 성장(투구·어깨·신발 소환·합성·재련, 호박석 세공)을 3부 끝 저장에서 미리 열어 놓고 돌려, 얼마나 빨리 차는지 본다(물의 신화 4단계에서 만듦).

사용: python3 tools/sim_sea.py <직업: musa|jagaek|sulsa|doin> [시간=30] [처음 받는 호박석 "희귀,영웅,전설"=3,0,0]
- 4부(바다)가 아직 게임에 없어서 곤륜 끝 사냥터에서 돈다(엽전·보석 수입은 4부 초입과 비슷하다고 보고). 진행 시뮬(tools/test_game.py 의 SIM)에 opts.sea 만 켠 것.
- 빌드된 index.html 을 쓴다(먼저 python3 tools/build.py). 30시간에 실제 1~2분.
- 4부를 넣은 뒤(5·7단계)에는 진짜 4부 진행 시뮬로 다시 재고, SLOT·AMB 수치를 맞춘다.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

cls = sys.argv[1]
hours = float(sys.argv[2]) if len(sys.argv) > 2 else 30
raw = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else '3,0,0').split(',')]
save = (T.ROOT / 'docs' / 'patch-sea' / 'sim' / f'save_{cls}_end.json').read_text(encoding='utf-8')
PROBE = """(raw) => { const G = window.__game, S = G.S, A = G.ambSum();
  if (raw) { S.amber.raw = raw.map((n, g) => (S.amber.raw[g] || 0) + n); return null; }
  return {atk:G.ST.atk, hp:G.ST.maxHp, power:G.power(G.ST), eq:G.NEW_SLOTS.map(k => S.equip[k]), ref:G.NEW_SLOTS.map(k => S.refine[k].lv), refW:[S.refine.weapon.lv, S.refine.armor.lv],
    lights:A.L, tier:A.tier, sea:G.seaSum(), gold:S.gold, gems:S.gems, m3:S.mat.m3, lv:S.level, stage:S.maxStage}; }"""


async def main():
    t0 = time.time()
    async with async_playwright() as p:
        b = await T.launch(p)
        page = await (await b.new_context()).new_page()
        await T.fresh(page)
        base = await page.evaluate("(a) => { const G = window.__game; G.quiet = true; G.setClass(a[0]); Object.assign(G.S, G.mergeState(JSON.parse(a[1]))); G.S.cls = a[0]; G.refreshStats(); return {atk:G.ST.atk, hp:G.ST.maxHp, power:G.power(G.ST)}; }", [cls, save])
        marks = list(range(120, int(hours * 60) + 1, 120))
        sv = __import__('json').loads(save); sv['amber'] = {'raw': raw, 'st': {}}
        r = await page.evaluate(T.SIM, [hours * 60, cls, {'dt': 0.2, 'marks': marks, 'sea': True, 'load': __import__('json').dumps(sv)}])
        end = await page.evaluate(PROBE, None)
        await b.close()
    for line in r['log']:
        print(line[:60], '…', line[line.find('새 칸'):] if '새 칸' in line else '')
    f = lambda x: f'{x:.2f}'
    print(f"\n{cls} {hours:.0f}시간 뒤(3부 끝 대비): 공격력 ×{f(end['atk'] / base['atk'])} · 체력 ×{f(end['hp'] / base['hp'])} · 전투력 ×{f(end['power'] / base['power'])}")
    print('  새 칸 장비 번호', end['eq'], '재련', end['ref'], '· 무기/방어구 3차 재련', end['refW'])
    print('  호박석 빛', end['lights'], '단', {k: v for k, v in end['tier'].items() if v})
    print('  바다 몫', {k: round(v, 3) for k, v in end['sea'].items() if v not in (0, 1)}, f"· 걸린 시간 {time.time() - t0:.0f}초")


asyncio.run(main())
