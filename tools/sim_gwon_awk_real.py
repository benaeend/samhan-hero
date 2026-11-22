"""권사 첫째 초각성기(연타 칸) — 실제 레이드를 끝까지 돌려 재기(2026-11-22). 사용: python3 tools/sim_gwon_awk_real.py [저장들] [JSON 덮어쓰기 예: '{"GWA.full":40}']
sim_gwon_awk.py(보스가 때리지 않는 45초 어림)와 달리 보스 체력·공격·동료·손 모델(자동)을 그대로 두고 일반 레이드(열린 것 중 위 2곳)와 진 레이드(열린 땅 위 2곳)를 끝까지 싸운다.
판마다 저장을 처음으로 되돌린다. 재는 것: 한 판에 터진 횟수 n, 걸린 시간, 이김, 총합 = n × 한 번 몫(초) ÷ 예전 한 방(5초 · 4차 뒤 8초)."""
import asyncio, json, statistics as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa
from playwright.async_api import async_playwright  # noqa
SIMD = T.ROOT / 'docs' / 'patch-sea' / 'sim'
JS = r"""
([save, br, over, rep, rs]) => {
  const G = window.__game; G.quiet = true; G.noFork = true; G.noInh = true;
  for (const [k, v] of Object.entries(over || {})) { const p = k.split('.'); let o = G; for (let z = 0; z < p.length - 1; z++) o = o[p[z]]; o[p[p.length - 1]] = v; }
  Object.assign(G.S, G.mergeState(JSON.parse(save)));
  const S = G.S; S.cls = 'gwon'; S.gwonBr = br; S.awaken = true; S.skV = 2; S.skSetMan = true; S.skManual = {}; S.mode = 'auto';
  G.migrateStory(); G.applyWorld(); G.refreshStats(); G.setStage(S.stage);
  const save0 = JSON.stringify(S);
  const reset = (pk) => { G.powK = pk || 1; const d = JSON.parse(save0); for (const k of Object.keys(S)) if (!(k in d)) delete S[k]; Object.assign(S, d); G.refreshStats(); G.resetRuntime(); S.raid.tk = 3; S.jin.day = ''; S.jin.fail = {}; S.inv.potion = 9999; S.inv.elixir = 9999; S.inv.mana = 9999; };
  const fights = [];
  reset(); const nu = G.raidUnlocked(); G.jinForce = false; for (let i = Math.max(0, nu - 2); i < nu; i++) fights.push(['r', i]);
  const jw = G.RAID_WORLDS.filter(R => G.jinOpen(R.w)).map(R => R.w).slice(-2); for (const w of jw) fights.push(['j', w]);
  const out = [];
  reset(); const pw1 = G.power(G.ST);
  for (let k = 0; k < rep; k++) for (const r of rs) for (const [kind, a] of fights){
    reset(); const rec = kind === 'r' ? G.raidRecPower(G.raidAt(a)) : G.jinRec(a, 0); reset(r * rec / pw1);
    if (!(kind === 'r' ? G.startRaid(a) : G.startJin(a, 0))) { out.push({kind, a, err:1}); continue; }
    const R = G.raid, B = R.boss, hp0 = B.maxHp; let t = 0, left = 1;
    for (; t < 200 && G.raid === R && !R.ending; t += 0.05){ G.update(0.05); left = Math.max(0, B.hp / hp0); }
    const n = R.awk ? R.awk.n : -1, g = R.awk ? R.awk.g : 0, win = !!R.win;
    for (let z = 0; z < 100 && G.raid; z++) G.update(0.05);
    if (G.raid) G.raidEnd(false);
    G.powK = 1;
    out.push({kind, a, r, t:+t.toFixed(1), n, g:+(g / G.GWA.full).toFixed(2), rate:+((R.awk.b || 0) / G.GWA.full).toFixed(2), full:+(R.awk.lp || 0).toFixed(2), win, left:+left.toFixed(2), sec:(S.job >= 4 ? G.GWA.sec4 : G.GWA.sec) / (S.job >= 4 ? G.AWAKEN_SEC4 : G.AWAKEN_SEC)});
  }
  return out;
}
"""
async def main():
    args = [a for a in sys.argv[1:] if not a.startswith('{')]
    saves = (args[0] if args else 'q113,q145,end,sea1,sea2,sea3,ind1,ind3').split(',')
    over = json.loads(sys.argv[-1]) if sys.argv[-1].startswith('{') else {}
    rep = int(over.pop('rep', 1)); rs = [float(x) for x in str(over.pop('rs', '0.5,0.8,1,1.3')).split(',')]
    allr = {1: [], 2: []}
    async with async_playwright() as p:
        b = await T.launch(p)
        async def one(sv, br):
            page = await (await b.new_context()).new_page(); await T.fresh(page)
            r = await page.evaluate(JS, [(SIMD / f'save_musa_{sv}.json').read_text(encoding='utf-8'), br, over, rep, rs]); await page.close()
            return sv, br, r
        for sv, br, r in await asyncio.gather(*[one(sv, br) for sv in saves for br in (1, 2)]):
            allr[br] += [x for x in r if not x.get('err')]
            print(sv, '주먹' if br == 1 else '발', ' '.join(f"[{x['kind']}{x['a']}x{x['r']}] {x['t']}s {x['n']}번+{x.get('g', 0)} 진행{x['full']} 덤{x['rate']}{'' if x['win'] else '(패)'}" if not x.get('err') else f"[{x['kind']}{x['a']}]오류" for x in r), flush=True)
        await b.close()
    for br in (1, 2):
        R = allr[br]
        L = [x for x in R if x['t'] >= 15]
        for lab, sub in (('일반', [x for x in R if x['kind'] == 'r']), ('진', [x for x in R if x['kind'] == 'j']), ('전체', R), ('15초+ 일반', [x for x in L if x['kind'] == 'r']), ('15초+ 진', [x for x in L if x['kind'] == 'j']), ('15초+ 이긴 판', [x for x in L if x['win']]), ('15초+ 전체', L)):
            if not sub: continue
            ns = [x['n'] for x in sub]; tot = [x['n'] * x['sec'] for x in sub]
            print(f"{'주먹' if br == 1 else '발'} {lab} {len(sub)}판: 횟수 평균 {st.mean(ns):.2f} (편차 {st.pstdev(ns):.2f}, {min(ns)}~{max(ns)}) · 총합 평균 x{st.mean(tot):.2f} (편차 {st.pstdev(tot):.2f}, {min(tot):.2f}~{max(tot):.2f}) · 시간 평균 {st.mean(x['t'] for x in sub):.0f}s · 덤 평균 {st.mean(x['rate'] for x in sub):.2f}칸 · 이김 {sum(x['win'] for x in sub)}/{len(sub)}")
asyncio.run(main())
