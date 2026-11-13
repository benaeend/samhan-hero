"""버티는 힘 재기 도구(물의 신화 9-4, docs/patch-sea/STAGE9_4.md 2-2절).

사용: python3 tools/sim_tank.py <모드> [인자…]
  anchors [직업…]                      저장 앵커마다 버티는 힘(log10)·부분(체력 레벨·방어구 재련·방어 펫·성주신)·지금 몬스터 기준(HERO_REF)·차이를 찍음 (2분)
  prog <1|23|3|4|5> [직업…] [lean=mild|hard] [off]
                                      진행 시뮬. 1 = 처음부터 100시간 · 23 = save_<직업>_q113 에서 이야기 182까지(최대 220시간) · 3 = save_<직업>_q145 에서 이야기 182까지(곤륜만, 최대 170시간) · 4 = end→sea1→sea2→sea3 · 5 = sea3→ind1→ind2→ind3.
                                      끝에 이정표 표 · 세계·싸움 종류별 계측 합 · 원자료를 docs/patch-sea/sim/tank_<직업>_<부>[_lean][_off].json 에 남김.
                                      (1·23은 세계 가운데 저장 tank_<직업>_w<세계>s<단계>.json 도 남김) 오래 걸림(1부 10분 · 23부 10분 · 4부 15분 · 5부 15분)
  ref [직업…]                          prog 가 남긴 tank_*_off.json 으로 기준표 TANK_REF · 직업 몫 TANK_CLS 초안을 찍음 (1분)
  fight <세계…> [n=20] [idx=0.7,1,1.3] [lean=…] [off]
                                      그 세계 저장마다 지금 최고 단계에서 힘(공격력·체력 함께)을 맞춰 벽(맨몸 25초)·쉬운 판(8초)·가까운 수문장(25초)을 만들고, 지수를 맞춰 n판 + 사냥터 10분(지수 0.4·0.7·1.0)
                                      (표 TANK_REF 가 비어 있으면 idx 는 「지금 버티는 힘의 몇 배」, 있으면 지수 그 자체. 탕약·산삼·감로수는 9999개라 탕약이 귀한 1부에서는 진행 시뮬보다 덜 쓰러진다)
  raid <세계…> [n=20] [r=0.8,1,1.3] [last=1] [off]
                                      그 세계 저장으로 일반 레이드 첫·가운데·끝을 r 로 n판. r = 1 은 「장치 없이 딱 45초에 깨는 힘 + 그 레이드 평균의 버티는 힘」(둘 다 r배로)
  공통 옵션: only=저장 이름 조각,… · tk=@파일|JSON (TANK 손잡이 덮어쓰기: k·bigK… 와 PAT·REF·CLS)
  tb <세계…> [n=20] [idx=…] [hand=auto,good] [off]
                                      타임 보스 노말·지옥, 1일 보스, 강림을 n판
  old                                 저장 표본 전부로 「지난 단계 보스·첫 토벌한 레이드를 다시 깰 수 있나·사냥터에서 안 물러나나」 (15분)
옵션 off 는 __game.tankOff = true (예전 방식 — 같은 코드에서 견주는 기준). I-1 단계에서는 장치가 없어서 켜든 끄든 같다.
빌드된 index.html 을 쓴다(먼저 python3 tools/build.py). 코어가 둘뿐이면 다른 점검과 겹치지 않게 flock /tmp/samhan-test.lock 으로.
(2026-11-14) 이 도구의 브라우저는 화면 프레임을 만들지 않는다(--enable-begin-frame-control 등) — 그리는 프로세스가 CPU를 가져가 시뮬이 굶던 것을 없애 진행 시뮬이 10배쯤 빨라졌다(3부 한 직업 78시간 = 4분).
곤륜 표·수치를 정한 스크립트와 로그는 scratchpad bal94t/ (rest.py 저장 대 표 · idx.py 켠 판의 지수 · cmp.py 켬/끔 이정표 · w4.py 곤륜 표).
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

ONLY = None    # only=이름 조각,… : 그 저장만
FCLS = None    # fight/raid/tb 가 볼 직업(기본 네 직업)
FIELD_IDX = [0.4, 0.7, 1.0]
LAST = False   # last=1 : raid 가 가장 뒤 레이드만
RUN = None     # run=이름 : prog 원자료 이름 꼬리표
NO_DRAW = "() => { window.requestAnimationFrame = () => 0; const st = document.createElement('style'); st.textContent = '*, *::before, *::after { animation: none !important; transition: none !important; } html { visibility: hidden !important; }'; document.head.appendChild(st); }"
TKSET = None   # tk=@파일 또는 tk=JSON: 시험용으로 TANK 손잡이를 덮어씀(PAT·REF·CLS 키는 그 표에)
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
([save, cls, off, lean, tkset]) => {
  const G = window.__game; G.quiet = true; G.noFork = true; G.gateOff = true; G.noInh = true;
  if (tkset) { for (const [k, v] of Object.entries(tkset)) { if (k === 'PAT') Object.assign(G.PAT, v); else if (k === 'REF') { for (const [w, t] of Object.entries(v)) G.TANK_REF[w] = t; } else if (k === 'CLS') Object.assign(G.TANK_CLS, v); else G.TANK[k] = v; } }
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
  // 보스에게 안 맞고 쓰러뜨리는 데 걸리는 초(손컨 끔). pk = 공격력·체력을 함께 곱하는 배율(powK)
  window.__ttk = (s, pk) => { let sum = 0; for (let q = 0; q < 2; q++){ window.__reset(); G.powK = pk || 1; G.PAT.off = true; G.refreshStats(); G.resetRuntime(); G.setStage(s); S.autoBoss = false; pots(); G.startBoss(); const B = G.bossRef; if (!B) { G.PAT.off = false; return 99; } B.atk = 0; B.aoe = 0;
    let t = 0; for (; t < 60 && G.bossActive; t += 0.05) G.update(0.05); G.PAT.off = false; sum += t; } return sum / 2; };
  // 그 단계를 딱 target초에 깨는 힘 배율(시간 ∝ 1/힘으로 고쳐 가며 찾음)
  const calPk = (s, target) => { let pk = 1, t = 0; for (let it = 0; it < 6; it++){ t = window.__ttk(s, pk); if (Math.abs(t - target) < target * 0.06) break; pk *= Math.max(0.1, Math.min(6, t >= 59 ? 4 : t / target)); } return {pk, t}; };
  // (2026-11-14 고침) 단계마다 몬스터가 조금씩만 세지는 세계(부상·바다)에서는 「22초 넘게 걸리는 첫 단계」가 기술 타이밍 운으로 흔들려서,
  // 지금 최고 단계에서 힘(공격력·체력 함께)을 맞춰 벽(25초)·쉬운 판(8초)을 만든다. 지수는 그 뒤 체력만 곱해 맞춘다. 수문장은 그 위 가장 가까운 9번째 단계
  window.__stages = () => { const s0 = Math.max(S.stage, S.maxStage), gate = s0 + ((9 - s0 % 10) + 10) % 10;
    const W = calPk(s0, 25), E = calPk(s0, 8), Gt = calPk(gate, 25);
    window.__reset(); return {wall:s0, easy:s0, gate, s0, pkW:W.pk, tW:W.t, pkE:E.pk, tE:E.t, pkG:Gt.pk, tG:Gt.t}; };
  // 보스 n판: k = 지수(표가 없으면 지금의 몇 배), pk = 힘 배율
  window.__boss = (s, k, n, pk) => { const A = {n:0, win:0, fall:0, low:0, minHp:0, dmg:0, heal:0, cap:0, sh:0, t:0, idx:0, fallN:0, time:0};
    for (let j = 0; j < n; j++){
      window.__reset(); G.powK = pk || 1; G.setStage(s); G.refreshStats();
      const base = G.tkHas(S.world) ? G.tankIdx(s) : 1; if (!lean && k != null) { G.tankK = k / base; G.refreshStats(); }
      G.resetRuntime(); G.setStage(s); S.autoBoss = false; pots(); G.tmLast = null;
      G.startBoss(); const T0 = G.S.stage; for (let t = 0; t < 70 && G.bossActive; t += 0.05) G.update(0.05);
      const L = G.tmLast; if (!L) continue;
      A.n++; A.win += L.win ? 1 : 0; A.fall += L.falls; A.fallN += L.falls > 0 ? 1 : 0; A.time += !L.win && !L.falls ? 1 : 0; A.low += L.low; A.minHp += L.minHp; A.dmg += L.dmg; A.sh += L.sh; A.cap += L.cap; A.t += L.t; A.idx += L.idx;
      A.heal += Object.entries(L.heal).filter(e => e[0] !== 'revive').reduce((a, e) => a + e[1], 0);
    }
    window.__reset(); return A; };
  // 사냥터 minutes 분: 쓰러짐·물러남·회복 몫
  window.__field = (s, k, minutes, pk) => { window.__reset(); G.powK = pk || 1; G.setStage(s); G.refreshStats(); const base = G.tkHas(S.world) ? G.tankIdx(s) : 1; if (!lean && k != null) { G.tankK = k / base; G.refreshStats(); }
    G.setStage(s); S.bossAuto = false; pots(); const f0 = S.rec.falls; let low = s; G.tmReset();
    for (let i = 0; i < minutes * 600; i++){ S.autoBoss = false; G.update(0.1); if (S.stage < low) low = S.stage; }
    const m = G.tmAgg()[S.world + ':field'] || {}; const out = {falls:S.rec.falls - f0, retreat:s - low, dmg:m.dmg || 0, heal:Object.entries(m.heal || {}).filter(e => e[0] !== 'revive').reduce((a, e) => a + e[1], 0), low:m.low || 0, n:m.n || 0};
    window.__reset(); return out; };
  // 일반 레이드 i 를 권장 전투력의 r배로 n판
  // r 축(2026-11-14 고침): 화면의 권장 전투력(raidRecPower)은 실제 피해와 수십~수백 배 어긋나 3~6초에 깨져 버렸다 → 「장치 없이(tankOff) 딱 45초에 깨는 힘」을 r = 1로 삼는다.
  // 판마다 걸린 시간으로 powK를 고쳐 가며(시간 ∝ 1/힘) 45초가 되는 배율을 찾는다
  const calC = {};
  window.__raidCal = i => { if (calC[i]) return calC[i]; const off0 = G.tankOff; G.tankOff = true; let pk = 1, t = 0;
    for (let it = 0; it < 7; it++){
      let ts = 0, m = it < 4 ? 1 : 3;
      for (let q = 0; q < m; q++){ window.__reset(); G.powK = pk; G.refreshStats(); G.resetRuntime(); pots(); S.raid.tk = 3; G.tmLast = null;
        if (!G.startRaid(i)) { ts += 45; continue; }
        for (let k = 0; k < 4000 && G.raid; k++) G.update(0.05);
        const L = G.tmLast; ts += L && L.win ? L.t : 180; }
      t = ts / m; if (Math.abs(t - 45) < 2 && it >= 4) break;
      pk *= Math.pow(Math.max(0.05, Math.min(8, t / 45)), it < 4 ? 1 : 0.7); }
    G.tankOff = off0; window.__reset(); G.refreshStats(); const info = G.raidAt(i);
    calC[i] = {pk, t, rec:G.raidRecPower(info), pw:G.power(G.ST), ref:info.ref, rd:G.S.rec.rdpsK || 0}; return calC[i]; };
  window.__raid = (i, r, n) => { const A = {n:0, win:0, t:0, fall:0, af:0, ad:0, dmg:0, heal:0, aheal:0, cap:0, err:'', idx:0};
    const cal = r == null ? null : window.__raidCal(i);
    for (let j = 0; j < n; j++){
      window.__reset(); G.refreshStats();
      G.powK = r == null ? 1 : r * cal.pk; G.refreshStats();
      if (r != null && G.tkHas(S.world)) { G.tankK = r / G.tankIdx(G.tkRaidS(G.raidAt(i).ref)); G.refreshStats(); }   // 권장 r배 용사 = 버티는 힘도 그 레이드 평균의 r배(체력만 곱해 맞춤)
      G.resetRuntime(); pots(); S.raid.tk = 3; G.tmLast = null; A.idx = G.tankIdx(G.tkRaidS(G.raidAt(i).ref));
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
    await page.evaluate(NO_DRAW)   # 그리기 끔: 화면을 그리는 프로세스(gpu)가 CPU를 다 가져가 시뮬(낮은 우선순위)이 굶는 것을 막는다(2026-11-14 — 코어 둘에서 10배쯤 빨라짐)
    info = await page.evaluate(JS_LOAD, [read_save(path), c, off, lean, TKSET])
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
TKA = "if (opts.tankoff) G.tankOff = true;"
SIM2 = SIM2.replace(TKA, TKA + " if (opts.tkset) { for (const [k, v] of Object.entries(opts.tkset)) { if (k === 'PAT') Object.assign(G.PAT, v); else if (k === 'REF') { for (const [w, t] of Object.entries(v)) G.TANK_REF[w] = t; } else if (k === 'CLS') Object.assign(G.TANK_CLS, v); else G.TANK[k] = v; } }")
assert TKA in T.SIM
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
    await page.evaluate(NO_DRAW)   # 그리기 끔: 화면을 그리는 프로세스(gpu)가 CPU를 다 가져가 시뮬(낮은 우선순위)이 굶는 것을 막는다(2026-11-14 — 코어 둘에서 10배쯤 빨라짐)
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
    tag = f'{part}' + (f'_{lean}' if lean else '') + ('_off' if off else '') + (f'_{RUN}' if RUN else '')   # run=이름: 같은 조건을 여러 번 돌려 판마다 운 차이를 볼 때(기준 저장은 안 덮음)
    base = {'dt': 0.2, 'tanklog': True, 'tmlog': True, 'snapW': SNAPW, 'tankoff': off, 'lean': lean, 'tkset': TKSET}
    segs = []   # (시간, 시작 저장, 옵션)
    if part == '1':
        marks = [m for m in (60, 240, 720, 1440, 2880, 4320, 5760, 6000) if m <= 6000]
        segs.append((100, None, dict(base, marks=marks)))
    elif part == '23':
        save = (SIMD / f'save_{cls}_q113.json').read_text(encoding='utf-8')
        segs.append((220, save, dict(base, marks=[600, 1440, 2880, 5760, 8640, 12000], load=save, stopQ=182, leanLoad=bool(lean))))
    elif part == '3':   # 3부만(곤륜 기준표용): save_<직업>_q145 에서 이야기 182까지(최대 170시간)
        save = (SIMD / f'save_{cls}_q145.json').read_text(encoding='utf-8')
        segs.append((170, save, dict(base, marks=[600, 1440, 2880, 5760, 8640], load=save, stopQ=182, leanLoad=bool(lean))))
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
    for kk, v in (snaps.items() if off and not lean and not RUN else []):   # 세계 가운데 저장(장치 끈 기준 판만 — 켠 판이 기준 저장을 덮지 않게)
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
PARTS = [[0, 1, 2], [3, 4], [5, 6, 7], [8, 9, 10]]   # 직업 몫을 묶는 부(1부 · 2·3부 · 4부 · 5부)


def mode_ref(classes):
    """기준표 초안. (2026-11-14 고침) 네 직업이 모두 닿은 단계 칸만 묶고(한 직업만 앞서간 칸이 표를 흔들지 않게), 직업 몫은 부마다 따로 낸다."""
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
    bins = {}   # (w, bin) → {c: [(s, lg)…]}
    for c, W in rows.items():
        for w, lst in W.items():
            for s, lg in lst:
                bins.setdefault((w, (s - 1) // 5), {}).setdefault(c, []).append((s, lg))
    mean = lambda v: sum(v) / len(v)
    cb = {k: {c: (mean([s for s, _ in v]), mean([lg for _, lg in v])) for c, v in cd.items()} for k, cd in bins.items() if len(cd) == len(rows)}
    part_of = {w: pi for pi, ws in enumerate(PARTS) for w in ws}
    cls_off = {}   # (c, part) → 몫
    for c in rows:
        for pi in range(len(PARTS)):
            diffs = [cd[c][1] - mean([x[1] for x in cd.values()]) for (w, _b), cd in cb.items() if part_of[w] == pi]
            cls_off[(c, pi)] = mean(diffs) if diffs else 0.0
    ref = {}
    for (w, bi), cd in sorted(cb.items()):
        ref.setdefault(w, []).append((mean([x[0] for x in cd.values()]), mean([x[1] - cls_off[(c, part_of[w])] for c, x in cd.items()])))
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
    print('const TANK_CLS = {' + ', '.join(f"{c}:[{', '.join(f'{cls_off.get((c, part_of[w]), 0):.2f}' for w in range(11))}]" for c in CLASSES) + '};')


# ───────────────────────── fight ─────────────────────────
def boss_line(label, A, k):
    n = max(1, A['n'])
    return (f"    {label:<22s} 이김 {A['win'] / n * 100:3.0f}% · 쓰러진 판 {A['fallN'] / n * 100:3.0f}% · 시간 초과 {A['time'] / n * 100:3.0f}% · 쓰러짐 {A['fall'] / n:.2f}/판 · 30% 아래 {A['low'] / n:.2f}/판 · 가장 낮은 체력 {A['minHp'] / n * 100:.0f}% "
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
        async for c, stem, page, i in world_pages(b, w, FCLS, off, lean):
            if ONLY and not any(o in stem for o in ONLY):
                await page.close()
                continue
            st = await page.evaluate('() => window.__stages()')
            print(f"## {WN[w]} · {KO[c]} · {stem} (Lv{i['lv']}) — {st['wall']}단계에서 벽(힘 ×{st['pkW']:.3g} → 맨몸 {st['tW']:.0f}초)·쉬운 판(×{st['pkE']:.3g} → {st['tE']:.0f}초) · 수문장 {st['gate']}(×{st['pkG']:.3g} → {st['tG']:.0f}초)"
                  + (f' · lean={lean}' if lean else '') + (' · off' if off else ''), flush=True)
            for label, s, pk in (('벽', st['wall'], st['pkW']), ('쉬운 판', st['easy'], st['pkE']), ('수문장', st['gate'], st['pkG'])):
                for k in ([None] if lean else idxs):
                    A = await page.evaluate('([s, k, n, pk]) => window.__boss(s, k, n, pk)', [s, k, n, pk])
                    print(boss_line(f'{label} {s} 지수 {"그대로" if k is None else k}', A, k) + f" · 실제 지수 {A['idx'] / max(1, A['n']):.2f}", flush=True)
            for k in ([None] if lean else FIELD_IDX):
                A = await page.evaluate('([s, k, pk]) => window.__field(s, k, 10, pk)', [st['wall'], k, st['pkW']])
                print(f"    사냥터 10분(단계 {st['wall']} 지수 {'그대로' if k is None else k}): 쓰러짐 {A['falls']} · 물러남 {A['retreat']}단계 · 회복 몫 {A['heal'] / max(1, A['dmg']):.2f} · 30% 아래 {A['low']}", flush=True)
            await page.close()


# ───────────────────────── raid ─────────────────────────
async def mode_raid(b, worlds, n, rs, off):
    for w in worlds:
        seen = set()
        async for c, stem, page, i in world_pages(b, w, FCLS, off):
            if ONLY and not any(o in stem for o in ONLY):
                await page.close()
                continue
            cnt = i['raids']
            if cnt < 1:
                await page.close()
                continue
            pick = [cnt - 1] if LAST else sorted({0, (cnt - 1) // 2, cnt - 1})
            print(f"## {WN[w]} · {KO[c]} · {stem} (Lv{i['lv']}, 열린 레이드 {cnt}곳) — 첫·가운데·끝 = {pick}" + (' · off' if off else ''), flush=True)
            for ri in pick:
                cal = await page.evaluate('([i]) => window.__raidCal(i)', [ri])
                print(f"    레이드 {ri}(ref {cal['ref']}단계): 45초에 깨는 힘 = 지금의 {cal['pk']:.3g}배(맞춘 뒤 {cal['t']:.0f}초) · 화면 권장은 지금의 {cal['rec'] / cal['pw']:.3g}배 · 실제 피해 배율 rdpsK {cal['rd']:.3g}"
                      + (' ← 맞춤 실패(첫 기술 한 바퀴에 끝나거나 아주 오래 걸리거나 — 아래 줄은 믿지 말 것)' if abs(cal['t'] - 45) > 8 else ''), flush=True)
                for r in rs:
                    A = await page.evaluate('([i, r, n]) => window.__raid(i, r, n)', [ri, r, n])
                    k = max(1, A['n'])
                    print(f"    레이드 {ri} r {int(r * 100)}%: 이김 {A['win'] / k * 100:3.0f}% · {A['t'] / k:.0f}초 · 용사 쓰러짐 {A['fall'] / k:.2f} · 동료 쓰러짐 {A['af'] / k:.2f}"
                          f" · 회복 몫 {A['heal'] / max(1, A['dmg']):.2f} · 동료 회복 몫 {A['aheal'] / max(1, A['ad']):.2f} · 용사 지수 {A['idx']:.2f}" + (f" · {A['err']}" if A['err'] else ''), flush=True)
            await page.close()


# ───────────────────────── tb ─────────────────────────
async def mode_tb(b, worlds, n, idxs, hands, off):
    for w in worlds:
        async for c, stem, page, i in world_pages(b, w, FCLS, off):
            if ONLY and not any(o in stem for o in ONLY):
                await page.close()
                continue
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
    if ONLY:
        files = [p for p in files if any(o in p.name for o in ONLY)]
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
        # (2026-11-14 고침) 첫 토벌한 레이드만 본다 — 열려만 있고 아직 못 깬 레이드(레벨로 열려 세기가 한참 위인 것)는 장치를 꺼도 못 깨서 ✗가 잘못 떴다
        done = await page.evaluate("() => { const G = window.__game, S = G.S, out = []; for (let i = 0; i < G.raidUnlocked(); i++) if (S.raid.first[G.raidAt(i).key]) out.push(i); return out; }")
        cnt = len(done)
        if cnt > 0:
            res = []
            for ri in sorted({done[0], done[(cnt - 1) // 2], done[-1]}):
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
    global TKSET, ONLY, FCLS, LAST, RUN
    RUN = opt.get('run')
    LAST = bool(opt.get('last'))
    ONLY = opt['only'].split(',') if opt.get('only') else None
    FCLS = classes or CLS4
    if opt.get('tk'):
        v = opt['tk']
        TKSET = json.loads(Path(v[1:]).read_text(encoding='utf-8') if v.startswith('@') else v)
    async with async_playwright() as p:
        # 캔버스를 그래픽 프로세스가 아니라 페이지 안에서 그리게(2026-11-14): 진행 시뮬은 새 몬스터·장비 그림을 만들 때마다 픽셀을 되읽는데(hdFinish),
        # 그 일을 맡는 그래픽 프로세스가 브라우저마다 하나라 코어 둘에서 시뮬이 그 대기로 거의 멈춰 있었다. 결과(수치)는 같다
        try:
            b = await p.chromium.launch(args=['--no-sandbox', '--disable-gpu', '--disable-accelerated-2d-canvas', '--disable-gpu-compositing', '--enable-begin-frame-control'])
        except Exception:
            b = await T.launch(p)
        try:
            if mode == 'anchors':
                await mode_anchors(b, classes or CLASSES)
            elif mode == 'prog':
                part = rest[0] if rest and rest[0] in ('1', '23', '3', '4', '5') else '1'
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
