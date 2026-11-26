"""천공의 탑 501~600층 · 초월 레이드 세기 재기(11월 21일).

사용(먼저 python3 tools/build.py — 빌드된 index.html 을 쓴다):
  python3 tools/sim_trans.py ladder <직업> <저장.json>…       저장마다 [D0, EHP, PW](log10)와 레벨 — 초월 레이드의 TRANS_LADDER 기준값(무사)
  python3 tools/sim_trans.py tower <직업> <저장.json> [n=3]   그 저장이 탑 501~600층(수미산 단계 띠)에서 일반 층 · 문지기 층을 몇 단계까지 버티는지 이분 탐색(n판 중 과반)
  python3 tools/sim_trans.py trial <직업> <저장.json> [k…] [n=20] [rs=0.8,1.0] [ov=D0,EHP,PW]   경지 시험 k(0~9)를 같은 방식으로(경지 시험 REALM_LADDER·fit 그대로, 11월 26일)
  python3 tools/sim_trans.py ex <직업> <저장.json> [n=10] [from=1] [to=40] [off=0]  (off = 계단 0을 시험 10보다 몇 계단 쉽게 둘지, REALM_EX.off)   끝없는 시험: 저장 그대로의 힘(powK=1)으로 계단마다 n판 — 과반을 못 이기는 첫 계단(손 모델별)
  python3 tools/sim_trans.py table <직업> <저장.json> [k…] [n=20] [rs=0.8,1.0] [ov=D0,EHP,PW]   초월 레이드 k(0~4)를 권장 전투력 80·100·130·200%로 손 모델 3가지(자동·평범·잘함) 클리어율 — 게임에 적힌 TRANS_LADDER 그대로(ov 를 주면 그 log10 기준으로 — 예: 진 레이드 수미산 값과 견줄 때)
- 저장은 수미산 이야기 끝(docs/patch-sea/sim/save_<직업>_ind3.json)에서 tools/sim_post.py 로 레벨을 올리며 남긴 것(예: /tmp/max700/end_musa_t650.json)
- 재는 법·손 모델은 tools/sim_jin.py 와 같다(JS_LOAD·JS_D0·HANDS를 그대로 가져다 씀)
"""
import asyncio
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

_src = (Path(__file__).resolve().parent / 'sim_jin.py').read_text(encoding='utf-8').replace('asyncio.run(main())', '')
_ns = {'__name__': 'sim_jin_lib', '__file__': str(Path(__file__).resolve().parent / 'sim_jin.py')}
exec(compile(_src, 'sim_jin.py', 'exec'), _ns)
JS_LOAD, JS_D0, HANDS, RS = _ns['JS_LOAD'], _ns['JS_D0'], _ns['HANDS'], _ns['RS']

JS_TOWER = r"""
([fl, st, n, gate]) => {   // 탑 fl층을 수미산 st단계 세기로 n판 — 이긴 판 수
  const G = window.__game, S = G.S, B = G.TOWER_BANDS; G.towerLvOff = true;
  const keep = B[B.length - 1].slice(); B[B.length - 1] = [10, 501, 600, st, st];
  let win = 0, el = 0;
  for (let j = 0; j < n; j++){
    window.__reset(); G.refreshStats(); G.resetRuntime();
    S.tower.best = fl - 1; S.tower.day = ''; S.tower.n = 0; S.inv.potion = 9999; S.inv.elixir = 9999; S.inv.mana = 9999;
    if (!G.startTower()) { B[B.length - 1] = keep; return {err:'start'}; }
    const R = G.raid, t0 = R.limit; for (let k = 0; k < 4000 && G.raid; k++) G.update(0.05);
    if (S.tower.best >= fl) win++;
  }
  B[B.length - 1] = keep; return {win};
}
"""
JS_TRANS = r"""
([k, hands, rs, n, pw1, ov]) => {
  const G = window.__game, S = G.S, out = {}; G.transForce = true;
  if (ov) G.transOv = [Math.pow(10, ov[0]) * G.JIN.t0, Math.pow(10, ov[1]) * G.JIN.a0 / Math.pow(10, G.tkLagLog ? G.tkLagLog() : 0), Math.pow(10, ov[2])];   // ov=D0,EHP,PW(log10): 진 레이드 값 등 다른 기준으로 견주어 볼 때
  for (const [hn, hand] of hands) for (const r of rs){
    let win = 0, el = 0, falls = 0, pots = 0;
    for (let j = 0; j < n; j++){
      window.__reset(); G.powK = r * G.transRec(k) / pw1; G.hand = hand; G.refreshStats(); G.resetRuntime();
      S.trans.rd.wk = ''; S.trans.rd.n = 0; S.inv.potion = 9999; S.inv.elixir = 9999; S.inv.mana = 9999;
      const n0 = S.trans.rd.tot[k] || 0;
      if (!G.startTrans(k)) return {err:'start'};
      const R = G.raid; let e = 0, f = 0, p = 0;
      for (let q = 0; q < 4000 && G.raid; q++){ G.update(0.05); if (G.raid && !G.raid.ending){ e = R.limit - R.time; f = R.falls || 0; p = R.pots || 0; } }
      if ((S.trans.rd.tot[k] || 0) > n0) win++; el += e; falls += f; pots += p;
    }
    out[hn + ':' + Math.round(r * 100)] = {win:win / n, el:el / n, falls:falls / n, pots:pots / n};
  }
  G.powK = 1; G.hand = null; return out;
}
"""


JS_TRIAL = r"""
([k, hands, rs, n, pw1, ov]) => {
  const G = window.__game, S = G.S, out = {}; G.trialForce = true;
  if (ov) G.trialOv = [Math.pow(10, ov[0]) * G.JIN.t0, Math.pow(10, ov[1]) * G.JIN.a0 / Math.pow(10, G.tkLagLog ? G.tkLagLog() : 0), Math.pow(10, ov[2])];
  for (const [hn, hand] of hands) for (const r of rs){
    let win = 0, el = 0, falls = 0;
    for (let j = 0; j < n; j++){
      window.__reset(); G.powK = r * G.trialRec(k) / pw1; G.hand = hand; G.refreshStats(); G.resetRuntime();
      S.inv.potion = 9999; S.inv.elixir = 9999; S.inv.mana = 9999;
      const n0 = S.trans.tr.tot[k] || 0;
      if (!G.startTrial(k)) return {err:'start'};
      const R = G.raid; let e = 0, f = 0;
      for (let q = 0; q < 4000 && G.raid; q++){ G.update(0.05); if (G.raid && !G.raid.ending){ e = R.limit - R.time; f = R.falls || 0; } }
      if ((S.trans.tr.tot[k] || 0) > n0) win++; el += e; falls += f;
    }
    out[hn + ':' + Math.round(r * 100)] = {win:win / n, el:el / n, falls:falls / n};
  }
  G.powK = 1; G.hand = null; return out;
}
"""
JS_EX = r"""
([st, hand, n, rsc]) => {   // 끝없는 시험 st계단을 n판 — 이긴 판 수(rsc = 힘 배율)
  const G = window.__game, S = G.S; G.exForce = true;
  let win = 0;
  for (let j = 0; j < n; j++){
    window.__reset(); G.powK = rsc; G.hand = hand; G.refreshStats(); G.resetRuntime();
    S.trans.ex.best = st - 1; S.trans.ex.n = 0; S.trans.ex.extra = 0; S.trans.ex.day = ''; S.inv.potion = 9999; S.inv.elixir = 9999; S.inv.mana = 9999;
    if (!G.startEx()) return {err:'start'};
    for (let q = 0; q < 4000 && G.raid; q++) G.update(0.05);
    if (S.trans.ex.best >= st) win++;
  }
  G.powK = 1; G.hand = null; return {win};
}
"""


async def load(b, path, cls):
    page = await (await b.new_context()).new_page()
    await T.fresh(page)
    info = await page.evaluate(JS_LOAD, [Path(path).read_text(encoding='utf-8'), cls, None])
    return page, info


async def main():
    mode, cls = sys.argv[1], sys.argv[2]
    rest = sys.argv[3:]
    async with async_playwright() as p:
        b = await T.launch(p)
        if mode == 'ladder':
            for path in rest:
                page, info = await load(b, path, cls)
                d = await page.evaluate(JS_D0, [10])
                if isinstance(d, dict):
                    raise SystemExit(f'{path}: {d}')
                print(f"Lv.{info['lv']} 단계 {info['st']} [{math.log10(sum(d) / len(d)):.3f}, {math.log10(info['ehp']):.3f}, {math.log10(info['pw']):.3f}]  {path}", flush=True)
                await page.close()
        elif mode == 'tower':
            path = rest[0]; n = int([a for a in rest[1:] if a.startswith('n=')][0][2:]) if any(a.startswith('n=') for a in rest[1:]) else 3
            page, info = await load(b, path, cls)
            print(f"Lv.{info['lv']} 단계 {info['st']} PW 10^{math.log10(info['pw']):.2f}", flush=True)
            for label, fl in (('일반 층(505)', 505), ('문지기 층(510)', 510)):
                lo, hi = 60, 700   # lo 는 이기는 쪽, hi 는 지는 쪽
                while hi - lo > 2:
                    mid = (lo + hi) // 2
                    r = await page.evaluate(JS_TOWER, [fl, mid, n, fl % 10 == 0])
                    if 'err' in r:
                        raise SystemExit(r)
                    if r['win'] * 2 > n: lo = mid
                    else: hi = mid
                print(f'  {label}: 버티는 단계 약 {lo}', flush=True)
        elif mode == 'trial':
            ks = [int(a) for a in rest[1:] if a.isdigit()] or list(range(10))
            n = int([a for a in rest[1:] if a.startswith('n=')][0][2:]) if any(a.startswith('n=') for a in rest[1:]) else 20
            ov = [float(x) for x in [a for a in rest[1:] if a.startswith('ov=')][0][3:].split(',')] if any(a.startswith('ov=') for a in rest[1:]) else None
            rs = [float(x) for x in [a for a in rest[1:] if a.startswith('rs=')][0][3:].split(',')] if any(a.startswith('rs=') for a in rest[1:]) else RS
            page, info = await load(b, rest[0], cls)
            for k in ks:
                res = await page.evaluate(JS_TRIAL, [k, [[h, v] for h, v in HANDS.items()], rs, n, info['pw'], ov])
                if 'err' in res:
                    raise SystemExit(f'k={k}: {res}')
                print(f"## 경지 시험 {k + 1} · {cls} Lv.{info['lv']} · {n}판 (권장 전투력 비율별 클리어율)")
                for r in rs:
                    print(f'  {int(r * 100):3d}%  ' + '  '.join(f"{h} {res[f'{h}:{round(r * 100)}']['win'] * 100:3.0f}% (쓰러짐 {res[f'{h}:{round(r * 100)}']['falls']:.1f})" for h in HANDS), flush=True)
        elif mode == 'ex':
            def arg(key, d):
                v = [x.split('=', 1)[1] for x in rest[1:] if x.startswith(key + '=')]
                return type(d)(v[0]) if v else d
            n, lo, hi = arg('n', 10), arg('from', 1), arg('to', 40)
            rsc = float(arg('rs', '1.0'))
            page, info = await load(b, rest[0], cls)
            await page.evaluate('o => { window.__game.REALM_EX.off = o; }', float(arg('off', '0')))
            print(f"Lv.{info['lv']} PW 10^{math.log10(info['pw']):.2f} · 끝없는 시험 {lo}~{hi}계단 {n}판씩 (힘 배율 {rsc})", flush=True)
            for hn, hv in HANDS.items():
                first = None
                for st in range(lo, hi + 1):
                    r = await page.evaluate(JS_EX, [st, hv, n, rsc])
                    if 'err' in r:
                        raise SystemExit(r)
                    if r['win'] * 2 < n:
                        first = st; break
                print(f'  {hn}: 처음 막히는 계단 {first if first else str(hi) + "+"}', flush=True)
        elif mode == 'table':
            ks = [int(a) for a in rest[1:] if a.isdigit()] or [0, 1, 2, 3, 4]
            n = int([a for a in rest[1:] if a.startswith('n=')][0][2:]) if any(a.startswith('n=') for a in rest[1:]) else 20
            ov = [float(x) for x in [a for a in rest[1:] if a.startswith('ov=')][0][3:].split(',')] if any(a.startswith('ov=') for a in rest[1:]) else None
            rs = [float(x) for x in [a for a in rest[1:] if a.startswith('rs=')][0][3:].split(',')] if any(a.startswith('rs=') for a in rest[1:]) else RS
            page, info = await load(b, rest[0], cls)
            for k in ks:
                res = await page.evaluate(JS_TRANS, [k, [[h, v] for h, v in HANDS.items()], rs, n, info['pw'], ov])
                if 'err' in res:
                    raise SystemExit(f'k={k}: {res}')
                print(f"## 초월 레이드 {k} · {cls} Lv.{info['lv']} · {n}판 (권장 전투력 비율별 클리어율)")
                for r in rs:
                    print(f'  {int(r * 100):3d}%  ' + '  '.join(f"{h} {res[f'{h}:{round(r * 100)}']['win'] * 100:3.0f}% (쓰러짐 {res[f'{h}:{round(r * 100)}']['falls']:.1f})" for h in HANDS), flush=True)
        await b.close()

asyncio.run(main())
