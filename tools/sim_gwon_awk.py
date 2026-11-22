"""권사 첫째 초각성기(연타가 쌓여 저절로 터짐) 재기 도구(2026-11-22). 사용: python3 tools/sim_gwon_awk.py [저장들=q113,end,sea3,ind3] [JSON 덮어쓰기 예: '{"GWA.full":20}']
무사 저장에서 직업만 권사(주먹·발)로 바꿔 레이드를 끝까지 돌리고, 한 판에 터진 횟수·걸린 시간·총합(realDps 몫)을 예전 한 방(5초 몫 · 4차 뒤 8초 몫)과 견준다."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa
from playwright.async_api import async_playwright  # noqa
SIMD = T.ROOT / 'docs' / 'patch-sea' / 'sim'
JS = r"""
([save, br, over, idxs, durs]) => {
  const G = window.__game; G.quiet = true; G.noFork = true; G.noInh = true;
  for (const [k, v] of Object.entries(over || {})) { const p = k.split('.'); let o = G; for (let z = 0; z < p.length - 1; z++) o = o[p[z]]; o[p[p.length - 1]] = v; }
  Object.assign(G.S, G.mergeState(JSON.parse(save)));
  const S = G.S; S.cls = 'gwon'; S.gwonBr = br; S.awaken = true; S.skV = 2; S.skSetMan = true; S.skManual = {}; S.mode = 'auto';
  G.migrateStory(); G.applyWorld(); G.refreshStats(); G.setStage(S.stage);
  const out = [];
  for (const i of idxs) for (const dur of durs) {
    if (!G.raidReady(i)) continue;
    S.raid.tk = 3; S.inv.potion = 9999; S.inv.elixir = 9999; S.inv.mana = 9999;
    if (!G.startRaid(i)) continue;
    const R = G.raid; let t = 0; R.boss.atk = 0; R.boss.aoe = 0; R.boss.hp = R.boss.maxHp = dur > 0 ? G.realDps() * dur * (1 + 0.5 * R.allies.length) : 1e300; const tmax = dur > 0 ? 130 : 45;   // 보스는 때리지 않고, 체력은 혼자 dur초 치면 닳는 만큼(동료 몫 포함)
    for (; t < tmax && G.raid === R; t += 0.05) { G.update(0.05); if (Math.abs(t / 3 - Math.round(t / 3)) < 1e-6 && t > 0 && R.boss.hp > 0 && R.awk) G.damageHero(1); if (R.ending) { G.update(3); break; } }
    const sec = S.job >= 4 ? G.GWA.sec4 : G.GWA.sec, old = S.job >= 4 ? G.AWAKEN_SEC4 : G.AWAKEN_SEC;
    out.push({i, d: dur, t: Math.round(t), n: R.awk ? R.awk.n : -1, rate: +(((R.awk.n * G.GWA.full) + R.awk.g) / Math.max(1, t)).toFixed(2), win: R.win, tot: +(R.awk.n * sec / old).toFixed(2)});
    if (G.raid) G.raidEnd(false);
  }
  return out;
}
"""
async def main():
    saves = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('{') else 'q113,end,sea3,ind3').split(',')
    over = json.loads(sys.argv[-1]) if sys.argv[-1].startswith('{') else {}
    idxs = [0, 2]; durs = [int(x) for x in over.pop('durs', '40,70').split(',')] if isinstance(over.get('durs'), str) else [40, 70]
    async with async_playwright() as p:
        b = await T.launch(p)
        for sv in saves:
            for br in (1, 2):
                page = await (await b.new_context()).new_page(); await T.fresh(page)
                r = await page.evaluate(JS, [(SIMD / f'save_musa_{sv}.json').read_text(encoding='utf-8'), br, over, idxs, durs]); await page.close()
                print(sv, '주먹' if br == 1 else '발', ' '.join(f"[{x['i']}/{x['d']}] {x['t']}s {x['n']}번 충전/초 {x['rate']} 총합x{x['tot']}{'' if x['win'] else '(패)'}" for x in r), flush=True)
        await b.close()
asyncio.run(main())
