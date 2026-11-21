"""창객 「한 점 꿰기」 재기 도구(2026-11-19). 사용: python3 tools/sim_lance.py [저장들=q113,q145,end,sea3,ind3] [JSON 덮어쓰기 예: '{"PT.cd":0.5,"PT.burst":0.6}']
무사 저장에서 직업만 바꿔(base) 레이드 박자 bench 보스 150초를 직업마다 재고, 창객은 한 점 꿰기 끔(noPt)/켬을 나란히 잰다."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa
from playwright.async_api import async_playwright  # noqa
SIMD = T.ROOT / 'docs' / 'patch-sea' / 'sim'
CL = ['musa', 'jagaek', 'sulsa', 'doin', 'gungsa', 'changgaek']
JS = r"""
([save, cls, over, sec, off]) => {
  const G = window.__game; G.quiet = true; G.benchAvg = true; G.noFork = true; G.noInh = true; G.noApt = false;
  for (const [k, v] of Object.entries(over || {})) { const p = k.split('.'); let o = G; for (let z = 0; z < p.length - 1; z++) o = o[p[z]]; o[p[p.length - 1]] = v; }
  Object.assign(G.S, G.mergeState(JSON.parse(save)));
  const S = G.S; S.cls = cls; S.skV = 2; S.skSetMan = true; S.skManual = {}; S.mode = 'auto';
  G.migrateStory(); G.applyWorld(); G.refreshStats(); G.setStage(S.stage);
  const run = () => { S.inv.mana = 9999; S.inv.potion = 9999; S.inv.elixir = 9999; S.skSet = G.skPresetFor('boss').slice(); const r = G.bench(sec, false); return r.dps; };
  G.noPt = !!off; return run();
}
"""
async def main():
    saves = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('{') else 'q113,q145,end,sea3,ind3').split(',')
    over = json.loads(sys.argv[-1]) if sys.argv[-1].startswith('{') else {}
    sec = int(over.pop('sec', 150)); CLS = over.pop('cls', ','.join(CL)).split(','); REP = int(over.pop('rep', 1))
    async with async_playwright() as p:
        b = await T.launch(p)
        for sv in saves:
            row = {}
            for c in CLS:
                f = SIMD / f'save_musa_{sv}.json'; row[c] = {}
                for off in ((True, False) if c in ('changgaek', 'musa') else (False,)):
                    v = []
                    for _ in range(REP if c == 'changgaek' else 1):
                        page = await (await b.new_context()).new_page(); await T.fresh(page)
                        v.append(await page.evaluate(JS, [f.read_text(encoding='utf-8'), c, over, sec, off])); await page.close()
                    row[c]['off' if off else 'on'] = sum(v) / len(v)
                row[c].setdefault('off', row[c]['on'])
            mu = row['musa']['off'] if 'musa' in row else 1
            print(sv, ' '.join(f"{c}:{row[c]['on']/mu:.2f}" + (f"(끔 {row[c]['off']/mu:.2f}, x{row[c]['on']/row[c]['off']:.3f})" if c == 'changgaek' else f"[x{row[c]['on']/row[c]['off']:.3f}]") for c in CLS), flush=True)
        await b.close()
asyncio.run(main())
