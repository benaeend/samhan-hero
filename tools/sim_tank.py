"""버티는 힘 재기 도구(물의 신화 9-4, docs/patch-sea/STAGE9_4.md 2-2절).

사용: python3 tools/sim_tank.py <모드> [인자…]
  anchors [직업…]                      저장 앵커마다 버티는 힘(log10)·부분(체력 레벨·방어구 재련·방어 펫·성주신)·지금 몬스터 기준(HERO_REF)·차이를 찍음 (2분)
  prog <1|23|4|5> [직업…] [lean=mild|hard] [off]
                                      진행 시뮬. 1 = 처음부터 100시간 · 23 = save_<직업>_q113 에서 이야기 182까지(최대 220시간) · 4 = end→sea1→sea2→sea3 · 5 = sea3→ind1→ind2→ind3.
                                      끝에 이정표 표 · 세계·싸움 종류별 계측 합 · 원자료를 docs/patch-sea/sim/tank_<직업>_<부>[_lean][_off].json 에 남김.
                                      (1·23은 세계 가운데 저장 tank_<직업>_w<세계>s<단계>.json 도 남김) 오래 걸림(1부 10분 · 23부 10분 · 4부 15분 · 5부 15분)
  ref [직업…]                          prog 가 남긴 tank_*_off.json 으로 기준표 TANK_REF · 직업 몫 TANK_CLS 초안을 찍음 (1분)
  fight <세계…> [n=20] [idx=0.7,1,1.3] [lean=…] [off]
                                      그 세계 저장마다 벽 단계(보스를 쓰러뜨리는 데 22초 넘게 걸리는 첫 단계)·쉬운 단계(8초 안팎)·수문장에서 지수를 맞춰 n판 + 사냥터 10분
                                      (표 TANK_REF 가 비어 있으면 idx 는 「지금 버티는 힘의 몇 배」, 있으면 지수 그 자체)
  raid <세계…> [n=20] [r=0.8,1,1.3] [off]
                                      그 세계 저장으로 일반 레이드 첫·가운데·끝을 화면의 권장 전투력 비 r 로 n판
  tb <세계…> [n=20] [idx=…] [hand=auto,good] [off]
                                      타임 보스 노말·지옥, 1일 보스, 강림을 n판
  old                                 저장 표본 전부로 「지난 단계 보스·첫 토벌한 레이드를 다시 깰 수 있나·사냥터에서 안 물러나나」 (15분)
옵션 off 는 __game.tankOff = true (예전 방식 — 같은 코드에서 견주는 기준). I-1 단계에서는 장치가 없어서 켜든 끄든 같다.
빌드된 index.html 을 쓴다(먼저 python3 tools/build.py). 코어가 둘뿐이면 다른 점검과 겹치지 않게 flock /tmp/samhan-test.lock 으로.
"""
import asyncio
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

SIMD = T.ROOT / 'docs' / 'patch-sea' / 'sim'
BETAD = T.ROOT / 'tools' / 'beta_saves'
CLASSES = ['musa', 'jagaek', 'sulsa', 'doin', 'gungsa', 'changgaek']
CLS4 = ['musa', 'jagaek', 'sulsa', 'doin']
KO = {'musa': '무사', 'jagaek': '자객', 'sulsa': '술사', 'doin': '도인', 'gungsa': '궁사', 'changgaek': '창객'}
WN = ['이승', '저승', '천계', '부상', '곤륜', '동해', '남쪽 바다', '깊은 바다', '란카 길', '젖의 바다', '수미산']
SNAPW = [[0, 51], [0, 91], [1, 51], [2, 46], [3, 30], [3, 60], [4, 40], [4, 100]]   # prog 가 남기는 세계 가운데 저장
# 저장 앵커(이름 → 파일). 세계는 불러온 뒤 S.world 로 가린다
ANCH = [('저승 12', 'jin_{c}_w1s12.json'), ('저승 100', 'jin_{c}_w1s100.json'), ('천계 12', 'jin_{c}_w2s12.json'), ('천계 84', 'jin_{c}_w2s84.json'),
        ('부상 첫(q113)', 'save_{c}_q113.json'), ('곤륜 첫(q145)', 'save_{c}_q145.json'), ('곤륜 끝(end)', 'save_{c}_end.json'), ('동해 끝(sea1)', 'save_{c}_sea1.json'),
        ('남쪽 바다 끝(sea2)', 'save_{c}_sea2.json'), ('깊은 바다 끝(sea3)', 'save_{c}_sea3.json'), ('젖의 바다 첫(ind1)', 'save_{c}_ind1.json'),
        ('수미산 첫(ind2)', 'save_{c}_ind2.json'), ('수미산 끝(ind3)', 'save_{c}_ind3.json')]
# 세계별로 fight/raid/tb 가 쓸 저장 이름 후보(S.world 가 맞는 것만 씀)
WSAVES = {0: ['tank_{c}_w0s51', 'tank_{c}_w0s91'], 1: ['jin_{c}_w1s12', 'jin_{c}_w1s100', 'tank_{c}_w1s51'], 2: ['jin_{c}_w2s12', 'tank_{c}_w2s46', 'jin_{c}_w2s84'],
          3: ['save_{c}_q113', 'tank_{c}_w3s30', 'tank_{c}_w3s60'], 4: ['save_{c}_q145', 'tank_{c}_w4s40', 'tank_{c}_w4s100', 'save_{c}_end'], 5: ['save_{c}_end', 'save_{c}_sea1'],
          6: ['save_{c}_sea1', 'save_{c}_sea2'], 7: ['save_{c}_sea2', 'save_{c}_sea3'], 8: ['save_{c}_sea3', 'save_{c}_ind1'], 9: ['save_{c}_ind1', 'save_{c}_ind2'], 10: ['save_{c}_ind2', 'save_{c}_ind3']}

JS_LOAD = r"""
([save, cls, off, lean]) => {
  const G = window.__game; G.quiet = true; G.noFork = true; G.gateOff = true; G.noInh = true;
  Object.assign(G.S, G.mergeState(JSON.parse(save)));
  const S = G.S; S.cls = cls; if (S.world >= 3) G.refineInherit();
  S.mode = 'auto'; S.presetMode = 'auto'; S.bossAuto = false;
  if (off) G.tankOff = true;
  G.powK = 1; G.tankK = 1; G.refreshStats(); G.setStage(S.stage);
  const save0 = JSON.stringify(S);
  const pots = () => { S.inv.potion = 9999; S.inv.elixir = 9999; S.inv.mana = 9999; };
  // 판마다 저장을 처음으로 되돌린다(이기면 받는 것으로 다음 판이 쉬워지지 않게)
  window.__reset = () => { const d = JSON.parse(save0); for (const k of Object.keys(S)) if (!(k in d)) delete S[k]; Object.assign(S, d); G.powK = 1; G.tankK = 1; G.hand = null; G.tmReset();
    if (lean) G.tkLean(lean); };
  // 보스에게 안 맞고 쓰러뜨리는 데 걸리는 초(손컨 끔)
  window.__ttk = s => { window.__reset(); G.PAT.off = true; G.refreshStats(); G.setStage(s); S.autoBoss = false; pots(); G.startBoss(); const B = G.bossRef; if (!B) { G.PAT.off = false; return 99; } B.atk = 0; B.aoe = 0;
    let t = 0; for (; t < 60 && G.bossActive; t += 0.05) G.update(0.05); G.PAT.off = false; return t; };
  // 벽 단계(22초 넘게 걸리는 첫 단계) · 쉬운 단계(8초 안팎) · 그 근처 수문장
  window.__stages = () => { const s0 = S.stage; let wall = null; for (let s = s0; s < s0 + 90; s++) if (window.__ttk(s) > 22) { wall = s; break; }
    if (wall == null) wall = s0 + 90;
    let easy = s0; for (let s = wall - 1; s >= Math.max(1, wall - 40); s--) if (window.__ttk(s) <= 8) { easy = s; break; }
    const g1 = wall + ((8 - (wall - 1) % 10) + 10) % 10, g0 = g1 - 10, gate = g0 >= 1 && wall - g0 <= g1 - wall ? g0 : g1;   // 벽에 가장 가까운 수문장
    window.__reset(); return {wall, easy, gate, s0}; };
  // 보스 n판: k = 지수(표가 없으면 지금의 몇 배)
  window.__boss = (s, k, n) => { const A = {n:0, win:0, fall:0, low:0, minHp:0, dmg:0, heal:0, cap:0, sh:0, t:0, idx:0};
    for (let j = 0; j < n; j++){
      window.__reset(); G.setStage(s); G.refreshStats();
      const base = G.tkHas(S.world) ? G.tankIdx(s) : 1; if (!lean && k != null) { G.tankK = k / base; G.refreshStats(); }
      G.setStage(s); S.autoBoss = false; pots(); G.tmLast = null;
      G.startBoss(); const T0 = G.S.stage; for (let t = 0; t < 70 && G.bossActive; t += 0.05) G.update(0.05);
      const L = G.tmLast; if (!L) continue;
      A.n++; A.win += L.win ? 1 : 0; A.fall += L.falls; A.low += L.low; A.minHp += L.minHp; A.dmg += L.dmg; A.sh += L.sh; A.cap += L.cap; A.t += L.t; A.idx += L.idx;
      A.heal += Object.entries(L.heal).filter(e => e[0] !== 'revive').reduce((a, e) => a + e[1], 0);
    }
    window.__reset(); return A; };
  // 사냥터 minutes 분: 쓰러짐·물러남·회복 몫
  window.__field = (s, k, minutes) => { window.__reset(); G.setStage(s); G.refreshStats(); const base = G.tkHas(S.world) ? G.tankIdx(s) : 1; if (!lean && k != null) { G.tankK = k / base; G.refreshStats(); }
    G.setStage(s); S.bossAuto = false; pots(); const f0 = S.rec.falls; let low = s; G.tmReset();
    for (let i = 0; i < minutes * 600; i++){ S.autoBoss = false; G.update(0.1); if (S.stage < low) low = S.stage; }
    const m = G.tmAgg()[S.world + ':field'] || {}; const out = {falls:S.rec.falls - f0, retreat:s - low, dmg:m.dmg || 0, heal:Object.entries(m.heal || {}).filter(e => e[0] !== 'revive').reduce((a, e) => a + e[1], 0), low:m.low || 0, n:m.n || 0};
    window.__reset(); return out; };
  // 일반 레이드 i 를 권장 전투력의 r배로 n판
  window.__raid = (i, r, n) => { const A = {n:0, win:0, t:0, fall:0, af:0, ad:0, dmg:0, heal:0, aheal:0, cap:0, err:''};
    for (let j = 0; j < n; j++){
      window.__reset(); G.refreshStats(); const info = G.raidAt(i), rec = G.raidRecPower(info), pw1 = G.power(G.ST);
      G.powK = r == null ? 1 : r * rec / pw1; G.refreshStats(); G.resetRuntime(); pots(); S.raid.tk = 3; G.tmLast = null;
      if (!G.startRaid(i)) { A.err = 'start'; continue; }
      for (let k = 0; k < 4000 && G.raid; k++) G.update(0.05);
      const L = G.tmLast; if (!L) continue;
      A.n++; A.win += L.win ? 1 : 0; A.t += L.t; A.fall += L.falls; A.af += L.aFalls; A.ad += L.aDmg; A.dmg += L.dmg; A.aheal += L.aHeal; A.cap += L.cap;
      A.heal += Object.entries(L.heal).filter(e => e[0] !== 'revive').reduce((a, e) => a + e[1], 0);
    }
    window.__reset(); return A; };
  // 타임 보스(tb)·1일 보스(db)·강림(gr)
  window.__tb = (kind, diff, k, n, good) => { const A = {n:0, win:0, t:0, fall:0, af:0, dmg:0, heal:0, cap:0, err:0};
    for (let j = 0; j < n; j++){
      window.__reset(); G.setStage(S.stage); G.refreshStats();
      const base = G.tkHas(S.world) ? G.tankIdx(S.maxStage) : 1; if (!lean && k != null) { G.tankK = k / base; G.refreshStats(); }
      G.resetRuntime(); pots(); G.hand = good ? {dodge:1, counter:0.95} : null; G.tmLast = null; S.tb = {}; G.dbForce = true; G.dbCheck();
      let ok = false;
      try {
        if (kind === 'tb'){ const w = G.tbWindow(); if (!w.open) G.addTime(w.next - G.now() + 60000); ok = G.startTimeBoss(diff); }
        else if (kind === 'db') ok = G.startDBoss();
        else ok = G.startGangrim();
      } catch (e) { ok = false; }
      if (!ok) { A.err++; continue; }
      for (let q = 0; q < 6000 && G.raid; q++) G.update(0.05);
      const L = G.tmLast; if (!L) continue;
      A.n++; A.win += L.win ? 1 : 0; A.t += L.t; A.fall += L.falls; A.af += L.aFalls; A.dmg += L.dmg; A.cap += L.cap;
      A.heal += Object.entries(L.heal).filter(e => e[0] !== 'revive').reduce((a, e) => a + e[1], 0);
    }
    window.__reset(); return A; };
  window.__info = () => ({w:S.world, st:S.stage, ms:S.maxStage, lv:S.level, job:S.job, pow:Math.log10(G.tankPow()), hpLv:S.up.hp, atkLv:S.up.atk, armor:S.refine.armor.lv, weapon:S.refine.weapon.lv,
    petDR:G.petDR(), petHp:G.petHpPct(), guard:G.guardLv('seongju'), ref:Math.log10(G.mAtk(S.stage) * 2 * G.MOB_TTK), maxHp:G.ST.maxHp, taken:G.takenStatic(), tk:G.tkHas(S.world), raids:G.raidUnlocked()});
  return window.__info();
}
"""


def find_save(name, c):
    n = name.format(c=c)
    for d in (SIMD,):
        p = d / (n if n.endswith('.json') else n + '.json')
        if p.exists():
            return p
    return None


def read_save(path):
    d = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(d, dict) and 'save' in d and isinstance(d['save'], dict) and 'world' not in d:
        d = d['save']
    return json.dumps(d)


async def load(b, path, c, off=False, lean=None):
    page = await (await b.new_context()).new_page()
    await T.fresh(page)
    info = await page.evaluate(JS_LOAD, [read_save(path), c, off, lean])
    return page, info


def args_of(argv):
    """직업·옵션 가르기"""
    opt = {}
    rest = []
    for a in argv:
        if '=' in a:
            k, v = a.split('=', 1)
            opt[k] = v
        else:
            rest.append(a)
    return rest, opt


# ───────────────────────── anchors ─────────────────────────
async def mode_anchors(b, classes):
    print('저장 앵커별 버티는 힘 — tankPow(log10) · 지금 몬스터 기준 heroRef(log10) · 차이(버티는 힘 − 기준). 표가 비어 있는 동안은 기준이 예전 HERO_REF')
    for name, pat in ANCH:
        for c in classes:
            p = find_save(pat, c)
            if not p:
                continue
            page, i = await load(b, p, c)
            print(f"{name:<18s} {KO[c]} {WN[i['w']]} {i['st']}단계 Lv{i['lv']}: 버티는 힘 10^{i['pow']:.2f} · 기준 10^{i['ref']:.2f} · 차이 {i['pow'] - i['ref']:+.2f}(×{10 ** (i['pow'] - i['ref']):.3g}) "
                  f"· 체력 Lv{i['hpLv']}(공격 Lv{i['atkLv']}) · 방어구 +{i['armor']}(무기 +{i['weapon']}) · 방어 펫 받는 피해 -{i['petDR']:.0f}%·체력 +{i['petHp']:.0f}% · 성주신 Lv{i['guard']}", flush=True)
            await page.close()


# ───────────────────────── prog ─────────────────────────
ANCHOR = "if (opts.snapQ && !('q' in snaps)"
SIM2 = T.SIM.replace(ANCHOR, "if (opts.stopQ && G.S.quest.main >= opts.stopQ && !G.raid) { G.S.gold += lgBank.g; G.S.gems += lgBank.e; lgBank.g = lgBank.e = 0; snaps.out = JSON.stringify(G.S); first.END = Math.round(t / 60); break; }\n    " + ANCHOR)
assert SIM2 != T.SIM
hh = lambda m: '-' if m is None else (f'{m / 60:.1f}h' if m >= 60 else f'{m}m')
KINDS = ['field', 'boss', 'gate', 'raid', 'jin', 'tb', 'db', 'gr', 'other']


def tm_table(tm):
    """세계·싸움 종류별 계측 합 표 — 클리어율·쓰러짐·동료 쓰러짐·회복 몫·막힌 몫·30% 아래"""
    print('  세계·싸움      횟수  클리어  쓰러짐/판 동료쓰러짐/판 회복몫 막힌몫 보호막몫 30%아래/판 가장낮은체력 (지수 평균)')
    for w in range(11):
        for k in KINDS:
            A = tm.get(f'{w}:{k}')
            if not A or not A['n']:
                continue
            n = A['n']; heal = sum(v for h, v in A['heal'].items() if h != 'revive')
            win = f"{A['win'] / n * 100:3.0f}%" if k != 'field' else '  -'
            print(f"  {WN[w]:<6s}{k:<6s} {n:5d}  {win}   {A['falls'] / n:6.2f}   {A['aFalls'] / n:6.2f}      {heal / max(1, A['dmg']):5.2f}  {A['cap'] / max(1, A['dmg']):5.2f}  {A['sh'] / max(1, A['dmg']):5.2f}   {A['low'] / n:6.2f}   {A['minHp'] / n * 100:4.0f}%   {A['idx'] / n:.2f}")


async def run_seg(b, cls, hours, opts):
    page = await (await b.new_context()).new_page()
    await T.fresh(page)
    r = await page.evaluate(SIM2, [hours * 60, cls, opts])
    await page.close()
    return r


def merge_tm(a, b):
    for k, A in (b or {}).items():
        X = a.setdefault(k, {kk: (dict() if isinstance(v, dict) else 0) for kk, v in A.items()})
        for kk, v in A.items():
            if isinstance(v, dict):
                for h, x in v.items():
                    X[kk][h] = X[kk].get(h, 0) + x
            else:
                X[kk] += v


async def prog_one(b, cls, part, lean, off, ends):
    tag = f'{part}' + (f'_{lean}' if lean else '') + ('_off' if off else '')
    base = {'dt': 0.2, 'tanklog': True, 'tmlog': True, 'snapW': SNAPW, 'tankoff': off, 'lean': lean}
    segs = []   # (시간, 시작 저장, 옵션)
    if part == '1':
        marks = [m for m in (60, 240, 720, 1440, 2880, 4320, 5760, 6000) if m <= 6000]
        segs.append((100, None, dict(base, marks=marks)))
    elif part == '23':
        save = (SIMD / f'save_{cls}_q113.json').read_text(encoding='utf-8')
        segs.append((220, save, dict(base, marks=[600, 1440, 2880, 5760, 8640, 12000], load=save, stopQ=182, leanLoad=bool(lean))))
    else:
        chain = ['end', 'sea1', 'sea2'] if part == '4' else ['sea3', 'ind1', 'ind2']
        W0 = 5 if part == '4' else 8
        for k, st in enumerate(chain):
            save = (SIMD / f'save_{cls}_{st}.json').read_text(encoding='utf-8')
            w = W0 + k
            segs.append((40, save, dict(base, marks=list(range(120, 2401, 120)), load=save, raidlog=True, seaW=w, stopQ=ends[str(w)], leanLoad=bool(lean) and k == 0)))
    first, tank, tm, log, falls, tt = {}, [], {}, [], 0, 0
    snaps = {}
    for k, (hours, save, o) in enumerate(segs):
        if k and prev_out:
            o['load'] = prev_out
        r = await run_seg(b, cls, hours, o)
        prev_out = r['snaps'].get('out')
        for kk, v in r['first'].items():
            first.setdefault(kk, v + tt)
        tt += (r['first'].get('END') or hours * 60)
        tank += r.get('tank') or []; merge_tm(tm, r.get('tm')); log += r['log']
        snaps.update({kk: v for kk, v in r['snaps'].items() if kk.startswith('w')})
    for kk, v in snaps.items():   # 세계 가운데 저장
        (SIMD / f'tank_{cls}_{kk}.json').write_text(v, encoding='utf-8')
    out = SIMD / f'tank_{cls}_{tag}.json'
    out.write_text(json.dumps({'cls': cls, 'part': part, 'lean': lean, 'off': off, 'tank': tank, 'tm': tm, 'first': first, 'log': log[-3:]}, ensure_ascii=False), encoding='utf-8')
    return cls, first, tank, tm, log, str(out)


async def mode_prog(b, part, classes, lean, off):
    ends = None
    if part in ('4', '5'):
        page = await (await b.new_context()).new_page()
        await T.fresh(page)
        ends = await page.evaluate("() => { const G = window.__game; return {5:G.PART4A_END, 6:G.PART4B_END, 7:G.PART4_END, 8:G.PART5A_END, 9:G.PART5B_END, 10:G.MAIN_Q.length}; }")
        await page.close()
        ends = {str(k): v for k, v in ends.items()}
    t0 = time.time()
    res = await asyncio.gather(*[prog_one(b, c, part, lean, off, ends) for c in classes])
    for c, first, tank, tm, log, path in res:
        print(f'\n===== {KO[c]} 부 {part}{" lean=" + lean if lean else ""}{" off" if off else ""} =====')
        for line in log[-2:]:
            print(line[:230])
        T.long_table(c, first)
        for w in range(5, 11):
            print(f'        {WN[w]} ' + ' '.join(f"{s}:{hh(first.get(f'{w}:{s}'))}" for s in (4, 11, 21, 31, 41, 51, 61)))
        print('  세계별 쓰러짐: ' + ' · '.join(f"{WN[w]} {sum(A['falls'] for k, A in tm.items() if k.startswith(f'{w}:'))}" for w in range(11) if any(k.startswith(f'{w}:') for k in tm)))
        tm_table(tm)
        print('  원자료:', path)
    print(f'걸린 시간 {time.time() - t0:.0f}초')


# ───────────────────────── ref ─────────────────────────
def mode_ref(classes):
    rows = {}
    for p in sorted(SIMD.glob('tank_*_off.json')):
        d = json.loads(p.read_text(encoding='utf-8'))
        if d.get('lean') or d['cls'] not in classes:
            continue
        for w, s, _t, lg, *_ in d['tank']:
            rows.setdefault(d['cls'], {}).setdefault(w, []).append((s, lg))
    if not rows:
        print('tank_*_off.json 이 없다 — 먼저 prog … off 를 돌린다')
        return
    # 세계마다 5단계 칸으로 묶어 직업별 평균 log
    bins = {}   # (w, bin) → {c: [(s, lg)…]}
    for c, W in rows.items():
        for w, lst in W.items():
            for s, lg in lst:
                bins.setdefault((w, (s - 1) // 5), {}).setdefault(c, []).append((s, lg))
    mean = lambda v: sum(v) / len(v)
    cb = {k: {c: (mean([s for s, _ in v]), mean([lg for _, lg in v])) for c, v in cd.items()} for k, cd in bins.items()}
    cls_off = {}
    for c in rows:
        diffs = []
        for k, cd in cb.items():
            if c in cd and len(cd) >= 2:
                diffs.append(cd[c][1] - mean([x[1] for x in cd.values()]))
        cls_off[c] = mean(diffs) if diffs else 0.0
    ref = {}
    for (w, bi), cd in sorted(cb.items()):
        ref.setdefault(w, []).append((mean([x[0] for x in cd.values()]), mean([x[1] - cls_off[c] for c, x in cd.items()])))
    print('const TANK_REF = [')
    for w in range(11):
        if w not in ref:
            print('  [],')
            continue
        lst, top = [], -99
        for s, lg in ref[w]:
            top = max(top, lg)   # 단계가 오를수록 줄지 않게
            lst.append(f'[{round(s)}, {top:.2f}]')
        print('  [' + ', '.join(lst) + '],   // ' + WN[w])
    print('];')
    print('const TANK_CLS = {' + ', '.join(f'{c}:{cls_off.get(c, 0):.2f}' for c in CLASSES) + '};')


# ───────────────────────── fight ─────────────────────────
def boss_line(label, A, k):
    n = max(1, A['n'])
    return (f"    {label:<22s} 이김 {A['win'] / n * 100:3.0f}% · 쓰러짐 {A['fall'] / n:.2f}/판 · 30% 아래 {A['low'] / n:.2f}/판 · 가장 낮은 체력 {A['minHp'] / n * 100:.0f}% "
            f"· 회복 몫 {A['heal'] / max(1, A['dmg']):.2f} · 막힌 몫 {A['cap'] / max(1, A['dmg']):.2f} · 보호막 몫 {A['sh'] / max(1, A['dmg']):.2f} · {A['t'] / n:.0f}초")


async def world_pages(b, w, classes, off, lean=None):
    for c in classes:
        for pat in WSAVES.get(w, []):
            p = find_save(pat, c)
            if not p:
                continue
            page, i = await load(b, p, c, off, lean)
            if i['w'] != w:
                await page.close()
                continue
            yield c, p.stem, page, i


async def mode_fight(b, worlds, n, idxs, lean, off):
    for w in worlds:
        async for c, stem, page, i in world_pages(b, w, CLS4, off, lean):
            st = await page.evaluate('() => window.__stages()')
            print(f"## {WN[w]} · {KO[c]} · {stem} (Lv{i['lv']}, 지금 {i['st']}단계) — 벽 {st['wall']} · 쉬운 {st['easy']} · 수문장 {st['gate']}" + (f' · lean={lean}' if lean else '') + (' · off' if off else ''), flush=True)
            for label, s in (('벽 단계', st['wall']), ('쉬운 단계', st['easy']), ('수문장', st['gate'])):
                for k in ([None] if lean else idxs):
                    A = await page.evaluate('([s, k, n]) => window.__boss(s, k, n)', [s, k, n])
                    print(boss_line(f'{label} {s} 지수 {"그대로" if k is None else k}', A, k), flush=True)
            for k in ([None] if lean else idxs[:1] + idxs[-1:]):
                A = await page.evaluate('([s, k]) => window.__field(s, k, 10)', [st['wall'], k])
                print(f"    사냥터 10분(단계 {st['wall']} 지수 {'그대로' if k is None else k}): 쓰러짐 {A['falls']} · 물러남 {A['retreat']}단계 · 회복 몫 {A['heal'] / max(1, A['dmg']):.2f} · 30% 아래 {A['low']}", flush=True)
            await page.close()


# ───────────────────────── raid ─────────────────────────
async def mode_raid(b, worlds, n, rs, off):
    for w in worlds:
        seen = set()
        async for c, stem, page, i in world_pages(b, w, CLS4, off):
            cnt = i['raids']
            if cnt < 1:
                await page.close()
                continue
            pick = sorted({0, (cnt - 1) // 2, cnt - 1})
            print(f"## {WN[w]} · {KO[c]} · {stem} (Lv{i['lv']}, 열린 레이드 {cnt}곳) — 첫·가운데·끝 = {pick}" + (' · off' if off else ''), flush=True)
            for ri in pick:
                for r in rs:
                    A = await page.evaluate('([i, r, n]) => window.__raid(i, r, n)', [ri, r, n])
                    k = max(1, A['n'])
                    print(f"    레이드 {ri} 권장 {int(r * 100)}%: 이김 {A['win'] / k * 100:3.0f}% · {A['t'] / k:.0f}초 · 용사 쓰러짐 {A['fall'] / k:.2f} · 동료 쓰러짐 {A['af'] / k:.2f}"
                          f" · 회복 몫 {A['heal'] / max(1, A['dmg']):.2f} · 동료 회복 몫 {A['aheal'] / max(1, A['ad']):.2f}" + (f" · {A['err']}" if A['err'] else ''), flush=True)
            await page.close()


# ───────────────────────── tb ─────────────────────────
async def mode_tb(b, worlds, n, idxs, hands, off):
    for w in worlds:
        async for c, stem, page, i in world_pages(b, w, CLS4, off):
            print(f"## {WN[w]} · {KO[c]} · {stem} (Lv{i['lv']})" + (' · off' if off else ''), flush=True)
            for kind, diff in (('tb', 'normal'), ('tb', 'hell'), ('db', None), ('gr', None)):
                for k in idxs:
                    for hand in hands:
                        A = await page.evaluate('([kind, diff, k, n, good]) => window.__tb(kind, diff, k, n, good)', [kind, diff, k, n, hand == 'good'])
                        m = max(1, A['n'])
                        print(f"    {kind}{':' + diff if diff else ''} 지수 {k} 손 {hand}: 이김 {A['win'] / m * 100:3.0f}% · 쓰러짐 {A['fall'] / m:.2f} · 동료 쓰러짐 {A['af'] / m:.2f}"
                              f" · 회복 몫 {A['heal'] / max(1, A['dmg']):.2f} · {A['t'] / m:.0f}초" + (f" · 시작 못 함 {A['err']}" if A['err'] else ''), flush=True)
            await page.close()


# ───────────────────────── old ─────────────────────────
async def mode_old(b):
    files = sorted(BETAD.glob('*.json')) + sorted(p for p in SIMD.glob('*.json') if p.name.startswith(('save_', 'jin_', 'tank_')))
    bad = 0
    for p in files:
        try:
            d = json.loads(read_save(p))
        except Exception:
            continue
        c = d.get('cls') or 'musa'
        page, i = await load(b, p, c)
        s = max(1, i['ms'] - 1)
        A = await page.evaluate('([s]) => window.__boss(s, null, 5)', [s])
        win = A['win'] / max(1, A['n'])
        line = f"{p.name:<34s} {WN[i['w']]} {i['ms']}단계 Lv{i['lv']}: ⓐ지난 단계 {s} 보스 {win * 100:.0f}%"
        flags = []
        if win < 0.8:
            flags.append('ⓐ')
        cnt = i['raids']
        if cnt > 0:
            res = []
            for ri in sorted({0, (cnt - 1) // 2, cnt - 1}):
                R = await page.evaluate('([i]) => window.__raid(i, null, 5)', [ri])
                rw = R['win'] / max(1, R['n']) if R['n'] else 1
                res.append(f'{ri}:{rw * 100:.0f}%')
                if R['n'] and rw < 0.8:
                    flags.append('ⓑ')
            line += ' · ⓑ레이드 ' + ' '.join(res)
        F = await page.evaluate('([s]) => window.__field(s, null, 5)', [i['st']])
        line += f" · ⓒ사냥터 5분 쓰러짐 {F['falls']} 물러남 {F['retreat']}"
        if F['retreat'] > 0:
            flags.append('ⓒ')
        line += f" · ⓓ버티는 힘 10^{i['pow']:.2f}"
        print(('✗ ' if flags else '  ') + line + (f"  ← {''.join(sorted(set(flags)))}" if flags else ''), flush=True)
        bad += 1 if flags else 0
        await page.close()
    print(f'표본 {len(files)}개 가운데 ✗ {bad}개')


async def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    mode = sys.argv[1]
    rest, opt = args_of(sys.argv[2:])
    off = 'off' in rest
    rest = [a for a in rest if a != 'off']
    classes = [a for a in rest if a in CLASSES]
    nums = [int(a) for a in rest if a.isdigit()]
    n = int(opt.get('n', 20))
    lean = opt.get('lean')
    async with async_playwright() as p:
        b = await T.launch(p)
        try:
            if mode == 'anchors':
                await mode_anchors(b, classes or CLASSES)
            elif mode == 'prog':
                part = rest[0] if rest and rest[0] in ('1', '23', '4', '5') else '1'
                await mode_prog(b, part, classes or CLS4, lean, off)
            elif mode == 'ref':
                mode_ref(classes or CLS4)
            elif mode == 'fight':
                await mode_fight(b, nums or [1, 2, 3, 4], n, [float(x) for x in opt.get('idx', '0.7,1,1.3').split(',')], lean, off)
            elif mode == 'raid':
                await mode_raid(b, nums or [0, 2, 3, 4], n, [float(x) for x in opt.get('r', '0.8,1,1.3').split(',')], off)
            elif mode == 'tb':
                await mode_tb(b, nums or [3, 5], n, [float(x) for x in opt.get('idx', '1').split(',')], opt.get('hand', 'auto,good').split(','), off)
            elif mode == 'old':
                await mode_old(b)
            else:
                raise SystemExit(__doc__)
        finally:
            await b.close()


if __name__ == '__main__':
    asyncio.run(main())
