"""권사 혼자 보스 시너지(주먹 받아낸 힘 · 발 이어 차기) 재기 도구(2026-11-22). 사용: python3 tools/sim_gwon.py [저장들=q113,q145,end,sea3,ind3] [JSON 덮어쓰기 예: '{"PT.cd":0.5,"PT.burst":0.6}']
무사 저장에서 직업만 바꿔(base) 레이드 박자 bench 보스를 직업마다 재고, 권사는 주먹·발 갈래마다 시너지 끔(noGw)/켬을 나란히 잰다."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa
from playwright.async_api import async_playwright  # noqa
SIMD = T.ROOT / 'docs' / 'patch-sea' / 'sim'
CL = ['musa', 'jagaek', 'sulsa', 'doin', 'gungsa', 'changgaek', 'gwon1', 'gwon2']   # gwon1 = 권사 주먹 갈래 · gwon2 = 권사 발 갈래
JS = r"""
([save, cls0, over, sec, off]) => {
  const G = window.__game; G.quiet = true; G.benchAvg = true; G.noFork = true; G.noInh = true; G.noApt = false;
  for (const [k, v] of Object.entries(over || {})) { if (k === 'hitEvery') continue; const p = k.split('.'); let o = G; for (let z = 0; z < p.length - 1; z++) o = o[p[z]]; o[p[p.length - 1]] = v; }
  Object.assign(G.S, G.mergeState(JSON.parse(save)));
  const S = G.S; const cls = cls0.slice(0, 4) === 'gwon' ? 'gwon' : cls0; S.gwonBr = cls0 === 'gwon2' ? 2 : 1; S.cls = cls; S.skV = 2; S.skSetMan = true; S.skManual = {}; S.mode = 'auto';
  G.migrateStory(); G.applyWorld(); G.refreshStats(); G.setStage(S.stage);
  const run = () => { S.inv.mana = 9999; S.inv.potion = 9999; S.inv.elixir = 9999; S.skSet = G.skPresetFor('boss').slice(); const r = G.bench(sec, false, t => { if (over.hitEvery !== 0 && Math.abs(t / (over.hitEvery || 3) - Math.round(t / (over.hitEvery || 3))) < 1e-6 && t > 0) G.damageHero(1); }); return r.dps; };
  G.noGw = !!off; G.noPt = !!off; return run();
}
"""
async def main():
    saves = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('{') else 'q113,q145,end,sea3,ind3').split(',')
    over = json.loads(sys.argv[-1]) if sys.argv[-1].startswith('{') else {}
    sec = int(over.pop('sec', 120)); CLS = over.pop('cls', ','.join(CL)).split(','); REP = int(over.pop('rep', 1))
    async with async_playwright() as p:
        b = await T.launch(p)
        for sv in saves:
            row = {}
            for c in CLS:
                f = SIMD / f'save_musa_{sv}.json'; row[c] = {}
                for off in ((True, False) if c in ('gwon1', 'gwon2', 'musa') else (False,)):
                    v = []
                    for _ in range(REP if c in ('gwon1', 'gwon2') else 1):
                        page = await (await b.new_context()).new_page(); await T.fresh(page)
                        v.append(await page.evaluate(JS, [f.read_text(encoding='utf-8'), c, over, sec, off])); await page.close()
                    row[c]['off' if off else 'on'] = sum(v) / len(v)
                row[c].setdefault('off', row[c]['on'])
            mu = row['musa']['off'] if 'musa' in row else 1
            print(sv, ' '.join(f"{c}:{row[c]['on']/mu:.2f}" + (f"(끔 {row[c]['off']/mu:.2f}, x{row[c]['on']/row[c]['off']:.3f})" if c in ('gwon1', 'gwon2') else f"[x{row[c]['on']/row[c]['off']:.3f}]") for c in CLS), flush=True)
        await b.close()
asyncio.run(main())
