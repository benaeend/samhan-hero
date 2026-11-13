"""직업 적성 재기 도구(물의 신화 9-5, docs/patch-sea/STAGE9_5.md 4-1절).

사용: python3 tools/sim_apt.py <직업,직업…|all> [저장=q113,q145,end,sea3,ind3] [JSON 덮어쓰기]
- 저장은 docs/patch-sea/sim/save_<직업>_<저장>.json. JSON 에 "base":"musa" 가 있으면 무사 저장에서 직업만 바꿔 잰다(직업끼리 견주기).
- 판마다 저장을 불러와(mergeState) 같은 재화로 옵션만 고른 네 가지 빌드를 만든다(G.aptRebuild):
    asis 저장 그대로(패치 날) · even 고르게 뿌린 용사 B · match 맞는 능력으로 모은 용사 M · miss 엇나간 용사 X
  빌드마다 적성 켬/끔(G.noApt)으로 bench: 보스 150초(혼자, skPresetFor('boss') 조합) · 몹 떼 20초(skPresetFor('mob')). 감로수·탕약은 넉넉히.
- 한 줄: 직업 저장 | a(맞는 능력 둘) asis/even/match/miss | 보스: asis÷끔 · (적응 기간)asis÷끔 · B÷B끔 · M÷B · X÷B · (끔)M÷B끔 | 몹 떼: 같은 여섯.
  목표(4-2): B÷B끔 0.97~1.03 · M÷B 2부 이후 1.25~1.40(1부 끝 1.10~1.30) · X÷B 0.65~0.78 · asis÷끔 ≥ 0.92(적응 기간이면 ≥ 0.96).
- JSON 덮어쓰기 예: '{"APT.up":0.4, "APT.W.craft":2, "AMB_GOOD.8.t":[8,16,28], "base":"musa"}' (게임 훅 __game 아래 경로, 빌드 없이)
- 빌드된 index.html 을 쓴다(먼저 python3 tools/build.py). 한 판 5~10초 — 무거우니 코어가 둘뿐이면 flock /tmp/samhan-test.lock nice 로.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

SIMD = T.ROOT / 'docs' / 'patch-sea' / 'sim'
CLASSES = ['musa', 'jagaek', 'sulsa', 'doin', 'gungsa', 'changgaek']
BOSS_SEC, MOB_SEC = 150, 20

JS = r"""
([save, cls, over]) => {
  const G = window.__game; G.quiet = true; G.benchAvg = true; G.noFork = true; G.noInh = true; G.noApt = false; G.aptForce = null; G.aptNeutral = null; G.aptGraceForce = null;
  for (const [k, v] of Object.entries(over || {})) { const p = k.split('.'); let o = G; for (let z = 0; z < p.length - 1; z++) o = o[p[z]]; o[p[p.length - 1]] = v; }
  Object.assign(G.S, G.mergeState(JSON.parse(save)));
  const S = G.S; if (cls) S.cls = cls; S.skV = 2; S.skSetMan = true; S.skManual = {}; S.mode = 'auto';
  G.migrateStory(); G.applyWorld(); G.refreshStats(); G.setStage(S.stage);
  const save0 = JSON.stringify(S), main = G.APT_MAIN[S.cls], res = {};
  const reset = () => { const d = JSON.parse(save0); for (const k of Object.keys(S)) if (!(k in d)) delete S[k]; Object.assign(S, d); G.aptReset(); };
  const run = (off, grace) => { G.noApt = off; G.aptGraceForce = grace; G.aptReset(); G.refreshStats();
    S.inv.mana = 9999; S.inv.potion = 9999; S.inv.elixir = 9999; S.skSet = G.skPresetFor('boss').slice(); const b = G.bench(%d, false).dps;
    S.inv.mana = 9999; S.skSet = G.skPresetFor('mob').slice(); const m = G.bench(%d, true).dps;
    G.noApt = false; G.aptGraceForce = null; return [b, m]; };
  for (const mode of ['asis', 'even', 'match', 'miss']){
    reset(); G.refreshStats(); G.aptRebuild(mode); G.aptGraceForce = false; G.aptReset();
    const A = G.aptCalc(), r = {a:main.map(x => A.a[x]), spd:A.spd};
    r.on = run(false, false); r.off = run(true, false);
    if (mode === 'asis') r.grace = run(false, true);
    res[mode] = r;
  }
  reset(); G.aptRebuild('asis'); G.aptNeutral = null;
  return {cls:S.cls, world:S.world, main, res};
}
""" % (BOSS_SEC, MOB_SEC)

KO = {'musa': '무사', 'jagaek': '자객', 'sulsa': '술사', 'doin': '도인', 'gungsa': '궁사', 'changgaek': '창객'}


def fmt_row(cls, name, r):
    R = r['res']
    a = ' '.join(f"{x}:" + '/'.join(f"{R[m]['a'][i]:+.2f}" for m in ('asis', 'even', 'match', 'miss')) for i, x in enumerate(r['main']))
    parts = []
    for j, label in ((0, '보스'), (1, '몹 떼')):
        asis_off = R['asis']['on'][j] / R['asis']['off'][j]
        grace = R['asis']['grace'][j] / R['asis']['off'][j]
        b_off = R['even']['on'][j] / R['even']['off'][j]
        m_b = R['match']['on'][j] / R['even']['on'][j]
        x_b = R['miss']['on'][j] / R['even']['on'][j]
        m_b_off = R['match']['off'][j] / R['even']['off'][j]
        parts.append(f"{label}: asis÷끔 {asis_off:.2f}(적응 {grace:.2f}) B÷B끔 {b_off:.2f} M÷B {m_b:.2f} X÷B {x_b:.2f} (끔)M÷B끔 {m_b_off:.2f}")
    return f"{KO[cls]:<3} {name:<5} | a[{a}] 돛 {R['asis']['spd']:.0f}% | " + ' | '.join(parts)


async def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cl = sys.argv[1]
    classes = CLASSES if cl == 'all' else cl.split(',')
    saves = (sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('{') else 'q113,q145,end,sea3,ind3').split(',')
    over = json.loads(sys.argv[-1]) if sys.argv[-1].startswith('{') else {}
    base = over.pop('base', None)
    async with async_playwright() as p:
        b = await T.launch(p)
        for cls in classes:
            for sv in saves:
                f = SIMD / f"save_{base or cls}_{sv}.json"
                if not f.exists():
                    print(f"{KO.get(cls, cls)} {sv} | (저장 없음 {f.name})", flush=True)
                    continue
                page = await (await b.new_context()).new_page()
                await T.fresh(page)
                r = await page.evaluate(JS, [f.read_text(encoding='utf-8'), cls if base else None, over])
                print(fmt_row(cls, sv, r), flush=True)
                await page.close()
        await b.close()


asyncio.run(main())
