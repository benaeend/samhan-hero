"""상위 레이드 「진」 세기 재기와 클리어율 표(물의 신화 3단계).

사용:
  python3 tools/sim_jin.py measure            기준 저장(저장이 있는 직업 — 세계 0·1은 네 직업, 2부터 궁사·창객까지 여섯)으로 세계별·직업별 기준값을 재서 src/game.html 의 JIN_W 표를 찍는다
  python3 tools/sim_jin.py table [세계…] [n=판 수] [T0=…] [A0=…] [JIN.키=값…] [b]
      전투력 4단계(80·100·130·200%) × 손 모델 3가지(자동·평범·잘함) 클리어율 표. 'b'를 붙이면 그 땅 마지막 레이드(위 기준점)로,
      'syn'을 붙이면 파티 시너지를 켠 표(직업마다 가장 좋은 '내 파티' 조합 SYN_BEST — 권장 전투력·보스 세기는 시너지 없는 기준 그대로)
  python3 tools/sim_jin.py check [세계…]      게임에 적힌 JIN_W 그대로(덮어쓰지 않고) 첫 레이드를 권장 전투력 100%에서 몇 판

- 기준 저장(docs/patch-sea/sim): 진 레이드가 기준으로 삼는 용사 = '다음 세계를 지나는 용사'. 그 땅 첫 레이드는 a(막 들어선 때), 마지막 레이드는 b(거의 다 지난 때).
    이승 진: 저승 12단계(jin_*_w1s12) → 저승 100단계(jin_*_w1s100) · 시왕 진: 천계 12단계(jin_*_w2s12) → 천계 84단계(jin_*_w2s84)
    천계 진: 부상에 막 건넌 때(save_*_q113) → 곤륜에 막 들어선 때(save_*_q145) · 부상 진: 곤륜에 막 들어선 때 → 3부 끝(save_*_end)
    곤륜 진: 3부 끝(동해 들머리, save_*_end) → 동해 끝(save_*_sea1 — 5차 전직·새 장비 칸·3차 재련까지 한 용사)
    동해 진: 동해 끝(남쪽 바다 들머리, save_*_sea1) → 남쪽 바다 끝(save_*_sea2) · 남쪽 바다 진: 남쪽 바다 끝 → 깊은 바다 끝(save_*_sea3, 4부 끝). 깊은 바다 진은 5부에 들어서야 열린다
- 재는 것(직업마다): D0 = 손컨 패턴 없이(PAT.off) 보스에게 넣는 초당 피해, EHP = 최대 체력 ÷ 받는 피해 배율, PW = 화면의 전투력.
  보스 체력 = D0 × JIN.t0초, 보스 한 방 = EHP × JIN.a0, 권장 전투력 = PW.
- 표: 직업마다 화면 전투력이 권장 전투력의 r배가 되게 공격력·체력을 함께 곱해(__game.powK) n판씩.
- 손 모델: 자동 = 게임의 자동 손(피하기 0.8 × 진 0.5 = 0.4, 되받기 0.35) · 평범 = 피하기 0.75·되받기 0.6 · 잘함 = 피하기 1.0·되받기 0.95
- 빌드된 index.html 을 쓴다(먼저 python3 tools/build.py). 물약은 넉넉히 든 것으로(산삼 탕약 먼저 마심, 한 판 10개 한도는 그대로)
"""
import asyncio
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

SIMD = T.ROOT / 'docs' / 'patch-sea' / 'sim'
CLASSES = ['musa', 'jagaek', 'sulsa', 'doin', 'gungsa', 'changgaek']   # 궁사·창객 저장은 save_*_q113부터 있다(세계 0·1의 jin_* 저장은 네 직업뿐 — HAS가 거른다)
KO = {'musa': '무사', 'jagaek': '자객', 'sulsa': '술사', 'doin': '도인', 'gungsa': '궁사', 'changgaek': '창객'}
# 직업마다 가장 좋은 '내 파티'(나 포함 다섯, 물의 신화 9-2 — bench로 고름): 표의 'syn'이 이 조합의 시너지를 켠다(__game.synForce)
SYN_BEST = {'musa': dict(musa=1, changgaek=1, sulsa=1, doin=1, gungsa=1), 'jagaek': dict(jagaek=1, gungsa=1, musa=1, sulsa=1, doin=1), 'sulsa': dict(sulsa=1, doin=1, musa=1, jagaek=1, gungsa=1),
            'doin': dict(doin=1, sulsa=1, musa=1, jagaek=1, gungsa=1), 'gungsa': dict(gungsa=3, jagaek=1, musa=1), 'changgaek': dict(changgaek=1, musa=1, sulsa=1, doin=1, gungsa=1)}
REF = {0: ('jin_{c}_w1s12.json', 'jin_{c}_w1s100.json', 1.0), 1: ('jin_{c}_w2s12.json', 'jin_{c}_w2s84.json', 1.0),
       2: ('save_{c}_q113.json', 'save_{c}_q145.json', 1.0), 3: ('save_{c}_q145.json', 'save_{c}_end.json', 1.0), 4: ('save_{c}_end.json', 'save_{c}_sea1.json', 1.0),
       5: ('save_{c}_sea1.json', 'save_{c}_sea2.json', 1.0), 6: ('save_{c}_sea2.json', 'save_{c}_sea3.json', 1.0),
       7: ('save_{c}_sea3.json', 'save_{c}_ind1.json', 1.0), 8: ('save_{c}_ind1.json', 'save_{c}_ind2.json', 1.0), 9: ('save_{c}_ind2.json', 'save_{c}_ind3.json', 1.0)}   # 5부(물의 신화 9단계): 깊은 바다 진 = 4부 끝 → 란카 길 끝 · 란카 길 진 · 젖의 바다 진 (저장이 있는 직업만 잰다 — 표에 없는 직업은 게임이 평균을 씀)
HAS = lambda w, c: all((SIMD / n.format(c=c)).exists() for n in REF[w][:2] if n)   # 동해 진: 동해 끝(남쪽 바다 들머리) → 남쪽 바다 끝 · 남쪽 바다 진: 남쪽 바다 끝 → 깊은 바다 끝(4부 끝) — tools/sim_sea4.py가 남긴 저장(물의 신화 7단계)   # 곤륜 진: 3부 끝(동해 들머리) → 동해 끝(tools/sim_sea4.py가 남긴 저장, 물의 신화 5단계)
HANDS = {'자동': None, '평범': {'dodge': 0.75, 'counter': 0.6}, '잘함': {'dodge': 1.0, 'counter': 0.95}}
RS = [0.8, 1.0, 1.3, 2.0]

JS_LOAD = r"""
([save, cls, jinOv]) => {
  const G = window.__game; G.quiet = true; G.noFork = true; G.jinForce = true;
  Object.assign(G.S, G.mergeState(JSON.parse(save)));
  const S = G.S; S.cls = cls; if (S.world >= 3) G.refineInherit();
  S.mode = 'auto'; S.presetMode = 'auto';
  if (jinOv) Object.assign(G.JIN, jinOv);
  G.powK = 1; G.refreshStats(); G.setStage(S.stage);
  const save0 = JSON.stringify(S);
  // 판마다 저장을 처음으로 되돌린다(이기면 받는 장비·넋 구슬·아바타로 다음 판이 쉬워지지 않게)
  window.__reset = () => { const d = JSON.parse(save0); for (const k of Object.keys(S)) if (!(k in d)) delete S[k]; Object.assign(S, d); };
  window.__fight = (w, hand, powK, ov) => {
    window.__reset();
    G.powK = powK; G.hand = hand; G.jinOv = ov; G.refreshStats(); G.resetRuntime();
    S.jin.day = ''; S.jin.fail = {}; S.inv.potion = 9999; S.inv.elixir = 9999; S.inv.mana = 9999;
    const key = G.jinInfo(w, 0).key, n0 = S.jin.win[key] || 0;
    G.tmLast = null;
    if (!G.startJin(w, 0)) return {err:'start'};
    const R = G.raid, B = R.boss, hp0 = B.maxHp; let el = 0, falls = 0, pots = 0, left = 1;
    for (let k = 0; k < 4000 && G.raid; k++){ G.update(0.05); if (G.raid && !G.raid.ending){ el = R.limit - R.time; falls = R.falls || 0; pots = R.pots || 0; left = Math.max(0, B.hp / hp0); } }
    const win = (S.jin.win[key] || 0) > n0;
    const L = G.tmLast || {};   // 9-4 계측: 동료 쓰러짐(번)·동료 회복 몫(회복 ÷ 받은 피해)
    return {win, el, falls, pots, left:win ? 0 : left, af:L.aFalls || 0, ah:L.aHeal || 0, ad:L.aDmg || 0, ph:Object.values(L.heal || {}).reduce((a, b) => a + b, 0), pd:L.dmg || 0};
  };
  return {pw:G.power(G.ST), ehp:G.ST.maxHp / Math.max(0.05, G.takenK(true)), rd:G.realDps(), lv:S.level, w:S.world, st:S.maxStage, job:S.job};
}
"""
# D0: 보스가 때리지 않고(한 방 0) 체력이 아주 큰 판에서 60초 동안 넣은 피해(문턱 패턴·휘청 없이)
JS_D0 = r"""
([w]) => {
  const G = window.__game, S = G.S, j0 = Object.assign({}, G.JIN);
  G.JIN.time = 60; G.JIN.lives = 99; G.PAT.off = true;   // 손컨 패턴 없이 넣는 피해
  const out = [];
  for (let n = 0; n < 7; n++){
    window.__reset(); G.powK = 1; G.hand = {dodge:1, counter:0}; G.refreshStats(); G.resetRuntime();
    S.jin.day = ''; S.inv.potion = 9999; S.inv.elixir = 9999; S.inv.mana = 9999;
    G.jinOv = [G.realDps() * 1e6, 1e-200, 1];
    if (!G.startJin(w, 0)) return {err:'start'};
    const B = G.raid.boss, hp0 = B.maxHp; let hp = hp0, el = 0;
    for (let k = 0; k < 2000 && G.raid && !G.raid.ending; k++){ G.update(0.05); if (G.raid && !G.raid.ending){ hp = B.hp; el = G.raid.limit - G.raid.time; } }
    for (let k = 0; k < 200 && G.raid; k++) G.update(0.05);
    out.push((hp0 - hp) / Math.max(1, el));
  }
  Object.assign(G.JIN, j0); G.jinOv = null; G.PAT.off = false;
  return out;
}
"""
JS_RUN = r"""
([w, hands, rs, n, ov]) => {
  const G = window.__game, out = {};
  window.__reset(); G.powK = 1; G.refreshStats(); const pw1 = G.power(G.ST);
  for (const [hn, hand] of hands) for (const r of rs){
    const k = r * ov[2] / pw1; let win = 0, el = 0, falls = 0, pots = 0, left = 0, af = 0, ah = 0, ad = 0, ph = 0, pd = 0;
    for (let j = 0; j < n; j++){ const f = window.__fight(w, hand, k, ov); if (f.err) return f; win += f.win ? 1 : 0; el += f.el; falls += f.falls; pots += f.pots; left += f.left; af += f.af; ah += f.ah; ad += f.ad; ph += f.ph; pd += f.pd; }
    out[hn + ':' + Math.round(r * 100)] = {win:win / n, el:el / n, falls:falls / n, pots:pots / n, left:left / n, af:af / n, heal:pd > 0 ? ph / pd : 0, aheal:ad > 0 ? ah / ad : 0};
  }
  return out;
}
"""
JS_CHECK = r"""
([w, n]) => {
  const G = window.__game; window.__reset(); G.powK = 1; G.jinOv = null; G.refreshStats();
  const pw1 = G.power(G.ST), rec = G.jinRec(w, 0), out = {rec:Math.log10(rec), pw:Math.log10(pw1), tier:G.jinTier(pw1 / rec)[2]};
  for (const [hn, hand] of [['자동', null], ['평범', {dodge:0.75, counter:0.6}], ['잘함', {dodge:1, counter:0.95}]]){ let win = 0; for (let j = 0; j < n; j++) win += window.__fight(w, hand, rec / pw1, null).win ? 1 : 0; out[hn] = win / n; }
  return out;
}
"""


async def load(b, name, c, jin_ov):
    path = SIMD / name.format(c=c)
    if not path.exists():
        raise SystemExit(f'기준 저장 없음: {path}')
    page = await (await b.new_context()).new_page()
    await T.fresh(page)
    info = await page.evaluate(JS_LOAD, [path.read_text(encoding='utf-8'), c, jin_ov])
    return page, info


async def measure_one(b, w, name, c, jin_ov):
    """한 저장에서 [D0, EHP, PW](log10)"""
    page, info = await load(b, name, c, jin_ov)
    d = await page.evaluate(JS_D0, [w])
    if isinstance(d, dict):
        raise SystemExit(f'measure {w} {c}: {d}')
    return page, info, [math.log10(sum(d) / len(d)), math.log10(info['ehp']), math.log10(info['pw'])]


async def anchors(b, w, c, jin_ov, keep=None):
    """세계 w·직업 c의 a·b 기준점 [D0, EHP, PW](log10)과, keep('a'|'b') 쪽 페이지"""
    na, nb, frac = REF[w]
    pa, ia, va = await measure_one(b, w, na, c, jin_ov)
    if nb:
        pb, ib, vb0 = await measure_one(b, w, nb, c, jin_ov)
        vb = [va[k] + (vb0[k] - va[k]) * frac for k in range(3)]
    else:
        pb, ib, vb = None, None, [x + frac for x in va]
    page = pa if keep == 'a' else pb if keep == 'b' else None
    for pg in (pa, pb):
        if pg and pg is not page:
            await pg.close()
    return va, vb, page, (ia, ib)


def kv(args):
    out = {}
    for a in args:
        if '=' in a:
            k, v = a.split('=', 1)
            out[k] = float(v) if '.' in v or 'e' in v.lower() else int(v)
    return out


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'table'
    opt = kv(sys.argv[2:])
    worlds = [int(a) for a in sys.argv[2:] if a.isdigit()] or [0, 1, 2, 3, 4]
    top = 'b' in sys.argv[2:]; syn = 'syn' in sys.argv[2:]
    n = int(opt.pop('n', 20)); t0 = opt.pop('T0', None); a0 = opt.pop('A0', None)
    jin_ov = {k[4:]: v for k, v in opt.items() if k.startswith('JIN.')} or None
    async with async_playwright() as p:
        b = await T.launch(p)
        if mode == 'measure':
            print('const JIN_W = [')
            for w in worlds:
                rows = []
                for c in CLASSES:
                    if not HAS(w, c):
                        continue
                    va, vb, _, _ = await anchors(b, w, c, None)
                    rows.append(f"{c}:{{a:[{', '.join(f'{x:.3f}' for x in va)}], b:[{', '.join(f'{x:.3f}' for x in vb)}]}}")
                print('  {c:{' + ', '.join(rows) + '}},', flush=True)
            print('];')
        elif mode == 'check':
            for w in worlds:
                out = []
                for c in CLASSES:
                    if not HAS(w, c):
                        continue
                    page, info = await load(b, REF[w][0], c, jin_ov)
                    r = await page.evaluate(JS_CHECK, [w, n])
                    out.append(f"{c}: 권장 10^{r['rec']:.2f} 내 10^{r['pw']:.2f}({r['tier']}) 자동 {r['자동'] * 100:.0f}% 평범 {r['평범'] * 100:.0f}% 잘함 {r['잘함'] * 100:.0f}%")
                    await page.close()
                print(f'세계 {w} 진 첫 레이드(권장 전투력 100%로 맞춤) — ' + ' | '.join(out), flush=True)
        else:
            for w in worlds:
                res = {}
                g = None
                for c in CLASSES:
                    if not HAS(w, c):
                        continue
                    page, _ = await load(b, REF[w][1] if top and REF[w][1] else REF[w][0], c, jin_ov)
                    V = await page.evaluate('([w, c]) => window.__game.JIN_W[w].c[c] || null', [w, c])
                    if V:
                        va, vb = V['a'], V['b']
                    else:
                        await page.close()
                        va, vb, page, _ = await anchors(b, w, c, jin_ov, 'b' if top and REF[w][1] else 'a')
                    if g is None:
                        g = await page.evaluate('() => [window.__game.JIN.t0, window.__game.JIN.a0]')
                    v = vb if top else va
                    if syn:   # 기준(보스 체력·한 방·권장 전투력)은 시너지 없이 잰 값 그대로, 싸움에서만 시너지를 켠다
                        await page.evaluate('(cnt) => { const G = window.__game; G.synForce = G.synCalc(cnt); }', SYN_BEST[c])
                    ov = [10 ** v[0] * (t0 or g[0]), 10 ** v[1] * (a0 or g[1]), 10 ** v[2]]
                    res[c] = await page.evaluate(JS_RUN, [w, [[k, h] for k, h in HANDS.items()], RS, n, ov])
                    if 'err' in res[c]:
                        raise SystemExit(f'table {w} {c}: {res[c]}')
                    await page.close()
                print(f"## 세계 {w} 진 {'마지막' if top else '첫'} 레이드 — T0={t0 or g[0]} A0={a0 or g[1]} {jin_ov or ''} · 직업마다 {n}판{', 파티 시너지 켬(직업마다 최적 조합)' if syn else ''}, 괄호는 {'/'.join(KO[c] for c in res)}")
                print('  전투력   ' + '   '.join(f'{h:^22s}' for h in HANDS))
                for r in RS:
                    cells = []
                    for h in HANDS:
                        v = [res[c][f'{h}:{round(r * 100)}']['win'] for c in res]
                        cells.append(f"{sum(v) / len(v) * 100:3.0f}% ({'/'.join(f'{x * 100:.0f}' for x in v)})".ljust(22))
                    print(f'  {int(r * 100):3d}%    ' + '   '.join(cells))
                for h0 in HANDS:
                    det = '  '.join(f"{c}: {res[c][h0 + ':100']['el']:.0f}초 쓰러짐 {res[c][h0 + ':100']['falls']:.1f} 탕약 {res[c][h0 + ':100']['pots']:.1f} 남은 {res[c][h0 + ':100']['left'] * 100:.0f}%" for c in res)
                    print(f'  ({h0}·100%) {det}', flush=True)
                for h0 in HANDS:   # 9-4 계측: 동료가 쓰러진 횟수와 회복 몫(회복 ÷ 받은 피해)
                    ext = '  '.join(f"{c}: 동료 쓰러짐 {res[c][h0 + ':100']['af']:.1f} 용사 회복 몫 {res[c][h0 + ':100']['heal']:.2f} 동료 회복 몫 {res[c][h0 + ':100']['aheal']:.2f}" for c in res)
                    print(f'  ({h0}·100% 계측) {ext}', flush=True)
        await b.close()

asyncio.run(main())
