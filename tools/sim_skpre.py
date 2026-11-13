"""장착 8칸 추천 조합 재기(물의 신화 1단계): 전직 단계(2차·3차·4차)마다 익힌 기술에서 8개를 고르는 모든 조합을
bench(혼자 보스 30초 · 몹 떼 20초, 기술 레벨은 가운데값으로 고르게, 물약 넉넉히)로 재서 src/game.html 의 SK_PRE 표를 찍어 준다.

사용: python3 tools/sim_skpre.py [직업,직업…=musa,jagaek,sulsa,doin]
- 무사 저장 docs/patch-sea/sim/save_musa_{q113,q145,end}.json(2차·3차·4차)에서 직업만 바꿔 잰다(같은 장비·능력치로 견주려고).
- 1차까지는 익힌 기술이 8개 이하라 모두 낀다. boss = 보스 최고, mob = 몹 떼 최고, mix = 보스 0.65 + 몹 떼 0.35, party = 파티 버프(10)를 넣은 것 가운데 보스 최고.
- 새 전직·기술을 더하면(6차) SAVES·단계 수를 늘려 다시 돌린다. 5차(13개에서 8개)는 직업 하나에 3~4분: `python3 tools/sim_skpre.py musa 4`처럼 그 단계만 잴 수 있다.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

SIMD = T.ROOT / 'docs' / 'patch-sea' / 'sim'
SAVES = {1: 'save_musa_q113.json', 2: 'save_musa_q145.json', 3: 'save_musa_end.json', 4: 'save_musa_sea1.json', 5: 'save_musa_ind1.json'}   # 4: 5차(동해 끝, 물의 신화 5단계 — 기술 13개에서 8개, 1,287가지) · 5: 6차(천축, 9단계 나 — 기술 15개에서 8개, 6,435가지라 오래 걸림. 저장은 5차까지 마친 5부 무사라 아래 JS가 S.job을 6으로 올려 13·14번 기술을 연다)
TIERS = [int(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 else [1, 2, 3, 4]   # 6차(5)는 오래 걸려 기본에서 뺌: python3 tools/sim_skpre.py musa 5   # 둘째 인자로 잴 단계만(예: 4) — 나머지 단계는 표에 '-'로 찍힌다
JS = r"""
([save, cls]) => {
  const G = window.__game; G.quiet = true; G.benchAvg = true;
  Object.assign(G.S, G.mergeState(JSON.parse(save)));
  const S = G.S; S.cls = cls; if (G.TIER6) S.job = Math.max(S.job, 6); S.skV = 2; S.skSetMan = true; S.skManual = {}; S.mode = 'auto';
  if (G.aptRebuild && !G.noApt) G.aptRebuild('match');   // 물의 신화 9-5: 직업에 맞는 능력 쪽으로 올린 용사로 잰다(적성이 높을수록 맞는 꼬리표 기술이 세져 추천이 달라질 수 있음)
  for (const k in S.skills) S.skills[k] = Math.max(S.skills[k] || 0, 1);
  G.refreshStats(); G.setStage(S.stage);
  const learned = G.SKILLS.map((_, i) => i).filter(i => G.skLv(i) > 0);
  const lv = learned.map(i => S.skills[G.SKILLS[i].key]).sort((a, b) => a - b), mid = lv[Math.floor(lv.length / 2)];
  for (const i of learned) S.skills[G.SKILLS[i].key] = mid;
  G.refreshStats();
  const combos = [], n = learned.length, K = Math.min(G.SK_SLOTS, n);
  const rec = (st, cur) => { if (cur.length === K){ combos.push(cur.slice()); return; } for (let j = st; j < n; j++){ cur.push(learned[j]); rec(j + 1, cur); cur.pop(); } };
  rec(0, []);
  const out = [];
  for (const c of combos){
    S.skSet = c.slice(); S.skSetMan = true; S.inv.mana = 9999; S.inv.potion = 9999; const b = G.bench(30, false).dps;
    S.skSet = c.slice(); S.inv.mana = 9999; const m = G.bench(20, true).dps;
    out.push([c, b, m]);
  }
  return {learned, out};
}
"""


def table(cls, res):
    n = 15
    full = lambda first: first + [i for i in range(n) if i not in first]
    base0 = [0, 1, 2, 3, 4, 5, 6, 10]
    tb = {'boss': [full(base0)], 'party': [full([10] + base0[:-1])], 'mob': [full(base0)], 'mix': [full(base0)]}
    for tier in (1, 2, 3, 4, 5):
        if tier not in res:
            for k in tb:
                tb[k].append([])
            continue
        r = res[tier]; out = r['out']
        bmax = max(o[1] for o in out); mmax = max(o[2] for o in out)
        score = {'boss': lambda o: o[1], 'party': lambda o: o[1], 'mob': lambda o: o[2], 'mix': lambda o: 0.65 * o[1] / bmax + 0.35 * o[2] / mmax}
        for k in tb:
            pool = [o for o in out if 10 in o[0]] if k == 'party' else out
            best = sorted(max(pool, key=score[k])[0])
            if k == 'party':
                best = [10] + [i for i in best if i != 10]
            rest = sorted((i for i in r['learned'] if i not in best), key=lambda i: -max(score[k](o) for o in out if i in o[0]))
            tb[k].append(best + rest + [i for i in range(n) if i not in r['learned']])
        mix = max(out, key=score['mix'])
        print(f'// {cls} {tier + 1}차: mix는 보스 최고의 {mix[1] / bmax:.2f}·몹 떼 최고의 {mix[2] / mmax:.2f}', file=sys.stderr)
    js = lambda rows: '[' + ', '.join('[' + ','.join(map(str, x)) + ']' for x in rows) + ']'
    return f"  {cls}:{{boss:{js(tb['boss'])},\n    party:{js(tb['party'])},\n    mob:{js(tb['mob'])},\n    mix:{js(tb['mix'])}}},"


async def main():
    classes = (sys.argv[1] if len(sys.argv) > 1 else 'musa,jagaek,sulsa,doin').split(',')
    async with async_playwright() as p:
        b = await T.launch(p)
        for cls in classes:
            res = {}
            for tier, name in SAVES.items():
                if tier not in TIERS:
                    continue
                page = await (await b.new_context()).new_page()
                await T.fresh(page)
                if tier == 5:
                    await page.evaluate("() => { window.__game.TIER6 = true; }")
                res[tier] = await page.evaluate(JS, [(SIMD / name).read_text(encoding='utf-8'), cls])
                await page.close()
            print(table(cls, res), flush=True)
        await b.close()


asyncio.run(main())
