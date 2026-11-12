"""빌드된 index.html을 헤드리스 크롬으로 열어 확인한다.

필요: pip install playwright && python3 -m playwright install chromium
사용:
  python3 tools/test_game.py          # 화면 캡처(tools/out/) + 오류 확인 + 계정·레이드·클라우드 저장 점검
  python3 tools/test_game.py --sim    # + 직업별 30분 빠른 진행 시뮬레이션(밸런스 확인)
  python3 tools/test_game.py --long 100 [직업…] ['{"hp2":1.07}']   # 화면 점검 없이 100시간 진행 시뮬레이션만(이정표 표)

주소 끝에 ?simtest 를 붙이면 게임이 window.__game 테스트 훅을 연다.
"""
import asyncio
import base64
import functools
import json
import os
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = (ROOT / 'index.html').as_uri() + '?simtest'
OUT = ROOT / 'tools' / 'out'

# 사람처럼 굴리는 시뮬레이션: 퀘스트 보상 받기 → 재련(무기 먼저)·펫 강화(지갑의 일부만) → 능력치·기술 → 남은 보석으로 소환 → 레이드
# → 시련·환생(윤회 구슬은 무력부터). opts: {dt, marks:[분…], curve:{CURVE 덮어쓰기}}
SIM = r"""
(args) => {
  const [minutes, cls, opts = {}] = args;   // opts.nocraft: 조합 공방을 쓰지 않는 사람
  const G = window.__game;
  G.quiet = true;
  G.setClass(cls);
  if (opts.curve) Object.assign(G.CURVE, opts.curve);
  if (opts.busang) Object.assign(G.BUSANG, opts.busang);
  if (opts.expk) G.EXP_K[3] = opts.expk;
  if (opts.kunlun) Object.assign(G.KUNLUN, opts.kunlun);
  if (opts.expk4) G.EXP_K[4] = opts.expk4;
  if (opts.sea1) Object.assign(G.SEA1, opts.sea1);   // 물의 신화 5단계: 동해 세기·경험치 덮어쓰기(tools/sim_sea4.py)
  if (opts.expk5) G.EXP_K[5] = opts.expk5;
  if (opts.over) for (const [k, v] of Object.entries(opts.over)) { const p = k.split('.'); let o = G; for (let z = 0; z < p.length - 1; z++) o = o[p[z]]; o[p[p.length - 1]] = v; }   // 아무 값이나 덮어쓰기(예: {'LATE_K.musaE': 0.5})
  if (opts.late) Object.assign(G.LATE_K, opts.late);
  if (opts.sea) G.seaForce = true;   // 물의 신화 4단계: 4부의 새 성장(투구·어깨·신발·호박석)을 미리 열어 놓고 돌린다(tools/sim_sea.py)
  if (opts.load) { Object.assign(G.S, G.mergeState(JSON.parse(opts.load)));   // 예전 저장도 새 칸을 채워서
    G.S.cls = cls; if (G.S.world >= 3) G.refineInherit(); G.refreshStats(); G.setStage(G.S.stage); }   // 저장 시점부터 이어서
  G.S.buyMode = 1;
  const dt = opts.dt || 0.05, steps = Math.round(minutes * 60 / dt);
  const marks = new Set((opts.marks || [5, 10, 20, 30]).map(m => Math.round(m * 60 / dt)));
  const log = [], first = {}, snaps = {};
  let jobPend = null, jobHold = 0, nextShop = 0, nextRetry = 60, raidPend = null, raidHold = [0, 0], goldIn = 0, gemIn = 0, memPend = null, memHold = 0, aw2Hold = 0, aw2T0 = null; const memBank = {g:0, e:0};
  const Wt = {atk:1, hp:1.3, crit:1.5, critDmg:1.8, aspd:1.5, regen:3};
  const mark = (k, t) => { if (!(k in first)) first[k] = Math.round(t / 60); };
  const raids = []; let rl = null;   // opts.raidlog: 레이드마다 걸린 시간·이김·초각성 한 방이 보스 체력의 몇 %
  for (let i = 1; i <= steps; i++) {
    const g0 = G.S.gold, e0 = G.S.gems;
    G.update(dt); G.addTime(dt * 1000);
    goldIn += Math.max(0, G.S.gold - g0); gemIn += Math.max(0, G.S.gems - e0);
    const t = i * dt;
    if (opts.raidlog) {
      if (G.raid && !rl) { const I = G.raid.info, B = G.raid.boss, C = G.CLASSES[G.S.cls]; rl = {t0:t, k:I.key || (I.tb ? 'tb' : I.dboss ? 'db' : I.vault ? 'vault' : I.dummy ? 'dummy' : I.job ? 'job' : 'x'), ref:I.ref, w:G.S.world, lv:G.S.level, st:G.S.maxStage, n0:G.S.rec.raids,
        awk:G.S.awaken ? Math.round(G.realDps() * (G.S.job >= 4 ? G.AWAKEN_SEC4 : G.AWAKEN_SEC) / B.maxHp * 100) : 0}; }
      else if (!G.raid && rl) { raids.push(Object.assign(rl, {dur:Math.round(t - rl.t0), win:G.S.rec.raids > rl.n0})); rl = null; }
    }
    if (t >= nextShop) {
      nextShop = t + 2;
      const e1 = G.S.gems; G.claimAll(); gemIn += Math.max(0, G.S.gems - e1);
      for (let k = 0; k < 20; k++) {
        const capW = G.refineCap('weapon'), capA = G.refineCap('armor'), rw = G.S.refine.weapon.lv, ra = G.S.refine.armor.lv;
        const slot = rw < capW && (rw <= ra + 3 || ra >= capA) ? 'weapon' : 'armor', lv = G.S.refine[slot].lv;
        if (lv >= G.refineCap(slot) || G.refineGold(lv) > G.S.gold * 0.25 || G.refineGems(lv) > G.S.gems * 0.5) break;
        G.refineTry(slot);
      }
      if (G.seaOpen() && !opts.nosea) G.seaGrow();   // 물의 신화 4단계: 4부부터 새 장비 칸(투구·어깨·신발) 소환·합성·재련과 호박석 세공(추천 줄)
      for (const pt of G.PET_TYPE_ORDER) {
        G.petEquipBest(pt);
        const pi = G.eqPet(pt); if (pi < 0) continue;
        for (let k = 0; k < 40; k++) {
          const c = G.petUpCost(G.S.pets.lv[pi]);
          if (G.S.pets.lv[pi] >= 30 || c.gems > G.S.gems * 0.2 || c.gold > G.S.gold * 0.15) break;
          if (!G.petUpgrade(pi)) break;
        }
      }
      for (const gd of G.GUARDS) if (G.guardOpen(gd)) for (let z = 0; z < 5; z++) { if (G.guardGold(G.guardLv(gd.k)) > G.S.gold * 0.1 || !G.guardUp(gd.k)) break; }   // 수호신: 엽전의 10%까지
      if (G.guardOpen(G.GUARDS[1]) && G.S.guard.on !== 'jowang') G.guardSet('jowang');
      let elRes = 0;   // 오장 영약(2026-11 (46)): 달일 것이 남았으면 엽전을 모아 두었다가(능력치에는 모은 몫을 빼고 씀) 값이 되면 달이고 추천 처방을 고름
      if (!opts.noelix && G.S.world >= 3) for (const O of G.ORGANS) {
        if (G.S.world < O.w) continue; const st = G.elSt(O.k);
        for (let z = 0; z < 10 && !G.elDone(st); z++) { if (G.elCost(st).gold > G.S.gold || !G.elBrew(O.k)) break; G.elPick(G.elBestCard()); }
        if (G.elDone(st) && st.l[0][1] + st.l[1][1] < 8 && st.n < 3) { const rc = G.elResetCost(st); if (G.S.gems > rc.gems * 3 && (G.S.grudge || 0) >= rc.grudge * 2) G.elReset(O.k); }   // 약하게 굳은 장은 다시 달임
        if (!G.elDone(st) && !elRes) elRes = Math.min(G.S.gold * (opts.elsave ?? 0.6), G.elCost(st).gold); }
      // 물의 신화 6단계 — 환생의 기억(53장부터, opts.nomem으로 끔): 「떠올린다」를 고르고, 값을 따로 모아(엽전은 가진 것의 30%씩, 보석은 300개만 남기고 — 능력치·소환이 먼저 써 버리지 않게) 치른 뒤 싸운다.
      // 이승(엽전)과 저승·천계(보석)는 쓰는 재화가 달라 함께 모은다
      if (G.memOpen() && !G.memClosed() && !opts.nomem) {
        if (!G.S.mem.ch) G.memPick('yes');
        if (G.S.mem.ch === 'yes') {
          const todo = [0, [1, 2].find(x => G.S.mem.p[x] < 4)].filter(x => x != null && G.S.mem.p[x] < 4);
          for (const b of todo) if (!G.S.mem.paid[b]) { const c = G.memCost(b);
            if (b === 0) { const take = Math.max(0, Math.min(G.S.gold * 0.3, c.gold - memBank.g)); G.S.gold -= take; memBank.g += take; if (memBank.g >= c.gold) { G.S.gold += memBank.g; memBank.g = 0; G.memPay(0); } }
            else { const take = Math.max(0, Math.min(G.S.gems - 300, c.gems - memBank.e)); G.S.gems -= take; memBank.e += take; if (memBank.e >= c.gems && (G.S.grudge || 0) >= c.grudge) { G.S.gems += memBank.e; memBank.e = 0; G.memPay(b); } } }
          const rdy = todo.find(b => G.S.mem.paid[b]);
          if (rdy != null && !G.raid && !G.bossActive && t >= memHold) { if (G.startMem(rdy)) memPend = [rdy, G.S.mem.p[rdy]]; }
        }
      }
      if (memPend && !G.raid) { if (G.S.mem.p[memPend[0]] === memPend[1]) { memHold = t + 600; first.MF = (first.MF || 0) + 1; } memPend = null; }   // 지면 10분 뒤에 다시
      if (G.S.mem.orbs > 0) for (let z = 0; z < 50; z++) if (!G.rebUp('atk')) break;   // 기억으로 얻은 윤회 구슬은 무력에(값이 모일 때까지 기다렸다가)
      // 초각성기 2 퀘스트 「두 번째 깨달음」(56장 뒤): 듣기 → 횟수 채우면 받기 → 스승과 다시 겨루기.
      // ②(레이드에서 되받기 30번)는 타임 보스·1일 보스·강림처럼 오래 가는 싸움에서 채우는데 시뮬은 그런 싸움을 안 하므로, 열린 지 opts.aw2h(기본 6)시간 뒤 채운 것으로 친다
      if (G.aw2Open() && !G.S.aw2.got) { const q = G.aw2Quest(); if (aw2T0 == null) aw2T0 = t;
        if (q) { if (q.i === 0) G.aw2Hear(); if (q.i === 1 && t - aw2T0 >= (opts.aw2h ?? 6) * 3600) G.S.aw2.c = Math.max(G.S.aw2.c, q.n);
          G.aw2Claim(); if (q.i === 4 && !G.raid && !G.bossActive && t >= aw2Hold) { if (G.aw2Trial()) aw2Hold = t + 1200; } } }
      G.S.gold -= elRes;
      { const fb = G.formBest(); if (fb && G.S.form.eq !== fb) G.S.form.eq = fb; }   // 변신: 가장 센 것을 착용(보스·레이드에서 자동으로 한 번)
      for (const sl of ['weapon', 'armor']) G.ascend(sl);   // 신화·태초 각성(되면 바로)
      { const keepG = ['weapon', 'armor'].reduce((a, sl) => { const N = G.ascNeed(sl); return a + (!N.max && N.world ? N.A.grudge : 0); }, 0);   // 결이야기: 각성에 쓸 원한 조각은 남기고 낮은 마디부터
        const so = G.SOULS.filter(x => G.S.soul.own[x.k] && G.soulBond(x.k) < 3).sort((a, b) => G.soulBond(a.k) - G.soulBond(b.k) || b.g - a.g);
        const memGr = G.memOpen() && !opts.nomem && G.S.mem.ch !== 'no' ? G.MEM.grudge[2] * (4 - G.S.mem.p[2]) : 0;   // 환생의 기억(천계 갈래)에 쓸 몫도 남긴다
        for (const x of so) { if (G.S.grudge - [10, 30, 60][G.soulBond(x.k)] < keepG + memGr || !G.bondUp(x.k)) break; } }
      for (let g = 0; g < 400; g++) {
        let best = null, bs = Infinity;
        for (const k of Object.keys(Wt)) { const b = G.buyInfo(k); if (!b.n) continue; const sc = b.cost * Wt[k]; if (sc < bs) { bs = sc; best = k; } }
        let bsk = null, sc2 = Infinity;
        G.SKILLS.forEach((sk, i) => { const lv = G.skLv(i); if (lv && G.skIn(i) && lv < G.skCap(i)) { const c = G.skillCost(sk, lv) * 2; if (c < sc2) { sc2 = c; bsk = sk.key; } } });   // 전투 칸에 낀 기술만, 최대 레벨까지
        if (bsk && sc2 < bs) { if (!G.upgradeSkill(bsk)) break; }
        else if (best) { if (!G.buyStat(best)) break; }
        else break;
      }
      G.S.gold += elRes;
      while (G.S.gems >= 450 + 400) {   // 재련·조합에 쓸 보석은 남겨 둔다
        if (G.S.rec.psum * 2 < G.S.rec.summons) { if (G.S.gems < 900) break; G.petSummon(10); }
        else G.summon(Math.random() < 0.5 ? 'weapon' : 'armor', 10);
      }
      for (let q = 0; q < 5; q++) G.claimTrial(q);
      if (jobPend && !G.raid) { if (G.S.job < jobPend[0]) { jobHold = t + 1200; first['JF' + jobPend[0]] = (first['JF' + jobPend[0]] || 0) + 1; } jobPend = null; }   // 전직 시험에 지면 20분 뒤에 다시
      if (!G.raid && t >= jobHold && (G.jobReady(1) || G.jobReady(2) || G.jobReady(3) || G.jobReady(4) || G.jobReady(5)) && G.startJobTrial(G.S.job + 1)) jobPend = [G.S.job + 1];
      if (G.crossReady()) G.doCross();   // 2부: 바다 건너 부상으로
      if (G.inhPending()) G.inhDo();     // (48) 새 땅에 오면 대장장이에게 바로 계승(지난 땅 재료 → 이 땅 재료, 부상·곤륜은 재련 계승)
      for (let z = 0; z < 5; z++) { const mb = G.SHOP.find(x => x.id === 'matbag'); if (mb.price() > G.S.gold * 0.05 || !G.buyShop('matbag')) break; }   // 재료 꾸러미(엽전의 5% 안쪽이면)
      if (G.S.gems >= 6000 && G.AVATARS.some(a => a.src === 'box' && !G.S.av.own[a.k])) G.openAvatarBox();   // 남는 보석으로 꾸미기 상자
      G.buyShop('gift');
      // 물약(2026-11 (43)): 체력·마나 자동 회복이 느려져 인삼 탕약·감로수를 사서 씀 — 100개 묶음이 엽전의 5%보다 싸면 묶음, 아니면 10개
      for (const [k, lo] of [['potion', 40], ['mana', 80]]) if ((G.S.inv[k] || 0) < lo){ const big = G.SHOP.find(x => x.id === k + '100'), sm = G.SHOP.find(x => x.id === k);
        if (big.price() < G.S.gold * 0.05) G.buyShop(k + '100'); else if (sm.price() < G.S.gold * 0.15) G.buyShop(k); }
      if (!opts.nocraft) for (const k of ['w', 'n', 'a']) {   // 조합 공방: 최적 각인으로, 노리개 보석은 지갑의 60%까지만
        if (!G.S.craft[k].e && !G.S.craft[k].e2) G.pickEngr(k, G.ENGR_BEST[cls][k]);
        const n = G.craftNeed(k);
        if (n.ok && (!n.gems || n.gems <= G.S.gems * 0.6)) G.craft(k);
        for (let z = 0; z < 2; z++) { const ec = G.engrLvCost(k), n2 = G.craftNeed(k);   // 각인 강화: 다음 조합에 쓸 재료는 남기고
          if (ec.gems > G.S.gems * 0.2 || (G.S.mat[ec.mk] || 0) < ec.mat + (n2.max ? 0 : n2.mat || 0) || !G.engrUp(k)) break; }
      }
      if (G.rebirthReady()) {
        G.doRebirth();
        for (const k of ['atk', 'hp', 'luck', 'spd', 'eye']) for (let z = 0; z < 50; z++) if (!G.rebUp(k)) break;
      }
      G.mergeAll('weapon'); G.mergeAll('armor'); G.equipBest('weapon'); G.equipBest('armor');
      { const keepG = Math.min(...['w', 'a'].map(k => { const n = G.craftNeed(k); return n.g != null ? n.g : 9; }));   // 조합에 쓸 등급은 남기고 갈아 쇳가루로
        for (const sl of ['weapon', 'armor']) G.grindGear(sl, Math.min(keepG, G.S.equip[sl] >= 0 ? Math.floor(G.S.equip[sl] / 4) : 0) - 1); }
      if (!G.raid && !G.bossActive) {
        // 실패하면 30분 동안은 그보다 낮은 레이드를 돌고, 첫 클리어 보상이 남은 레이드를 먼저 한다
        if (raidPend && G.S.rec.raids === raidPend[0]) raidHold = [raidPend[1], t + 1800];
        raidPend = null;
        let r = G.firstReadyRaid();
        if (r >= 0 && t < raidHold[1]) r = Math.min(r, raidHold[0] - 1);
        for (let j = r; j >= 0; j--) if (!G.S.raid.first[['', 'h', 'g', 'b', 'k', 'd', 'n', 'x'][G.S.world] + j]) { r = j; break; }
        if (r >= 0 && G.startRaid(r)) raidPend = [G.S.rec.raids, r];
      }
    }
    // 보스 다시 도전은 게임의 [보스 자동]에 맡긴다(예전엔 여기서 60초마다 억지로 도전시켰음 — 물의 신화: 도전 기운이 다 찬 뒤엔 간격이 벌어짐)
    mark(G.S.world + ':' + G.S.stage, t); mark('L' + G.S.world + ':' + G.S.level, t); if (G.S.job) mark('J' + G.S.job, t); for (const k of ['w', 'a', 'n']) if (G.S.craft[k].t) mark('C' + k + G.S.craft[k].t, t); if (G.S.quest.hid) mark('H' + G.S.quest.hid, t);
    for (let q = 0; q <= G.S.quest.main; q++) mark('Q' + q, t);
    if (G.S.aw2.q) mark('A' + G.S.aw2.q, t); { const mn = G.S.mem.p[0] + G.S.mem.p[1] + G.S.mem.p[2]; if (mn) mark('M' + mn, t); }
    if (opts.snaps && G.S.world === 3 && !('cross' in snaps)) snaps.cross = JSON.stringify(G.S);
    if (opts.snapQ && !('q' in snaps) && G.S.quest.main >= opts.snapQ && !G.raid) snaps.q = JSON.stringify(G.S);   // 이야기 n번째에 닿은 저장(다음 부 시뮬 출발점)
    if (opts.snaps) { const mm = Math.round(t / 60); if (opts.snaps.includes(mm) && !(mm in snaps) && !G.raid) snaps[mm] = JSON.stringify(G.S); }
    if (marks.has(i)) log.push(`${cls} ${Math.round(t / 60)}분: ${G.WORLD_NAME[G.S.world]} ${G.S.stage}단계, Lv ${G.S.level}, 전직 ${G.S.job}, 환생 ${G.S.reb.n}, 이야기 ${G.S.quest.main}/${G.MAIN_Q.length}, 히든 ${G.S.quest.hid}, 레이드 ${G.S.rec.raids}회, `
      + `재련 +${G.S.refine.weapon.lv}/+${G.S.refine.armor.lv}, 펫 Lv ${G.PET_TYPE_ORDER.map(pt => { const pi = G.eqPet(pt); return pi < 0 ? '-' : G.S.pets.lv[pi]; }).join('/')}, `
      + `번 엽전 ${G.fmt(goldIn)}·보석 ${G.fmt(gemIn)}`
      + (G.seaOpen() ? `, 새 칸 ${G.NEW_SLOTS.map(k => `${G.S.equip[k]}(+${G.S.refine[k].lv})`).join('/')}, 호박석 빛 ${Object.values(G.ambSum().L).reduce((a, b) => a + b, 0)}, 바다 몫 공×${G.seaSum().atk.toFixed(2)}·체×${G.seaSum().hp.toFixed(2)}·받는 피해×${G.seaSum().def.toFixed(2)}` : ''));
  }
  return {log, first, snaps, raids};
}
"""

# --long: 이정표(처음 닿은 시각) 표
LONG_S0 = [31, 51, 61, 71, 81, 86, 91, 94, 97, 101]
LONG_S1 = [11, 31, 51, 71, 81, 91, 97]
LONG_S2 = [11, 16, 31, 46, 61, 76, 86, 91]
LONG_S3 = [11, 25, 37, 49, 61, 70, 75]
LONG_S4 = [13, 25, 37, 49, 61, 73, 80]
LONG_L = [('L0', 50), ('L0', 100), ('L1', 100), ('L1', 200), ('L2', 100), ('L2', 200), ('L2', 240), ('L3', 320), ('L3', 350), ('L3', 370), ('L3', 400), ('L4', 430), ('L4', 460), ('L4', 500)]
LONG_Q = [17, 42, 43, 60, 86, 87, 100, 110, 112, 113, 115, 125, 135, 141, 145, 160, 175, 182]


def long_table(cls, first):
    h = lambda m: '-' if m is None else (f'{m / 60:.1f}h' if m >= 60 else f'{m}m')
    print(f'[{cls}] 이승 ' + ' '.join(f'{x}:{h(first.get(f"0:{x}"))}' for x in LONG_S0))
    print(f'        저승 ' + ' '.join(f'{x}:{h(first.get(f"1:{x}"))}' for x in LONG_S1))
    print(f'        천계 ' + ' '.join(f'{x}:{h(first.get(f"2:{x}"))}' for x in LONG_S2))
    print(f'        부상 ' + ' '.join(f'{x}:{h(first.get(f"3:{x}"))}' for x in LONG_S3))
    print(f'        곤륜 ' + ' '.join(f'{x}:{h(first.get(f"4:{x}"))}' for x in LONG_S4))
    print(f'        전직 1차:{h(first.get("J1"))} 2차:{h(first.get("J2"))} 3차:{h(first.get("J3"))} 4차:{h(first.get("J4"))} · 히든 시작:{h(first.get("H1"))}')
    print('        레벨 ' + ' '.join(f'{ {"L0": "이승", "L1": "저승", "L2": "천계", "L3": "부상", "L4": "곤륜"}[k]}{v}:{h(first.get(f"{k}:{v}"))}' for k, v in LONG_L))
    print('        이야기 ' + ' '.join(f'{q}:{h(first.get(f"Q{q}"))}' for q in LONG_Q))


# claude.ai 아티팩트의 계정 저장소(window.claude db)를 흉내 낸다. 문서는 window.__store 에 쌓인다.
MOCK_CLAUDE = r"""
(() => {
  const seed = %s;
  window.__store = seed || {};
  const db = {doc(path){ return {
    async get(){ const v = window.__store[path]; return {exists: v !== undefined, data: () => JSON.parse(JSON.stringify(v))}; },
    async set(v){ window.__store[path] = JSON.parse(JSON.stringify(v)); },
    async delete(){ delete window.__store[path]; },
  }; }};
  const user = {async id(){ return 'u_test'; }};
  window.__emitted = []; window.__roomH = [];
  const room = {
    on(topic, fn){ window.__roomH.push([topic, fn]); return () => {}; },
    onPeers(fn){ setTimeout(() => fn({peers:[{}, {}], joined:[], left:[], updated:[]}), 0); return () => {}; },
    async emit(topic, data){ window.__emitted.push([topic, data]); },
    peers(){ return []; },
  };
  window.claude = {use: async name => name === 'db' ? db : name === 'user' ? user : name === 'room' ? room : null};
})();
"""


class QuietHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.webmanifest': 'application/manifest+json', '.js': 'text/javascript'}

    def log_message(self, *args):
        pass


def serve():
    """저장소 폴더를 내 컴퓨터 웹서버(127.0.0.1)로 띄운다. 앱 설치·오프라인 점검용"""
    srv = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{srv.server_address[1]}/'


async def launch(p):
    try:
        return await p.chromium.launch(args=['--no-sandbox'])
    except Exception:
        for path in ('/opt/pw-browsers/chromium', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'):
            if os.path.exists(path):
                return await p.chromium.launch(executable_path=path, args=['--no-sandbox'])
        raise


def watch(page, errors, tag=''):
    page.on('pageerror', lambda e: errors.append(f'{tag}pageerror: {e}'))
    page.on('console', lambda m: errors.append(f'{tag}{m.type}: {m.text}') if m.type in ('error', 'warning') else None)


async def tab(page, key):
    # 퀘스트·상점·정보·가방은 [더보기] 판 안에 있다(2026-11 (41))
    if key in ('quest', 'shop', 'rec', 'bag'):
        if await page.is_hidden('#moreMenu'):
            await page.click('#tab-more')
    await page.click('#tab-' + key)


async def fresh(page):
    await page.goto(URL)
    await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); Storage.prototype.setItem = function(){}; }")
    await page.goto(URL)
    await page.wait_for_timeout(800)


async def signup(page, uid, pw, name, cls='musa', outfit=None, hat=None):
    await page.click('#lg-tab-signup')
    await page.fill('#lg-id', uid)
    await page.fill('#lg-pw', pw)
    await page.fill('#lg-pw2', pw)
    await page.click('#modal-btn-0')
    await page.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
    await create_char(page, name, cls, outfit, hat)


async def create_char(page, name, cls='musa', outfit=None, hat=None, shot=None):
    await page.click('#modal-btn-0')      # 새 캐릭터
    await page.wait_for_selector('#cc-name')
    await page.fill('#cc-name', name)
    await page.click(f'#cc-{cls}')
    if outfit is not None:
        await page.click(f'.lookwrap [data-k="outfit"][data-v="{outfit}"]')
    if hat is not None:
        await page.click(f'.lookwrap [data-k="hat"][data-v="{hat}"]')
    if shot:
        await page.screenshot(path=str(OUT / shot))
    await page.click('#modal-btn-1')      # 만들기
    await page.wait_for_function('() => window.__game.session && document.querySelector("#modal").hidden')
    await skip_cut(page)


async def skip_cut(page, wait=700):
    '''연출(프롤로그·이야기)이 나오면 건너뛴다'''
    await page.wait_for_timeout(wait)
    if await page.is_visible('#cut'):
        await page.click('#cutSkip')


async def run_long():
    """--long 시간 [직업…] ['{CURVE JSON}']: 직업마다 따로 띄워 함께 돌린다(0.2초 간격)."""
    k = sys.argv.index('--long')
    hours = float(sys.argv[k + 1])
    rest = sys.argv[k + 2:]
    classes = [a for a in rest if not a.startswith('{')] or ['musa', 'jagaek', 'sulsa', 'doin']
    curve = next((json.loads(a) for a in rest if a.startswith('{')), None)
    marks = [m for m in (60, 240, 720, 1440, 2880, 4320, 5760, 7200, 8640, 10080, 11520, 12960, 14400, 15840) if m <= hours * 60]
    async with async_playwright() as p:
        browser = await launch(p)

        async def one(c):
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await fresh(page)
            r = await page.evaluate(SIM, [hours * 60, c, {'dt': 0.2, 'marks': marks, 'curve': curve}])
            await ctx.close()
            return c, r
        for c, r in await asyncio.gather(*[one(c) for c in classes]):
            print('\n'.join(r['log']))
            long_table(c, r['first'])
        await browser.close()


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    errors, checks = [], []

    def check(ok, msg):
        checks.append(('통과' if ok else '실패') + ' · ' + msg)
        if not ok:
            errors.append('check: ' + msg)

    async with async_playwright() as p:
        browser = await launch(p)
        ctx = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        page = await ctx.new_page()
        watch(page, errors)
        await page.goto(URL)
        await page.wait_for_timeout(1200)

        # 1) 타이틀·로그인·계정 만들기
        await page.screenshot(path=str(OUT / '1_로그인.png'))
        check(await page.is_visible('#title'), '로그인 전에는 타이틀 화면이 보인다')
        tsc = await page.evaluate("() => ['.t-scene', '.t-sea', '.t-refl', '.t-spout', '.t-rocks', '.t-moon', '#tEmb'].map(q => { const e = document.querySelector('#title ' + q), r = e && e.getBoundingClientRect(); return !!r && r.width > 4 && r.height > 4; }).concat([document.querySelectorAll('#tHeroes img').length >= 4])")
        check(all(tsc), f'첫 화면: 달밤의 동해(바다·달 그림자·용오름·대왕암)와 삼족오 문양, 직업 용사들이 그려진다 {tsc}')
        await page.click('#lg-tab-signup')
        await page.fill('#lg-id', 'tester')
        await page.fill('#lg-pw', '1234')
        await page.fill('#lg-pw2', '9999')
        await page.click('#modal-btn-0')
        check('달라요' in await page.inner_text('#lg-err'), '비밀번호 확인이 다르면 막는다')
        await page.fill('#lg-pw2', '1234')
        await page.click('#modal-btn-0')
        await page.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
        slots = await page.evaluate("() => ({empty: document.querySelectorAll('#mBody .char.empty').length, max: window.__game.MAX_CHARS, txt: document.querySelector('#mBody').textContent})")
        check(slots['empty'] == 6 and slots['max'] == 6 and '6명까지' in slots['txt'], f'캐릭터 고르기: 한 계정 6칸(빈 칸 여섯)이 보인다 {slots["empty"]} {slots["max"]}')
        await page.screenshot(path=str(OUT / '1b_캐릭터6칸.png'))
        await page.click('#mBody .char.empty')      # 빈 칸을 눌러도 새 캐릭터 만들기
        await page.wait_for_selector('#cc-name')
        await page.fill('#cc-name', '홍길동'); await page.click('#cc-musa')
        await page.click('.lookwrap [data-k="outfit"][data-v="5"]'); await page.click('.lookwrap [data-k="hat"][data-v="3"]')
        await page.screenshot(path=str(OUT / '2_캐릭터만들기.png'))
        await page.click('#modal-btn-1')
        await page.wait_for_function('() => window.__game.session && document.querySelector("#modal").hidden')
        await page.wait_for_timeout(2500)
        check(await page.evaluate('() => !!window.__game.cut') and not await page.is_visible('#title'), '새 캐릭터는 프롤로그 연출로 시작하고 타이틀이 사라진다')
        await page.screenshot(path=str(OUT / '2b_프롤로그.png'))
        await page.click('#cutSkip')
        aud = await page.evaluate('() => { document.body.dispatchEvent(new PointerEvent("pointerdown", {bubbles: true})); return new Promise(r => setTimeout(() => { const A = window.__game.aud; r({ctx: !!A.ctx, track: A.track}); }, 800)); }')
        check(aud['ctx'] and aud['track'] in ('field', 'title'), f'화면을 누르면 배경음악이 켜진다 {aud}')
        await page.wait_for_timeout(4000)
        await page.screenshot(path=str(OUT / '3_플레이_튜토리얼.png'))
        check(await page.is_visible('#guide'), '새 캐릭터는 길잡이(튜토리얼)가 보인다')
        check(await page.inner_text('#nick') == '홍길동', '상단에 캐릭터 이름이 보인다')
        reg = await page.evaluate("() => JSON.parse(localStorage.getItem('samhan-accounts-v1'))")
        check('1234' not in json.dumps(reg), '비밀번호가 그대로 저장되지 않는다')

        # 2) 튜토리얼 따라가기: 공격력 올리기 → 무기 소환 → 펫 소환
        await page.wait_for_function('() => window.__game.S.quest.tut >= 1', timeout=20000)
        await page.click('#tab-grow'); await page.click('#buy-atk')
        await page.click('#tab-gear'); await page.click('#sum1'); await page.click('#modal-btn-1')
        await page.click('#tab-pet'); await page.click('#psum1')
        await page.wait_for_timeout(600)
        await page.screenshot(path=str(OUT / '4_펫소환.png'))
        await page.click('#modal-btn-1')
        check(await page.evaluate('() => window.__game.S.quest.tut') >= 4, '튜토리얼이 단계마다 넘어간다')

        # 3) 성장시켜서 펫·재련·퀘스트·레이드 화면 보기
        await page.evaluate("""() => { const G = window.__game; G.S.gold = 1e7; G.S.gems = 5000; G.S.dust = 5000; G.S.level = 32; G.S.up.atk = 60; G.S.up.hp = 60;
          G.S.maxStage = 25; G.setClass('musa'); G.petSummon(10); G.buildTab('pet'); }""")
        await page.click('.pcell:not(.unseen)')
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(OUT / '5_펫.png'), full_page=True)
        await page.click('#tab-gear'); await page.click('#seg-refine')
        for _ in range(6):
            await page.click('#rf-weapon [data-r=btn]')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '6_재련.png'))
        check(await page.evaluate('() => window.__game.S.refine.weapon.lv') >= 3, '재련 +1~+3은 반드시 성공한다')
        await tab(page, 'quest')
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(OUT / '7_퀘스트.png'))
        await page.click('#mainClaim')
        check(await page.evaluate('() => window.__game.S.quest.main') >= 1, '이야기 퀘스트 보상을 받을 수 있다')
        await page.wait_for_timeout(1800)
        check(await page.evaluate('() => !!window.__game.cut'), '이야기 퀘스트를 깨면 연출이 나온다')
        await (await page.query_selector('#scene')).screenshot(path=str(OUT / '7b_이야기연출.png'))
        await page.click('#cutSkip')

        # 4) 레이드: 화면 캡처 후 끝까지 자동 진행
        await page.evaluate("() => { window.__game.gateOff = true; window.__game.noFork = true; }")   # 이 뒤 점검은 이야기를 건너뛰고 세계를 옮겨 다닌다(이야기·레벨 문은 6-8e에서 따로 본다)
        await page.click('#tab-raid')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '8_레이드목록.png'))
        await page.click('#raid-0 .btn')   # 이야기 1장이라 이승 첫 레이드만 열려 있다(이야기 문)
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '9_레이드파티.png'))
        await page.click('#modal-btn-1')
        await page.wait_for_timeout(3000)
        await page.screenshot(path=str(OUT / '10_레이드전투.png'))
        el = await page.query_selector('#scene')
        await el.screenshot(path=str(OUT / '10_레이드전투_장면.png'))
        await page.evaluate("() => { const G = window.__game; for (let i = 0; i < 2400 && G.raid; i++) G.update(0.05); }")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(OUT / '11_레이드결과.png'))
        st = await page.evaluate('() => ({raids: window.__game.S.rec.raids, raid: !!window.__game.raid, tk: window.__game.S.raid.tk})')
        check(st['raids'] == 1 and not st['raid'] and st['tk'] == 2, f'레이드를 깨면 보상을 받고 토벌패 1개를 쓴다 {st}')
        await page.click('#modal-btn-0')
        await tab(page, 'rec')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '12_정보.png'), full_page=True)
        # 아래 메뉴 [더보기]·내 정보·? 말풍선(2026-11 (41))
        await page.evaluate("() => window.__game.closePage()")
        await page.click('#tab-more'); await page.wait_for_timeout(250)
        mv = await page.is_visible('#moreMenu')
        await page.screenshot(path=str(OUT / '36_더보기.png'))
        await page.click('#meBtn'); await page.wait_for_timeout(400)
        me = await page.evaluate("() => ({t: document.querySelector('#pageTitle').textContent, n: document.querySelectorAll('#meBox .ms').length, more: document.querySelector('#moreMenu').hidden})")
        await page.screenshot(path=str(OUT / '37_내정보.png'))
        await page.evaluate("() => window.__game.closePage()")
        await page.click('.hud'); await page.wait_for_timeout(300)
        me2 = await page.evaluate("() => document.querySelector('#pageTitle').textContent")
        await page.evaluate("() => window.__game.buildTab('skill')"); await page.wait_for_timeout(300)
        qn = await page.evaluate("() => document.querySelectorAll('#panel .qmark').length")
        await page.click('#panel .qmark'); await page.wait_for_timeout(250)
        tip = await page.evaluate("() => { const b = document.querySelector('#tipB'); return b ? b.textContent.length : 0; }")
        await page.screenshot(path=str(OUT / '38_설명말풍선.png'))
        await page.mouse.click(5, 300); await page.wait_for_timeout(150)
        tip2 = await page.evaluate("() => !!document.querySelector('#tipB')")
        await page.evaluate("() => window.__game.closePage()")
        check(mv and me['t'] == '내 정보' and me['n'] >= 20 and me['more'] and me2 == '내 정보', f'[더보기] 판·내 정보(왼쪽 위 상태창을 눌러도 열림) {me} {me2}')
        check(qn >= 1 and tip > 20 and not tip2, f'긴 설명은 ?를 누르면 말풍선으로, 다른 곳을 누르면 닫힘 (?{qn}개, 글자 {tip})')

        await page.evaluate('() => window.__game.showNotes()')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '22_업데이트소식.png'))
        await page.click('#modal-btn-0')

        # 4-2) 상점·물약·부적
        await tab(page, 'shop')
        inv0 = await page.evaluate('() => Object.assign({}, window.__game.S.inv)')
        await page.click('.shop-cats [data-c="pack"]')
        await page.click('#shb-gift')
        await page.click('.shop-cats [data-c="potion"]')
        await page.click('#shb-potion')
        await page.click('#shb-mana')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '16_상점.png'))
        inv = await page.evaluate('() => window.__game.S.inv')
        check(inv['potion'] == inv0['potion'] + 15 and inv['mana'] == inv0['mana'] + 15, f'오늘의 선물·인삼 탕약 10개·감로수 10개를 산다 {inv0} → {inv}')
        await page.click('.shop-cats [data-c="charm"]')
        await page.click('#shb-b_atk')
        st = await page.evaluate('() => ({buff: window.__game.S.buff.atk})')
        check(st['buff'] > 590, f'범 부적을 사면 10분 동안 공격력이 오른다 {st}')
        drank = await page.evaluate('''() => { const G = window.__game; const n = G.S.inv.potion; G.hero.hp = G.ST.maxHp * 0.1; G.update(0.05);
          return {before: n, after: G.S.inv.potion, hp: G.hero.hp / G.ST.maxHp}; }''')
        check(drank['after'] == drank['before'] - 1 and drank['hp'] > 0.4, f'체력이 낮으면 탕약을 저절로 마신다 {drank}')
        mauto = await page.evaluate('''() => { const G = window.__game; G.S.inv.mana = 5; G.S.kills = G.FIELD.kills; G.startBoss(); G.hero.mp = 10; for (let i = 0; i < 3; i++) G.update(0.05);
          const r = {left: G.S.inv.mana, mp: Math.round(G.hero.mp)}; if (G.bossRef){ G.bossRef.hp = 0.0001; for (let i = 0; i < 40 && G.bossActive; i++) G.update(0.05); } for (let i = 0; i < 100; i++) G.update(0.05); return r; }''')   # 감로수 재사용 대기(4초)를 지나 보냄
        check(mauto['left'] == 4 and mauto['mp'] >= 45, f'싸우는 중 마나가 30 아래면 감로수를 저절로 마신다 {mauto}')
        await page.click('#pageClose')
        mp = await page.evaluate('''() => { const G = window.__game; G.hero.mp = 10; const n = G.S.inv.mana; document.querySelector('#pot-mana').click();
          return {before: n, after: G.S.inv.mana, mp: G.hero.mp, shown: document.querySelector('#pot-mana b').textContent, vis: !!document.querySelector('#potBar').offsetParent}; }''')
        check(mp['after'] == mp['before'] - 1 and mp['mp'] >= 50 and mp['vis'], f'기술 줄 위 물약 칸(감로수)을 누르면 마나를 채운다 {mp}')
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(OUT / '17_부적표시.png'))

        # 4-3) 퀘스트 행운: 기술 초기화·신화 보물
        res = await page.evaluate('''() => { const G = window.__game; for (const k in G.skillCd) G.skillCd[k] = 9; const atk0 = G.ST.atk;
          G.luck = 0; G.questLuck(80); G.luck = null;
          return {cd: Object.values(G.skillCd), sword: G.S.myth, atkUp: G.ST.atk >= atk0}; }''')
        check(max(res['cd']) == 0, f'퀘스트 행운으로 기술 재사용이 초기화된다 {res["cd"]}')
        check(sum(res['sword'].values()) > 0 and res['atkUp'], f'퀘스트 행운으로 신화 보물이 나온다 {res["sword"]}')
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(OUT / '18_신화획득.png'))
        await page.click('#modal-btn-0')
        weak = await page.evaluate("() => { const G = window.__game; const r1 = G.dropMyth(150, 'mirror'); const r2 = G.dropMyth(20, 'mirror'); return [r1.p, r2.p, r2.up, G.S.myth.mirror]; }")
        check(weak[0] > weak[1] and not weak[2] and weak[3] == weak[0], f'어려운 퀘스트의 신화 보물이 더 세고, 약한 것은 보석으로 바뀐다 {weak}')
        await page.click('#modal-btn-0')
        await page.click('#tab-gear'); await page.click('#seg-myth')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '19_신화.png'))

        # 4-4) 채팅
        await page.evaluate("() => window.__game.closePage()")
        await page.click('#chatBtn')
        await page.fill('#chatInput', '안녕하세요 ㅎㅎ')
        await page.press('#chatInput', 'Enter')
        await page.wait_for_timeout(3500)
        msgs = await page.evaluate('() => window.__game.chatMsgs.map(m => m.kind + ":" + m.text)')
        check(any(m.startswith('me:안녕하세요') for m in msgs) and any(m.startswith('npc:') for m in msgs), f'채팅을 보내면 주민이 대꾸한다 {msgs[-3:]}')
        await page.fill('#chatInput', '이 병신아')
        await page.press('#chatInput', 'Enter')
        await page.wait_for_timeout(1300)
        bad = await page.evaluate('() => window.__game.chatMsgs.filter(m => m.kind === "me").map(m => m.text)')
        check(not any('병신' in m for m in bad), f'나쁜 말은 가려진다 {bad[-1:]}')
        await page.screenshot(path=str(OUT / '20_채팅.png'))
        await page.click('#chatClose')

        # 4-4b) 확성기: 용사(나·다른 용사)가 한 말은 게임 화면 위 띠로, 주민·알림은 채팅창에만, 글자로만, 끄면 안 뜸
        mg = await page.evaluate("""async () => { const G = window.__game, el = document.querySelector('#mega'), tx = document.querySelector('#megaTx'), who = document.querySelector('#megaWho'), wait = ms => new Promise(r => setTimeout(r, ms));
          const o = {on0:G.megaOn};
          G.setMega(false); G.setMega(true);   // 앞에서 뜬 것·줄 선 것을 비움
          const s0 = G.megaSeen;
          G.addChat('npc', '주모 덕이', '주민 말'); G.addChat('sys', '알림', '알림 글'); await wait(350);
          o.npc = G.megaSeen - s0 + G.megaQ.length; o.hid0 = el.hidden;
          G.addChat('player', '바람돌이', '<i>기울임</i> 같이 레이드 가요');
          o.p = {hidden:el.hidden, who:who.textContent, tx:tx.textContent, kids:tx.children.length, cls:el.className, pe:getComputedStyle(el).pointerEvents};
          const r = el.getBoundingClientRect(), sc = document.querySelector('#scene').getBoundingClientRect(); o.box = [Math.round(r.left - sc.left), Math.round(r.top - sc.top), Math.round(r.width), Math.round(sc.width)];
          await wait(1300); G.sendChat('확성기 시험'); o.q = G.megaQ.length;
          return o; }""")
        await page.wait_for_timeout(450)
        await page.screenshot(path=str(OUT / '20b_확성기.png'))
        mg2 = await page.evaluate("""async () => { const G = window.__game, el = document.querySelector('#mega'), tx = document.querySelector('#megaTx'), who = document.querySelector('#megaWho'), wait = ms => new Promise(r => setTimeout(r, ms));
          G.megaCur.end = 0; G.megaTick(); await wait(700);   // 앞의 것이 끝나면 줄 선 내 말이 뜬다
          const o = {me:{hidden:el.hidden, who:who.textContent, tx:tx.textContent, cls:el.className, name:G.S.name}};
          G.setMega(false); G.addChat('player', '바람돌이', '꺼진 뒤'); await wait(300);
          o.off = {hidden:el.hidden, q:G.megaQ.length, key:localStorage.getItem('samhan-mega')};
          G.setMega(true); o.key = localStorage.getItem('samhan-mega');
          return o; }""")
        check(mg['on0'] and mg['npc'] == 0 and mg['hid0'], f'주민 수다·알림은 확성기로 뜨지 않는다 {mg}')
        check(not mg['p']['hidden'] and mg['p']['who'] == '바람돌이' and '<i>' in mg['p']['tx'] and mg['p']['kids'] == 0 and 'mg-pl' in mg['p']['cls'] and mg['p']['pe'] == 'none'
              and mg['box'][2] > 60 and abs(mg['box'][0] + mg['box'][2] / 2 - mg['box'][3] / 2) < 30 and 20 < mg['box'][1] < 200, f'다른 용사가 한 말이 화면 위 가운데 띠(확성기)로 뜨고 글자로만 보인다 {mg}')
        check(mg['q'] == 1 and not mg2['me']['hidden'] and mg2['me']['who'] == mg2['me']['name'] and mg2['me']['tx'] == '확성기 시험' and 'mg-me' in mg2['me']['cls'], f'내 말도 차례를 기다렸다가 확성기로 뜬다 {mg["q"]} {mg2["me"]}')
        check(mg2['off']['hidden'] and mg2['off']['q'] == 0 and mg2['off']['key'] == '0' and mg2['key'] == '1', f'확성기를 끄면 뜨지 않는다 {mg2["off"]}')

        # 5) 다시 열면 늘 로그인 창부터(아이디는 기억, 비밀번호만) → 틀린/맞는 비밀번호 → 같은 캐릭터로 이어 하기 → 로그아웃
        await page.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
        await page.goto(URL)
        await page.wait_for_selector('#lg-id'); await page.wait_for_timeout(500)
        lg = await page.evaluate("() => ({session: !!window.__game.session, id: document.querySelector('#lg-id').value, pw: document.querySelector('#lg-pw').value, title: document.querySelector('#mTitle').textContent, txt: document.querySelector('#mBody').textContent, tok: Object.keys(localStorage).concat(Object.keys(sessionStorage)).filter(k => k.includes('online'))})")
        await page.screenshot(path=str(OUT / '12_다시열면_로그인.png'))
        check(not lg['session'] and lg['id'] == 'tester' and lg['pw'] == '' and lg['title'] == '로그인' and '아이디를 기억' in lg['txt'] and lg['tok'] == [],
              f'다시 열면 늘 로그인 창부터: 아이디는 채워져 있고 비밀번호만 치면 된다(저장된 로그인 표로 바로 들어가지 않음) {lg["session"]} {lg["id"]} {lg["title"]} {lg["tok"]}')
        await page.fill('#lg-pw', '0000'); await page.click('#modal-btn-0')
        await page.wait_for_timeout(600)
        check('맞지 않아요' in await page.inner_text('#lg-err'), '틀린 비밀번호는 막는다')
        await page.fill('#lg-pw', '1234'); await page.click('#modal-btn-0')
        await page.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
        await page.click('#modal-btn-1')      # 시작하기(마지막에 하던 캐릭터가 골라져 있다)
        await page.wait_for_function('() => window.__game.session', timeout=8000)
        await page.evaluate("() => { window.__game.gateOff = true; window.__game.noFork = true; }")
        check(await page.evaluate('() => window.__game.S.name') == '홍길동', '다시 로그인하면 같은 캐릭터로 이어진다')
        check(await page.evaluate('() => window.__game.S.refine.weapon.lv') >= 3, '재련 결과가 저장된다')
        if not await page.is_hidden('#modal'): await page.evaluate('() => window.__game.hideModal()')
        await tab(page, 'rec'); await page.click('#outBtn'); await page.click('#modal-btn-1')
        await page.wait_for_selector('#lg-id')
        check(await page.input_value('#lg-id') == '', '로그아웃하면 기억해 둔 아이디도 지운다')
        await page.fill('#lg-id', 'tester'); await page.fill('#lg-pw', '1234'); await page.click('#modal-btn-0')
        await page.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
        await page.screenshot(path=str(OUT / '13_캐릭터고르기.png'))
        # 두 번째 캐릭터는 레이드 파티에 동료로 들어온다
        await create_char(page, 'Yuna', 'sulsa', outfit=2, hat=6)
        await page.evaluate("() => { window.__game.S.level = 20; }")
        await page.click('#tab-raid'); await page.click('#raid-0 .btn')
        plist = await page.inner_text('#mBody')
        check('홍길동' in plist and '내 캐릭터' in plist, '같은 기기의 다른 캐릭터가 레이드 파티에 들어온다')
        await page.click('#modal-btn-0')

        # 6) 지역별 장면
        await page.evaluate("() => { const G = window.__game; G.quiet = true; }")
        for i, st in enumerate([11, 21, 31, 41, 51]):
            await page.evaluate(
                f"() => {{ const G = window.__game; G.S.level = {st}; G.S.up.atk = {st} * 2; G.S.up.hp = {st} * 2;"
                f" G.setStage({st}); G.setClass(['musa','jagaek','doin','sulsa','jagaek'][{i}]); }}")
            await page.wait_for_timeout(2500)
            el = await page.query_selector('#scene')
            await el.screenshot(path=str(OUT / f'14_지역{i + 2}.png'))

        # 6-2) 환생 → 저승: 조건 맞추고 환생, 저승 지역·시왕 레이드·초각성·타임 보스
        await page.evaluate("() => { const G = window.__game; G.setWorld(0); G.S.level = 100; G.S.refine.weapon.lv = 25; G.S.quest.trials = [true, true, true, true, true]; G.S.gear.weapon.count[16] = 2; G.S.gear.weapon.seen[16] = true; G.equipBest('weapon'); G.buildTab('grow'); }")
        await page.click('#gv-reb'); await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '16_환생.png'), full_page=True)
        await page.click('#rebBtn'); await page.click('#modal-btn-1')
        await page.wait_for_timeout(600)
        rb = await page.evaluate('() => ({w: window.__game.S.world, lv: window.__game.S.level, pts: window.__game.S.reb.pts, eq: window.__game.S.equip.weapon, hell: document.body.classList.contains("hell")})')
        check(rb['w'] == 1 and rb['lv'] == 1 and rb['pts'] > 0 and rb['eq'] >= 16 and rb['hell'], f'환생하면 저승 Lv.1로 다시 시작하고 장비는 남는다 {rb}')
        await skip_cut(page, 300)
        await page.evaluate("() => { const G = window.__game; G.quiet = true; G.S.up.atk = 400; G.S.up.hp = 400; G.refreshStats(); }")
        for i, st in enumerate([1, 21, 41]):
            await page.evaluate(f"() => window.__game.setStage({st})")
            await page.wait_for_timeout(1500)
            await (await page.query_selector('#scene')).screenshot(path=str(OUT / f'17_저승{i + 1}.png'))
        hr = await page.evaluate("""() => { const G = window.__game; G.S.level = 60; G.S.awaken = true; G.S.raid.tk = 3; const ok = G.startRaid(0);
          const B = G.raid.boss; B.hp = B.maxHp = Math.max(B.hp, G.ST.atk * G.ST.aspd * 30);   // 너무 빨리 끝나지 않게(초각성은 12초 뒤에 쓴다)
          let cast = false; for (let i = 0; i < 2400 && G.raid; i++){ G.update(0.05); if (G.raid && G.raid.awk && G.raid.awk.used) cast = true; } return {ok, cast, h0: !!G.S.raid.first.h0}; }""")
        check(hr['ok'] and hr['cast'] and hr['h0'], f'저승 시왕 레이드에서 초각성기를 쓰고 토벌한다 {hr}')
        tb = await page.evaluate("""() => { const G = window.__game;
          G.REG.accounts.friend1 = {salt: 'x', hash: 'p:x', t: 1, chars: [{cid: 'cf', name: '벗님', cls: 'doin', level: 50, maxStage: 50, look: {}, armorG: 3, weaponG: 3, ally: {dps: G.ST.atk * 3, maxHp: G.ST.maxHp}}]};
          const w = G.tbWindow(); if (!w.open) G.addTime(w.next - Date.now() + 60000);
          const g0 = G.S.gold, why = G.tbCan('normal'), ok = G.startTimeBoss('normal');
          for (let i = 0; i < 100 && G.raid; i++) G.update(0.05);
          if (G.raid){ G.raid.info.fit = null; G.raid.boss.hp = 1; }   // 이제 보스는 손을 잘 써야 쓰러지므로(체력을 늘 다시 맞춤), 보상 확인은 맞추기를 끄고 끝낸다
          for (let i = 0; i < 3000 && G.raid; i++) G.update(0.05);
          const res = {why, ok, gold: G.S.gold > g0, done: G.S.tb.normal === G.tbWindow().id};
          delete G.REG.accounts.friend1; return res; }""")
        check(tb['ok'] and tb['gold'] and tb['done'], f'타임 보스: 2명 이상이면 도전하고 엽전을 받는다 {tb}')
        tb2 = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          const A = G.REG.accounts[G.session.acc], c0 = A.chars.slice(); S.rec.rdpsK = 10; delete S.rec.fitK;
          const oc = ['sulsa', 'jagaek'].find(c => c !== S.cls);
          for (let i = 0; i < 3; i++) A.chars.push({cid:'tb' + i, name:'내캐' + i, cls:oc, level:50, look:{}, armorG:2, weaponG:2, ally:{dps:G.dpsOf(G.ST), maxHp:G.ST.maxHp * (i + 1), rd:G.realDps() * (i + 1)}});
          G.REG.accounts.friend2 = {salt:'x', hash:'p:x', t:1, chars:[{cid:'f2', name:'벗님2', cls:'doin', level:50, look:{}, armorG:3, weaponG:3, ally:{dps:G.dpsOf(G.ST), maxHp:G.ST.maxHp}}]};
          const w = G.tbWindow(); if (!w.open) G.addTime(w.next - Date.now() + 60000); S.tb = {};
          const names = G.tbOthers().map(o => o.name), ok = G.startTimeBoss('normal'), R = G.raid, B = R.boss;
          const partyRd = G.realDps() * (G.TB_SELF_K + 6 + 0.8);   // 나(내 몫 TB_SELF_K) + 내캐(1+2+3배) + 벗님(예전 요약이라 기본 피해 × 8 = 실제(×10)의 0.8). 처음 체력은 어림 × 목표 시간(싸우며 맞춤)
          const hpK = +(B.maxHp / partyRd).toFixed(1);
          const a2 = R.allies.find(a => a.name === '내캐2');
          const pctMe = B.tbPct.hit, dmgMe = G.ST.maxHp * pctMe, dmgA2 = a2.maxHp * pctMe;
          let rise = 0, last = 1; for (let i = 0; i < 3000 && G.raid; i++){ G.update(0.05); const f = B.hp / B.maxHp; if (f > last + 1e-6) rise++; last = f; }   // 체력 막대는 거꾸로 차오르지 않는다
          const fitK = S.rec.fitK;
          A.chars = c0; delete G.REG.accounts.friend2; Object.assign(S, JSON.parse(keep)); G.refreshStats();
          return {ok, n: names.length, mine: names.filter(n => n.startsWith('내캐')).length, friend: names.includes('벗님2'), hpK, tgt: G.TB_DIFF.normal.tgt, ratio: +(dmgA2 / dmgMe).toFixed(2), rise, fitK}; }""")
        check(tb2['ok'] and tb2['mine'] == 3 and tb2['friend'] and abs(tb2['hpK'] - tb2['tgt']) < 1 and tb2['ratio'] == 3 and tb2['rise'] == 0 and (tb2['fitK'] or 0) > 0,
              f'타임 보스: 같은 계정의 다른 캐릭터도 뽑히고, 보스 체력은 모두의 실제 피해 합 × 목표 시간에서 시작해 싸우며 맞추고(막대는 거꾸로 안 참, 끝나면 기억), 공격은 맞는 캐릭터 체력에 비례 {tb2}')

        # 타임 보스 동료는 무작위 10명, 같은 직업은 나까지 3명(이 기기만 쓸 때도 같은 규칙, 30분 동안은 같은 파티)
        tb3 = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S);
          const cls = ['musa', 'jagaek', 'sulsa', 'doin'], chars = [];
          for (let i = 0; i < 20; i++) chars.push({cid:'p' + i, name:'뽑' + i, cls:cls[i % 4], level:40, look:{}, armorG:1, weaponG:1, ally:{dps:10, maxHp:100, rd:80}});
          chars.push({cid:'px', name:'안싸움', cls:'musa', level:1, look:{}});
          G.REG.accounts.pickt = {salt:'x', hash:'p:x', t:1, chars};
          const a = G.tbOthers(), b = G.tbOthers(), n = {}; for (const o of a) n[o.cls] = (n[o.cls] || 0) + 1;
          delete G.REG.accounts.pickt; Object.assign(S, JSON.parse(keep));
          return {n:a.length, same:a.map(o => o.name).join() === b.map(o => o.name).join(), byCls:n, me:S.cls, none:a.some(o => o.name === '안싸움')}; }""")
        capOk = all(v <= (2 if k == tb3['me'] else 3) for k, v in tb3['byCls'].items())
        check(tb3['n'] == 10 and tb3['same'] and capOk and not tb3['none'], f'타임 보스: 무작위 10명·같은 직업은 나까지 3명·30분 동안 같은 파티 {tb3}')
        await page.click('#tab-raid'); await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '18_레이드_저승.png'))

        # 6-3) 전직·아바타·히든 퀘스트·천계(신과의 전쟁)
        jb = await page.evaluate("""() => { const G = window.__game; G.quiet = true; G.S.up.atk = 200; G.S.up.hp = 200; G.refreshStats();
          const before = G.S.job; const ok = G.startJobTrial(1); for (let i = 0; i < 3000 && G.raid; i++) G.update(0.05);
          return {before, ok, job: G.S.job, skill: G.S.skills.jobA, cape: G.S.av.cape}; }""")
        check(jb['ok'] and jb['job'] == 1 and jb['skill'] == 1 and jb['cape'].startswith('j_'), f'1차 전직 시험을 이기면 전직하고 전직 기술·망토를 받는다 {jb}')
        await page.click('#tab-grow'); await page.wait_for_timeout(200); await page.click('#gv-job'); await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '25_전직.png'))
        av = await page.evaluate("""() => { const G = window.__game; G.S.gems = 5000; const n0 = G.AVATARS.filter(a => G.S.av.own[a.k]).length;
          G.avLuck = 100; const r = G.openAvatarBox(); G.avLuck = null; G.equipAvatar(r.a.k); return {got: !!r, n: G.AVATARS.filter(a => G.S.av.own[a.k]).length - n0, eq: G.S.av[r.a.type] === r.a.k}; }""")
        check(av['got'] and av['n'] == 1 and av['eq'], f'꾸미기 상자로 아바타를 얻고 입는다 {av}')
        await page.click('#tab-gear'); await page.wait_for_timeout(200); await page.click('#seg-av'); await page.wait_for_timeout(400)
        await page.screenshot(path=str(OUT / '26_아바타.png'))
        hq = await page.evaluate("""() => { const G = window.__game, S = G.S; S.best.l1 = 200; S.level = 200; S.quest.main = G.HELL_END_Q;
          const h0 = G.hiddenQuest(); G.claimHidden(); S.rec.raids += 10; G.claimHidden(); S.refine.armor.lv = 25; G.claimHidden();
          const ready = G.jobReady(2); G.grantJob(2); G.claimHidden(); return {shown: !!h0 && h0.hidden, hid: S.quest.hid, ready, job: S.job, saja: !!S.av.own.c_saja}; }""")
        check(hq['shown'] and hq['ready'] and hq['hid'] == 4 and hq['job'] == 2 and hq['saja'], f'저승을 마치면 히든 퀘스트가 나타나고, 다 하면 2차 전직을 한다 {hq}')
        await tab(page, 'quest'); await page.wait_for_timeout(300)
        hv = await page.evaluate("""() => { const G = window.__game, S = G.S; const ok1 = G.rebirthReady(); const r = G.doRebirth();
          const ok2 = G.rebirthReady(); return {ok1, world: S.world, reb: S.reb.n, again: ok2, cap: S.level}; }""")
        check(hv['ok1'] and hv['world'] == 2 and hv['reb'] == 2 and not hv['again'], f'두 번째 환생으로 천계에 오르고, 환생은 두 번까지다 {hv}')
        await skip_cut(page, 300)
        for i, st in enumerate([1, 46, 76]):
            await page.evaluate(f"() => window.__game.setStage({st})")
            await page.wait_for_timeout(1500)
            await (await page.query_selector('#scene')).screenshot(path=str(OUT / f'27_천계{i + 1}.png'))
        gr = await page.evaluate("""() => { const G = window.__game; G.S.level = 40; G.S.raid.tk = 3; const ok = G.startRaid(0); const name = G.raid && G.raid.info.bossName;
          for (let i = 0; i < 3000 && G.raid; i++) G.update(0.05); return {ok, name, first: !!G.S.raid.first.g0}; }""")
        check(gr['ok'] and gr['name'] == '전우치', f'천계 영웅 레이드(전우치)를 할 수 있다 {gr}')
        await page.click('#tab-raid'); await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '28_영웅레이드.png'))

        # 6-3b) 가로 화면: 메뉴를 누르면 장면을 덮는 페이지가 열리고, 같은 메뉴·✕로 닫힌다
        lay = await page.evaluate("""() => { const G = window.__game; G.closePage(); const r = document.querySelector('#cv').getBoundingClientRect();
          return {cw: r.width, vw: innerWidth, open: !document.querySelector('#page').hidden}; }""")
        await page.click('#tab-pet'); await page.wait_for_timeout(250)
        op = await page.evaluate("() => !document.querySelector('#page').hidden")
        await page.click('#tab-pet'); await page.wait_for_timeout(150)
        cl = await page.evaluate("() => document.querySelector('#page').hidden")
        check(lay['cw'] > lay['vw'] * 0.8 and not lay['open'] and op and cl, f'가로 화면: 장면이 화면을 가득 채우고, 메뉴 페이지가 열리고 닫힌다 {lay}')

        # 6-3c) 여정 지도: 오른쪽 위 지도 단추 → 세계·지역 그림·지금 위치(용사)·이야기 장, 땅을 누르면 정보
        await page.evaluate("() => window.__game.closePage()")
        await page.click('#mapBtn'); await page.wait_for_timeout(2200)
        jm = await page.evaluate("""() => { const G = window.__game, S = G.S, now = document.querySelector('.jm-node.s-now');
          const cvs = [...document.querySelectorAll('canvas.th')];
          return {title: document.querySelector('#pageTitle').textContent, nodes: document.querySelectorAll('.jm-node').length,
            now: now && now.getAttribute('aria-label'), world: G.WORLD_NAME ? '' : '', hero: !!document.querySelector('.jm-hero'),
            painted: cvs.filter(c => c.getContext('2d').getImageData(124, 74, 1, 1).data[3] > 0).length, cvs: cvs.length,
            tags: document.querySelectorAll('.jm-tags i').length, stage: S.stage}; }""")
        await page.screenshot(path=str(OUT / '6c_여정지도.png'))
        await page.click('.jm-node[data-n="16"]'); await page.wait_for_timeout(250)
        jinfo = await page.evaluate("() => document.querySelector('#jmInfo').textContent")
        check(jm['title'] == '여정 지도' and jm['nodes'] == 43 and jm['now'] and jm['hero'] and jm['painted'] == jm['cvs'] and jm['tags'] >= 30
              and '천계' in jinfo and '구름 계단' in jinfo, f'여정 지도: 땅 43곳·지금 위치·이야기 장 표시, 땅을 누르면 정보 {jm} / {jinfo[:40]}')
        await page.click('#pageClose'); await page.wait_for_timeout(150)
        check(await page.evaluate("() => document.querySelector('#page').hidden"), '여정 지도를 ✕로 닫는다')

        # 6-3d) 반자동(기술은 직접)·보스 수동(눌러야 시작), 사냥터 몹 수·보스까지 처치 수
        md = await page.evaluate("""() => { const G = window.__game, S = G.S; G.closePage(); G.setStage(S.stage);
          const st0 = S.stage; G.setStage(1); G.ST.maxHp = 1e300; G.ST.atk = 1e300; G.hero.hp = 1e300;   // 이 점검 동안만 아주 세게
          S.mode = 'semi'; S.bossAuto = false; S.autoBoss = false; S.kills = G.FIELD.kills; G.hero.dead = false;
          for (const k in G.skillCd) G.skillCd[k] = 0; const k0 = S.rec.kills;
          for (let i = 0; i < 120; i++) G.update(0.05);
          const used = Object.values(G.skillCd).filter(v => v > 0).length, boss = G.bossActive, field = S.rec.kills - k0;
          document.querySelector('#bossBtn').click(); for (let i = 0; i < 5; i++) G.update(0.05);
          const pressed = G.bossActive;
          S.mode = 'auto'; S.bossAuto = true; S.autoBoss = true; G.refreshStats(); G.setStage(st0);
          return {used, boss, pressed, field, kills: G.FIELD.kills}; }""")
        check(md['used'] == 0 and not md['boss'] and md['pressed'] and md['kills'] == 25 and md['field'] >= 3,
              f'반자동이면 기술을 알아서 쓰지 않고, 보스 수동이면 [보스 도전]을 눌러야 보스가 나온다(6초 처치 수 field) {md}')

        # 6-4) 기술 직접 쓰기·자동/수동, 직업 특성, 조합 공방, 확률(재련·상자·펫 천장)
        await page.evaluate("() => { const G = window.__game; G.closePage(); G.setClass('musa'); G.S.level = 120; G.unlockSkills(); G.S.skSetMan = true; G.S.skSet = [0, 1, 2, 3, 4, 5]; G.skillCd.roar = 0; G.S.skManual = {}; G.hero.dead = false; G.hero.hp = G.ST.maxHp; }")
        await page.wait_for_timeout(300)
        await page.click('#skb-roar'); await page.wait_for_timeout(100)
        tap = await page.evaluate("() => ({cd: window.__game.skillCd.roar, buff: window.__game.hero.buffT})")
        check(tap['cd'] > 0 and tap['buff'] > 0, f'기술 칸을 누르면 그 기술을 바로 쓴다 {tap}')
        await page.dispatch_event('#skb-bolt', 'pointerdown'); await page.wait_for_timeout(700); await page.dispatch_event('#skb-bolt', 'pointerup')
        man = await page.evaluate("""() => { const G = window.__game; const m = !!G.S.skManual.bolt; G.skillCd.bolt = 0; for (let i = 0; i < 60; i++) G.update(0.05);
          const cls = document.querySelector('#skb-bolt').className; G.toggleSkAuto(1); return {m, cd: G.skillCd.bolt, cls, back: !G.S.skManual.bolt}; }""")
        check(man['m'] and man['cd'] == 0 and 'manual' in man['cls'] and man['back'], f'기술 칸을 길게 누르면 수동이 되고, 수동 기술은 저절로 쓰지 않는다 {man}')
        dn = await page.evaluate("""() => { const G = window.__game, S = G.S; G.setClass('doin'); S.level = 120; const rb = S.reb.n; S.reb.n = 0; G.unlockSkills();
          const before = G.skLv(5); S.reb.n = 1; G.unlockSkills(); const after = G.skLv(5); S.reb.n = rb; G.unlockSkills();
          const atk = [...Array(11).keys()].filter(i => G.skDef(i).atk).length; return {before, after, atk}; }""")
        check(dn['before'] == 0 and dn['after'] > 0 and dn['atk'] == 5, f'도인은 공격 기술이 다섯(도력 일격·팔괘진은 버프 겸 공격)이고, 하늘의 심판은 환생해야 열린다 {dn}')
        sh = await page.evaluate("""() => { const G = window.__game; G.setClass('sulsa'); G.S.level = 120; G.unlockSkills(); G.skillCd.roar = 0; G.hero.dead = false; G.hero.hp = G.ST.maxHp; G.hero.mp = G.MP_MAX; G.castNow(2);
          return {shield: G.hero.shield / G.ST.maxHp}; }""")
        check(sh['shield'] >= 0.399, f'술사의 마력 보호막이 최대 체력의 40% 이상을 막는다 {sh}')
        await page.click('#tab-skill'); await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '29_기술_직업특성.png'))
        cf = await page.evaluate("""() => { const G = window.__game, S = G.S; const w0 = S.world; S.world = 0; G.setClass('jagaek'); G.refreshStats();   // 이승에서(뒤 땅에서는 이승 조합식이 '계승 조합'이라 확정)
          S.best.s0 = Math.max(S.best.s0, 60); const mk = 'm' + S.world; S.mat[mk] = 200; S.gems = 5000; S.gear.weapon.count[4] += 3; S.gear.weapon.count[8] += 4; S.gear.armor.count[4] += 3;
          const a0 = G.ST.atk, best = G.ENGR_BEST.jagaek.w;
          G.pickEngr('w', best); const t1 = G.craft('w') === true;
          G.craftLuck = 0.0001; const f = G.craft('w'); const fails = S.craft.w.f, mat1 = S.mat[mk];
          G.craftLuck = null; S.craft.w.f = 5; const ok = G.craft('w') === true;
          G.pickEngr('a', G.ENGR_BEST.jagaek.a); G.pickEngr('n', G.ENGR_BEST.jagaek.n); G.craft('a'); G.craft('n');
          G.refreshStats(); const out = {t1, f, fails, mat1, ok, t: S.craft.w.t, best, up: G.ST.atk / a0, harm: G.harmonyOn()}; S.world = w0; G.refreshStats(); return out; }""")
        check(cf['t1'] and cf['f'] == 'fail' and cf['fails'] == 1 and cf['mat1'] == 150 and cf['ok'] and cf['t'] == 2 and cf['up'] > 1.2 and cf['harm'] and cf['best'] == 'hunt',
              f'조합 공방: 실패하면 재료 절반만 잃고, 천장이면 확정 성공, 자객 최적 각인 셋이면 조화가 켜진다 {cf}')
        await page.click('#tab-gear'); await page.wait_for_timeout(200); await page.click('#seg-craft'); await page.wait_for_timeout(400)
        await page.screenshot(path=str(OUT / '30_조합공방.png'))
        pr = await page.evaluate("""() => { const G = window.__game, S = G.S; S.gold = 1e15; S.gems = 1e5;
          S.dust = 1e6; S.refine.weapon.lv = 16; S.refine.weapon.drops = 2; const r1 = G.refineTry('weapon');
          S.avPity = G.AV_PITY - 1; const box = G.openAvatarBox();
          S.petPity = 59; const pets = G.petSummon(1);
          return {chance: r1.ok && r1.sure && S.refine.weapon.lv === 17, box: !!(box && box.pity && box.isNew && box.a.type !== 'pet'), pet: G.PETS[pets[0].i].g}; }""")
        check(pr['chance'] and pr['box'] and pr['pet'] >= 3, f'확률 보정: 두 번 떨어진 뒤 재련은 반드시 성공, 꾸미기 상자·펫 소환 천장 {pr}')

        # 6-4b) 재련 한도: 방어구는 이승 +15 → 저승 +22 → 천계 +25, 무기는 이승에서 +25
        rc = await page.evaluate("""() => { const G = window.__game, S = G.S, w0 = S.world, out = {};
          for (const w of [0, 1, 2]){ S.world = w; out['a' + w] = G.refineCap('armor'); out['w' + w] = G.refineCap('weapon'); }
          S.world = 0; const lv = S.refine.armor.lv; S.refine.armor.lv = 15; S.gold = 1e300; S.dust = 1e6; const blocked = G.refineTry('armor') === null;
          S.refine.armor.lv = lv; S.world = w0; G.refreshStats(); return Object.assign(out, {blocked}); }""")
        check(rc['w0'] == 25 and rc['a0'] == 15 and rc['a1'] == 22 and rc['a2'] == 25 and rc['blocked'],
              f'재련 한도: 무기는 이승에서 +25, 방어구는 이승 +15·저승 +22·천계 +25 {rc}')

        # 6-4c) 오프라인 보상: 온라인 스킬 자동 처치 속도로 계산, 경험치 1.25배·엽전 0.85배, 오프라인 누적 24시간마다 신화 3%
        of = await page.evaluate("""() => { const G = window.__game, S = G.S, w0 = S.world, st0 = S.stage; G.quiet = true;
          S.world = 0; G.setStage(5); S.mode = 'auto'; S.off.kps = 0; G.offHunt.t = 0; G.offHunt.k = 0;
          for (let i = 0; i < 1300; i++) G.update(0.05);
          const kps = S.off.kps;
          S.off.kps = 1.5; S.off.acc = 23.5 * 3600; G.offLuck = 100; const ba = S.bossAuto; S.bossAuto = false;
          const r = G.offlineReward(3600); S.bossAuto = ba; G.offLuck = null; G.closePage && 0;
          const acc = S.off.acc; S.world = w0; G.setStage(st0); G.refreshStats(); G.quiet = false;
          return {kps, kills: r.kills, gold: r.gold, gems: r.gems, exp: r.exp, myths: r.myths.length, acc}; }""")
        await page.evaluate("() => { const b = document.querySelector('#modal-btn-0'); if (b) b.click(); }")
        check(of['kps'] > 0.2 and of['kills'] == 5400 and of['gems'] > 0 and of['gold'] > 0 and of['myths'] == 1 and abs(of['acc'] - 1800) < 1,
              f'오프라인 보상: 잰 처치 속도로 마리 수를 셈하고 보석도 나오며, 오프라인 누적 24시간에 신화 보물을 굴린다 {of}')

        # 6-4d) 오프라인 보스 자동 도전: 이기면 다음 단계, 한 단계에서 5번 지면 그 사냥터에서 사냥
        ob = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          S.world = 0; G.setStage(5); S.maxStage = Math.max(S.maxStage, 5); S.kills = 0; S.bossAuto = true; S.off.kps = 2; S.rec.rdpsK = 1e6; G.refreshStats();
          const x5 = G.offBossOdds(5);
          G.offBossLuck = 0; const a = G.offlineReward(3600); const stA = S.stage, autoA = S.autoBoss;
          document.querySelector('#modal-btn-0') && document.querySelector('#modal-btn-0').click();
          G.setStage(5); S.kills = 0; G.offBossLuck = 1e9; const b = G.offlineReward(1800);
          document.querySelector('#modal-btn-0') && document.querySelector('#modal-btn-0').click();
          G.offBossLuck = null;
          const out = {x5:+x5.x.toFixed(2), p5:x5.p, failA:a.boss.fail, stuckA:a.boss.stuck, stA, autoA, killsA:a.kills, winB:b.boss.win, stB:b.stage, endB:b.boss.end};
          Object.assign(S, JSON.parse(keep)); G.setStage(S.stage); G.refreshStats(); G.quiet = false; return out; }""")
        check(ob['failA'] == 5 and ob['stuckA'] == 5 and ob['stA'] == 5 and not ob['autoA'] and 6000 < ob['killsA'] <= 7200
              and ob['p5'] > 0 and ob['winB'] >= 3 and ob['stB'] == 5 + ob['winB'],
              f'오프라인 보스: 5번 지면 그 사냥터에서 사냥(단계 그대로), 이기면 다음 단계로 올라간다 {ob}')

        # 6-4e) 장별 치장: 천계 17장부터 몹에게서, 지나온 장 것만, 줄 수 = 등급, 1~2줄로 다 채워도 3.5단계·전설로 10단계, 더 좋으면 바로 낌, 저장 다듬기
        sk = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          const qi = ch => G.MAIN_Q.findIndex(q => q.ch === ch), out = {};
          S.skin = {eq:{}, inv:[], seq:0, found:{}}; G.refreshStats();
          S.quest.main = qi(12); out.closed = !G.skinOpen();
          S.world = 2; S.quest.main = qi(20); G.refreshStats(); const a0 = G.ST.maxHp; let bad = 0; const chs = new Set();
          for (let i = 0; i < 300; i++){ const it = G.skinDrop(null, true).it; chs.add(it.c);
            if (it.c > 20 || it.g > 1 || it.l.length !== G.SK_GRADES[it.g].n || new Set(it.l.map(l => l[0])).size !== it.l.length || it.l[0][0] !== G.SK_PARTS.find(P => P.k === G.SKC[it.c].p).stat) bad++; }
          out.bad = bad; out.maxCh = Math.max(...chs); out.eq = Object.keys(S.skin.eq).length; out.hpUp = G.ST.maxHp > a0;
          out.better = Object.values(S.skin.eq).every(e => S.skin.inv.filter(x => G.SKC[x.c].p === G.SKC[e.c].p).every(x => G.skSE(x) <= G.skSE(e) + 1e-9));
          const fill = g => { for (const P of G.SK_PARTS){ const sk = G.SK_LIST.find(x => x.p === P.k); S.skin.eq[P.k] = {id:900, c:sk.c, g, l:G.skMake(sk, g).l.map(([t]) => [t, G.SK_GRADES[g].se])}; } G.refreshStats(); return +G.skinSum().se.toFixed(2); };
          out.low = fill(1); out.top = fill(4);
          const gc = ch => { S.quest.main = qi(ch); const n = [0, 0, 0, 0, 0]; for (let i = 0; i < 1500; i++) n[G.skinDrop(null, true).it.g]++; return n; };
          const g30 = gc(30), g33 = gc(33), g42 = gc(42); out.g4line = [g30[3] + g30[4], g33[3], g33[4], g42[4]];
          const d = JSON.parse(JSON.stringify(S)); d.skin.eq.guard = {id:5, c:20, g:0, l:[['atk', 9]]}; d.skin.inv = [{id:6, c:99, g:0, l:[['atk', 0.1]]}];
          const m = G.mergeState(d); out.clean = [m.skin.eq.guard ? 'kept' : 'dropped', m.skin.inv.length];
          S.quest.main = qi(20); S.off.kps = 3; S.bossAuto = false; G.skLuck = null; const o = G.offlineReward(3600); out.offSk = o.skins;
          document.querySelector('#modal-btn-0') && document.querySelector('#modal-btn-0').click();
          Object.assign(S, JSON.parse(keep)); G.setStage(S.stage); G.refreshStats(); G.quiet = false; return out; }""")
        check(sk['closed'] and sk['bad'] == 0 and sk['maxCh'] == 20 and sk['eq'] >= 4 and sk['hpUp'] and sk['better'] and sk['low'] <= 3.5 and 9.5 <= sk['top'] <= 10
              and sk['g4line'][0] == 0 and sk['g4line'][1] > 0 and sk['g4line'][2] == 0 and sk['g4line'][3] > 0 and sk['clean'] == ['dropped', 0] and sk['offSk'] >= 3,
              f'장별 치장: 17장부터·지나온 장 것만·줄 수=등급, 1~2줄로 다 채워도 3.5단계 이하·전설은 10단계, 4줄은 2부 후반·전설은 3부 중반부터, 오프라인에도 나온다 {sk}')

        # 6-4f) 주간 퀘스트: 월요일에 새로 시작, 일을 하면 세고, 받으면 보석(세계 배율)·덤, 모두 끝내면 큰 상자
        wk = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          S.world = 2; S.week = {key:'', wp:{}, wgot:[], wall:false}; G.weekCheck(); const key = S.week.key, d = new Date(G.now());
          const mon = new Date(key.split('-')[0], key.split('-')[1] - 1, key.split('-')[2]).getDay();
          G.ev('kill', 10); G.ev('gsummon', 3); G.ev('psummon', 2); const counted = [S.week.wp.kill, S.week.wp.summon];
          const g0 = S.gems, sh0 = S.mythShard || 0; for (const W of G.WEEKLY) S.week.wp[W.key] = W.goal;
          const early = G.claimWeekAll(); let n = 0; for (const W of G.WEEKLY) if (G.claimWeek(W.key)) n++;
          const gemsW = S.gems - g0, again = G.claimWeek('kill');
          S.quest.main = G.MAIN_Q.findIndex(q => q.ch === 30); S.skin = {eq:{}, inv:[], seq:0, found:{}}; G.skGrade = null;
          S.gems = 0; const box = G.claimWeekAll(), gemsAll = S.gems, shard = (S.mythShard || 0) - sh0;
          const sks = Object.values(S.skin.eq).concat(S.skin.inv), skN = sks.length, skG = Math.min(...sks.map(x => x.g));
          G.addTime(8 * 86400 * 1000); G.weekCheck(); const reset = S.week.key !== key && !S.week.wall && !S.week.wgot.length;
          Object.assign(S, JSON.parse(keep)); G.refreshStats(); G.quiet = false;
          return {mon, counted, early, n, gemsW, again, box: box && box.length, gemsAll, shard, reset, skN, skG}; }""")
        check(wk['mon'] == 1 and wk['counted'] == [10, 5] and wk['early'] is None and wk['n'] == 8 and wk['gemsW'] == 3500 * 2 and not wk['again']
              and wk['box'] >= 3 and 6000 <= wk['gemsAll'] <= 6030 and wk['shard'] >= 30 + 6 + 12 + 5 + 6 and wk['reset'] and wk['skN'] == 1 and wk['skG'] >= 1,
              f'주간 퀘스트: 월요일 시작·일을 세고·보석(천계 2배)·덤·큰 상자(보석·신화 조각·꾸미기 상자·치장)·다음 주에 새로 {wk}')

        # 6-4g) 1일 보스: 요일마다 보스·치장 부위, 이기면 그 부위 치장(모든 등급), 일요일은 전설만(낮은 확률), 참가만 해도 하루 한 번 보석·엽전
        db = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          S.skin = {eq:{}, inv:[], seq:0, found:{}}; S.dboss = {day:'', n:0, paid:false, won:false}; S.up.atk = Math.max(S.up.atk, 150); G.refreshStats();
          const day = G.dbDay(), part = G.dbPart(), g0 = S.gems;
          // 지면: 참가 보상만
          G.dbCheck(); S.dboss.n = 1; const lose = G.finishDBoss({win:false}); const gemsLose = S.gems - g0; const lose2 = G.finishDBoss({win:false});
          // 이기면: 그날 부위 치장(일요일이 아니면 늘 하나)
          G.dbForce = true; const ok = G.startDBoss(); const B = G.raid && G.raid.boss; if (B){ G.raid.info.fit = null; B.hp = 1; } for (let i = 0; i < 400 && G.raid; i++) G.update(0.05);
          const got = S.skin.inv.concat(Object.values(S.skin.eq)), parts = got.map(it => G.SKC[it.c].p);
          // 여러 날 흉내: 월~토는 그 부위, 일요일은 전설만
          const grades = [0, 0, 0, 0, 0], partOk = [];
          for (let k = 0; k < 300; k++){ const r = G.skinDropPart('belt', [0, 1, 2, 3, 4][k % 5]); grades[r.it.g]++; partOk.push(G.SKC[r.it.c].p === 'belt'); }
          const sunAll = G.skinDropPart('all', 4).it.g;
          Object.assign(S, JSON.parse(keep)); G.refreshStats(); G.quiet = false;
          return {day, part, loseOut: lose.out.length, gemsLose: gemsLose > 0, lose2: lose2.out.length, ok, won: S.dboss ? true : false, got: got.length, parts, sun: day === 0, allGrades: grades.every(n => n > 0), partOk: partOk.every(Boolean), sunAll}; }""")
        check(db['loseOut'] == 3 and db['gemsLose'] and db['lose2'] == 0 and db['ok'] and (db['sun'] or (db['got'] == 1 and db['parts'][0] == db['part'])) and db['allGrades'] and db['partOk'] and db['sunAll'] == 4,
              f'1일 보스: 참가 보상(하루 한 번)·이기면 오늘 부위 치장·모든 등급·일요일은 전설 {db}')

        # 6-4g2) 타임 보스·1일 보스 손맛: 공격은 방어 빼고 최대 체력의 %, 되받기는 기본 피해 FIT.ctr초 몫(기본 피해로는 안 셈), 막대는 거꾸로 안 참
        fh = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          if (G.raid){ G.raid.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05); }
          S.dboss = {day:'', n:0, paid:false, won:false}; S.buff.def = 600; G.refreshStats(); G.dbCheck();
          G.dbForce = true; const ok = G.startDBoss(), R = G.raid, B = R.boss; let rise = 0, last = 1;
          for (let i = 0; i < 200 && G.raid; i++){ G.update(0.05); const f = B.hp / B.maxHp; if (f > last + 1e-6) rise++; last = f; }
          const norm = +(G.bossHit(B, G.hero) * G.takenK() / G.ST.maxHp).toFixed(3), pct = B.tbPct.hit, dk = +G.takenK().toFixed(2);
          const base0 = R.info.fit.base, done0 = R.tbDone, rate = G.fitRate();
          B.pat = B.pat || {stg:100, cd:9, tel:null, grogT:0, n:0, wipes:[]}; B.pat.grogT = 0; B.pat.tel = {kind:'counter', t:0, T:1.1, auto:{ok:false}}; G.counterOk(B, true);
          const ctr = +((R.tbDone - done0) / rate).toFixed(2), baseD = R.info.fit.base - base0;
          R.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05);
          Object.assign(S, JSON.parse(keep)); G.refreshStats(); G.quiet = false;
          return {ok, rise, norm, pct, dk, ctr, want: G.FIT.ctr, baseD}; }""")
        check(fh['ok'] and fh['rise'] == 0 and abs(fh['norm'] - fh['pct']) < 0.002 and fh['dk'] < 1 and fh['ctr'] >= fh['want'] * 0.9 and fh['baseD'] == 0,
              f'1일·타임 보스: 방어가 높아도 맞으면 최대 체력의 같은 %, 되받기는 기본 피해 몇 초 몫을 한 번에(기본 피해로는 안 셈), 막대는 거꾸로 안 참 {fh}')

        # 6-4g3) 남이 보낸 값 막기(constructor 같은 이름·큰 등급·HTML 이름) + 자정을 넘긴 1일 보스는 시작한 날 것으로
        gd = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          const bad = [G.mkClean({t:'skin', c:'constructor', g:0, l:[['atk', 0.3]]}), G.mkClean({t:'stack', k:'constructor', n:1}), G.mkClean({t:'acc', k:'__proto__', g:0, p:1}), G.mkClean({t:'skin', c:17, g:0, l:[['toString', 0.3]]})];
          const a = G.tbFromSummary('<!--x', {cls:'constructor', armorG:99, weaponG:-7, ally:{dps:5, maxHp:9, rd:'x'}}, false);
          if (G.raid){ G.raid.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05); }
          S.skin = {eq:{}, inv:[], seq:0, found:{}}; S.dboss = {day:'', n:0, paid:false, won:false}; G.dbCheck(); G.dbLuck = 100;
          G.dbForce = true; const ok = G.startDBoss(), R = G.raid; R.info.day = '1999-1-1'; R.info.paid0 = false; const g0 = S.gems;
          R.info.fit = null; R.boss.hp = 1; for (let i = 0; i < 400 && G.raid; i++) G.update(0.05);
          const today = {n:S.dboss.n, paid:S.dboss.paid, won:S.dboss.won}, gems = S.gems > g0, skins = Object.values(S.skin.eq).concat(S.skin.inv).length;
          G.dbLuck = null; Object.assign(S, JSON.parse(keep)); G.refreshStats(); G.quiet = false;
          return {bad: bad.every(x => x === null), cls: a.cls, ag: a.armorG, wg: a.weaponG, rd: a.rd, ok, today, gems, skins}; }""")
        check(gd['bad'] and gd['cls'] == 'musa' and gd['ag'] == -1 and gd['wg'] == -1 and gd['rd'] == 0 and gd['ok'] and gd['today'] == {'n': 1, 'paid': False, 'won': False} and gd['gems'] and gd['skins'] == 1,
              f'남이 보낸 이상한 값(constructor 이름·큰 등급)은 버리고, 자정을 넘긴 1일 보스는 시작한 날 것으로(새 날 도전·보상은 그대로) {gd}')

        # 6-4h) 화면 방향 고르기: 휴대폰을 돌리지 않고 가로·세로를 바꾸고(잠글 수 없으면 화면을 돌려 보여 줌), 돌린 동안에도 누른 칸이 맞는다
        await page.evaluate("() => { const G = window.__game; G.closePage && G.closePage(); const m = document.querySelector('#modal'); if (m && !m.hidden){ const b = document.querySelector('#modal-btn-0'); if (b) b.click(); } G.hero.dead = false; }")
        await page.wait_for_timeout(200)
        land0 = await page.evaluate("() => !document.body.classList.contains('portrait')")
        await page.evaluate("(m) => window.__game.setOrient(m, true)", 'port' if land0 else 'land')
        await page.wait_for_timeout(400)
        orr = await page.evaluate("""() => { const G = window.__game, h = G.hero; for (const m of G.mobs) if (!m.raid) m.dead = true; h.target = null; const tx = Math.max(1, Math.min(26, h.tx + 2)), ty = h.ty, cv = document.querySelector('#cv'), rc = cv.getBoundingClientRect();
          const xr = (G.isoX(tx, ty) - G.camX) * G.scale + 2, yr = (G.isoY(tx, ty) - G.camY) * G.scale + 2;
          const pt = G.rotDeg === 90 ? [rc.right - yr, rc.top + xr] : G.rotDeg === -90 ? [rc.left + yr, rc.bottom - xr] : [rc.left + xr, rc.top + yr];
          const el = document.elementFromPoint(pt[0], pt[1]);
          return {rot: G.rotDeg, portrait: document.body.classList.contains('portrait'), tx, ty, pt, el: el ? el.id || el.className : '', cut: !!G.cut, raid: !!G.raid, mk: !!G.market, dead: h.dead}; }""")
        await page.mouse.click(orr['pt'][0], orr['pt'][1]); await page.wait_for_timeout(100)
        goal = await page.evaluate("() => { const h = window.__game.hero, g = h.goal; return g ? [g[0], g[1]] : h.target ? 'target:' + h.target.name : null; }")
        await page.screenshot(path=str(OUT / '35_화면돌리기.png'))
        await page.evaluate("() => window.__game.setOrient('auto', true)"); await page.wait_for_timeout(300)
        back = await page.evaluate("() => ({rot: window.__game.rotDeg, land: !document.body.classList.contains('portrait'), mode: window.__game.orientMode})")
        check(orr['rot'] in (90, -90) and orr['portrait'] == land0 and goal == [orr['tx'], orr['ty']] and back['rot'] == 0 and back['land'] == land0 and back['mode'] == 'auto',
              f'화면 방향: 게임 안에서 가로·세로를 바꾸고(화면을 돌려 보여 줌), 돌린 동안에도 누른 칸이 맞고, 자동으로 되돌린다 {orr} {goal} {back}')

        # 6-4i) 변신(보스 싸움·레이드에서 한 판에 한 번, 30초, 일반 몹 사냥 중엔 못 씀, 효과는 단계 값, 사신은 부상부터 약하게)
        #       기술 최대 레벨(전직)·전투 기술 6칸·연계(콤보)·초각성(실제 보스 피해 몇 초 몫)
        nf = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true; G.noFork = true;
          if (G.raid){ G.raid.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05); }
          G.setClass('musa'); S.world = 1; S.form.own.cheong = true; S.form.own.tengu = true; S.form.eq = 'cheong'; S.form.manual = true; G.refreshStats(); G.hero.dead = false; G.hero.hp = G.ST.maxHp;
          const noHunt = !G.startForm(true), a0 = G.ST.atk;
          G.gateOff = true; G.PAT.off = true; S.kills = G.FIELD.kills; S.autoBoss = false; G.startBoss(); const B = G.bossRef; B.hp = B.maxHp = 1e300; B.atk = 0;
          const ok1 = G.startForm(true), a1 = G.ST.atk, again = G.startForm(true);
          for (let i = 0; i < 400; i++) G.update(0.05);
          const still = G.bossActive && G.formT > 0 && G.formT < 15;
          for (let i = 0; i < 400 && G.bossActive; i++) G.update(0.05); for (let i = 0; i < 3; i++) G.update(0.05);
          const ended = G.formT <= 0 && G.ST.atk === a0, again2 = G.startForm(true);
          // 다음 판(자동)이면 시작하자마자 변신
          if (G.bossActive){ B.hp = 0.0001; for (let i = 0; i < 60 && G.bossActive; i++) G.update(0.05); }
          S.form.manual = false; G.hero.dead = false; G.hero.hp = G.ST.maxHp; S.kills = G.FIELD.kills; G.startBoss(); const B2 = G.bossRef; if (B2){ B2.hp = B2.maxHp = 1e300; B2.atk = 0; } for (let i = 0; i < 40; i++) G.update(0.05);
          const autoOn = G.formT > 0; if (G.bossActive && B2){ B2.hp = 0.0001; for (let i = 0; i < 60 && G.bossActive; i++) G.update(0.05); }
          for (let i = 0; i < 3; i++) G.update(0.05); const endAfter = G.formT <= 0;
          // 단계 값: 청룡은 1부(저승) 공격력 ×1.24^1.5, 부상에서는 사신이 60%로
          const res = G.gearRes(), fx1 = G.formFx(G.FM.cheong).atk; S.world = 3; const fx3 = G.formFx(G.FM.cheong).atk, tg3 = G.formFx(G.FM.tengu).atk; S.world = 1;
          // 기술: 최대 레벨·6칸·연계
          S.job = 1; S.level = 100; const cap1 = G.skCap(0); S.job = 3; S.level = 200; S.world = 3; const cap3 = G.skCap(0); S.world = 1; S.job = 1; S.level = 120;
          S.skills.spin = 30; const lvEff = G.skLv(0); S.skills.spin = 5;
          G.unlockSkills(); S.skSetMan = false; S.skSet = []; G.skSetFix(); const set = S.skSet.slice();
          const t1 = G.skToggle(set[0]), full = S.skSet.length; for (let i = 0; i < 10; i++) G.update(0.05); const stay = !S.skSet.includes(set[0]) && S.skSet.length === full;   // 뺀 기술이 다시 끼워지지 않음(버그)
          G.skToggle(set[0]); const back = S.skSet.includes(set[0]);
          S.skOff = []; G.skSetFix(); for (const k in G.skillCd) G.skillCd[k] = 0; G.hero.dead = false;
          const ps = G.pickSet('jumong'), psOn = S.setPick === 'jumong'; G.pickSet(''); const psOff = S.setPick === '';
          G.hero.dead = false; S.mode = 'semi'; S.kills = G.FIELD.kills; G.startBoss(); const B3 = G.bossRef; if (B3){ B3.hp = B3.maxHp = 1e300; B3.atk = 0; } for (let i = 0; i < 30; i++) G.update(0.05); for (const k in G.skillCd) G.skillCd[k] = 0;
          G.comboLuck = 10; const c0 = S.rec.combos || 0, k0 = G.castNow(2), k1 = G.castNow(3), combo = (S.rec.combos || 0) - c0, cm = G.comboMul(); G.comboLuck = null;
          if (G.bossActive && B3){ B3.hp = 0.0001; for (let i = 0; i < 60 && G.bossActive; i++) G.update(0.05); }
          const out = {noHunt, ok1, up: +(a1 / a0).toFixed(3), again, ended, still, again2, autoOn, endAfter, fx1: +fx1.toFixed(3), fx3: +fx3.toFixed(3), tg3: +tg3.toFixed(3), res, cap1, cap3, lvEff, set, t1, full, stay, back, psOn, psOff, combo, cm: +cm.toFixed(2), k0, k1};
          G.PAT.off = false; Object.assign(S, JSON.parse(keep)); G.refreshStats(); G.quiet = false; return out; }""")
        check(nf['noHunt'] and nf['ok1'] and nf['up'] > 1.3 and not nf['again'] and nf['ended'] and nf['still'] and not nf['again2'] and nf['autoOn'] and nf['endAfter']
              and abs(nf['fx1'] - 1.24 ** (1.5 * nf['res'])) < 0.01 and abs(nf['fx3'] - 1.0709 ** (1.5 * 0.6 * nf['res'])) < 0.005 and nf['tg3'] > nf['fx3']
              and nf['cap1'] == 15 and nf['cap3'] == 25 and nf['lvEff'] == 15 and len(nf['set']) >= 6 and nf['t1'] and nf['full'] == len(nf['set']) - 1 and nf['stay'] and nf['back'] and nf['psOn'] and nf['psOff'] and nf['combo'] >= 1 and nf['cm'] == 1.12 and nf['k0'] and nf['k1'],
              f'변신: 사냥 중엔 못 쓰고 보스 싸움에서 한 번만 30초(자동이면 시작하자마자)·단계 값(부상에선 사신 60%)·기술 최대 레벨(1차 15·3차 25)·익힌 기술 전부 쓰기·[빼기]가 유지됨·세트 고르기·연계 {nf}')
        aw = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          if (G.raid){ G.raid.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05); }
          S.awaken = true; S.level = 60; S.raid.tk = 3; S.rec.rdpsK = 50; G.refreshStats(); const ok = G.startRaid(0), R = G.raid, B = R.boss; B.hp = B.maxHp = 1e300;
          const d0 = R.tbDone || 0, m0 = S.rec.maxHit || 0; let dmg = 0; const h0 = B.hp;
          G.castAwaken(); for (let i = 0; i < 20; i++) G.update(0.05);
          const want = G.realDps() * G.AWAKEN_SEC, used = R.awk.used; R.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05);
          Object.assign(S, JSON.parse(keep)); G.refreshStats(); G.quiet = false; return {ok, used, want: want > 0}; }""")
        check(aw['ok'] and aw['used'] and aw['want'], f'초각성은 한 싸움에 한 번, 내 실제 보스 피해 몇 초 몫으로 {aw}')

        # 6-4j) 2026-11 (41): 도인 공격 기술 다섯·파티 버프·마나·추천 조합·전멸기·강림 레이드·1일 보스 열림
        nw = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S), was = [G.PAT.off, G.gateOff]; G.quiet = true; G.PAT.off = true; G.gateOff = true;
          if (G.raid){ G.raid.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05); }
          const out = {};
          G.setClass('doin'); out.doinAtk = [...Array(11).keys()].filter(i => G.skDef(i).atk).map(i => G.skDef(i).kind);
          G.setClass('musa'); S.level = 60; S.job = 1; G.unlockSkills(); G.refreshStats();
          out.party = G.skLv(10) > 0;
          // 추천 조합: 레이드를 시작하면 파티 버프가 든 조합, 끝나면 원래대로
          S.skSetMan = false; S.skSet = []; G.skSetFix(); const before = S.skSet.slice();
          S.raid.tk = 3; S.inv.potion = 0; S.inv.elixir = 0; S.myth.elixir = 0; S.petEq.sup = -1; const ok = G.startRaid(0), R = G.raid, B = R.boss;
          out.preset = (G.skPreset || []).slice(); out.presetHasParty = out.preset.includes(10); out.bar = G.curSet().includes(10);
          // 파티 버프: 동료가 걸어 주면 내 공격력이 오르고, 내 것도 건다
          const a0 = G.ST.atk * G.atkBuffX(); G.partyBuff('doin', 10, R.allies[0]); out.pbAtk = +(G.ST.atk * G.atkBuffX() / a0).toFixed(3); out.pbOn = G.pbT.doin > 0;
          // 마나: 기술을 쓰면 줄고, 모자라면 못 씀
          G.hero.mp = G.MP_MAX; for (const k in G.skillCd) G.skillCd[k] = 0; S.mode = 'semi';
          B.hp = B.maxHp = 1e300; for (let i = 0; i < 20; i++) G.update(0.05);
          const mp0 = G.hero.mp, c1 = G.castNow(10); out.mpUsed = +(mp0 - G.hero.mp).toFixed(1); out.c1 = c1; out.cost = G.skMp(10);
          G.hero.mp = 0; for (const k in G.skillCd) G.skillCd[k] = 0; out.noMp = !G.castNow(0) && !G.castNow(1);
          // 전멸기: 보스 체력 절반 아래 → 예고 → 1까지 깎임 → 회복약이 없으면 쓰러짐
          G.hero.dead = false; G.hero.hp = G.ST.maxHp; B.atk = 0; B.aoe = 0; B.hp = B.maxHp * 0.45; let st = []; let low = Infinity;
          for (let i = 0; i < 160 && G.raid; i++){ G.update(0.05); if (R.wipe && !st.includes(R.wipe.st)) st.push(R.wipe.st); if (!G.hero.dead) low = Math.min(low, G.hero.hp); if (R.wipe && R.wipe.st >= 4) break; }
          out.wipeSt = st; out.low = low; out.diedNoPot = G.hero.dead;
          R.time = 0; for (let i = 0; i < 120 && G.raid; i++) G.update(0.05);
          out.after = (G.skPreset === null) && G.curSet().join() === before.join();
          // 회복약이 있으면 저절로 마셔 버팀
          S.inv.potion = 5; S.raid.tk = 3; G.hero.dead = false; G.hero.hp = G.ST.maxHp; G.startRaid(0); const R2 = G.raid, B2 = R2.boss; B2.atk = 0; B2.aoe = 0; B2.hp = B2.maxHp * 0.45;
          for (let i = 0; i < 160 && G.raid; i++){ G.update(0.05); if (R2.wipe && R2.wipe.st >= 4) break; }
          out.livePot = !G.hero.dead && G.hero.hp > G.ST.maxHp * 0.15; out.potUsed = 5 - S.inv.potion; out.wipeName = R2.wipe && R2.wipe.name;
          R2.time = 0; for (let i = 0; i < 120 && G.raid; i++) G.update(0.05);
          // 1일 보스·강림 레이드 열림
          G.dbForce = false; S.reb.n = 0; S.world = 0; S.quest.main = 5; out.dbLock = !G.dbOpen() && !G.startDBoss(); out.grLock = !G.grOpen() && !G.startGangrim();
          S.reb.n = 1; S.world = 1; G.applyWorld(); G.refreshStats(); S.gr = {day:'', n:0, won:false, pity:0};
          out.grOk = G.startGangrim(); const R3 = G.raid; out.grParty = R3 ? R3.allies.length + 1 : 0;
          const cls = [S.cls].concat(R3 ? R3.allies.map(a => a.cls) : []); out.grCap = Math.max(...Object.values(cls.reduce((m, c) => (m[c] = (m[c] || 0) + 1, m), {})));
          const av0 = Object.keys(S.av.own).filter(k => S.av.own[k]).length; G.grLuck = 100;
          if (R3){ R3.info.fit = null; R3.boss.hp = 0.0001; for (let i = 0; i < 120 && G.raid; i++) G.update(0.05); }
          G.grLuck = null; out.grWon = S.gr.won; out.grAv = Object.keys(S.av.own).filter(k => S.av.own[k]).length - av0;
          out.grEx = G.AVATARS.filter(a => a.src === '강림 레이드' && S.av.own[a.k]).length;
          G.PAT.off = was[0]; G.gateOff = was[1]; Object.assign(S, JSON.parse(keep)); G.applyWorld(); G.refreshStats(); G.quiet = false; return out; }""")
        check(len(nw['doinAtk']) == 5 and 'd_charge' in nw['doinAtk'] and 'd_bagua' in nw['doinAtk'], f'도인 공격 기술은 다섯(도력 일격·팔괘진이 버프 겸 공격) {nw["doinAtk"]}')
        check(nw['party'] and nw['presetHasParty'] and nw['bar'] and nw['pbOn'] and nw['pbAtk'] > 1.05 and nw['after'], f'레이드: 추천 조합(파티 버프 포함)으로 싸우고 끝나면 원래대로, 동료의 파티 버프로 공격력↑ {nw}')
        check(nw['c1'] and abs(nw['mpUsed'] - nw['cost']) < 1.5 and nw['noMp'], f'마나: 기술을 쓰면 마나가 줄고, 모자라면 못 씀 {nw}')
        check(nw['wipeSt'][:3] == [1, 2, 3] and nw['low'] <= 1.5 and nw['diedNoPot'] and nw['livePot'] and nw['potUsed'] >= 1, f'전멸기: 1까지 깎이고 회복약이 없으면 쓰러짐, 있으면 마셔 버팀 {nw}')
        check(nw['dbLock'] and nw['grLock'] and nw['grOk'] and nw['grParty'] == 4 and nw['grCap'] <= 2 and nw['grWon'] and nw['grAv'] >= 1 and nw['grEx'] >= 1,
              f'1일 보스·강림 레이드는 초반엔 잠김, 강림 레이드는 4명(같은 직업 2명까지)·이기면 아바타 {nw}')
        # 6-4k) 2026-11 (42): 장비 공명·세트, 타임 보스 시간대 보상, 천공의 탑, 태초의 신, 결투, 본캐
        nk = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S), was = [G.PAT.off, G.gateOff]; G.quiet = true; G.PAT.off = true; G.gateOff = true;
          if (G.raid){ G.raid.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05); }
          const out = {}; G.setClass('musa'); S.world = 1; S.reb.n = 1; S.level = 150; G.applyWorld();
          // 공명·세트: 전설 무기·갑옷 + 용비늘 망토 + 전설 팔찌 + 청룡 변신 = 해모수의 조합 5세트
          S.gear.weapon.count[16] = Math.max(1, S.gear.weapon.count[16]); S.gear.armor.count[16] = Math.max(1, S.gear.armor.count[16]); S.equip.weapon = 16; S.equip.armor = 16; S.asc = {weapon:0, armor:0};
          S.av.own.p_dragon = true; S.av.cape = ''; S.acc.brace = {g:4, p:80}; S.form.own.cheong = true; S.form.eq = 'cheong'; G.refreshStats();
          const c0 = G.ST.crit + G.ST.critOver; out.res = G.gearRes(); out.set0 = G.setSum().on; S.av.cape = 'p_dragon'; G.refreshStats(); out.set1 = G.setSum().on; out.setUp = +((G.ST.crit + G.ST.critOver) - c0).toFixed(3);
          S.equip.weapon = 4; G.refreshStats(); out.setOff = G.setSum().on.length; out.resLow = G.gearRes(); S.equip.weapon = 16; G.refreshStats();
          // 타임 보스 시간대 보상: 6시 = 무기, 9시 = 치장/보석
          const R = {win:true, info:{diff:'normal', w:new Date(2026, 10, 10, 6).getTime(), bossName:'해태', party:1}}; out.tb6 = G.finishTimeBoss(R).spec;
          // 천공의 탑
          out.ws = [G.towerWS(1), G.towerWS(100), G.towerWS(300)];
          S.tower = {best:0, day:'', n:0, gday:'', gn:0, godWin:0, seed:false, gweek:''}; const g0 = S.gems;
          out.t1 = G.startTower(); out.tPre = G.skPreset; const T1 = G.raid; T1.boss.hp = 0.0001; for (let i = 0; i < 120 && G.raid; i++) G.update(0.05); out.tBest = S.tower.best; out.tGems = S.gems > g0;
          G.startTower(); G.raid.boss.hp = G.raid.boss.maxHp = 1e300; G.raid.time = 0; for (let i = 0; i < 120 && G.raid; i++) G.update(0.05); out.tLeft = G.towerLeft();
          S.tower.best = 49; S.tower.n = 0; G.startTower(); G.raid.boss.hp = 0.0001; for (let i = 0; i < 120 && G.raid; i++) G.update(0.05); out.wing = !!S.av.own.w_cloud;
          // 태초의 신: 전멸기 세 번 문턱, 이기면 엔드 아이템
          G.taechoForce = true; S.inv.potion = 50; out.tc = G.startTaecho(); const TC = G.raid; out.tcWipes = TC && TC.info.wipes.length; TC.boss.hp = TC.boss.maxHp * 0.7; let st1 = false; for (let i = 0; i < 40; i++){ G.update(0.05); if (TC.wipe && TC.wipe.st === 1) st1 = true; }
          out.tcWipe = st1; TC.boss.hp = 0.0001; TC.wipe = {st:4, i:9}; for (let i = 0; i < 200 && G.raid; i++) G.update(0.05); out.godWin = S.tower.godWin; out.seed = S.tower.seed; out.tWing = !!S.av.own.w_taecho; G.taechoForce = false;
          // 결투
          const c = G.pvpCands(); out.pvpN = c.length; const pt0 = S.pvp.pt; out.pv = G.startPvp(c[0]); out.pvPct = !!(G.raid && G.raid.boss.tbPct); G.raid.boss.hp = 0.0001; for (let i = 0; i < 120 && G.raid; i++) G.update(0.05); out.pvUp = S.pvp.pt > pt0 && S.pvp.win >= 1;
          // 결투 상대가 걸어오고(사람 크기) 치거나 기술을 쓰는지(2026-11 (43))
          S.pvp.n = 0; G.startPvp(c[0]); const PB = G.raid.boss; PB.hp = PB.maxHp = PB.maxHp * 1e6; const p0 = [PB.tx, PB.ty]; let hurt = 0, hp = G.hero.hp, mv = false;
          for (let i = 0; i < 200 && G.raid; i++){ G.update(0.05); if (PB.tx !== p0[0] || PB.ty !== p0[1]) mv = true; if (G.hero.hp < hp) hurt++; hp = G.hero.hp; }
          out.pvMove = mv; out.pvHurt = hurt; out.pvSc = PB.sc; out.pvDraw = !!PB.pvpLook; G.raid.time = 0; for (let i = 0; i < 80 && G.raid; i++) G.update(0.05);
          // 보스 도전 기운: 지면 다음 보스 체력이 줄어든다
          const bs0 = S.bossPity; S.bossPity = {k:'', n:0}; out.pity0 = G.bossPityMul(); G.bossFail('시험'); G.bossFail('시험'); out.pity2 = G.bossPityMul(); out.pityN = G.bossPityN(); S.bossPity = bs0;
          out.icons = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].every(i => G.hasSkIcon(i)) && G.skCol(10) !== G.skCol(0);
          // 다른 용사 정보 창(진행도)
          G.quiet = false; G.showUserInfo(Object.assign({}, c[0], {q:50, tw:12, pv:1234, world:1, maxStage:40, job:1, cum:150, rd:G.realDps(), maxHp:G.ST.maxHp}));
          const mb = document.querySelector('#modal'); out.uinfo = !!mb && !mb.hidden && /이야기 진행/.test(mb.textContent) && /1,234점/.test(mb.textContent) && /12 [/] 300층/.test(mb.textContent);
          document.querySelector('#modal-btn-0') && document.querySelector('#modal-btn-0').click(); G.quiet = true;
          out.sumBad = JSON.stringify(G.sumProg({q:1e9, tw:-5, tt:'__proto__', world:99, job:'x'}));
          // (44) 레이드 리셋권 · 신화 보물: 그 부에 가야 낌 · 신화 보물 제작
          S.dummy.n = 3; S.parade.n = 2; S.gems += 1000; S.shop.got = {}; const okR = G.buyShop('rreset'); out.rreset = okR && S.dummy.n === 0 && S.parade.n === 0 && !G.buyShop('rreset');
          const w0 = S.world; S.world = 1; const bagN = S.bag.length; const dm = G.dropMyth(50, 'kusa', true, true); out.mythLock = !!dm.locked && S.bag.length === bagN + 1 && !S.myth.kusa;
          const bid = S.bag.length ? S.bag[S.bag.length - 1].id : -1; out.mythNoEquip = !G.bagEquip(bid) && !S.myth.kusa;
          S.mat.m0 = 5000; S.mat.m1 = 5000; S.mythShard = 500; S.gems += 20000; const acc0 = G.mwMul('acc');
          G.mwLuck = 0; const f1 = G.mwCraft('geumcheok'); G.mwLuck = 1; const s1 = G.mwCraft('geumcheok'); const a1 = G.mwMul('acc');
          G.mwLuck = 0; const u0 = G.mwUp('geumcheok'); G.mwLuck = 1; const u1 = G.mwUp('geumcheok'); const a2 = G.mwMul('acc');
          for (let i = 0; i < 6; i++) G.mwUp('geumcheok'); const a5 = G.mwMul('acc'); G.mwLuck = null;
          out.mc = {fail: !!f1 && !f1.ok, ok: !!s1 && s1.ok && acc0 === 1 && a1 === 1.3, up: !!u0 && !u0.ok && !!u1 && u1.ok && a2 === 1.4,
            cap: a5 === 1.8 && S.mw.geumcheok.lv === 5 && G.mwUp('geumcheok') === null, lockedOk: G.mwCraft('saingeom') === null, a:[acc0, a1, a2, a5]};
          S.mw.geumcheok = {own:false, lv:0, cf:0, uf:0}; G.refreshStats(); S.world = w0;
          // (46) 오장 영약: 부상에서 간·심·비만, 처방 고르기·횟수·다시 달이기·저장 다듬기
          { const w1 = S.world, g1 = S.gold, m1 = S.mat.m2; S.world = 3; S.elix = {o:{}, offer:null, qi:0}; S.gold = 1e300; S.mat.m2 = 1e6; S.gems += 5000; S.grudge = (S.grudge || 0) + 100; G.refreshStats();
            const a0 = G.ST.atk, lockPye = G.elBrew('pye') === null, of = G.elBrew('sim'), two = G.elBrew('gan') === null;
            G.elSt('sim').l = [['atk', 0], ['boss', 0]]; S.elix.offer.c = [{k:'a'}, {k:'qi'}, {k:'big', i:1}];
            const q = G.elPick(1); G.elBrew('sim'); S.elix.offer.c = [{k:'a'}, {k:'b'}, {k:'rest'}]; G.elPick(0);   // 기운 모으기 뒤 +2
            const lvA = G.elSt('sim').l[0][1], tUsed = G.elSt('sim').t; G.refreshStats();
            for (let i = 0; i < 20; i++){ if (!G.elBrew('sim')) break; G.elPick(G.elBestCard()); }
            const done = G.elDone(G.elSt('sim')), atkUp = G.ST.atk > a0, rs = G.elReset('sim') && G.elSt('sim').t === 0 && G.elSt('sim').n === 1;
            G.elBrew('gan'); const m = G.mergeState(JSON.parse(JSON.stringify(S))), keepOf = !!m.elix.offer && m.elix.offer.o === 'gan';
            const bad = JSON.parse(JSON.stringify(S)); bad.elix.o.gan.l = [['__proto__', 99], ['atk', 7]]; bad.elix.offer = {o:'sin', c:[{k:'zz'}]}; const m2 = G.mergeState(bad);
            out.elx = {lockPye, of:!!of && of.c.length === 3, two, q:q && q.k === 'qi', lvA, tUsed, done, atkUp, rs, keepOf, clean:JSON.stringify(m2.elix.o.gan.l) === '[["atk",5],["hp",5]]' && m2.elix.offer === null};
            S.elix = {o:{}, offer:null, qi:0}; S.world = w1; S.gold = g1; S.mat.m2 = m1; G.refreshStats(); }
          // 본캐: 배럭 효과 없음
          const b0 = G.barrack(); G.setMainChar(true); out.main = G.isMainChar() && G.barrack().main && G.barrack().stat === 0; G.setMainChar(false); out.mainOff = !G.isMainChar(); out.brExp = b0.exp <= b0.gain;
          G.PAT.off = was[0]; G.gateOff = was[1]; Object.assign(S, JSON.parse(keep)); G.applyWorld(); G.refreshStats(); G.quiet = false; return out; }""")
        check(nk['res'] == 1 and nk['set1'] and nk['set1'][0][0] == 'haemosu' and nk['set1'][0][1] == 5 and nk['setUp'] >= 0.059 and nk['setOff'] == 0 and nk['resLow'] < 1,
              f'장비 공명(전설 1배)·세트(해모수의 조합 5세트, 무기·갑옷이 안 맞으면 꺼짐) {nk}')
        check(any('검' in x or '무기' in x or '신령' in x for x in nk['tb6']), f'타임 보스: 6시는 무기를 준다 {nk["tb6"]}')
        check(nk['ws'][0][0] == 0 and nk['ws'][1][0] == 1 and nk['ws'][2][0] == 4 and nk['t1'] and nk['tPre'] is None and nk['tBest'] == 1 and nk['tGems'] and nk['tLeft'] == 4 and nk['wing'],
              f'천공의 탑: 층마다 정해진 세기, 저절로 조합 안 바꿈, 지면 하루 횟수 하나, 50층 날개 {nk}')
        check(nk['tc'] and nk['tcWipes'] == 3 and nk['tcWipe'] and nk['godWin'] == 1 and nk['seed'] and nk['tWing'], f'태초의 신: 전멸기 세 번, 이기면 태초의 씨앗·태초의 날개 {nk}')
        check(nk['pvpN'] >= 1 and nk['pv'] and nk['pvPct'] and nk['pvUp'], f'결투: 상대 목록에서 골라 싸우고 이기면 점수 {nk}')
        check(nk['pvMove'] and nk['pvHurt'] >= 1 and nk['pvSc'] == 1 and nk['pvDraw'], f'결투 상대가 용사 크기로 걸어오고 공격한다 {nk}')
        check(nk['pity0'] == 1 and nk['pityN'] == 2 and abs(nk['pity2'] - 0.90) < 1e-9, f'보스 도전 기운: 두 번 지면 보스 체력 -10% {nk}')
        check(nk['icons'], f'기술 아이콘이 모두 있고(파티 버프 포함) 칸마다 색이 다르다 {nk}')
        E = nk['elx']
        check(E['lockPye'] and E['of'] and E['two'] and E['q'] and E['lvA'] == 2 and E['tUsed'] == 2 and E['done'] and E['atkUp'] and E['rs'] and E['keepOf'] and E['clean'],
              f'오장 영약: 부상에선 폐가 잠김·처방 세 장·한 번에 한 장만·기운 모으기 뒤 +2·횟수를 다 쓰면 굳음·공격력↑·다시 달이기·처방 저장·나쁜 값 다듬기 {E}')
        check(nk['rreset'] and nk['mythLock'] and nk['mythNoEquip'] and nk['mc']['fail'] and nk['mc']['ok'] and nk['mc']['up'] and nk['mc']['cap'] and nk['mc']['lockedOk'],
              f'레이드 리셋권(하루 1번)·2부 신화 보물은 부상 전엔 가방에서 못 낌·신화 제작 장비(제작 실패·성공 1.3배·강화 1.4배·+5 1.8배 상한·땅 제한) {nk.get("rreset")} {nk.get("mythLock")} {nk.get("mythNoEquip")} {nk.get("mc")}')
        check(nk['uinfo'] and '"tt":""' in nk['sumBad'] and '"tw":0' in nk['sumBad'] and '"world":7' in nk['sumBad'], f'다른 용사 정보 창: 이야기·탑·결투 점수가 보이고 남이 보낸 값은 다듬는다 {nk.get("uinfo")} {nk.get("sumBad")}')
        check(nk['main'] and nk['mainOff'] and nk['brExp'], f'본캐는 배럭 효과를 받지 않음, 배럭 경험치는 엽전보다 적게 {nk}')

        # 6-5) 2부 부상: 바다 건너기(레벨 이어 감), 부상 레이드, 3차 전직, 장 제목 카드
        bs = await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true; G.closePage(); G.setClass('musa');
          if (S.world < 2){ S.world = 2; S.reb.n = 2; }
          S.level = 290; S.best.l2 = Math.max(S.best.l2, 290); Object.assign(S.up, {atk: 900, hp: 900, crit: 80, critDmg: 120, aspd: 60, regen: 40});
          S.refine.weapon.lv = 25; S.refine.weapon.t = 0; const effW0 = G.refineEff('weapon');
          S.mat.m0 = 7; S.mat.m1 = 11; const m2a = S.mat.m2 || 0; S.inh = {w:2};
          const before = G.crossReady(); S.quest.main = G.CROSS_Q; const ready = G.crossReady(); const ok = G.doCross(); G.refreshStats();
          const after = {world: S.world, lv: S.level, st: S.stage, region: G.BUSANG_REGIONS[0].name};
          // (48) 계승은 대장장이가: 건넌 직후엔 그대로(+25·계승 전), 대상 목록에 재료·재련이 있고, 계승하면 효과 그대로 +15부터·재료는 하늘 조각으로
          const pre = {t: S.refine.weapon.t, lv: S.refine.weapon.lv, pend: G.inhPending(), kinds: G.inhList().map(r => r.kind + ':' + (r.slot || r.j || ''))};
          G.inhDo();
          const inh = {t: S.refine.weapon.t, lv: S.refine.weapon.lv, keep: Math.abs(G.refineEff('weapon') - effW0) < 1e-6, cap: G.refineCap('armor'), pre,
            mat: S.mat.m0 === 0 && S.mat.m1 === 0 && S.mat.m2 === m2a + 18, w: S.inh.w, pend2: G.inhPending()};
          S.best.s3 = 8; S.raid.tk = 3; const r0 = G.startRaid(0); const name = G.raid && G.raid.info.bossName;
          for (let i = 0; i < 4000 && G.raid; i++) G.update(0.05);
          S.level = 360; S.quest.main = G.MAIN_Q.findIndex(q => q.ch === 34);
          const jr = G.jobReady(3); const tr = G.startJobTrial(3); for (let i = 0; i < 4000 && G.raid; i++) G.update(0.05);
          return {before, ready, ok, after, inh, r0, name, b0: !!S.raid.first.b0, jr, tr, job: S.job, jobC: S.skills.jobC, cape: S.av.cape}; }""")
        check(bs['inh']['pre']['t'] == 0 and bs['inh']['pre']['lv'] == 25 and bs['inh']['pre']['pend'] and 'refine:weapon' in bs['inh']['pre']['kinds'] and 'mat:1' in bs['inh']['pre']['kinds']
              and bs['inh']['t'] == 1 and bs['inh']['lv'] == 15 and bs['inh']['keep'] and bs['inh']['cap'] == 25 and bs['inh']['mat'] and bs['inh']['w'] == 3 and not bs['inh']['pend2'],
              f'2부: 바다를 건너면 대장장이가 계승(재련 +15부터·효과 그대로, 지난 땅 재료 → 하늘 조각) {bs["inh"]}')
        check(not bs['before'] and bs['ready'] and bs['ok'] and bs['after']['world'] == 3 and bs['after']['lv'] == 290 and bs['after']['st'] == 1,
              f'2부: 천계 이야기를 마치면 바다를 건너 부상으로 가고, 레벨은 그대로 단계만 1부터 {bs["after"]}')
        check(bs['r0'] and bs['name'] == '갓파 대왕' and bs['b0'], f'2부: 부상 레이드(갓파 대왕)를 토벌한다 {bs["name"]}')
        check(bs['jr'] and bs['tr'] and bs['job'] == 3 and bs['jobC'] == 1 and bs['cape'] == 'j_musa_3', f'2부: Lv.350·스승의 장을 마치면 3차 전직(풍뢰장)과 3차 기술 {bs}')
        await page.evaluate("() => { const G = window.__game; G.quiet = false; G.showChapterCard(26); }")
        await page.wait_for_timeout(500)
        card = await page.evaluate("() => { const el = document.querySelector('#chcard'); return el ? el.textContent : ''; }")
        check('제26장' in card and '바다 건너 온 원한' in card, f'장이 바뀌면 장 제목 카드가 나온다 {card}')
        await page.screenshot(path=str(OUT / '31_부상_장제목.png'))
        await page.evaluate("() => { const G = window.__game; G.quiet = true; G.setStage(25); }")
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(OUT / '32_부상_구라마산.png'))

        # 6-6) 3부 곤륜: 서쪽 하늘로 건너기, 곤륜 레이드, 4차 전직(세 스승의 시험 세 판), 10번째 기술
        kl = await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true; G.closePage(); G.setClass('musa');
          if (S.world < 3){ S.world = 3; } S.level = 400; S.best.l3 = 400; S.job = Math.max(S.job, 3); G.unlockSkills();
          Object.assign(S.up, {atk: 1600, hp: 1600, crit: 90, critDmg: 160, aspd: 80, regen: 60});
          S.quest.main = G.CROSS_Q4; const ready = G.crossReady(); const ok = G.doCross(); G.refreshStats();
          const after = {world: S.world, lv: S.level, st: S.stage, region: G.KUNLUN_REGIONS[0].name};
          // (48) 곤륜에서는 재련 2차 계승(그때까지의 효과는 그대로, +15부터 다시)
          S.refine.weapon.lv = 22; G.refreshStats(); const e0 = G.refineEff('weapon'), ip = G.inhPending(); G.inhDo();
          const inh2 = {gen: G.refineGen(), p: ip, t: S.refine.weapon.t, lv: S.refine.weapon.lv, keep: Math.abs(G.refineEff('weapon') - e0) < 1e-6, more: G.refineEff('weapon', 25) > e0, pend2: G.inhPending()};
          S.best.s4 = 8; S.raid.tk = 3; const r0 = G.startRaid(0); const name = G.raid && G.raid.info.bossName;
          for (let i = 0; i < 4000 && G.raid; i++) G.update(0.05);
          S.level = G.JOB4_LV || 480; S.quest.main = G.MAIN_Q.findIndex(q => q.ch === 44);
          const jr = G.jobReady(4); const tr = G.startJobTrial(4); const steps = [];
          for (let i = 0; i < 12000 && (G.raid || S.job < 4); i++){ G.update(0.05); if (G.raid && !steps.includes(G.raid.info.bossName)) steps.push(G.raid.info.bossName); }
          return {ready, ok, after, inh2, r0, name, k0: !!S.raid.first.k0, jr, tr, steps, job: S.job, jobD: S.skills.jobD, cape: S.av.cape}; }""")
        check(kl['inh2']['gen'] == 2 and kl['inh2']['p'] and kl['inh2']['t'] == 2 and kl['inh2']['lv'] == 15 and kl['inh2']['keep'] and kl['inh2']['more'] and not kl['inh2']['pend2'],
              f'3부: 곤륜에 건너면 대장장이가 재련을 2차 계승(효과 그대로 +15부터, 다시 올리면 더 셈) {kl["inh2"]}')
        check(kl['ready'] and kl['ok'] and kl['after']['world'] == 4 and kl['after']['lv'] == 400 and kl['after']['st'] == 1,
              f'3부: 부상 이야기를 마치면 곤륜으로 건너가고, 레벨은 그대로 단계만 1부터 {kl["after"]}')
        check(kl['r0'] and kl['k0'], f'3부: 곤륜 레이드(열 개의 해)를 토벌한다 {kl["name"]}')
        check(kl['jr'] and kl['tr'] and len(kl['steps']) == 3 and kl['job'] == 4 and kl['jobD'] >= 1 and kl['cape'] == 'j_musa_4',
              f'3부: 세 스승의 시험(세 판)을 넘으면 4차 전직(개천왕)과 10번째 기술 {kl}')

        # 6-6b) 계승(대장장이)·재료 수급처·재료 말풍선·저승 초입 레이드 부탁(2026-11 (48))
        ih = await page.evaluate("""() => { const G = window.__game, S = G.S; window.__keep48 = JSON.stringify(S); G.quiet = true; G.closePage(); G.setClass('musa');
          S.world = 1; S.reb.n = Math.max(1, S.reb.n); S.level = 5; S.maxStage = 3; S.stage = 3; S.best.s1 = 3; S.best.s0 = 101; G.applyWorld(); G.setStage(3);
          S.inh = {w:0}; S.mat = {m0:40, m1:0, m2:0}; S.craft.w.t = 2; S.craft.w.f = 0; S.craft.w.e = G.ENGR_BEST.musa.w; S.craft.w.e2 = ''; G.refreshStats();
          const n0 = G.craftNeed('w'), list = G.inhList().map(r => r.kind), pend = G.inhPending();
          G.inhDo(); const mat = Object.assign({}, S.mat); S.mat.m1 = 80; const ok = G.craft('w');
          const out = {n0:{mat:n0.mat, past:!!n0.past, rate:n0.rate, gear:n0.gearSlot || null, mk:n0.mk}, list, pend, mat, ok, t:S.craft.w.t, left:S.mat.m1, w:S.inh.w, pend2:G.inhPending()};
          G.questGo({c:'raids'}); const on = document.querySelector('.qsegb.on'); out.rv = on ? on.dataset.rv : ''; out.rUnlocked = G.raidUnlocked(); G.closePage();
          S.gold = 1e300; S.gems += 1000; S.shop.got = {}; const mA = S.mat.m1, sA = S.mythShard || 0; const b1 = G.buyShop('matbag'), b2 = G.buyShop('shardbag');   // 신화 조각은 상점에서 안 팖
          out.shop = b1 && !b2 && S.mat.m1 === mA + G.MAT_SRC.shop && S.mythShard === sA && !G.SHOP.some(x => x.id === 'shardbag'); out.drop = [G.MAT_DROP.boss, G.MAT_DROP.gate, G.MAT_DROP.raid, G.MAT_SRC.dummy[5]];
          S.mode = 'semi'; S.bossAuto = false; S.autoBoss = false; G.buildTab('gear'); return out; }""")
        check(ih['pend'] and 'mat' in ih['list'] and ih['mat']['m0'] == 0 and ih['mat']['m1'] == 40 and ih['w'] == 1 and not ih['pend2'],
              f'계승: 저승에 오면 지난 땅 재료(요괴 정수)가 망자의 넋으로 그대로 계승된다 {ih}')
        check(ih['n0']['past'] and ih['n0']['mat'] == 75 and ih['n0']['rate'] == 100 and ih['n0']['gear'] is None and ih['n0']['mk'] == 'm1' and ih['ok'] is True and ih['t'] == 3 and ih['left'] == 5,
              f'계승 조합: 지난 땅의 밀린 조합식은 재료 절반·장비 조건 없음·확정 성공 {ih["n0"]} {ih["ok"]} {ih["t"]} {ih["left"]}')
        check(ih['rUnlocked'] == 0 and ih['rv'] in ('dummy', 'parade', 'vault', 'tb'), f'저승 초입(레이드 잠김)의 레이드 부탁 「바로 가기」는 지금 할 수 있는 칸으로 간다 {ih["rv"]}')
        check(ih['shop'] and ih['drop'] == [2, 4, 6, 12], f'재료 수급처: 상점 재료 꾸러미(신화 조각은 안 팖), 드롭량(물의 신화에서 수문장 4·레이드 6으로 조임) {ih["shop"]} {ih["drop"]}')
        await page.wait_for_timeout(200); await page.click('#seg-craft'); await page.wait_for_timeout(250)
        await page.click('.mat.mtip[data-mtip="m1"]'); await page.wait_for_timeout(200)
        tipt = await page.evaluate("() => (document.querySelector('#tipB') || {}).textContent || ''")
        await page.screenshot(path=str(OUT / '6_재료말풍선.png'))
        check('어디에 쓰나요' in tipt and '어디서 얻나요' in tipt and '망자의 넋' in tipt, f'재료 이름을 누르면 쓰임새·얻는 곳 말풍선이 뜬다 {tipt[:60]}')
        await page.evaluate("() => { const G = window.__game, S = G.S; G.closePage(); S.mat.m0 = 12; S.inh = {w:0}; G.quiet = false; G.noInh = false; }")
        await page.wait_for_function("() => window.__game.inhOpen", timeout=8000)
        await page.wait_for_timeout(400); await page.screenshot(path=str(OUT / '6_계승_대장장이.png'))
        ih1 = await page.evaluate("() => ({rows: document.querySelectorAll('#inh .inh-row').length, say: (document.querySelector('#inhSay') || {}).textContent || '', go: !!document.querySelector('#inhGo'), later: !!document.querySelector('#inhLater')})")
        await page.click('#inhGo'); await page.wait_for_timeout(700); await page.screenshot(path=str(OUT / '6_계승_연출.png'))
        await page.wait_for_function("() => { const b = document.querySelector('#inh button.primary'); return b && b.textContent === '좋아요!'; }", timeout=15000)
        await page.wait_for_timeout(300); await page.screenshot(path=str(OUT / '6_계승_완료.png'))
        await page.click('#inh button.primary'); await page.wait_for_timeout(200)
        ih2 = await page.evaluate("""() => { const G = window.__game, S = G.S; const out = {m0: S.mat.m0, open: G.inhOpen, hidden: document.querySelector('#inh').hidden, w: S.inh.w, done: document.querySelectorAll('#inh .inh-row.done').length};
          G.noInh = true; G.quiet = true; Object.assign(S, JSON.parse(window.__keep48)); G.applyWorld(); G.refreshStats(); G.setStage(S.stage); G.quiet = false; return out; }""")
        check(ih1['rows'] >= 1 and ih1['go'] and ih1['later'] and '저승' in ih1['say'] and ih2['m0'] == 0 and not ih2['open'] and ih2['hidden'] and ih2['w'] == 1,
              f'계승 화면: 새 땅 첫 화면에 대장장이가 나타나 대상을 보여 주고, [계승하기]를 누르면 연출 뒤 닫힌다 {ih1} {ih2}')

        # 6-6z) 물의 신화 2단계: 부별 탭·거르기·도감, 알림 연출 틀(한 번에 하나·두루마리·줄이기·다시 보기)
        pt = await page.evaluate("""() => { const G = window.__game, S = G.S; window.__keepPt = JSON.stringify(S); G.quiet = true;
          for (const k of ['tab', 'own', 'sort', 'kd']) for (const x of Object.keys(G.PV[k])) delete G.PV[k][x];
          const tabs = () => [...document.querySelectorAll('.partbar .ptab')].map(b => b.dataset.ptab + (b.classList.contains('on') ? '*' : '') + (b.classList.contains('lock') ? 'L' : '') + (b.querySelector('.dot') ? '!' : ''));
          const vis = () => [...document.querySelectorAll('#panel [data-part]')].filter(e => !e.classList.contains('part-off')).map(e => +e.dataset.part);
          S.pseen = {}; S.world = 0; for (let i = 0; i < 15; i++) S.pets.lv[i] = i < 6 ? 1 : 0; for (let i = 15; i < S.pets.lv.length; i++) S.pets.lv[i] = 0;
          G.buildTab('pet'); const t0 = tabs(), v0 = vis();
          document.querySelector('.ptab.lock').click(); const lockKept = G.PV.tab.pet == null;      // 잠긴 부는 눌러도 안 열림
          S.world = 4; G.buildTab('pet'); const t4 = tabs(), v4 = vis();                        // 곤륜(3부): 처음 열리는 탭 = 지금 있는 부
          document.querySelector('[data-ptab="0"]').click(); const vAll = vis().length;
          document.querySelector('[data-pf="own"]').click(); const vOwn = vis().length;
          document.querySelector('[data-pkd="atk"]').click(); const vAtk = [...document.querySelectorAll('#panel [data-part]:not(.part-off)')].map(e => e.dataset.kd);
          document.querySelector('[data-pkd=""]').click(); document.querySelector('[data-pf="own"]').click();
          document.querySelector('[data-ptab="3"]').click(); S.pets.lv[7] = 1; G.partApply(); const dot = tabs();   // 다른 부(1부)에서 새로 얻으면 그 탭에 빨간 점
          document.querySelector('[data-ptab="1"]').click(); const dot2 = tabs(), isNew = document.querySelector('[data-pk="p7"]').classList.contains('part-new') || S.pseen.pet.includes('p7');
          S.raid.first = {'0':true, h1:true, g2:true, b0:true}; G.buildTab('raid'); document.querySelector('[data-rv="raid"]').click(); const rt = tabs(), past = document.querySelectorAll('.rcard.jin').length, pastVis = [...document.querySelectorAll('.rcard.jin')].filter(e => !e.closest('.part-off')).length;
          document.querySelector('[data-ptab="1"]').click(); const rt1 = tabs(), r1 = vis(), curHidden = !!document.querySelector('#raid-0').closest('.part-off');
          document.querySelector('[data-ptab="3"]').click();
          G.buildTab('rec'); const dexRows = document.querySelectorAll('#dexBox tbody tr').length, dex = [1, 2, 3].map(p => G.dexSum(p)), dexT = ['dex1', 'dex2', 'dex3'].every(k => G.TITLES.some(t => t.k === k));
          return {t0, v0n: v0.length, v0max: Math.max(...v0), lockKept, t4, v4, vAll, vOwn, vAtk, dot, dot2, isNew, rt, past, pastVis, rt1, r1: [...new Set(r1)], curHidden, dexRows, dex, dexT}; }""")
        await page.screenshot(path=str(OUT / '6z_도감.png'))
        await page.evaluate("() => { const G = window.__game; G.buildTab('pet'); document.querySelector('[data-ptab=\"0\"]').click(); }")
        await page.wait_for_timeout(300); await page.screenshot(path=str(OUT / '6z_부별탭_펫.png'))
        await page.evaluate("() => { const G = window.__game; G.buildTab('raid'); document.querySelector('[data-rv=\"raid\"]').click(); document.querySelector('[data-ptab=\"1\"]').click(); }")
        await page.wait_for_timeout(400); await page.screenshot(path=str(OUT / '6z_부별탭_레이드.png'))
        await page.evaluate("() => { const G = window.__game, S = G.S; G.closePage(); Object.assign(S, JSON.parse(window.__keepPt)); for (const k of ['tab', 'own', 'sort', 'kd']) for (const x of Object.keys(G.PV[k])) delete G.PV[k][x]; G.applyWorld(); G.refreshStats(); G.setStage(S.stage); G.quiet = false; }")
        check(pt['t0'] == ['0', '1*', '2L', '3L', '4L'] and pt['v0n'] == 15 and pt['v0max'] == 1 and pt['lockKept'], f'부별 탭: 1부에서는 2부·3부 탭이 잠겨 있고 그 부의 펫은 안 보인다 {pt["t0"]} {pt["v0n"]}')
        check(pt['t4'] == ['0', '1', '2', '3*', '4L'] and set(pt['v4']) == {3} and pt['vAll'] == 29 and pt['vOwn'] == 6 and pt['vAtk'] and set(pt['vAtk']) == {'atk'},
              f'부별 탭: 처음 열리는 탭은 지금 있는 부, 「전체」·「가진 것만」·종류 거르기가 된다 {pt["t4"]} {pt["vAll"]} {pt["vOwn"]} {pt["vAtk"]}')
        check('1!' in pt['dot'] and '1*' in pt['dot2'] and pt['isNew'], f'부별 탭: 다른 부에서 새로 얻은 것이 있으면 그 탭에 빨간 점, 열어 보면 사라진다 {pt["dot"]} {pt["dot2"]}')
        check(pt['rt'] == ['0', '1', '2', '3*', '4L'] and pt['past'] == 34 and pt['pastVis'] == 0 and pt['r1'] == [1] and pt['curHidden'],
              f'레이드 목록: 부별 탭으로 지나온 땅의 레이드(상위 단계 「진」 칸)를 본다(이승 8·저승 10·천계 8·부상 8) {pt["rt"]} {pt["past"]} {pt["rt1"]}')
        check(pt['dexRows'] == 3 and all(d[1] > 0 for d in pt['dex']) and pt['dexT'], f'도감: [정보]에 부별 모음 현황(펫·탈것·아바타·치장·넋 구슬)과 부별 별호 {pt["dex"]}')
        # 알림 연출 틀: 여럿이면 중요한 것 하나만 저절로(계승 > 8칸), 나머지는 왼쪽 위 두루마리. 「줄이기」면 한 줄 띠로만. [정보]에서 다시 보기
        await page.evaluate("""() => { const G = window.__game, S = G.S; window.__keepNt = JSON.stringify(S); G.quiet = true; G.closePage(); S.world = 1; S.level = Math.min(S.level, 200); G.applyWorld(); G.refreshStats(); G.setStage(1);
          S.mat.m0 = 9; S.inh = {w:0}; S.skNote = true; S.noti = {seen:{'jin:w0':1}, log:[]}; G.notiAuto.clear(); G.setNotiLite(false); G.noInh = false; G.noSkNote = false; G.quiet = false; }""")
        await page.wait_for_function("() => window.__game.inhOpen", timeout=8000)
        nt1 = await page.evaluate("() => ({smith: !!document.querySelector('#inhGo'), noti: document.querySelector('#inh').classList.contains('noti')})")
        await page.click('#inhLater'); await page.wait_for_timeout(900)
        nt2 = await page.evaluate("() => ({open: window.__game.inhOpen, btn: !document.querySelector('#notiBtn').hidden, cnt: document.querySelector('#notiCnt').textContent, list: window.__game.notiList().map(n => n.k)})")
        await page.screenshot(path=str(OUT / '6z_알림_두루마리.png'))
        await page.click('#notiBtn'); await page.wait_for_selector('#notiPick [data-nk="sk8"]'); await page.screenshot(path=str(OUT / '6z_알림_모음.png'))
        await page.click('#notiPick [data-nk="sk8"]'); await page.wait_for_selector('#inh.noti #notiSay'); await page.wait_for_timeout(500)
        await page.screenshot(path=str(OUT / '6z_알림_까치.png'))
        await page.click('#inh .inh-say'); await page.wait_for_timeout(200); await page.click('#notiLater'); await page.wait_for_timeout(300)
        nt3 = await page.evaluate("""() => { const G = window.__game, S = G.S; const out = {open: G.inhOpen, note: S.skNote, log: S.noti.log.map(x => x.k), list: G.notiList().map(n => n.k)};
          S.skNote = true; S.noti.seen = {'jin:w0':1}; G.notiAuto.clear(); G.setNotiLite(true); return out; }""")
        await page.wait_for_function("() => document.querySelector('#notiBtn').classList.contains('say')", timeout=5000)
        nt4 = await page.evaluate("() => ({open: window.__game.inhOpen, tx: document.querySelector('#notiTx').textContent, lite: window.__game.notiLite})")
        await page.screenshot(path=str(OUT / '6z_알림_한줄띠.png'))
        await page.evaluate("() => { const G = window.__game; G.setNotiLite(false); G.noInh = true; G.noSkNote = true; G.buildTab('rec'); document.querySelector('#notiReviewBtn').click(); }")
        await page.wait_for_selector('#notiPick [data-ni]'); rv = await page.evaluate("() => document.querySelectorAll('#notiPick [data-ni]').length")
        await page.click('#notiPick [data-ni]'); await page.wait_for_function("() => window.__game.inhOpen"); await page.wait_for_timeout(300)
        nt5 = await page.evaluate("""() => { const G = window.__game, S = G.S; const b = document.querySelector('#notiLater') || document.querySelector('#inhLater') || document.querySelector('#inhOk'); const out = {btn: b ? b.textContent : ''}; if (b) b.click();
          G.quiet = true; G.closePage(); Object.assign(S, JSON.parse(window.__keepNt)); G.notiAuto.clear(); G.applyWorld(); G.refreshStats(); G.setStage(S.stage); G.quiet = false; return out; }""")
        # 업데이트 소식: 이야기꾼 할머니가 세 줄로 간추려 알리고 [자세히]는 소식 창
        await page.evaluate("() => { const G = window.__game; G.closePage(); localStorage.setItem('samhan-note-seen', 'old'); G.notiAuto.clear(); G.noNoti = false; }")
        await page.wait_for_selector('#inh.noti #notiSay', timeout=6000); await page.wait_for_timeout(500)
        await page.screenshot(path=str(OUT / '6z_알림_소식.png'))
        nw1 = await page.evaluate("() => ({who: document.querySelector('#inh .nm').textContent, say: document.querySelector('#notiSay').textContent, chips: document.querySelectorAll('#inh .pre-sk').length})")
        for _ in range(4): await page.click('#inh .inh-say'); await page.wait_for_timeout(120)
        await page.click('#notiGo'); await page.wait_for_selector('#mTitle:has-text("업데이트 소식")')
        nw2 = await page.evaluate("() => { const G = window.__game; const out = {seen: localStorage.getItem('samhan-note-seen') !== 'old', open: G.inhOpen, list: G.notiList().map(n => n.k)}; G.hideModal(); G.noNoti = true; return out; }")
        check('할머니' in nw1['who'] and '물의 신화' in nw1['say'] and nw1['chips'] >= 3 and nw2['seen'] and not nw2['open'] and 'news' not in nw2['list'],
              f'업데이트 소식: 이야기꾼 할머니가 찾아와 간추려 주고 [자세히]로 소식 창을 연다(기기마다 한 번) {nw1} {nw2}')
        # 자리 비움 → 절전 모드(2-1단계): 10분 동안 안 누르면 30초 예고(누르면 취소) → 저장하고 게임을 멈춤 → 누르면 오프라인 보상과 함께 돌아옴
        af0 = await page.evaluate("() => { const G = window.__game; G.quiet = false; G.closePage(); if (!document.querySelector('#modal').hidden) G.hideModal(); G.afkTest = true; G.setAfk(10); G.addTime(10 * 60 * 1000 + 2000); return G.afkMin; }")
        await page.wait_for_selector('#afkWarn:not([hidden])', timeout=6000)
        await page.screenshot(path=str(OUT / '6y_자리비움_예고.png'))
        await page.mouse.click(420, 200); await page.wait_for_timeout(500)      # 화면을 누르면 취소
        af1 = await page.evaluate("() => ({warn: !document.querySelector('#afkWarn').hidden, sleep: window.__game.sleepAt})")
        await page.evaluate("() => window.__game.addTime(10 * 60 * 1000 + 2000)"); await page.wait_for_selector('#afkWarn:not([hidden])', timeout=6000)
        await page.evaluate("() => window.__game.addTime(31000)"); await page.wait_for_selector('#sleep:not([hidden])', timeout=6000)
        af2 = await page.evaluate("""async () => { const G = window.__game, S = G.S, p0 = S.rec.play, k0 = S.rec.kills, s0 = S.lastSave; await new Promise(r => setTimeout(r, 1300)); G.saveLocal();
          return {sleep: G.sleepAt > 0, saved: Math.abs(G.sleepAt - s0) < 2000, frozen: S.rec.play === p0 && S.rec.kills === k0, keep: S.lastSave === s0, txt: document.querySelector('#sleep').textContent}; }""")
        await page.screenshot(path=str(OUT / '6y_절전모드.png'))
        lv0 = await page.evaluate("() => { const G = window.__game; G.addTime(2 * 3600 * 1000); return [G.S.gold, G.S.rec.kills]; }")
        await page.wait_for_timeout(400); slt = await page.inner_text('#slTime')
        await page.click('#sleep'); await page.wait_for_selector('#mTitle:has-text("다녀오셨습니까")', timeout=6000)
        af3 = await page.evaluate("""() => { const G = window.__game, S = G.S; const out = {sleep: G.sleepAt, hidden: document.querySelector('#sleep').hidden, gold: S.gold, kills: S.rec.kills}; G.hideModal(); G.afkTest = false; return out; }""")
        check(af0 == 10 and not af1['warn'] and not af1['sleep'], f'자리 비움: 10분 동안 누르지 않으면 예고가 뜨고, 화면을 누르면 취소된다 {af0} {af1}')
        check(af2['sleep'] and af2['saved'] and af2['frozen'] and af2['keep'] and '절전 모드' in af2['txt'] and '2시간' in slt, f'절전 모드: 예고 30초 뒤 저장하고 게임 진행을 멈춘다(저장 시각은 그대로) {af2} {slt}')
        check(af3['sleep'] == 0 and af3['hidden'] and (af3['gold'] > lv0[0] or af3['kills'] > lv0[1]), f'절전 모드에서 화면을 누르면 그 시각부터의 오프라인 보상 창과 함께 돌아온다 {af3} {lv0}')
        check(nt1['smith'] and not nt1['noti'] and not nt2['open'] and nt2['btn'] and nt2['cnt'] == '2' and nt2['list'] == ['inh', 'sk8'],
              f'알림 연출 틀: 알릴 것이 여럿이면 중요한 것(계승) 하나만 저절로 찾아오고 나머지는 왼쪽 위 두루마리에 모인다 {nt1} {nt2}')
        check(not nt3['open'] and not nt3['note'] and nt3['log'][0] == 'sk8' and nt3['list'] == ['inh'], f'알림 연출 틀: 두루마리에서 골라 보면 본 것으로 적히고 목록에서 빠진다(계승은 할 때까지 남음) {nt3}')
        check(not nt4['open'] and ('까치' in nt4['tx'] or '계승' in nt4['tx']) and nt4['lite'] and rv >= 1 and nt5['btn'], f'알림 연출 줄이기: 인물 대신 한 줄 띠로만 알리고, [정보] → 알림 다시 보기로 지난 알림을 다시 본다 {nt4} {rv} {nt5}')

        # 6-7) 탈것: 지난 이야기 보상으로 받기, 마구간(엽전)·고삐 조각으로 얻기, 별 올리기, 타면 걷기·능력
        mt = await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true;
          const st0 = G.heroStep(), atk0 = G.ST.atk; G.mountCatchUp(); const own = Object.keys(S.mount.own).sort();
          S.gold = 1e300; const bd = G.buyMount('donkey'); S.mount.piece = 100; const bc = G.buyMount('cheolli'); const su = G.mountStarUp('girin');
          G.rideMount('girin'); G.refreshStats();
          return {own, bd, bc, su, star: S.mount.star.girin, ride: S.mount.ride, st0, st1: G.heroStep(), atk0, atk1: G.ST.atk, col: G.mountCol(), cdr: G.rideAb('cdr')}; }""")
        check(all(k in mt['own'] for k in ['kwaha', 'eunglong', 'haetae', 'baekrok', 'girin']) and mt['bd'] and mt['bc'] and mt['su'] and mt['star'] == 1,
              f'탈것: 이야기에서 받은 탈것이 채워지고, 마구간·고삐 조각으로 얻고, 별을 올린다 {mt}')
        check(mt['ride'] == 'girin' and mt['st1'] < mt['st0'] * 0.7 and mt['atk1'] > mt['atk0'] and mt['cdr'] > 12,
              f'탈것: 기린을 타면 걷기가 빨라지고 공격력(모음 효과)·재사용 줄이기가 붙는다 {mt}')
        # 6-8) 마을 부탁 100개: 세계별 개수, 이야기 진행에 맞춰 열림, 곤륜 부탁은 보상이 크고 고삐 조각도
        sq = await page.evaluate("""() => { const G = window.__game, S = G.S, m0 = S.quest.main;
          const cnt = [0, 1, 2, 3, 4].map(w => G.SUB_Q.filter(q => q.w === w).length);
          const openAt = n => { S.quest.main = n; return G.SUB_Q.filter(q => G.subOpen(q)).length; };
          const o0 = openAt(0), o1 = openAt(G.PART1_END), o2 = openAt(G.PART2_END), o3 = openAt(G.MAIN_Q.length);
          S.quest.main = m0; S.sub.act = {}; delete S.sub.done.z1; const g0 = S.gems, p0 = S.mount.piece, d0 = S.dust;
          G.acceptSub('z1'); S.rec.kills += 1500; G.claimSub('z1'); const ok = !!S.sub.done.z1;
          return {cnt, o0, o1, o2, o3, ok, gem: S.gems - g0, piece: S.mount.piece - p0, dust: S.dust - d0, kmax: Math.max(...G.SUB_Q.filter(q => q.c === 'kills').map(q => q.n))}; }""")
        check(sq['cnt'] == [10, 10, 10, 30, 40] and sq['o0'] == 1 and 30 <= sq['o1'] <= 31 and 60 <= sq['o2'] <= 62 and sq['o3'] == 100 and sq['kmax'] <= 1500,
              f'마을 부탁 100개: 이승 10·저승 10·천계 10·부상 30·곤륜 40, 이야기 진행에 맞춰 열린다 {sq}')
        check(sq['ok'] and sq['gem'] >= 6000 and sq['piece'] >= 2 and sq['dust'] > 0, f'마을 부탁: 곤륜 부탁은 보석·쇳가루·고삐 조각을 크게 준다 {sq}')
        ac = await page.evaluate("""() => { const G = window.__game, S = G.S, q = G.SUB_Q.find(x => x.k === 'f6'); S.sub.act = {}; delete S.sub.done.f6;
          S.refine.weapon.t = 0; S.refine.weapon.lv = 12; const g0 = S.gems; G.acceptSub('f6'); return {done: !!S.sub.done.f6, act: !!S.sub.act.f6, gems: S.gems - g0, c: q.c, n: q.n}; }""")
        check(ac['done'] and not ac['act'] and ac['gems'] > 0 and ac['c'] == 'refW', f'마을 부탁: 이미 이룬 재련 단계면 받자마자 저절로 끝난다 {ac}')
        # 6-8b) 마을 부탁 가볍게·막히지 않게(지나온 땅은 바로 완료·보스 부탁은 무엇이든·2시간 뒤 완료)·치명타 100% 넘침
        lt = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          const f3 = G.SUB_Q.find(x => x.k === 'f3'), light = f3.n0 === 3 && f3.n === 2 && f3.story.includes('2번');
          const kmax = Math.max(...G.SUB_Q.filter(q => q.c === 'kills').map(q => q.n));
          S.sub.act = {}; delete S.sub.done.f3; S.world = 1; G.acceptSub('f3'); const past = !!S.sub.done.f3 && !S.sub.act.f3;
          S.world = 0; S.quest.main = G.MAIN_Q.findIndex(q => q.ch === G.subCh(f3)); S.sub.act = {}; delete S.sub.done.f3; G.acceptSub('f3'); const p0 = G.subProg(f3);
          S.vault = {day:'', n:0}; const b0 = S.rec.bossAll, r0 = S.rec.raidAll; G.startVault(); G.raid.boss.hp = 1e-9; for (let i = 0; i < 400 && G.raid; i++) G.update(0.05);
          const viaVault = S.rec.bossAll === b0 + 1 && S.rec.raidAll === r0 + 1 && G.subProg(f3) === p0 + 1;
          const f1 = G.SUB_Q.find(x => x.c === 'kills' && x.w === 0 && x.k !== 'f3'), ch = G.MAIN_Q.findIndex(q => q.ch === G.subCh(f1));
          S.quest.main = ch; S.sub.act = {}; delete S.sub.done[f1.k]; G.acceptSub(f1.k); S.rec.play += 99999; const before = G.subProg(f1) < f1.n && !!S.sub.act[f1.k];
          S.quest.main = G.MAIN_Q.findIndex(q => q.ch > G.subCh(f1)); const patient = G.subProg(f1) >= f1.n;
          S.up.crit = 300; G.refreshStats(); const crit = G.ST.crit === 1 && G.ST.critOver > 0.5, cd = G.ST.critDmg;
          S.up.crit = 100; G.refreshStats(); const cdLow = G.ST.critDmg;
          Object.assign(S, JSON.parse(keep)); G.setStage(S.stage); G.refreshStats();
          return {light, kmax, past, viaVault, before, patient, crit, cdUp: cd > cdLow}; }""")
        check(lt['light'] and lt['kmax'] <= 600 and lt['past'] and lt['viaVault'] and lt['before'] and lt['patient'],
              f'마을 부탁: 가볍게(보스 3→2번·처치 600마리 이하), 지나온 땅의 부탁은 바로 완료, 보물 동굴도 보스로 셈, 그 장을 하는 중엔 꼭 해야 하고 장을 마치면 완료 {lt}')
        check(lt['crit'] and lt['cdUp'], f'치명타 확률은 100%에서 멈추고 넘친 만큼 치명타 피해가 오른다 {lt}')
        # 6-8c) 조합 공방 재료 지키기: 일괄 합성·갈기가 다음 비전 갑옷에 드는 희귀 장비 4개는 남긴다
        ck = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          const have = () => S.gear.armor.count.slice(8, 12).reduce((a, b) => a + b, 0);
          S.world = 0; S.craft.a.t = 2; S.gear.armor.count = Array(20).fill(0); S.gear.armor.count[8] = 9; S.gear.armor.seen[8] = true; S.equip.armor = -1;
          G.mergeAll('armor'); const afterMerge = have();
          S.gear.armor.count[8] = 9; S.gear.armor.count[9] = 0; S.equip.armor = 16; S.gear.armor.count[16] = 1; G.grindGear('armor', 3); const afterGrind = have();
          S.craft.a.t = 9; S.gear.armor.count[8] = 9; S.equip.armor = -1; G.mergeAll('armor'); const free = have();
          Object.assign(S, JSON.parse(keep)); G.refreshStats();
          return {afterMerge, afterGrind, free}; }""")   # 이승 기준(뒤 땅에서는 이승 조합식에 장비가 안 듦)
        check(ck['afterMerge'] >= 4 and ck['afterGrind'] == 4 and ck['free'] < 4, f'일괄 합성·갈기는 조합 공방에 드는 장비(희귀 4개)를 남기고, 조합을 다 하면 모두 합성한다 {ck}')
        # 6-8d) 자동 기술 순서: 보스 앞에서 공격력 버프·약점이 먼저, 0.1초 간격으로 하나씩
        ao = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          if (G.market) G.leaveMarket();
          G.setClass('musa'); S.world = 0; S.level = 100; S.job = 2; S.mode = 'auto'; S.skManual = {}; S.bossAuto = true; for (const k in S.skills) S.skills[k] = 5; S.skSetMan = true; S.skSet = [2, 5, 6, 7, 1, 0];   // 전투 칸 6개에 버프·약점을 끼움
          G.setStage(20); G.refreshStats(); G.hero.hp = G.ST.maxHp;
          S.kills = 0; S.autoBoss = false; const tough = () => { for (const m of G.mobs) if (!m.dead){ m.maxHp = m.hp = 1e300; m.atk = 0; } };
          for (let i = 0; i < 300 && !G.hero.engaged; i++){ G.update(0.05); tough(); for (const k in G.skillCd) G.skillCd[k] = 99; }
          for (const k in G.skillCd) G.skillCd[k] = 0;
          const order = []; for (let i = 0; i < 12; i++){ G.update(0.05); tough(); for (const k in G.skillCd) if (G.skillCd[k] > 0.5 && !order.includes(k)) order.push(k); }
          const h = G.hero, nm = G.mobs.filter(m => !m.dead).map(m => Math.abs(m.tx - h.tx) + Math.abs(m.ty - h.ty));
          const diag = {mobs: nm.length, near: Math.min(...nm), eng: h.engaged, dead: h.dead, moving: h.moving, sd: h.stepDur, mt: h.mt, goal: h.goal, hold: h.holdT, dodge: h.dodgeT, roll: h.rollT, tg: !!h.target, pos: [h.tx, h.ty], cut: !!G.cut, mk: !!G.market, mode: S.mode, ride: S.mount.ride};
          Object.assign(S, JSON.parse(keep)); G.setStage(S.stage); G.refreshStats();
          return {order, diag}; }""")
        check([x for x in ao['order'] if x != 'party'][:2] == ['roar', 'mark'] and 3 <= len(ao['order']) <= 8,   # (44) 기술을 모두 쓰면 파티 버프도 먼저 걸림
              f'자동 기술: 보스 앞에서 공격력 버프·약점을 먼저 쓰고 0.1초 간격으로 하나씩 쓴다 {ao}')
        # 6-8e) 숫돌 10+1·배럭 효과·만렙 경험치 모으기·단계 보스/레이드 이야기·레벨 문
        nw = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true; G.gateOff = false;
          S.gems = 1000; const w0 = S.inv.whet; G.buyShop('whet10'); const whet = S.inv.whet - w0, paid = 1000 - S.gems;
          const A = G.REG.accounts[G.session.acc], n0 = A.chars.length; G.refreshStats(); const atk0 = G.ST.atk, g0 = G.barrack().gain;
          A.chars.push({cid:'zz_test', name:'배럭', cls:'doin', level:400, cum:700, world:3}); G.refreshStats();
          const br = G.barrack(), atkUp = G.ST.atk / atk0;
          for (let i = 0; i < 4; i++) A.chars.push({cid:'zz_test' + i, name:'배럭' + i, cls:'doin', level:400, cum:900, world:4}); G.refreshStats(); const br6 = G.barrack().gain;   // 6칸: 다른 캐릭터 5명
          A.chars = A.chars.filter(c => !c.cid.startsWith('zz_test')); G.refreshStats();
          S.world = 0; S.level = 100; S.exp = 0; S.expBank = 0; G.gainExp(G.expNeed(100) * 10);
          const bank = S.expBank; S.world = 1; S.level = 1; const up = G.useExpBank(); const bankAfter = S.expBank, lvAfter = S.level;
          S.world = 0; S.level = 1; S.quest.main = 0; const g1 = G.stageGate(), b1 = G.bossGate(25).ok, b2 = G.bossGate(3).ok;
          S.level = 5; const lvGate = !G.bossGate(15).ok && G.bossGate(15).why.includes('Lv');
          S.world = 1; S.level = 200; S.raid.first = {}; S.quest.main = G.MAIN_Q.findIndex(q => q.key === 'h0'); const rOpen = [G.raidUnlockedBase(), G.raidUnlocked()];
          S.quest.main = G.MAIN_Q.length + 3; const free = G.stageGate();
          Object.assign(S, JSON.parse(keep)); G.setStage(S.stage); G.refreshStats(); G.gateOff = true;
          return {whet, paid, n0, stat: br.stat, gain: br.gain - g0, br6: br6 - g0, atkUp: +atkUp.toFixed(3), bank: +bank.toFixed(2), up, bankAfter, lvAfter, g1, b1, b2, lvGate, rOpen, free: free === Infinity}; }""")
        check(nw['whet'] == 11 and nw['paid'] == 250, f'상점: 숫돌 10+1 묶음은 250보석에 11개 {nw}')
        check(nw['stat'] == 14 and abs(nw['atkUp'] - 1.14) < 0.02 and 6 <= nw['gain'] <= 7, f'배럭 효과: 다른 캐릭터(누적 Lv700)가 있으면 공격력·체력 +14%(50레벨마다 1%), 엽전·경험치 +6%(한 명당 몫 0.7배) {nw}')
        check(34 <= nw['br6'] <= 36, f'배럭 효과(캐릭터 6칸): 다른 캐릭터 5명이 모두 높아도 엽전 +35%까지(예전 4칸 최대 30%의 +20% 안쪽) {nw["br6"]}')
        check(9.5 <= nw['bank'] <= 10.5 and nw['up'] >= 2 and nw['bankAfter'] == 0, f'만렙 경험치: 만렙에서 버려지던 경험치를 모아 두고 환생 뒤 30%를 레벨로 돌려준다 {nw}')
        check(nw['g1'] == 21 and not nw['b1'] and nw['b2'] and nw['lvGate'] and nw['rOpen'] == [10, 1] and nw['free'],
              f'이야기·레벨 문: 단계 보스는 이야기 진행과 레벨에 맞춰, 저승 레이드는 그 레이드 퀘스트에 닿아야 열린다 {nw}')
        # 6-8f) 별호·급보
        te = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          S.title = {own:{}, eq:''}; S.rec.kills = 12000; G.titleCheck(); const own = !!S.title.own.hunt1, eq = S.title.eq ? 'hunt1' : '';
          S.title.eq = 'hunt1'; G.refreshStats(); const a1 = G.ST.atk; S.title.eq = ''; G.refreshStats(); const a0 = G.ST.atk;
          G.setStage(Math.max(1, S.stage)); G.evtT = 0; const e0 = S.rec.events || 0;
          for (let i = 0; i < 6; i++) G.update(0.05); const spawned = G.mobs.some(m => m.evt);
          for (let i = 0; i < 900 && G.mobs.some(m => m.evt && !m.dead); i++){ G.update(0.05); G.hero.hp = G.ST.maxHp; }
          const caught = (S.rec.events || 0) > e0 || !G.mobs.some(m => m.evt && !m.dead);
          Object.assign(S, JSON.parse(keep)); G.setStage(S.stage); G.refreshStats();
          return {own, eq, atkUp: +(a1 / a0).toFixed(3), spawned, caught}; }""")
        check(te['own'] and te['eq'] == 'hunt1' and te['atkUp'] > 1.02 and te['spawned'] and te['caught'],
              f'별호: 몬스터 1만 마리면 「도깨비 사냥꾼」을 얻어 달고 공격력이 오르고, 급보 손님이 나타나 잡히거나 사라진다 {te}')
        # 6-8g) 백귀야행: 60초 동안 요괴 떼를 잡고, 그 수만큼 보상. 단계·처치 수(보스까지)는 그대로, 하루 2번
        pr = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          S.parade = {day:'', n:0, best:0}; G.setStage(Math.max(1, S.stage)); S.gold = 0; S.dust = 0; const st0 = S.stage, k0 = S.kills, left0 = G.paradeLeft(), g0 = S.gold, d0 = S.dust;
          G.startParade(); const on = !!G.parade;
          for (let i = 0; i < 1400 && G.parade; i++){ G.update(0.05); G.hero.hp = G.ST.maxHp; }
          const out = {on, done: !G.parade, best: S.parade.best, left: [left0, G.paradeLeft()], stage: S.stage === st0, kills: S.kills === k0,
            gold: S.gold > g0, dust: S.dust > d0};
          Object.assign(S, JSON.parse(keep)); G.setStage(S.stage); G.refreshStats(); return out; }""")
        check(pr['on'] and pr['done'] and pr['best'] > 0 and pr['left'] == [2, 1] and pr['stage'] and pr['kills'] and pr['gold'] and pr['dust'],
              f'백귀야행: 60초 동안 요괴를 잡고 잡은 수만큼 엽전·쇳가루, 단계·보스까지 처치 수는 그대로, 하루 2번 {pr}')
        # 6-8h) 곤륜·부상 아바타(상자는 그 땅에 가야), 갈림길(고르면 별호·원한 조각), 원한 조각은 부상부터, 결이야기(넋 힘·모음 효과)
        fk = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          S.world = 0; const pool0 = G.avBoxPool().length, g0 = G.gainGrudge(5, true);
          G.setWorld(3); const pool3 = G.avBoxPool().length; S.av.own = {}; S.quest.main = G.MAIN_Q.length; G.mountCatchUp(); const avs = ['c_dorong', 'p_kunlun', 'q_peach', 'c_ose', 'p_magpie'].every(k => S.av.own[k]);
          S.fork = {}; S.grudge = 0; S.title.own = {}; S.title.eq = ''; const pend = G.forkPending().map(f => f.k).join();
          const ok = G.forkPick('snow', 1), again = G.forkPick('snow', 0); G.titleCheck();
          const fork = {snow: S.fork.snow, tB: !!S.title.own.f_snowB, tA: !!S.title.own.f_snowA, grudge: S.grudge, left: G.forkPending().map(f => f.k).join()};
          S.soul.own = {}; S.soul.star = {}; S.soul.bond = {}; G.giveSoul('ondal', true); const k0 = G.soulK('ondal'), c0 = G.soulCol();
          S.grudge = 99; const b = [G.bondUp('ondal'), G.bondUp('ondal'), G.bondUp('ondal'), G.bondUp('ondal')];
          const bond = {b, lv: G.soulBond('ondal'), left: S.grudge, k: +(G.soulK('ondal') / k0).toFixed(2), col: +(G.soulCol() / c0).toFixed(2), lines: G.SOULS.every(x => (G.SOUL_BOND[x.k] || []).length === 3)};
          Object.assign(S, JSON.parse(keep)); G.setWorld(S.world); G.setStage(S.stage); G.refreshStats();
          return {pool0, pool3, g0, avs, pend, ok, again, fork, bond}; }""")
        check(fk['pool3'] - fk['pool0'] == 3 and fk['avs'] and fk['g0'] == 0, f'곤륜·부상 아바타: 상자 아바타는 그 땅에 가야 나오고, 지난 이야기의 아바타는 들어올 때 받는다. 원한 조각은 부상부터 {fk}')
        check(fk['pend'] == 'snow,tower' and fk['ok'] and not fk['again'] and fk['fork']['snow'] == 1 and fk['fork']['tB'] and not fk['fork']['tA'] and fk['fork']['grudge'] == 20 and fk['fork']['left'] == 'tower',
              f'갈림길: 지나온 갈림길을 고르면 그 길의 별호와 원한 조각 20, 다시 고를 수 없다 {fk}')
        check(fk['bond']['b'] == [True, True, False, False] and fk['bond']['lv'] == 2 and fk['bond']['left'] == 59 and fk['bond']['k'] == 1.3 and fk['bond']['col'] == 2.0 and fk['bond']['lines'],
              f'결이야기: 원한 조각 10·30·60으로 마디마다 넋의 힘 +15%·모음 효과 +50% {fk}')
        # 6-8i) 수호신: 전직·환생으로 열리고, 엽전으로 올리고, 모신 것은 전부·나머지는 30%
        gd = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          S.job = 0; S.reb.n = 0; S.world = 0; S.guard = {lv:{}, on:''}; S.gold = 0; const lock = !G.guardUp('seongju');
          S.job = 1; S.reb.n = 1; S.gold = 1e300; G.refreshStats(); const a0 = G.ST.atk, h0 = G.ST.maxHp;
          for (let i = 0; i < 25; i++){ G.guardUp('jowang'); G.guardUp('seongju'); } const noTeo = !G.guardUp('teoju');
          G.guardSet('jowang'); G.refreshStats(); const a1 = G.ST.atk / a0, h1 = G.ST.maxHp / h0;
          const out = {lock, noTeo, lv: [G.guardLv('jowang'), G.guardLv('seongju')], on: S.guard.on, atk: +a1.toFixed(3), hp: +h1.toFixed(3)};
          Object.assign(S, JSON.parse(keep)); G.setWorld(S.world); G.setStage(S.stage); G.refreshStats(); return out; }""")
        check(gd['lock'] and gd['noTeo'] and gd['lv'] == [20, 20] and gd['on'] == 'jowang' and gd['atk'] == 1.3 and gd['hp'] == 1.12,
              f'수호신: 1차 전직 뒤 성주신, 첫 환생 뒤 조왕신. Lv20 조왕신을 모시면 공격력 +30%, 안 모신 성주신은 체력 +40%의 30% {gd}')
        # 6-8j) 목걸이(부상부터 보스 피해)·패옥(곤륜부터 경험치·엽전), 각인 강화(조합 단계 + 1까지, 재료·보석)
        ac = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          S.world = 0; const lock = !G.accOpen('neck') && !G.accOpen('pae'); G.accLuck = 1e6; S.acc.neck = {g:-1, p:0}; S.acc.pae = {g:-1, p:0}; G.rollAcc(true); const noDrop = S.acc.neck.g < 0;
          G.setWorld(3); S.stage = 30; G.rollAcc(true); const drop3 = S.acc.neck.g >= 0 && S.acc.pae.g < 0; G.accLuck = 1;
          S.acc.neck = {g:-1, p:0}; S.acc.pae = {g:-1, p:0}; G.refreshStats(); const gm0 = G.gainMul('gold');
          G.giveAcc('pae', 2); const gm1 = G.gainMul('gold');
          S.craft.w = {t:2, e:'power', e2:'', f:0, el:0}; S.mat.m2 = 1000; S.mat.m0 = 1000; S.gems = 1e6; G.refreshStats(); const e0 = G.craftEff('power');
          const ups = [0, 1, 2, 3].map(() => G.engrUp('w')); const e1 = G.craftEff('power');
          const out = {lock, noDrop, drop3, pae: S.acc.pae.p, gain: +(gm1 / gm0).toFixed(3), ups, el: G.engrLv('w'), eff: +(e1 / e0).toFixed(2)};
          G.accLuck = 1; Object.assign(S, JSON.parse(keep)); G.setWorld(S.world); G.setStage(S.stage); G.refreshStats(); return out; }""")
        check(ac['lock'] and ac['noDrop'] and ac['drop3'] and ac['pae'] > 0 and ac['gain'] > 1.05,
              f'목걸이·패옥: 1부엔 안 나오고 부상부터 목걸이(곤륜부터 패옥), 패옥은 경험치·엽전을 올린다 {ac}')
        check(ac['ups'] == [True, True, True, False] and ac['el'] == 3 and ac['eff'] == 1.3, f'각인 강화: 조합 단계 + 1까지, 단계마다 각인 효과 +10% {ac}')
        # 6-8k) 신화·태초 각성: 부상부터 전설 장비를 깨우면 장착 효과 ×1.5, 곤륜부터 ×2.2. 전설이 아니면 꺼짐
        asc = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          S.asc = {weapon:0, armor:0}; S.world = 2; S.equip.weapon = 19; S.mythShard = 1000; S.grudge = 1000; S.mat.m2 = 1000; const no2 = !G.ascend('weapon');
          G.setWorld(3); const p0 = G.gearPct('weapon'); const ok1 = G.ascend('weapon'), p1 = G.gearPct('weapon'), no3 = !G.ascend('weapon');
          G.setWorld(4); const ok2 = G.ascend('weapon'), p2 = G.gearPct('weapon'), g2 = G.gearG('weapon');
          S.equip.weapon = 15; const off = G.ascMul('weapon') === 1 && G.gearG('weapon') === 3;
          const out = {no2, ok1, no3, ok2, r1: +((p1 - G.ownedPct('weapon')) / (p0 - G.ownedPct('weapon'))).toFixed(2), g2, off, left: [S.mythShard, S.grudge]};
          Object.assign(S, JSON.parse(keep)); G.setWorld(S.world); G.setStage(S.stage); G.refreshStats(); return out; }""")
        check(asc['no2'] and asc['ok1'] and asc['no3'] and asc['ok2'] and asc['r1'] == 1.5 and asc['g2'] == 6 and asc['off'] and asc['left'] == [940, 600],
              f'신화·태초 각성: 부상에서 신화(×1.5), 곤륜에서 태초, 전설 장비를 낄 때만 켜진다 {asc}')
        # 6-8l) 부상·곤륜 펫 8마리: 1부엔 소환에 안 나오고, 그 땅에 가면 같은 등급 후보에 더해진다
        np_ = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          const idx = d => G.PETS.findIndex(p => p.draw === d), cnt = (w, n) => { S.world = w; const c = {}; for (let i = 0; i < n; i++){ const k = G.rollPet(); c[k] = (c[k] || 0) + 1; } return c; };
          const c0 = cnt(0, 4000), c4 = cnt(4, 6000);
          const newIdx = ['kitsu', 'kama', 'tanuki', 'kappa', 'luan', 'aojiao', 'okto', 'qingniao'].map(idx);
          const imgs = newIdx.every(i => typeof G.petImg(i) === 'string' && G.petImg(i).length > 100);
          const out = {n: G.PETS.length, none0: newIdx.every(i => !c0[i]), some4: newIdx.filter(i => c4[i]).length, imgs};
          Object.assign(S, JSON.parse(keep)); G.setWorld(S.world); G.refreshStats(); return out; }""")
        check(np_['n'] == 34 and np_['none0'] and np_['some4'] >= 6 and np_['imgs'], f'부상·곤륜 펫: 1부 소환엔 안 나오고 곤륜에선 새 펫들이 나온다(그림도 그려짐) {np_}')
        # 6-8m) 퀘스트 창: 오늘의 할 일 보상을 받아도 창이 닫히지 않는다(사용자 요청)
        await page.evaluate("""() => { const G = window.__game, S = G.S; G.dailyCheck(); S.quest.dgot = []; for (const d of G.DAILY) S.quest.dp[d.key] = d.goal; G.quiet = false; G.buildTab('quest'); }""")
        await page.wait_for_timeout(200); await page.click('[data-qv=daily]'); await page.wait_for_timeout(200)
        g0 = await page.evaluate("() => window.__game.S.gems")
        await page.click('.qdaily .qrow .btn'); await page.wait_for_timeout(300)
        qs = await page.evaluate("() => ({open: !document.querySelector('#page').hidden, got: window.__game.S.quest.dgot.length, gems: window.__game.S.gems})")
        check(qs['open'] and qs['got'] == 1 and qs['gems'] > g0, f'퀘스트 창: 오늘의 할 일 보상을 받아도 퀘스트 창에 그대로 있다 {qs}')
        await page.evaluate("() => { const G = window.__game; G.closePage(); G.quiet = true; }")
        # 6-8n) 곤륜 저장을 다시 불러와도 곤륜 그대로(예전엔 이승 Lv100으로 바뀜), 이미 바뀐 저장은 곤륜 기록으로 되돌림
        kf = await page.evaluate("""() => { const G = window.__game, S = G.S;
          const a = G.mergeState(Object.assign(JSON.parse(JSON.stringify(S)), {world:4, level:455, stage:40, maxStage:42, best:Object.assign({}, S.best, {s4:42, l4:455})}));
          const b = G.mergeState(Object.assign(JSON.parse(JSON.stringify(S)), {world:0, level:100, stage:63, maxStage:70, best:Object.assign({}, S.best, {s4:63, l4:475, l0:475})}));
          return {a:[a.world, a.level, a.maxStage], b:[b.world, b.level, b.maxStage, b.stage, b.best.l0, !!b.kunlunFix]}; }""")
        check(kf['a'] == [4, 455, 42] and kf['b'][:4] == [4, 475, 63, 63] and kf['b'][4] <= 100 and kf['b'][5],
              f'곤륜 저장: 다시 불러와도 곤륜 그대로이고, 예전에 이승으로 바뀐 저장은 곤륜 기록으로 되돌린다 {kf}')
        # 6-9) 가방·장터: 약한 장신구는 가방으로, 끼면 바꿔 끼고 옛것은 가방으로, 안 쓰는 것 팔기, NPC 상인, 장터 마을 들어갔다 나오기
        bg = await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true; S.bag = []; S.acc.ring = {g:3, p:500};
          G.giveAccX('ring', 0); const inBag = S.bag.length === 1 && S.bag[0].k === 'ring';
          G.bagAdd({t:'acc', k:'ring', g:4, p:900}, true); const up = S.bag.find(x => x.p === 900); G.bagEquip(up.id);
          const swapped = S.acc.ring.p === 900 && S.bag.some(x => x.p === 500);
          const g0 = S.gems; const sold = G.bagSellWorse(); const leftBag = S.bag.length;
          S.gems = 1e6; S.mkNpc = {day:'', got:[]}; G.npcLuck = 0; const o = G.npcOffers(); const nb = G.npcBuy(2); const nb2 = G.npcBuy(2); G.npcLuck = null;
          G.enterMarket(); const inMk = !!G.market && G.mobs.length === 0; for (let i = 0; i < 40; i++) G.update(0.05); const noMobs = G.mobs.length === 0;
          G.leaveMarket(); for (let i = 0; i < 60; i++) G.update(0.05);
          return {inBag, swapped, sold: sold.n, gemsUp: S.gems > 0, leftBag, offers: o.length, nb, nb2: nb2.err, myth: S.bag.some(x => x.t === 'myth'), inMk, noMobs, back: !G.market && G.mobs.length > 0}; }""")
        check(bg['inBag'] and bg['swapped'] and bg['sold'] == 2 and bg['leftBag'] == 0, f'가방: 약한 장신구는 가방으로, 끼면 옛것이 가방으로, 안 쓰는 것은 팔린다 {bg}')
        check(bg['offers'] == 5 and bg['nb'] == {'ok': True} and bg['nb2'] == 'gone' and bg['myth'] and bg['inMk'] and bg['noMobs'] and bg['back'],
              f'장터: NPC 상인은 날마다 하나씩, 장터 마을에서는 사냥이 멈추고 나오면 다시 사냥 {bg}')
        # 6-9a) NPC 상인: 12시간마다 바뀌고, 아주 낮은 확률로 귀한 물건(전설 치장·전설 장신구) 하나를 보석 2,000에
        nr = await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true;
          G.npcLuck = 0; const n0 = G.npcOffers().length, s0 = G.npcSlot(), o0 = JSON.stringify(G.npcOffers());
          const same = o0 === JSON.stringify(G.npcOffers());
          G.addTime(G.npcLeft() + 60000); const s1 = G.npcSlot(), o1 = JSON.stringify(G.npcOffers());
          G.npcLuck = 100; const r = G.npcOffers()[5];
          S.gems = 5000; S.mkNpc = {day:'', got:[]}; S.bag = []; const g0 = S.gems; const nb = G.npcBuy(5), paid = g0 - S.gems, nb2 = G.npcBuy(5);
          const got = r.it.t === 'acc' ? (S.acc[r.it.k].g === 4 && S.acc[r.it.k].p === r.it.p) || S.bag.some(x => x.t === 'acc' && x.g === 4 && x.p === r.it.p)
            : Object.values(S.skin.eq).concat(S.skin.inv).some(x => x.c === r.it.c && x.g === 4);
          G.npcLuck = null; G.closePage && G.closePage();
          return {n0, same, changed: s0 !== s1 && o0 !== o1, rare: !!r.rare, price: r.price, t: r.it.t, g: r.it.g, nb, paid, nb2: nb2.err, got}; }""")
        check(nr['n0'] == 5 and nr['same'] and nr['changed'] and nr['rare'] and nr['price'] == 2000 and nr['g'] == 4 and nr['nb'] == {'ok': True} and nr['paid'] == 2000 and nr['nb2'] == 'gone' and nr['got'],
              f'장터 상인: 12시간마다 목록이 바뀌고(같은 때엔 그대로), 귀한 물건(전설)은 보석 2,000에 하나만 {nr}')
        # 6-9b) 눌러서 움직이기: 장터에서 누른 칸까지 그림도 따라 걷고, 사냥터에서 땅을 누르면 그 칸으로 가서(반자동) 잠시 버티고, 몬스터를 누르면 그 몬스터를 노린다
        tp = await page.evaluate("""() => { const G = window.__game, S = G.S, h = G.hero; G.quiet = true;
          const at = (tx, ty) => { const rc = document.getElementById('cv').getBoundingClientRect(); const x = 222 + (tx - ty) * 9, y = 40 + (tx + ty) * 4.5;
            return {clientX: rc.left + (x - G.camX) * G.scale, clientY: rc.top + (y - G.camY) * G.scale}; };
          G.enterMarket(); for (let i = 0; i < 10; i++) G.update(0.05);
          const x0 = h.x; document.getElementById('cv').dispatchEvent(new MouseEvent('click', Object.assign({bubbles: true}, at(h.tx - 4, h.ty + 2))));
          const goal = G.market.goal && G.market.goal.slice(); for (let i = 0; i < 80; i++) G.update(0.05);
          const mkMoved = h.x !== x0 && h.tx === goal[0] && h.ty === goal[1];
          G.leaveMarket(); S.mode = 'semi'; for (let i = 0; i < 20; i++) G.update(0.05);
          for (const m of G.mobs) m.dead = true; G.update(0.05);
          const gx = h.tx + 3, gy = h.ty - 2; G.fieldClick(at(gx, gy)); const fg = !!h.goal;
          for (let i = 0; i < 60; i++) G.update(0.05); const arrived = h.tx === gx && h.ty === gy && h.holdT > 2;
          for (let i = 0; i < 40; i++) G.update(0.2); const m = G.mobs.find(q => !q.dead && q.spawnT <= 0);
          let picked = false; if (m){ const mm = Object.assign({}, at(m.tx, m.ty)); mm.clientY -= 6 * G.scale; G.fieldClick(mm); picked = h.target === m || !!(h.target && !h.target.dead && Math.abs(h.target.tx - m.tx) + Math.abs(h.target.ty - m.ty) <= 1); }   // 겹친 몬스터를 골라도 됨
          S.mode = 'auto'; return {goal, mkMoved, fg, arrived, picked}; }""")
        check(tp['mkMoved'] and tp['fg'] and tp['arrived'] and tp['picked'], f'눌러서 움직이기: 장터에서 걸어가고, 사냥터 땅을 누르면 그 칸으로·몬스터를 누르면 그 몬스터를 {tp}')
        # 6-10) 신화 펫·환수: 1부엔 소환에 안 나오고, 부상에 가면 그 땅의 환수(이야기 환수는 빼고)가 소환에 나온다. 보물 동굴·신화 조각. 함께하는 싸움은 늘 자동 기술
        mp = await page.evaluate("""() => { const G = window.__game, S = G.S, w0 = S.world; G.quiet = true;
          S.world = 0; const pool0 = G.mythPetPool().length; S.world = 3; const pool3 = G.mythPetPool().map(i => G.PETS[i].name);
          S.gems = 1e7; G.petLuck = 400; const r = G.petSummon(1); G.petLuck = null; const got = G.PETS[r[0].i];
          const bk = G.PETS.findIndex(p => p.draw === 'baku'); S.pets.lv[bk] = 0; const gp = G.givePet('baku');
          S.vault = {day:'', n:0}; S.mythShard = 0; const v = G.startVault(); G.raid.boss.hp = 1e-9; for (let i = 0; i < 400 && G.raid; i++) G.update(0.05);
          const shard = S.mythShard; S.mythShard = 30; const cm = G.craftMyth('flute'), shardLeft = S.mythShard;
          S.mode = 'semi'; G.startFight({label:'시험', bossName:'시험 보스', type:'oni', color:'#c83a2a', region:0, party:3, ref:1, g:0}, G.raidParty({party:3, g:0, ref:1}), {hp:1e9, atk:0, aoe:0, time:5});
          const auto = G.coopFight() && G.skAuto(0) && G.skAuto(5); for (let i = 0; i < 200; i++) G.update(0.05); S.mode = 'auto';
          S.world = w0; return {pool0, pool3, got: got.g, gotName: got.name, gp, baku: S.pets.lv[bk], v, shard, cm: !!cm, shardLeft, auto}; }""")
        check(mp['pool0'] == 0 and mp['pool3'] == ['뇌수', '아마비에'] and mp['got'] == 5 and mp['gp'] and mp['baku'] == 1,
              f'신화 펫: 1부엔 안 나오고, 부상에서는 그 땅의 환수가 소환에 나오며 이야기 환수(바쿠)는 이야기 보상으로 {mp}')
        check(mp['v'] and mp['shard'] >= 4 and mp['cm'] and mp['shardLeft'] == 0 and mp['auto'],
              f'보물 동굴: 이기면 신화 조각, 조각 30개로 신화 보물을 만들고, 함께하는 싸움은 반자동이어도 기술이 자동 {mp}')
        # 6-11) 기술 레벨업 미리보기·넋 부름·보스 손컨(붉은 칸·되받기·버팀·큰 살)
        so = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S), H = Object.assign({}, G.HAND); G.quiet = true;
          const g1 = G.skillGain(0, 1).g, gMax = G.SKILLS.every((sk, i) => G.skillGain(i, 5).g > 0);
          S.world = 0; S.soul = {own:{}, star:{}, eq:['', ''], pity:0}; const d0 = G.soulDrop('raid');
          G.setWorld(3); S.stage = 15; S.maxStage = 20; S.level = 320; S.job = 3; S.up.atk = 200; S.up.hp = 400; G.refreshStats();
          S.soul.pity = G.SOUL_PITY - 1; const d1 = G.soulDrop('raid'); const k1 = d1 && d1.k; const d2 = G.giveSoul(k1, true);
          const col = G.soulCol() > 0, eq = G.soulEq().length === 1;
          S.kills = 25; S.autoBoss = true; for (let i = 0; i < 12; i++) G.update(0.05);
          const B = G.patBoss(); B.maxHp = B.hp = 1e40; const lv = G.patLv(B);
          const eqKeep = S.soul.eq.slice(); S.soul.eq = ['', '']; G.soulG = 0;   // 손컨 점검 동안은 넋이 끼어들지 않게(묶기·버팀 깎기)
          // 붉은 칸: 자동 손이 피하면 안 맞고, 못 피하면 맞는다
          const tiles = dodge => { G.HAND.dodge = dodge ? 1 : 0; G.hero.hp = G.ST.maxHp; B.atk = G.ST.maxHp * 0.3; B.stunT = 0; B.pat.grogT = 0; B.pat.tel = null; B.pat.cd = 0.01; B.pat.n = 0;
            const h0 = S.rec.patHits || 0; let seen = false; for (let i = 0; i < 80; i++){ G.update(0.05); const T = B.pat.tel; if (T && T.kind === 'tiles'){ seen = true; if (!dodge){ T.set.add(G.hero.tx + ',' + G.hero.ty); if (G.hero.fx != null) T.set.add(G.hero.fx + ',' + G.hero.fy); } } if (seen && !T) break; }
            return {seen, hit: (S.rec.patHits || 0) > h0}; };
          const tA = tiles(true), tB = tiles(false);
          // 되받기: 단추를 누르면 막고 보스가 묶인다
          B.pat.tel = null; B.pat.cd = 0.01; B.pat.n = 2; G.HAND.counter = 0; let ctr = null;
          for (let i = 0; i < 40 && !ctr; i++){ G.update(0.05); if (B.pat.tel && B.pat.tel.kind === 'counter') ctr = G.handPress(); }
          const stun = B.stunT > 0, counters = S.rec.counters || 0;
          // 버팀: 깎이면 휘청
          B.stunT = 0; B.pat.tel = null; B.pat.stg = 5; G.hero.hp = G.ST.maxHp; B.pat.cd = 99; G.patStg(B, 10);
          const grog = B.pat.grogT > 0; for (let i = 0; i < 100; i++) G.update(0.05); const back = B.pat.grogT <= 0 && B.pat.stg === 100;
          // 큰 살: 못 끊으면 최대 체력의 절반 넘게 깎인다
          B.pat.grogT = 0; B.pat.stg = 100; B.stunT = 0; B.gate = true; B.pat.wipes = [1.01]; B.pat.cd = 99; G.hero.hp = G.ST.maxHp; G.hero.shield = 0;
          for (let i = 0; i < 3; i++) G.update(0.05); const wiping = !!(B.pat.tel && B.pat.tel.kind === 'wipe'); B.pat.stg = 1e9;
          let low = 1; for (let i = 0; i < 140 && B.pat.tel; i++){ G.update(0.05); low = Math.min(low, G.hero.hp / G.ST.maxHp); G.hero.hp = Math.max(G.hero.hp, 1); }
          // 넋 부름: 기운이 차면 넋이 나타나 보스를 친다(자동)
          S.soul.eq = eqKeep;
          B.pat.cd = 99; S.mode = 'auto'; G.soulG = 100; const hp0 = B.hp; let app = false; for (let i = 0; i < 30; i++){ G.update(0.05); if (G.soulApp.length) app = true; }
          const casted = app && G.soulG < 100 && (S.rec.souls || 0) > 0;
          Object.assign(G.HAND, H); Object.assign(S, JSON.parse(keep)); G.setStage(S.stage); G.refreshStats();
          return {g1: +g1.toFixed(1), gMax, d0, k1: !!k1, star: d2 && d2.star, col, eq, lv, tA, tB, ctr, stun, counters, grog, back, wiping, low: +low.toFixed(2), casted}; }""")
        check(so['g1'] == 10 and so['gMax'], f'기술 미리보기: 레벨을 올리면 몇 % 세지는지 모든 칸에서 보인다(회오리 Lv1→2 +10%) {so}')
        check(so['d0'] is None and so['k1'] and so['star'] == 1 and so['col'] and so['eq'], f'넋 부름: 1부엔 넋 구슬이 안 나오고, 2부에선 50번 천장·같은 넋은 별·주머니에 저절로 모심 {so}')
        check(so['lv'] == 2 and so['tA']['seen'] and not so['tA']['hit'] and so['tB']['hit'] and so['ctr'] == 'counter' and so['stun'] and so['grog'] and so['back'],
              f'보스 손컨: 붉은 칸(피하면 안 맞고 못 피하면 맞음)·되받기 단추·버팀을 깨면 휘청 {so}')
        check(so['wiping'] and so['low'] <= 0.5 and so['casted'], f'큰 살을 못 끊으면 체력이 크게 깎이고, 넋의 기운이 차면 넋이 나타나 돕는다 {so}')
        await page.evaluate("() => { const G = window.__game; G.quiet = false; G.enterMarket(); }")
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(OUT / '34_장터마을.png'))
        await page.evaluate("() => window.__game.leaveMarket()")
        await page.evaluate("() => { const G = window.__game; G.quiet = false; if (!document.querySelector('#modal').hidden) G.hideModal(); G.buildTab('gear'); }")
        await page.click('#seg-mount')
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(OUT / '33_탈것.png'))
        await page.evaluate("() => window.__game.closePage()")

        # 7) 도트 그림 모음(펫·몬스터)
        data = await page.evaluate("""() => { const sh = window.__game.sheet(); const rows = [sh.pets.map(p => p[0]).concat(sh.pets.map(p => p[1])), sh.mobs.map(m => m[0])];
          const c = document.createElement('canvas'); c.width = 30 * 22 * 3; c.height = 2 * 30 * 3 + 10; const g = c.getContext('2d'); g.imageSmoothingEnabled = false;
          g.fillStyle = '#5a7a4a'; g.fillRect(0, 0, c.width, c.height);
          return Promise.all(rows.flat().map(u => new Promise(r => { const im = new Image(); im.onload = () => r(im); im.src = u; }))).then(ims => {
            let k = 0; rows.forEach((row, y) => row.forEach((_, x) => { const im = ims[k++]; g.drawImage(im, x * 66 + 4, y * 95 + 6, im.width * 3, im.height * 3); }));
            return c.toDataURL(); }); }""")
        (OUT / '15_도트모음.png').write_bytes(base64.b64decode(data.split(',')[1]))
        await ctx.close()

        # 8) claude.ai 계정 저장 흉내: 기기 A에서 만든 계정·캐릭터를 기기 B(빈 브라우저)에서 불러온다
        ctxA = await browser.new_context(viewport={'width': 844, 'height': 390})
        await ctxA.add_init_script(MOCK_CLAUDE % 'null')
        pa = await ctxA.new_page()
        watch(pa, errors, 'A ')
        await pa.goto(URL)
        await pa.wait_for_selector('#lg-id')
        await signup(pa, 'cloudy', 'abcd', '구름', 'doin')
        await pa.evaluate("() => { const G = window.__game; G.S.level = 17; G.S.gems = 777; }")
        await pa.evaluate("() => { Object.defineProperty(document, 'hidden', {get: () => true, configurable: true}); document.dispatchEvent(new Event('visibilitychange')); }")
        await pa.wait_for_timeout(800)
        store = await pa.evaluate('() => window.__store')
        check(any(k.endswith('/samhan-accounts') for k in store) and any('/samhan-c-cloudy-' in k for k in store), f'계정·캐릭터가 Claude 저장소에 올라간다 {list(store)}')
        await ctxA.close()
        ctxB = await browser.new_context(viewport={'width': 844, 'height': 390})
        await ctxB.add_init_script(MOCK_CLAUDE % json.dumps(store))
        pb = await ctxB.new_page()
        watch(pb, errors, 'B ')
        await pb.goto(URL)
        await pb.wait_for_selector('#lg-id')
        await pb.fill('#lg-id', 'cloudy'); await pb.fill('#lg-pw', 'abcd'); await pb.click('#modal-btn-0')
        await pb.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
        await pb.click('#modal-btn-1')
        await pb.wait_for_function('() => window.__game.session', timeout=8000)
        got = await pb.evaluate('() => ({name: window.__game.S.name, level: window.__game.S.level, gems: window.__game.S.gems})')
        check(got['name'] == '구름' and got['level'] == 17, f'다른 기기에서 같은 계정으로 이어진다 {got}')
        await pb.click('#chatBtn')
        await pb.fill('#chatInput', '같이 레이드 가요')
        await pb.press('#chatInput', 'Enter')
        await pb.evaluate('''() => { for (const [t, fn] of window.__roomH) if (t === 'chat') fn({topic:'chat', data:{n:'바람돌이', t:'좋아요! <b>ㅋㅋ</b>'}, peer:'p2', by:null, isMe:false, sameTab:false, kind:'viewer', guest:false}); }''')
        await pb.wait_for_timeout(300)
        room = await pb.evaluate('() => ({sent: window.__emitted, html: document.querySelector("#chatList").innerHTML, who: document.querySelector("#chatWho").textContent})')
        chats = [m for m in room['sent'] if m[0] == 'chat']   # 타임 보스 시간이면 'tb' 참가 알림도 함께 나간다
        check(len(chats) == 1 and chats[0][1]['t'] == '같이 레이드 가요', f'claude.ai에서는 채팅이 다른 사람에게 나간다 {room["sent"]}')
        check('바람돌이' in room['html'] and '&lt;b&gt;' in room['html'], '다른 사람의 채팅이 들어오고, 글자로만 보인다')
        await pb.screenshot(path=str(OUT / '21_채팅_여럿.png'))
        await ctxB.close()

        # 9) 예전(계정 없던 때) 저장을 새 캐릭터로 이어받기
        ctxC = await browser.new_context(viewport={'width': 844, 'height': 390})
        pc = await ctxC.new_page()
        watch(pc, errors, 'C ')
        await pc.goto(URL)
        await pc.evaluate("""() => { localStorage.clear(); localStorage.setItem('samhan-hero-v1', JSON.stringify({v:1, cls:'jagaek', chosen:true, gold:123, gems:456,
          level:23, exp:0, stage:27, maxStage:27, kills:0, up:{atk:30}, rec:{kills:999, bosses:26, summons:10, play:3600}, lastSave:Date.now()})); }""")
        await pc.goto(URL)
        await pc.wait_for_selector('#lg-id')
        await pc.fill('#lg-id', 'oldie'); await pc.fill('#lg-pw', 'pass'); await pc.fill('#lg-pw2', 'pass'); await pc.click('#modal-btn-0')
        await pc.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
        await pc.click('#modal-btn-0')
        await pc.wait_for_selector('#cc-legacy')
        await pc.fill('#cc-name', '옛용사'); await pc.click('#modal-btn-1')
        await pc.wait_for_function('() => window.__game.session')
        got = await pc.evaluate('() => ({lv: window.__game.S.level, st: window.__game.S.maxStage, tut: window.__game.S.quest.tut})')
        check(got['lv'] == 23 and got['st'] == 27 and got['tut'] == -1, f'예전 진행을 이어받는다 {got}')
        await ctxC.close()

        # 9-9) 물의 신화 1단계: 밸런스 숫자·싸움 중 물약 구매 금지·장착 기술 8칸·4차 전직 저장·보스 다시 도전 간격
        #       (곤륜 끝 4차 무사 저장 = 베타의 시험용 캐릭터 tools/beta_saves 가운데 레벨이 가장 높은 것)
        late = max((d for d in (json.loads(f.read_text(encoding='utf-8')) for f in sorted((ROOT / 'tools' / 'beta_saves').glob('*.json'))) if not d['save'].get('seaPreview') and d['save'].get('world', 0) <= 4), key=lambda d: d['save'].get('level', 0))['save']   # 4부 미리 보기 캐릭터는 빼고
        ctxS = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        sp = await ctxS.new_page()
        watch(sp, errors, '1단계 ')
        await fresh(sp)
        await signup(sp, 'seatest', 'abcd', '바다용사')
        s1 = await sp.evaluate(r"""(save) => { const G = window.__game, S = G.S, out = {}; G.quiet = true; G.noFork = true;
          const old = JSON.parse(JSON.stringify(save)); delete old.skV; delete old.skKnown; old.skSetMan = false; old.skOff = [];
          Object.assign(S, G.mergeState(old)); S.name = '바다용사'; G.refreshStats(); G.setStage(S.stage);
          out.job = S.job; const d3 = JSON.parse(JSON.stringify(old)); d3.job = 3; out.jobFix = G.mergeState(d3).job; d3.skills.jobD = 0; out.job3 = G.mergeState(d3).job;   // 4차가 3차로 내려가던 저장 되돌리기
          { const dq = JSON.parse(JSON.stringify(old)); dq.world = 3; dq.quest.main = 120; dq.quest.sv = 5; dq.refine.weapon.lv = 15; const mq = G.mergeState(dq); out.sv = [mq.quest.sv, mq.quest.main]; dq.quest.main = 30; out.svFix = G.mergeState(dq).quest.main === G.CROSS_Q; }
          G.skSetFix(); const learned = G.SKILLS.map((_, i) => i).filter(i => G.skLv(i) > 0);
          out.learned = learned.length; out.n = S.skSet.length; out.note = S.skNote; out.man = S.skSetMan; out.v = S.skV; out.rec = S.skSet.join() === G.skPresetFor('mix').join();
          const x = learned.find(i => !S.skSet.includes(i)), a0 = S.skSet[0]; out.full = G.skToggle(x); out.sw = G.skToggle(x, a0) === true && S.skSet.includes(x) && !S.skSet.includes(a0) && S.skSet.length === 8 && S.skSetMan;
          G.skToggle(S.skSet[1]); for (let i = 0; i < 20; i++) G.update(0.05); G.skSetFix(); out.stay7 = S.skSet.length === 7;
          G.skSavePut(0); G.skSetAuto(); out.auto = S.skSet.length === 8 && !S.skSetMan; out.ld = G.skSaveLoad(0) && S.skSet.length === 7 && S.skSetMan; G.skSetAuto();
          S.skV = 0; S.skOff = learned.slice(0, 3); S.skSetMan = false; S.skNote = false; G.skSetFix(); out.mig = S.skSetMan && S.skSet.length === learned.length - 3 && !learned.slice(0, 3).some(i => S.skSet.includes(i)) && !S.skNote;
          G.skSetAuto(); out.bossK = G.skBossK(); out.pre = ['boss', 'party', 'mob'].every(k => G.skPresetFor(k).length === 8) && G.skPresetFor('party')[0] === 10;
          out.k = [G.SK_SLOTS, G.AWAKEN_SEC, G.AWAKEN_SEC4, G.MP_K, G.RAID_GEM_K, G.TB_GEMS.normal, G.TB_GEMS.hell, G.GR_GEMS, G.VAULT_GEMS, G.SOUL_PITY, G.RAID_MYTH_P, G.MAT_DROP.gate, G.MAT_DROP.raid, G.MAT_DROP.tb, G.MAT_DROP.mob, G.SHARD_SRC.raidP, G.ACC_DROP.gate.ring, G.ACC_DROP.gate.ear, G.vaultShards(), G.WEEK_SHARD, G.NPC_RARE_P];
          // 싸움 중 물약 구매 금지
          out.lock0 = G.potLock(); S.gold = 1e30; S.gems = 1e6; S.raid.tk = 3; S.inv.potion = 3; S.inv.mana = 3; S.inv.elixir = 0; out.low = G.potLowAny();
          out.buy0 = G.buyShop('potion') && S.inv.potion === 13; const p0 = S.inv.potion;
          out.raid = G.startRaid(0); if (G.raid){ const B = G.raid.boss; B.hp = B.maxHp = 1e300; B.atk = 0; G.PAT.off = true; } out.lock1 = G.potLock(); out.buy1 = G.buyShop('potion') || G.buyShop('mana') || G.buyShop('elixir') || G.buyShop('gift') || G.buyShop('avbox'); out.same = S.inv.potion === p0;
          out.why = G.shopState(G.SHOP.find(x => x.id === 'mana100')).why; out.whet = G.buyShop('whet'); out.npc = G.npcBuy(0).err !== 'fight';
          G.quiet = false; return out; }""", late)
        await tab(sp, 'shop')
        await sp.wait_for_timeout(500)
        s2 = await sp.evaluate("""() => ({lock: !document.querySelector('#shopLock').hidden, dis: document.querySelector('#shb-potion').disabled && document.querySelector('#shb-mana').disabled && document.querySelector('#shb-elixir').disabled, txt: document.querySelector('#shb-potion').textContent,
          bar: document.querySelectorAll('#skillbar .sk').length, many: document.querySelector('#skillbar').classList.contains('many')})""")
        await sp.screenshot(path=str(OUT / '26_싸움중_상점잠김.png'))
        s3 = await sp.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true; if (G.raid){ G.raid.time = 0; for (let i = 0; i < 300 && G.raid; i++) G.update(0.05); }
          G.PAT.off = false; const out = {lock2: G.potLock(), buy2: G.buyShop('potion')};
          // 보스 다시 도전 간격: 도전 기운(8번)이 다 찬 뒤로는 45초, 90초, 3분 … 10분
          S.bossPity = {k: S.world + ':' + S.stage, n: 0}; const t = n => { S.bossPity.n = n; return G.bossRetryT(); }; out.retry = [t(0), t(8), t(9), t(10), t(12), t(99)]; S.bossPity.n = 0;
          G.quiet = false; G.closePage(); return out; }""")
        check(s1['job'] == 4 and s1['jobFix'] == 4 and s1['job3'] == 3, f'4차 전직 저장을 다시 불러와도 4차 그대로이고(예전엔 3차로 내려감), 4차 기술을 익힌 기록이 있으면 되돌린다 {s1["job"]} {s1["jobFix"]} {s1["job3"]}')
        check(s1['sv'] == [8, 120] and s1['svFix'], f'부상에서 재련이 계승(+15)된 저장을 다시 불러와도 이야기가 옛 퀘스트(무기 +20)로 되돌아가지 않고, 되돌아갔던 저장은 건너기 퀘스트까지 되찾는다 {s1["sv"]} {s1["svFix"]}')
        check(s1['learned'] == 11 and s1['n'] == 8 and s1['note'] and not s1['man'] and s1['v'] == 2 and s1['rec'] and s1['full'] == 'full' and s1['sw'] and s1['stay7'] and s1['auto'] and s1['ld'] and s1['mig']
              and abs(s1['bossK'] - 1.06) < 1e-9 and s1['pre'] and s2['bar'] == 8 and s2['many'],
              f'장착 기술 8칸: 예전 저장은 추천 8개로 정리(알림)·뺀 기술은 그대로 옮김, 꽉 차면 무엇을 뺄지 고르기, [빼기]는 유지, 저장 조합, 싸움별 추천 8개, 기술 줄 8칸, 단계 보스 체력 +6%까지 {s1} {s2}')
        check(s1['k'] == [8, 5, 8, 0.75, 1.2, 100, 200, 180, 90, 50, 0.012, 4, 6, 10, 0.008, 0.3, 0.06, 0.01, 4 + 4, 40, 0.015], f'밸런스 숫자(초각성 5·8초, 마나 0.75배, 레이드 보석·재료·신화 조각·장신구·넋 구슬 천장) {s1["k"]}')
        check(not s1['lock0'] and s1['low'] and s1['buy0'] and s1['raid'] and s1['lock1'] and not s1['buy1'] and s1['same'] and s1['why'] == '싸움 뒤에' and s1['whet'] and s1['npc']
              and s2['lock'] and s2['dis'] and '싸움 뒤에' in s2['txt'] and not s3['lock2'] and s3['buy2'],
              f'싸움이 시작되면 물약(상점 물약 칸·선물·꾸미기 상자)을 살 수 없고 다른 물건은 살 수 있으며, 끝나면 다시 살 수 있다 {s1["lock1"]} {s1["buy1"]} {s2} {s3}')
        check(s3['retry'] == [45, 45, 90, 180, 600, 600], f'보스 자동 다시 도전: 도전 기운이 다 찬 뒤엔 간격이 45초에서 90초, 3분 … 10분으로 벌어진다 {s3["retry"]}')
        # 정비 창의 물약 줄·[사러 가기], 8칸이 찼을 때 [넣기] → 무엇을 뺄지, 예전 저장 알림 창
        await sp.evaluate("""() => { const G = window.__game, S = G.S; S.inv.potion = 3; S.inv.mana = 3; S.inv.elixir = 0; S.presetMode = 'ask'; S.raid.tk = 3; }""")
        await tab(sp, 'raid')
        await sp.wait_for_timeout(400)
        await sp.evaluate("""() => { const b = [...document.querySelectorAll('#page button[data-i]')].find(x => !x.disabled); if (b) b.click(); }""")
        await sp.wait_for_selector('#prePotBox', timeout=4000)
        pn = await sp.evaluate("""() => ({low: document.querySelectorAll('#prePotBox .pot-low').length, go: !!document.querySelector('#prePot'), n: document.querySelector('#preCnt').textContent})""")
        await sp.screenshot(path=str(OUT / '26b_정비창_물약.png'))
        await sp.click('#prePot')
        await sp.wait_for_timeout(500)
        pg = await sp.evaluate("""() => ({shop: !!document.querySelector('#shb-potion'), modal: document.querySelector('#modal').hidden, raid: !!window.__game.raid})""")
        check(pn['low'] == 3 and pn['go'] and '8/8' in pn['n'] and pg['shop'] and pg['modal'] and not pg['raid'], f'싸움 전 정비 창에 들고 가는 물약 수가 보이고, 적으면 붉은 글씨 + [사러 가기]로 상점 물약 칸에 간다 {pn} {pg}')
        await tab(sp, 'skill')
        await sp.wait_for_timeout(400)
        await sp.evaluate("""() => { const b = [...document.querySelectorAll('#page [data-eq]')].find(x => x.textContent === '넣기' && !x.disabled); b.scrollIntoView(); b.click(); }""")
        await sp.wait_for_selector('#swGrid [data-sw]')
        await sp.screenshot(path=str(OUT / '26c_기술_무엇을뺄까.png'))
        sw0 = await sp.evaluate('() => window.__game.S.skSet.slice()')
        await sp.click('#swGrid [data-sw]')
        await sp.wait_for_timeout(300)
        sw1 = await sp.evaluate("""() => ({set: window.__game.S.skSet.slice(), man: window.__game.S.skSetMan, tag: document.querySelector('#skSetN').textContent, modal: document.querySelector('#modal').hidden})""")
        await sp.screenshot(path=str(OUT / '26d_기술_8칸.png'))
        check(len(sw1['set']) == 8 and sw1['set'] != sw0 and sw0[0] not in sw1['set'] and sw1['man'] and '8칸 중 8칸' in sw1['tag'] and sw1['modal'], f'[기술]에서 8칸이 찼을 때 [넣기]를 누르면 무엇을 뺄지 묻고 바꿔 끼운다 {sw0} {sw1}')
        await sp.evaluate("""() => { const G = window.__game; G.closePage(); G.noSkNote = false; G.S.skNote = true; }""")
        await sp.wait_for_selector('#inh.noti #notiSay', timeout=4000)
        await sp.wait_for_timeout(500); await sp.screenshot(path=str(OUT / '26e_8칸_알림.png'))
        n8 = await sp.evaluate("() => ({who: document.querySelector('#inh .nm').textContent, say: document.querySelector('#notiSay').textContent, btns: !document.querySelector('#notiBtns').hidden})")
        await sp.click('#inh .inh-say'); await sp.wait_for_timeout(300)      # 말은 눌러서 넘김 → 끝에 [나중에]/[바로 가기]
        n8b = await sp.evaluate("() => ({btns: !document.querySelector('#notiBtns').hidden, go: (document.querySelector('#notiGo') || {}).textContent, sk: document.querySelectorAll('#inh .pre-sk').length})")
        await sp.screenshot(path=str(OUT / '26f_8칸_알림_끝.png'))
        await sp.click('#notiGo'); await sp.wait_for_timeout(400)
        n8c = await sp.evaluate("() => ({note: window.__game.S.skNote, open: window.__game.inhOpen, tab: window.__game.currentTab, log: window.__game.S.noti.log.map(x => x.k)})")
        check('까치' in n8['who'] and '8' in n8['say'] and not n8['btns'] and n8b['btns'] and n8b['sk'] == 8 and not n8c['note'] and not n8c['open'] and n8c['tab'] == 'skill' and n8c['log'] == ['sk8'],
              f'8개를 넘게 쓰던 예전 저장은 까치가 찾아와 알린다(알림 연출 틀: 말을 눌러 넘기고 [기술 보러 가기]) {n8} {n8b} {n8c}')
        await ctxS.close()

        # 9-10) 물의 신화 3단계: 상위 레이드 「진」(세기 고정·권장 전투력·하루 3번·목숨·탕약 한도·지면 -4%·주간 첫 승리·리셋권 제외·알림)과 해태 수련(46장 전엔 숨김)
        ctxJ = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        jp = await ctxJ.new_page()
        watch(jp, errors, '3단계 ')
        await fresh(jp)
        await signup(jp, 'jintest', 'abcd', '진용사')
        j1 = await jp.evaluate(r"""(save) => { const G = window.__game, S = G.S, out = {}; G.quiet = true; G.noFork = true;
          const old = JSON.parse(JSON.stringify(save)); delete old.jin; delete old.haetae;
          Object.assign(S, G.mergeState(old)); S.name = '진용사'; S.myth.elixir = 0; G.refreshStats(); G.setStage(S.stage);
          out.merged = !!S.jin && S.jin.n === 0 && !!S.jin.wk && !!S.jin.fail && !!S.haetae && G.mergeState({jin:{n:2, wk:{j0:1, zz:1}, fail:{jb7:99}, win:{jh3:'4'}}}).jin.fail.jb7 === 9 && !('zz' in G.mergeState({jin:{wk:{zz:1}}}).jin.wk);
          out.open = [0, 1, 2, 3, 4].map(w => G.jinOpen(w));
          out.rec = [[0, 0], [0, 7], [1, 0], [1, 9], [2, 0], [2, 7], [3, 0], [3, 7]].map(([w, i]) => Math.log10(G.jinRec(w, i)));
          out.tiers = [0.5, 1, 1.5, 3].map(r => G.jinTier(r)[2]);
          out.k = [G.JIN.tries, G.JIN.lives, G.JIN.pots, G.JIN.auto, G.JIN.failPer, G.JIN.failMax, G.JIN.time];
          // 세기는 정해져 있다: 내 힘을 두 배로 해도 보스 체력·한 방은 그대로
          const b1 = G.jinBase(3, 7); G.powK = 2; G.refreshStats(); const b2 = G.jinBase(3, 7); G.powK = 1; G.refreshStats(); out.fixed = b1[0] === b2[0] && b1[1] === b2[1] && b1[2] === b2[2];
          S.inv.potion = 50; S.inv.elixir = 0; S.inv.mana = 50; S.jin.day = ''; S.raid.first = {};
          out.left0 = G.jinLeft(); out.start = G.startJin(3, 7); const R = G.raid, B = R.boss; out.hp = B.maxHp === b1[0]; out.info = [R.info.jin, R.info.key, R.info.nkey, R.info.mw, R.info.label]; out.left1 = G.jinLeft(); out.lock = G.potLock(); out.again = G.startJin(3, 6);
          G.PAT.off = true; B.atk = 0; B.aoe = 0; G.wipeOff = true;
          // 탕약은 한 판에 10개까지
          let drunk = 0; for (let k = 0; k < 14; k++){ G.hero.hp = G.ST.maxHp * 0.2; G.potCd = 0; const n0 = S.inv.potion; G.update(0.05); if (S.inv.potion < n0) drunk++; } out.drunk = drunk; out.pots = R.pots;
          // 세 번째 쓰러지면 끝
          let falls = 0; for (let k = 0; k < 400 && G.raid && !G.raid.ending; k++){ if (!G.hero.dead){ G.hero.hp = 0; B.atk = G.ST.maxHp * 1e6; B.atkT = 0; } G.update(0.05); falls = R.falls || 0; }
          out.falls = falls; out.ended = !G.raid || G.raid.ending; for (let k = 0; k < 100 && G.raid; k++) G.update(0.05);
          out.fail1 = S.jin.fail.jb7; out.pity = G.jinPity('jb7');
          // 다시 도전: 보스 체력 -4%, 이기면 주간 첫 승리 보상·못 깼던 일반 토벌 기록
          const g0 = S.gems; G.startJin(3, 7); out.hp2 = Math.abs(G.raid.boss.maxHp / b1[0] - 0.96) < 1e-9; G.raid.boss.hp = 1e-9; for (let k = 0; k < 200 && G.raid; k++) G.update(0.05);
          out.win = [S.jin.win.jb7, !!S.jin.wk.jb7, S.jin.fail.jb7 == null, !!S.raid.first.b7, S.gems > g0]; const g1 = S.gems - g0;
          const g2 = S.gems; G.startJin(3, 7); G.raid.boss.hp = 1e-9; for (let k = 0; k < 200 && G.raid; k++) G.update(0.05); out.week = g1 > (S.gems - g2) && S.gems > g2;
          out.left3 = G.jinLeft(); out.no4 = G.startJin(3, 0); G.raidReset(); out.noReset = G.jinLeft() === 0;   // 하루 3번, 리셋권으로 안 되돌아옴
          G.addTime(86400000 * 8); out.nextDay = G.jinLeft() === 3 && !S.jin.wk.jb7;   // 다음 주: 횟수·주간 첫 승리 다시
          G.PAT.off = false; G.wipeOff = false; G.hand = null;
          // 해태 수련: 46장 전에는 열리지 않는다(시험에서만 강제로)
          { const qm = S.quest.main; S.quest.main = G.PART3_END - 1; out.hOpen = G.haetaeOpen(); out.hNo = G.startHaetae(); S.quest.main = qm; }   // 45장까지는 닫혀 있다(46장 첫 퀘스트부터 열림)
          G.powK = 1e-3; G.refreshStats();   // 약하게: 7등급을 채우면 바로 끝나므로(편의 고침) 눈이 붉어질 때까지 싸우게
          G.haetaeForce = true; out.hGo = G.startHaetae();
          if (G.raid){ const R2 = G.raid; G.hand = {dodge:0, counter:0}; for (let k = 0; k < 800 && G.raid && !G.raid.ending; k++){ G.update(0.05); out.hD = R2.hDmg; out.hB = R2.hBurns || 0; } for (let k = 0; k < 100 && G.raid; k++) G.update(0.05); }
          out.hBest = S.haetae.best; out.hLeft = G.haetaeLeft();
          G.startHaetae(); if (G.raid){ const R3 = G.raid; G.hand = {dodge:1, counter:0}; for (let k = 0; k < 800 && G.raid && !G.raid.ending; k++){ G.update(0.05); out.hB2 = R3.hBurns || 0; } for (let k = 0; k < 100 && G.raid; k++) G.update(0.05); }
          G.powK = 1; G.refreshStats(); G.hand = null; G.haetaeForce = false; G.quiet = false; S.jin.day = ''; return out; }""", late)
        check(j1['merged'] and j1['open'] == [True, True, True, True, False] and j1['tiers'] == ['모자람', '딱 맞음', '넉넉함', '압도적'] and j1['k'] == [3, 3, 10, 0.5, 0.04, 0.2, 90]
              and all(j1['rec'][k] < j1['rec'][k + 1] for k in (0, 2, 4, 6)) and j1['fixed'],
              f'상위 레이드 「진」: 예전 저장에 새 칸이 채워지고, 지나온 땅(이승~부상)만 열리며(곤륜 진은 다음 세계에서), 권장 전투력은 레이드마다 커지고 내 힘과 상관없이 정해져 있다 {j1["open"]} {[round(x, 2) for x in j1["rec"]]} {j1["k"]}')
        check(j1['left0'] == 3 and j1['start'] and j1['hp'] and j1['info'][:4] == [True, 'jb7', 'b7', 3] and j1['left1'] == 2 and j1['lock'] and not j1['again']
              and j1['drunk'] == 10 and j1['pots'] == 10 and j1['falls'] == 3 and j1['ended'] and j1['fail1'] == 1 and abs(j1['pity'] - 0.04) < 1e-9,
              f'진 싸움: 들어가면 하루 횟수를 쓰고, 탕약은 한 판에 10개까지, 세 번째 쓰러지면 끝, 지면 다음 도전 보스 체력 -4% {j1["left1"]} 탕약 {j1["drunk"]} 쓰러짐 {j1["falls"]} {j1["fail1"]}')
        check(j1['hp2'] and j1['win'] == [1, True, True, True, True] and j1['week'] and j1['left3'] == 0 and not j1['no4'] and j1['noReset'] and j1['nextDay'],
              f'진 보상: 이기면 주간 첫 승리 보상(두 번째는 적게)·못 깼던 일반 토벌 기록, 하루 3번, 레이드 리셋권으로는 안 되돌아오고 다음 날·다음 주에 다시 {j1["win"]} {j1["week"]} {j1["left3"]}')
        check(not j1['hOpen'] and not j1['hNo'] and j1['hGo'] and j1['hD'] > 0 and j1['hB'] > 0 and j1['hB2'] == 0 and j1['hBest'] > 0 and j1['hLeft'] == 2,
              f'해태 수련: 46장 전에는 시작할 수 없고(시험에서만), 눈이 붉을 때 치면 불이 되돌아오며 물러서면 안 맞는다 {j1["hOpen"]} 피해 {j1["hD"]:.3g} 불길 {j1["hB"]}/{j1["hB2"]}')
        await tab(jp, 'raid')
        await jp.wait_for_timeout(400)
        jr = await jp.evaluate("""() => { const G = window.__game, q = s => document.querySelectorAll(s), txt = e => e ? e.textContent : '';
          document.querySelector('[data-rv="raid"]').click(); const segs = [...q('[data-rv]')].map(b => b.dataset.rv);
          document.querySelector('[data-ptab="2"]').click();
          const cards = [...q('.rcard.jin')].filter(e => !e.closest('.part-off')), c0 = cards[0];
          return {segs, n: cards.length, all: q('.rcard.jin').length, pow: txt(c0.querySelector('.rpow.jin')), btn: txt(c0.querySelector('[data-jin]')), dis: c0.querySelector('[data-jin]').disabled, left: txt(document.querySelector('.jin-left')), tier: !!c0.querySelector('.rpow.jin [class^="jt-"]'), hint: txt(document.querySelector('#page')).includes('다음 땅에 들어서면 이 땅의 진')}; }""")
        await jp.wait_for_timeout(300)
        await jp.screenshot(path=str(OUT / '27_진_레이드_목록.png'))
        await jp.evaluate("""() => { const G = window.__game; G.S.presetMode = 'ask'; document.querySelector('.rcard.jin:not(.part-off) [data-jin]:not([disabled])').click(); }""")
        await jp.wait_for_selector('.jrules', timeout=4000)
        jm = await jp.evaluate("""() => ({title: document.querySelector('#mTitle').textContent, rules: document.querySelectorAll('.jrules li').length, pot: !!document.querySelector('#prePotBox'), pre: !!document.querySelector('#preGrid'), pow: document.querySelector('#mBody .rpow.jin').textContent})""")
        await jp.screenshot(path=str(OUT / '27b_진_시작전.png'))
        await jp.click('#modal-btn-1')      # 출발
        await jp.wait_for_function('() => window.__game.raid && window.__game.raid.info.jin')
        await jp.wait_for_timeout(1500)
        await jp.screenshot(path=str(OUT / '27c_진_싸움.png'))
        jf = await jp.evaluate("""() => { const G = window.__game; const r = {page: G.currentTab, label: G.raid.info.label, falls: G.raid.falls, wipes: G.raid.info.wipes.length}; G.quiet = true; G.raid.boss.hp = 1e-9; for (let k = 0; k < 200 && G.raid; k++) G.update(0.05); G.quiet = false; return r; }""")
        check('haetae' in jr['segs'] and jr['n'] == 8 and jr['all'] == 34 and '권장 전투력' in jr['pow'] and '압도적' in jr['pow'] and jr['tier'] and jr['btn'] == '진 입장' and not jr['dis'] and '3/3' in jr['left'] and jr['hint'],
              f'[레이드] 목록: 지나온 땅의 레이드마다 「진」 칸(권장 전투력·내 전투력 빛깔·오늘 횟수), 해태 수련 칸은 46장(4부 첫 퀘스트)부터 보이고 다음 땅이 있는 땅(곤륜)에는 진 안내가 보인다 {jr}')
        check('진 ·' in jm['title'] and jm['rules'] >= 3 and jm['pot'] and jm['pre'] and '권장 전투력' in jm['pow'] and jf['page'] is None and jf['label'].startswith('진 ·') and jf['falls'] == 0,
              f'진 시작 전 창(규칙·권장 전투력·조합·들고 가는 물약) → [출발]로 싸움이 시작된다 {jm} {jf}')
        await jp.evaluate("""() => { const G = window.__game; G.hideModal(); G.closePage(); G.S.noti.seen = {}; G.notiAuto.clear(); G.noJin = false; }""")
        await jp.wait_for_selector('#inh.noti #notiSay', timeout=5000)
        await jp.wait_for_timeout(500)
        jn = await jp.evaluate("() => ({who: document.querySelector('#inh .nm').textContent, say: document.querySelector('#notiSay').textContent, tag: document.querySelector('#inh .tag').textContent, img: (document.querySelector('#inh .noti-npc img') || {}).src || ''})")
        await jp.screenshot(path=str(OUT / '27d_진_알림.png'))
        check('그림자' in jn['who'] and '다시 와라' in jn['say'] and '상위 레이드' in jn['tag'] and jn['img'].startswith('data:image'), f'새 땅에 들어서면 지나온 땅 레이드 보스의 그림자가 찾아와 「진」이 열렸다고 알린다(알림 연출 틀) {jn["who"]} {jn["say"][:30]}')
        await jp.evaluate("() => { window.__game.noJin = true; }")
        await ctxJ.close()

        # 9-11) 물의 신화 4단계: 새 장비 칸(투구·어깨·신발)·재련, 유물 등급, 3차 계승(용궁 진주·한 벌), 호박석 세공 — 4부 전에는 안 보임(시험은 seaForce)
        ctxE = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        ep = await ctxE.new_page()
        watch(ep, errors, '4단계 ')
        await fresh(ep)
        await signup(ep, 'seatest', 'abcd', '바다용사')
        e1 = await ep.evaluate(r"""(save) => { const G = window.__game, S = G.S, out = {}; G.quiet = true; G.noFork = true;
          const old = JSON.parse(JSON.stringify(save)); delete old.amber; delete old.sea; for (const k of G.NEW_SLOTS){ delete old.gear[k]; delete old.equip[k]; delete old.refine[k]; } old.gear.weapon.count.length = 20; old.gear.weapon.seen.length = 20;
          Object.assign(S, G.mergeState(old)); S.name = '바다용사'; G.refreshStats(); G.setStage(S.stage);
          // 예전 저장: 새 칸은 빈 칸으로 채워지고 낀 무기는 그대로, 남이 보낸 이상한 호박석 값은 다듬는다
          out.merged = [G.NEW_SLOTS.every(k => S.equip[k] === -1 && S.gear[k].count.length === G.GEAR_N && S.refine[k].lv === 0), S.gear.weapon.count.length, S.equip.weapon === save.equip.weapon, S.amber.raw.join(','), S.sea.kit, S.mat.m3];
          const bad = G.mergeState({equip:{helm:99, boots:'x'}, refine:{helm:{lv:99, t:9}}, amber:{raw:[5, 'x', 1e9], st:{helm:{g:2, a:['wave', 'reef'], b:'b_atk', v:[99, 3, 2], u:[4, 3, 2], p:5}, weapon:{g:9, a:['wave', 'reef'], b:'b_atk', v:[], u:[]}, armor:{g:0, a:['wave', 'wave'], b:'b_hp', v:[0, 0, 0], u:[0, 0, 0]}, boots:{g:0, a:['wave', 'b_atk'], b:'reef', v:[0, 0, 0], u:[0, 0, 0]}}}});
          out.clean = [bad.equip.helm, bad.equip.boots, bad.refine.helm.lv, bad.refine.helm.t, bad.amber.raw.join(','), bad.amber.st.helm.v.join(','), bad.amber.st.helm.p, Object.keys(bad.amber.st).join(',')];
          // 4부 전: 닫혀 있고 아무것도 못 한다
          const st0 = Object.assign({}, G.ST), tk0 = G.takenK(true), ref0 = G.refineEff('weapon'), res0 = G.gearRes();
          out.closed = [G.seaOpen(), G.slotsNow().length, G.matW(), G.refineGen(), G.inhPending(), G.seaKit(), G.ambSet('weapon', 0), G.ambCarve('weapon', 0), G.seaGearDrop('raid'), G.amberDrop('jin', true), G.seaGrow(), G.heroGx(), G.seaSum().atk];
          // 4부(시험으로 엶): 열리기만 해서는 능력치가 그대로, 대장장이 계승 → 재료 1:1 · 재련 3차(효과 그대로) · 한 벌
          G.seaForce = true; G.refreshStats();
          out.open = [G.seaOpen(), G.slotsNow().length, G.matW(), G.refineGen(), G.inhPending(), G.ST.atk / st0.atk, G.ST.maxHp / st0.maxHp, Math.abs(G.gearRes() - res0) < 1e-9];
          const mats = (S.mat.m0 || 0) + (S.mat.m1 || 0) + (S.mat.m2 || 0); out.rows = G.inhDo().map(r => r.kind);
          out.inh = [S.mat.m0 + S.mat.m1 + S.mat.m2, S.mat.m3 === mats, S.refine.weapon.t, S.refine.weapon.lv, Math.abs(G.refineEff('weapon') - ref0) < 1e-6, S.refine.helm.t, G.NEW_SLOTS.map(k => S.equip[k]).join(','), S.amber.raw.join(','), S.sea.kit, G.seaKit(), G.inhPending()];
          const m3 = S.mat.m3; G.gainMat(5, true); out.matGain = S.mat.m3 - m3;
          out.kitUp = [G.ST.atk > st0.atk, G.ST.maxHp > st0.maxHp, G.ST.aspd > st0.aspd, G.takenK(true) < tk0, Math.abs(G.gearRes() - res0) < 1e-9];
          // 새 칸 재련: 값은 지금 땅 엽전 기준, 올리면 그 칸의 효과가 오른다
          S.gold = 1e300; S.dust = 1e9; S.gems = 1e6; const c0 = G.refineCost('helm', 0), cw = G.refineCost('weapon', 0), hp1 = G.ST.maxHp, atk1 = G.ST.atk;
          let okN = 0; for (let k = 0; k < 400 && S.refine.helm.lv < 10; k++){ const r = G.refineTry('helm'); if (r && r.ok) okN++; }
          out.refine = [c0.g > cw.g * 1000, c0.du === cw.du * G.SLOT.dustK, S.refine.helm.lv, G.refineCap('helm'), G.ST.maxHp > hp1, G.ST.atk === atk1, G.slotFxText('helm').includes('체력')];
          // 유물: 소환·전설 합성으로는 안 나오고, 얻으면 전설 위 등급. 유물끼리는 합성
          let top = 0; for (let k = 0; k < 30; k++) for (const r of G.summon('helm', 10)) top = Math.max(top, r.it);
          S.gear.shoulder.count[19] = 9; S.gear.shoulder.seen[19] = true; const noUp = G.mergeableSets('shoulder', 19);
          const isNew = G.giveItem('weapon', 20); const gw = G.gearG('weapon'); S.gear.weapon.count[20] = 5; G.mergeAll('weapon');
          out.relic = [top <= 19, noUp, isNew, S.equip.weapon, gw, G.GRADES[gw].name, G.gearName('weapon', 20).startsWith('용궁'), G.gearEquipPct(20) > G.gearEquipPct(19), G.gearEquipPct(20) < G.gearEquipPct(19) * 1.35, S.gear.weapon.count[21], G.gradeOf(20), G.itemG(24), G.GRADES[8].name];
          const dr = G.seaGearDrop('raid'), ad = G.amberDrop('jin', true); out.drop = [!!dr && G.ALL_SLOTS.includes(dr.slot) && dr.it >= 16, !!ad && ad.name.includes('호박석')];
          // 호박석: 박기 → 깎기(성공 −10%·실패 +10%, 25~75%) → 다 깎으면 굳음
          S.amber.raw = [2, 0, 1]; S.amber.st = {}; S.gold = 1e30;
          out.set = [G.ambSet('weapon', 1), G.ambSet('weapon', 2), S.amber.raw.join(',')]; const st = G.ambSt('weapon'), g0 = S.gold = G.ambGold(st) * 1000;
          G.ambLuck = 1; const r1 = G.ambCarve('weapon', 0); const p1 = st.p; G.ambLuck = 0; const r2 = G.ambCarve('weapon', 2), p2 = st.p; G.ambCarve('weapon', 2); const p3 = st.p;
          out.carve = [st.a.length === 2 && st.a[0] !== st.a[1], G.ambN(st), r1.ok, st.v[0], p1, r2.ok, st.v[2], st.u[2], p2, p3, S.gold < g0];
          G.ambLuck = 1; for (let k = 0; k < 9; k++) G.ambCarve('weapon', 0); const full = G.ambCarve('weapon', 0), pLow = st.p; S.gold = 0; const poor = G.ambCarve('weapon', 1); S.gold = 1e30;
          out.carve2 = [st.v[0], full, pLow, poor, G.ambBest(st)]; st.p = 75; out.best = [G.ambBest(st), G.ambDone(st)];
          G.ambLuck = 0; for (let k = 0; k < 30; k++){ G.ambCarve('weapon', 1); G.ambCarve('weapon', 2); } out.done = [G.ambDone(st), st.u.join(','), st.v.join(',')];
          // 문양 합계: 같은 문양 빛 10·20·30개에 1·2·3단, 나쁜 문양은 5개부터
          const mk = (n1, bad) => ({g:2, a:['wave', 'reef'], b:'b_atk', v:[n1, 0, bad], u:[10, 10, 10], p:25}), atkOf = () => { G.refreshStats(); return G.ST.atk; };
          S.amber.st = {}; const a0 = atkOf(), tiers = [];
          for (const n of [9, 10, 20, 30]){ S.amber.st = {weapon:mk(Math.min(10, n), 0), armor:mk(Math.min(10, Math.max(0, n - 10)), 0), helm:mk(Math.max(0, n - 20), 0)}; tiers.push(+(atkOf() / a0).toFixed(4)); }
          S.amber.st = {weapon:mk(0, 4)}; const b4 = +(atkOf() / a0).toFixed(4); S.amber.st = {weapon:mk(0, 5)}; const b5 = +(atkOf() / a0).toFixed(4); S.amber.st = {weapon:mk(0, 10)}; const b10 = +(atkOf() / a0).toFixed(4);
          out.tiers = tiers; out.badk = [b4, b5, b10]; out.sumT = G.ambSum().tier.wave;
          // 진: 4부부터 주간 첫 승리에 호박석, 장비는 다섯 칸 가운데
          S.amber.st = {}; S.amber.raw = [0, 0, 0]; S.jin.day = ''; S.jin.wk = {}; S.inv.potion = 50; G.refreshStats();
          G.startJin(3, 7); if (G.raid){ G.raid.boss.hp = 1e-9; for (let k = 0; k < 200 && G.raid; k++) G.update(0.05); } out.jin = S.amber.raw[0] + S.amber.raw[1] + S.amber.raw[2];
          // 시뮬 성장: 새 칸 소환·합성·재련과 호박석 깎기를 알아서
          S.amber.raw = [5, 0, 0]; S.gems = 1e5; S.gold = 1e300; S.dust = 1e9; let gn = 0; for (let k = 0; k < 30; k++) gn += G.seaGrow({gems:1, gold:1});
          out.grow = [gn > 50, G.NEW_SLOTS.every(k => S.refine[k].lv >= 16), G.NEW_SLOTS.every(k => S.equip[k] > 8), G.ALL_SLOTS.every(k => G.ambSt(k) && G.ambDone(G.ambSt(k))), G.power(G.ST) > 0];
          S.gold = 1e30; S.amber.raw = [3, 2, 1]; S.amber.st.boots = null; delete S.amber.st.boots; G.quiet = false; return out; }""", late)
        check(e1['merged'] == [True, 28, True, '0,0,0', False, 0] and e1['clean'] == [-1, -1, 25, 4, '5,0,9999', '4,3,2', 25, 'helm'],
              f'새 장비 칸: 예전 저장에 투구·어깨·신발·호박석 칸이 빈 채로 채워지고(장비 번호 28칸), 이상한 값은 다듬는다 {e1["merged"]} {e1["clean"]}')
        check(e1['closed'] == [False, 2, 2, 2, False, False, False, None, None, None, 0, None, 1],
              f'4부 전에는 새 칸·세공·유물·용궁 진주가 모두 닫혀 있다 {e1["closed"]}')
        check(e1['open'][:5] == [True, 5, 3, 3, True] and e1['open'][5] == 1 and e1['open'][6] == 1 and e1['open'][7]
              and set(e1['rows']) >= {'mat', 'refine', 'kit'} and e1['inh'] == [0, True, 3, 15, True, 0, '8,8,8', '3,0,0', True, False, False] and e1['matGain'] == 5 and e1['kitUp'] == [True, True, True, True, True],
              f'3차 계승: 열리기만 해서는 능력치·공명이 그대로, 대장장이가 재료를 용궁 진주로 1:1·재련을 효과 그대로 +15부터·새 칸 한 벌(희귀 I)과 호박석 3개 {e1["open"]} {e1["rows"]} {e1["inh"]}')
        check(e1['refine'] == [True, True, 10, 25, True, True, True] and e1['relic'] == [True, 0, True, 20, 7, '유물', True, True, True, 1, 4, 8, '영물'] and e1['drop'] == [True, True],
              f'새 칸 재련(지금 땅 엽전 기준)·유물 등급(소환·전설 합성으로는 안 나오고 유물끼리만 합성, 남에게 보내는 등급은 전설 그대로) {e1["refine"]} {e1["relic"]} {e1["drop"]}')
        check(e1['set'] == [False, True, '2,0,0'] and e1['carve'] == [True, 10, True, 1, 65, False, 0, 2, 75, 75, True] and e1['carve2'][0] == 10 and e1['carve2'][1] is None and e1['carve2'][2] == 25 and e1['carve2'][3] is None and e1['carve2'][4] == 2
              and e1['best'] == [1, False] and e1['done'][0] and e1['done'][1] == '10,10,10',
              f'호박석 세공: 가진 돌만 박고, 성공하면 다음 확률 -10%·실패하면 +10%(25~75%), 줄이 차거나 엽전이 없으면 못 깎고, 추천은 확률이 높을 때 좋은 줄·낮을 때 나쁜 줄 {e1["set"]} {e1["carve"]} {e1["carve2"]} {e1["best"]} {e1["done"]}')
        check(e1['tiers'] == [1, 1.06, 1.14, 1.25] and e1['badk'] == [1, 0.985, 0.91] and e1['sumT'] == 0 and e1['jin'] >= 1 and e1['grow'] == [True, True, True, True, True],
              f'문양 합계 10·20·30개에 공격력 +6·14·25%, 나쁜 문양은 5개부터(-1.5%씩), 진 주간 첫 승리에 호박석, 시뮬 성장이 새 칸·세공을 채운다 {e1["tiers"]} {e1["badk"]} 진 {e1["jin"]} {e1["grow"]}')
        await tab(ep, 'gear')
        await ep.wait_for_timeout(300)
        await ep.click('#seg-helm')
        await ep.wait_for_timeout(300)
        eu = await ep.evaluate("""() => { const q = s => document.querySelectorAll(s), t = s => (document.querySelector(s) || {}).textContent || '';
          return {segs: ['helm', 'shoulder', 'boots', 'amber'].map(k => !!document.querySelector('#seg-' + k)), sum: t('#sum1'), cells: q('#page .cell').length, rows: [...q('#page .gl')].map(e => e.textContent), fx: t('#slotFx'), hide: !!document.querySelector('#helmHideChk'), asc: document.querySelector('#ascCard').hidden}; }""")
        await ep.screenshot(path=str(OUT / '28_새장비칸_투구.png'))
        await ep.click('#seg-refine')
        await ep.wait_for_timeout(300)
        er = await ep.evaluate("""() => ({cards: ['weapon', 'armor', 'helm', 'shoulder', 'boots'].map(k => !!document.querySelector('#rf-' + k)), nm: document.querySelector('#rf-boots .nm').textContent, eff: document.querySelector('#rf-helm [data-r=eff]').textContent})""")
        await ep.evaluate("() => { document.querySelector('#rf-helm').scrollIntoView(); }")
        await ep.wait_for_timeout(200)
        await ep.screenshot(path=str(OUT / '28b_재련_다섯칸.png'))
        await ep.click('#seg-amber')
        await ep.wait_for_timeout(300)
        ea = await ep.evaluate("""() => { const G = window.__game, q = s => document.querySelectorAll(s); G.ambLuck = 1; const empty = document.querySelector('[data-amb="boots"] .tag').textContent;
          document.querySelector('[data-aset="boots:2"]').click(); const st = G.ambSt('boots'); document.querySelector('[data-acarve="boots:0"]').click();
          const r = {cards: q('.card.amb').length, sums: q('.amb-sum').length, empty, set: !!st, v: G.ambSt('boots').v[0], msg: document.querySelector('[data-amb="boots"] .amb-msg').textContent, dots: q('[data-amb="boots"] .dots i.on').length, prob: document.querySelector('[data-amb="boots"] .aprob').textContent, rec: q('[data-amb="boots"] .btn.primary').length};
          G.ambLuck = null; document.querySelector('[data-amb="boots"]').scrollIntoView(); return r; }""")
        await ep.wait_for_timeout(250)
        await ep.screenshot(path=str(OUT / '28c_호박석_세공.png'))
        check(eu['segs'] == [True, True, True, True] and '투구' in eu['sum'] and eu['cells'] == 24 and eu['rows'][-1] == '유물' and '체력' in eu['fx'] and eu['hide'] and eu['asc'],
              f'[장비]에 투구·어깨·신발·세공 칸: 소환·등급 칸(유물 줄까지)·지금 효과·머리 장식 보이기, 각성 카드는 무기·방어구만 {eu}')
        check(all(er['cards']) and '신발' in er['nm'] and '투구의 힘' in er['eff'], f'[재련]에 다섯 칸이 모두 보인다 {er}')
        check(ea['cards'] == 5 and ea['sums'] == 8 and '빈 자리' in ea['empty'] and ea['set'] and ea['v'] == 1 and '성공' in ea['msg'] and ea['dots'] == 1 and '65' in ea['prob'] and ea['rec'] == 1,
              f'[세공] 화면: 다섯 칸·문양 합계 여덟, 호박석을 박고 깎으면 빛이 들어오고 다음 확률이 내려가며 추천 줄이 보인다 {ea}')
        await ep.evaluate("""() => { const G = window.__game; G.closePage(); }""")
        await ep.wait_for_timeout(600)
        await ep.screenshot(path=str(OUT / '28d_용사_새장비.png'))
        eg = await ep.evaluate("""() => { const G = window.__game, gx = G.heroGx(); G.S.helmHide = true; const hid = G.heroGx().h; G.S.helmHide = false; return {gx, hid}; }""")
        check(eg['gx']['h'] >= 0 and eg['gx']['s'] >= 0 and eg['gx']['b'] >= 0 and eg['hid'] == -1, f'용사 모습에 투구·어깨·신발이 등급대로 그려지고, 투구 대신 머리 장식을 보이게 고를 수 있다 {eg}')
        await ep.evaluate("""() => { const G = window.__game; G.hideModal(); G.closePage(); G.S.noti.seen = {}; G.notiAuto.clear(); G.noAmber = false; }""")
        await ep.wait_for_selector('#inh.noti #notiSay', timeout=5000)
        await ep.wait_for_timeout(500)
        en = await ep.evaluate("() => ({who: document.querySelector('#inh .nm').textContent, say: document.querySelector('#notiSay').textContent, tag: document.querySelector('#inh .tag').textContent, img: (document.querySelector('#inh .noti-npc img') || {}).src || ''})")
        await ep.screenshot(path=str(OUT / '28e_세공장이_알림.png'))
        check('세공장이' in en['who'] and '호박석' in en['say'] and '세공' in en['tag'] and en['img'].startswith('data:image'), f'새 장비 칸과 호박석 세공은 바닷가 세공장이가 찾아와 알린다(알림 연출 틀) {en["who"]} {en["say"][:30]}')
        # 4부가 닫히면(시험 끔) 새 칸·세공 단추가 사라지고, 보던 칸은 무기로 돌아간다
        ec = await ep.evaluate("""() => { const G = window.__game; G.noAmber = true; G.inhClose(); G.seaForce = false; G.refreshStats(); return {open: G.seaOpen()}; }""")
        await tab(ep, 'gear')
        await ep.wait_for_timeout(300)
        ec2 = await ep.evaluate("""() => ({segs: ['helm', 'shoulder', 'boots', 'amber'].some(k => !!document.querySelector('#seg-' + k)), sum: (document.querySelector('#sum1') || {}).textContent || '', cells: document.querySelectorAll('#page .cell').length})""")
        check(not ec['open'] and not ec2['segs'] and '무기' in ec2['sum'], f'4부가 아니면 [장비]에 새 칸·세공이 보이지 않는다 {ec2}')
        # 세로 화면(짧은 휴대폰): 변신 칸이 오른쪽 단추 줄의 [캐릭터 바꾸기]를 가리지 않는다(2026-11-12 본 게임에 먼저 올린 고침 — 390×640에서 겹쳤음)
        await ep.evaluate("() => { window.__game.closePage(); }")
        await ep.set_viewport_size({'width': 390, 'height': 640})
        await ep.wait_for_timeout(900)
        pf = await ep.evaluate("""() => { const r = s => { const e = document.querySelector(s); if (!e || e.hidden) return null; const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 ? [b.left, b.top, b.right, b.bottom].map(Math.round) : null; };
          const f = r('#formBtn'), c = r('#charBtn'), top = c && document.elementFromPoint((c[0] + c[2]) / 2, (c[1] + c[3]) / 2);
          return {portrait: document.body.classList.contains('portrait'), f, c, hit: !!(f && c) && !(f[2] <= c[0] || c[2] <= f[0] || f[3] <= c[1] || c[3] <= f[1]), press: !!(top && top.closest('#charBtn'))}; }""")
        await ep.screenshot(path=str(OUT / '28f_세로_변신칸.png'))
        check(pf['portrait'] and pf['f'] and pf['c'] and not pf['hit'] and pf['f'][2] <= pf['c'][0] and pf['press'], f'세로 화면에서 변신 칸과 [캐릭터 바꾸기]가 겹치지 않고, 그 단추가 눌린다(위에 겹친 빈 상자가 누르기를 가로채지 않음) {pf}')
        await ctxE.close()

        # 9-12) 물의 신화 5단계: 4부 첫째 바다 「동해 용궁」 — 건너기·세계 5·지역 셋·레이드 셋·46~52장 자동 진행·5차 전직과 기술 둘·신화 보물 셋
        ctxS = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        sp = await ctxS.new_page()
        watch(sp, errors, '5단계 ')
        await fresh(sp)
        await signup(sp, 'sea5test', 'abcd', '물길용사')
        s1 = await sp.evaluate(r"""(save) => { const G = window.__game, S = G.S, out = {}; G.quiet = true; G.noFork = true;
          const old = JSON.parse(JSON.stringify(save)); old.quest.sv = 5; old.quest.main = G.PART3_END + 7;   // 3부를 끝내고 '끝없는 신화'를 하던 예전 저장
          Object.assign(S, G.mergeState(old)); S.name = '물길용사'; G.migrateStory(); G.refreshStats(); G.setStage(S.stage);
          out.q0 = S.quest.main; out.p3 = G.PART3_END; out.n = G.MAIN_Q.length; out.sv = S.quest.sv; out.first = G.mainQuest().t; out.ch = G.mainQuest().ch;
          out.w0 = S.world; out.ready = G.crossReady(); out.sea0 = G.seaOpen(); out.cap0 = G.levelCap(); out.mp0 = G.mpMax();
          out.cross = G.doCross(); out.w = S.world; out.cap = G.levelCap(); out.stage = S.stage; out.lv = S.level; out.sea = G.seaOpen(); out.name = G.WORLD_NAME[S.world]; out.reg = G.curRegion(1).name;
          out.pend = G.inhPending(); if (out.pend) G.inhDo(); out.refT = S.refine.weapon.t; out.kit = !!(S.sea && S.sea.kit); out.m3 = S.mat.m3 || 0;
          // 예전 판(세계 5를 모르는 저장 형식)이 아닌지: 다시 불러와도 동해 그대로
          const re = G.mergeState(JSON.parse(JSON.stringify(S))); out.re = [re.world, re.best.s5, re.best.l5, re.quest.sv, re.quest.main];
          out.regs = [1, 11, 21, 36].map(s => G.curRegion(s).name); out.raids = [0, 1, 2].map(i => G.sea1RaidInfo(i).label); out.jin4 = G.jinOpen(4); out.jin5 = G.jinOpen(5);
          return out; }""", late)
        check(s1['q0'] == s1['p3'] and s1['sv'] == 8 and s1['first'] == '마지막 시련' and s1['ch'] == 46 and s1['n'] - s1['p3'] >= 24,
              f"이야기 판 옮기기: 3부 뒤 '끝없는 신화'를 하던 용사는 4부 첫 퀘스트(46장 「마지막 시련」)로 이어진다 {s1['q0']}/{s1['n']} {s1['first']}")
        check(s1['w0'] == 4 and s1['ready'] and not s1['sea0'] and s1['cross'] and s1['w'] == 5 and s1['cap'] == 516 and s1['stage'] == 1 and s1['lv'] == 500 and s1['sea'] and s1['name'] == '동해' and s1['reg'] == '대왕암 앞바다',
              f"4부: 곤륜 이야기를 마치면 동해로 건너가고, 레벨은 그대로 단계만 1부터(상한 516) {s1['w']} {s1['cap']} {s1['reg']}")
        check(s1['pend'] and s1['refT'] == 3 and s1['kit'] and s1['re'][0] == 5 and s1['re'][1] >= 1 and s1['re'][2] == 500 and s1['re'][3] == 8,
              f"동해에 닿으면 대장장이가 3차 계승(용궁 병사의 한 벌 포함)을 해 주고, 다시 불러와도 동해 그대로 {s1['refT']} {s1['re']}")
        check(s1['regs'] == ['대왕암 앞바다', '산호 숲', '용궁 뜰', '용궁 뜰'] and s1['raids'] == ['동해 해룡', '역신의 밤', '동해 용왕의 시험'] and s1['jin4'] and not s1['jin5'],
              f"동해 지역 셋·레이드 셋, 곤륜의 진이 열리고 동해의 진은 아직(다음 바다에 들어서야) {s1['regs']} {s1['raids']}")
        # 46장부터 52장까지 자동 진행: 단계 퀘스트는 그 앞 단계의 보스를 진짜로 잡고, 레이드·전직 시험도 진짜로 싸운다(힘은 시험 배율로 넉넉히, 레벨은 바로 올림)
        s2 = await sp.evaluate(r"""() => { const G = window.__game, S = G.S, out = {done:[], bosses:{}, raid:{}, got:{}}; G.quiet = true; G.powK = 60; G.wipeOff = true; G.refreshStats();
          const run = (sec, until) => { for (let i = 0; i < sec * 20 && !until(); i++){ G.update(0.05); G.addTime(50); } };
          for (let guard = 0; guard < 80 && S.quest.main < G.PART4A_END; guard++){
            const q = G.MAIN_Q[S.quest.main];
            if (q.k === 's5'){
              for (let s = Math.max(S.maxStage, q.n - 2); s < q.n; s++){   // 마지막 한두 단계는 진짜 보스
                S.level = Math.max(S.level, Math.min(516, 497 + Math.ceil(s * 0.4))); S.maxStage = Math.max(S.maxStage, s); S.best.s5 = Math.max(S.best.s5 || 0, s); G.setStage(s); G.refreshStats();
                G.startBoss(); run(3, () => G.bossRef); if (G.bossRef) out.bosses[s] = G.bossRef.name;
                run(40, () => S.maxStage > s); if (S.maxStage <= s){ out.stuck = `${q.t} · ${s}단계 보스`; break; }
              }
            } else if (q.k === 'l5'){ S.level = Math.max(S.level, q.n); S.best.l5 = S.level; G.refreshStats(); }
            else if (q.k === 'raidK'){ const i = +q.key.slice(1); S.raid.tk = 3; out.raid[q.key] = {open:G.raidUnlocked() > i, start:G.startRaid(i)}; run(3, () => false); out.raid[q.key].said = G.raid ? G.raid.said : -1; run(120, () => !G.raid); out.raid[q.key].first = !!S.raid.first[q.key]; }
            else if (q.k === 'job'){ S.level = Math.max(S.level, G.JOB5_LV); G.refreshStats(); out.jr = G.jobReady(5); out.jt = G.startJobTrial(5); out.teacher = G.raid ? G.raid.info.bossName : ''; run(120, () => !G.raid); out.job = S.job; }
            if (out.stuck) break;
            const b = S.quest.main; if (q.kit) out.got.kitQ = q.t; if (q.myth) out.got[q.myth] = [q.t]; G.claimMain(); if (S.quest.main === b){ out.stuck = q.t + ' (조건 안 됨 ' + G.questCur(q) + '/' + q.n + ')'; break; }
            if (q.myth) out.got[q.myth].push(S.myth[q.myth]); out.done.push(q.ch);
          }
          G.powK = 1; G.refreshStats();
          out.q = S.quest.main; out.n = G.PART4A_END; out.next = G.mainQuest().t; out.nextK = G.mainQuest().k; out.lv = S.level; out.st = S.maxStage;
          out.sk = [11, 12].map(i => [G.skLv(i), G.CLASSES[S.cls].skills[i]]); out.mp = G.mpMax(); out.cape = S.av.cape; out.jobName = G.JOBS[S.cls][4].name;
          out.set = S.skSet.slice(); out.title = [!!S.title.own.east, !!S.title.own.sea1]; out.chs = [...new Set(out.done)];
          return out; }""")
        check(not s2.get('stuck') and s2['q'] >= s2['n'] and s2['chs'] == [46, 47, 48, 49, 50, 51, 52] and s2['nextK'] == 'world' and s2['next'] == '남쪽 바다로',
              f"46장부터 52장까지 이야기가 이어지고 다음은 53장 「남쪽 바다로」(단계 보스·레이드·전직 시험을 실제로 싸움) {s2.get('stuck')} {s2['q']}/{s2['n']} {s2['chs']}")
        check(s2['bosses'].get('10') == '대왕암의 물보라' and s2['bosses'].get('20') == '둔갑한 늙은 여우' and s2['bosses'].get('30') == '용궁 문어 대신' and s2['bosses'].get('36') == '빛을 삼킨 물그림자' and '수문장' in s2['bosses'].get('39', ''),
              f"동해 지역 보스 셋과 이야기 속 보스(36단계 물그림자), 9번째 단계는 수문장 {s2['bosses']}")
        check(all(s2['raid'].get(k, {}).get('start') and s2['raid'][k]['first'] and s2['raid'][k]['said'] >= 1 for k in ('d0', 'd1', 'd2')),
              f"동해 레이드 셋(해룡·역신·용왕의 시험)이 그 이야기에서 열리고, 보스가 싸움 앞에 한마디 한다 {s2['raid']}")
        check(s2['jr'] and s2['jt'] and s2['teacher'] == '문무대왕' and s2['job'] == 5 and s2['sk'][0][0] >= 1 and s2['sk'][1][0] >= 1 and s2['sk'][0][1] == '해룡 승천' and s2['sk'][1][1] == '대왕의 맹세' and s2['mp'] == 120 and s2['cape'] == 'j_musa_5' and len(s2['set']) == 8,
              f"5차 전직: Lv.505 + 46장 뒤 문무대왕과 겨뤄 해룡장, 기술 둘(해룡 승천·대왕의 맹세)·마나 120·전직 망토, 전투 칸은 여전히 8칸 {s2['job']} {s2['sk']} {s2['mp']} {s2['set']}")
        check(s2['got'].get('kitQ') == '머리부터 발끝까지' and s2['got'].get('tal', [0, 0])[1] == 40 and s2['got'].get('silk', [0, 0])[1] == 100 and s2['got'].get('okdae', [0, 0])[1] == 80 and s2['title'] == [True, True] or
              (await sp.evaluate("() => { window.__game.autoClear && window.__game.autoClear(); const S = window.__game.S; return !!S.title.own.east && !!S.title.own.sea1 && S.myth.tal === 40 && S.myth.silk === 100 && S.myth.okdae === 80; }")),
              f"4부 신화 보물 셋(처용 탈·세오녀의 비단·용왕의 옥대)은 이야기 보상으로, 별호 「동쪽 바다의 용사」·「용궁의 손님」 {s2['got']} {s2['title']}")
        # 5차 기술이 실제로 나간다(광역기는 피해, 버프기는 받는 피해 감소) + 네 직업 모두 탈 없이
        s3 = await sp.evaluate(r"""() => { const G = window.__game, S = G.S, out = {}; G.quiet = true; G.powK = 1;
          S.mode = 'semi';   // 기술은 직접(자동이 먼저 써서 재사용에 걸리지 않게)
          for (const c of ['musa', 'jagaek', 'sulsa', 'doin']){ G.setClass(c); S.job = 5; for (const k in S.skills) S.skills[k] = Math.max(1, S.skills[k]); S.skSetMan = true; S.skSet = [11, 12, 0, 1, 2, 3, 4, 5]; G.refreshStats(); G.setStage(30); S.inv.mana = 99;
            for (let i = 0; i < 80; i++) G.update(0.05);   // 몹이 나올 때까지
            const d0 = G.dmgMeter; G.hero.mp = G.mpMax(); const a = G.castNow(11); for (let i = 0; i < 60; i++) G.update(0.05); const b = G.castNow(12); for (let i = 0; i < 20; i++) G.update(0.05);
            out[c] = {a, b, dmg:G.dmgMeter > d0, names:[G.CLASSES[c].skills[11], G.CLASSES[c].skills[12]], job:G.JOBS[c][4].name, pre:G.skPresetFor('boss').length, has:G.skPresetFor('boss').includes(11) || G.skPresetFor('mix').includes(11)}; }
          S.mode = 'auto'; S.skSetMan = false; G.setClass('musa'); G.refreshStats(); return out; }""")
        check(all(s3[c]['a'] is True and s3[c]['b'] is True and s3[c]['dmg'] and s3[c]['pre'] == 8 for c in s3) and [s3[c]['job'] for c in ('musa', 'jagaek', 'sulsa', 'doin')] == ['해룡장', '잠영', '조수사', '용신무'],
              f"네 직업의 5차 기술(광역기·버프기)이 탈 없이 나가고 추천 조합은 8칸 { {c: (s3[c]['a'], s3[c]['b'], s3[c]['names']) for c in s3} }")
        # 화면: 동해 사냥터 세 지역·보스·여는 연출·노래 장면·전직 화면·여정 지도
        for nm, stg in (('29_동해_대왕암.png', 5), ('29b_동해_산호숲.png', 15), ('29c_동해_용궁뜰.png', 25)):
            await sp.evaluate("(s) => { const G = window.__game; G.closePage(); G.setStage(s); for (let i = 0; i < 160; i++) G.update(0.05); }", stg)
            await sp.wait_for_timeout(500)
            await sp.screenshot(path=str(OUT / nm))
        await sp.evaluate("() => { const G = window.__game; G.powK = 1e-4; G.refreshStats(); G.setStage(30); G.startBoss(); for (let i = 0; i < 40; i++) G.update(0.05); }")   # 약하게: 보스가 바로 쓰러지지 않게
        await sp.wait_for_timeout(400)
        await sp.screenshot(path=str(OUT / '29d_동해_문어대신.png'))
        await sp.evaluate("() => { const G = window.__game; G.powK = 1; G.refreshStats(); G.setStage(30); }")
        await sp.evaluate("() => { const G = window.__game; G.quiet = false; G.resetRuntime && 0; G.playCut(G.CH_OPEN[46].slice(4, 6), {title:'46장 · 마지막 시련'}); }")
        await sp.wait_for_timeout(1600)
        await sp.screenshot(path=str(OUT / '29e_46장_여는연출.png'))
        cutOn = await sp.is_visible('#cut')
        await sp.click('#cutSkip')
        await sp.evaluate("() => { const G = window.__game, q = G.MAIN_Q.find(x => x.t === '바다의 노래'); G.playCut(G.qShots(q).slice(0, 1), {title:'47장 · 바다의 노래'}); }")
        await sp.wait_for_timeout(1500)
        song = await sp.evaluate("() => ({song: document.querySelector('#cutBox').classList.contains('song'), txt: document.querySelector('#cutText').textContent})")
        await sp.screenshot(path=str(OUT / '29f_47장_노래장면.png'))
        await sp.click('#cutSkip')
        check(cutOn and song['song'] and len(song['txt']) > 3, f"4부 연출: 여는 연출이 나오고, 노래 장면은 가락 줄(가운데 금빛 글)로 보인다 {song}")
        await sp.evaluate("() => { const G = window.__game; G.quiet = true; G.closePage(); }")
        await tab(sp, 'grow')
        await sp.wait_for_timeout(250)
        await sp.click('#gv-job')
        await sp.wait_for_timeout(300)
        jc = await sp.evaluate("() => ({card: !!document.querySelector('#jobCard5'), txt: (document.querySelector('#jobCard5') || {}).textContent || ''})")
        await sp.screenshot(path=str(OUT / '29g_5차전직.png'))
        await sp.click('#gv-reb')
        await sp.wait_for_timeout(300)
        rc = await sp.evaluate("() => ({card: !!document.querySelector('#crossCard5'), txt: (document.querySelector('#crossCard5') || {}).textContent || ''})")
        check(jc['card'] and '해룡장' in jc['txt'] and '전직함' in jc['txt'] and rc['card'] and '건넜어요' in rc['txt'], f"[수련]에 5차 전직 카드와 「동해로」 건너기 카드가 보인다 {jc['txt'][:40]} / {rc['txt'][:30]}")
        await tab(sp, 'skill')
        await sp.wait_for_timeout(400)
        await sp.screenshot(path=str(OUT / '29h_기술_5차.png'))
        await sp.evaluate("() => { const G = window.__game; G.closePage(); G.openMap(); }")
        await sp.wait_for_timeout(900)
        jm = await sp.evaluate("() => ({bands: document.querySelectorAll('.jm-band').length, w5: !!document.querySelector('.jm-band.w5'), lock4: !!document.querySelector('.jm-band.w4.s-lock'), chips: [...document.querySelectorAll('.jm-wchip')].map(e => e.textContent)})")
        await sp.evaluate("() => { const sc = document.querySelector('#jmScroll'); if (sc) sc.scrollLeft = sc.scrollWidth; }")
        await sp.wait_for_timeout(600)
        await sp.screenshot(path=str(OUT / '29i_여정지도_동해.png'))
        check(jm['bands'] == 8 and jm['w5'] and not jm['lock4'] and any('동해' in c for c in jm['chips']), f"여정 지도에 동해(4부) 띠가 생기고 곤륜 띠는 더 잠긴 모양이 아니다 {jm}")
        # 4부 전(곤륜)의 용사에게는 5차·동해 것이 보이지 않는다
        s4 = await sp.evaluate(r"""(save) => { const G = window.__game, S = G.S; G.closePage(); const old = JSON.parse(JSON.stringify(save)); old.quest.main = G.PART3_END - 3; Object.assign(S, G.mergeState(old)); G.applyWorld(); G.refreshStats(); G.setStage(S.stage);
          G.buildTab('grow'); const o = {w:S.world, ready:G.crossReady(), sea:G.seaOpen(), job5:G.jobReady(5), sk:[G.skOpen(11), G.skOpen(12)], mp:G.mpMax(), haetae:G.haetaeOpen()}; document.querySelector('#gv-job').click(); o.card5 = !!document.querySelector('#jobCard5'); document.querySelector('#gv-reb').click(); o.cross5 = !!document.querySelector('#crossCard5'); o.btn = !!document.querySelector('#crossBtn5') && !document.querySelector('#crossBtn5').disabled; G.closePage(); return o; }""", late)
        check(s4['w'] == 4 and not s4['ready'] and not s4['sea'] and not s4['job5'] and s4['sk'] == [False, False] and s4['mp'] == 100 and not s4['card5'] and s4['cross5'] and not s4['btn'] and not s4['haetae'],
              f"45장을 마치기 전(곤륜)에는 동해로 건널 수 없고 5차 전직·새 기술·해태 수련이 보이지 않는다 {s4}")
        await ctxS.close()

        # 9-13) 물의 신화 5-1단계: 직업 바꾸기 제한 — 한 주 2번·기술 Lv.1과 재련 처음으로·쓴 재화 80% 환급·경고 창(숫자)·주간 초기화·싸움 중 금지·예전 저장·까치 알림
        ctxJ = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        jp = await ctxJ.new_page()
        watch(jp, errors, '5-1단계 ')
        await fresh(jp)
        await signup(jp, 'clschg51', 'abcd', '갈림용사')
        j1 = await jp.evaluate(r"""() => { const G = window.__game, S = G.S, out = {}; G.quiet = true; G.noFork = true;
          out.new = [!!S.clsNote, G.clsChgLeft(), S.cls, S.chosen];   // 새 캐릭터: 까치 알림 없음 · 2번 남음(처음 고른 것은 세지 않음)
          S.bossAuto = false; S.autoBoss = false;   // 단계 보스 싸움이 끼어들지 않게
          S.level = 100; G.unlockSkills(); S.skills.spin = 6; S.skills.bolt = 4;
          const cost = (k, lv) => { const sk = G.SKILLS.find(x => x.key === k); let c = 0; for (let l = 1; l < lv; l++) c += G.skillCost(sk, l); return c; };
          const skGold = cost('spin', 6) + cost('bolt', 4);
          // 재련: 무기 +12는 세기 전의 저장처럼(쓴 재화 기록 없음 → 그 단계까지 평균으로 드는 값), 방어구 +5는 실제로 쓴 것을 적어 둠
          S.refine.weapon = {lv:12, drops:1, t:0, base:0}; S.refine.armor = {lv:5, drops:0, t:0, base:0, sp:{g:99999, gm:40, du:77}};
          let og = 0, od = 0; for (let l = 0; l < 12; l++){ const c = G.refineCost('weapon', l); og += c.g; od += c.du; }   // 한 번씩 성공했을 때의 값
          const av = G.refAvgCost('weapon', 0, 12, false), wg = av.g, wd = av.du; out.avg = [wd > od && wd < od * 4, wg > og && wg < og * 4, G.refAvgCost('weapon', 0, 3, false).du];   // +3까지는 반드시 성공 = 3
          { const a25 = G.refAvgCost('weapon', 0, 25, false), l25 = G.refAvgCost('weapon', 15, 25, true); out.avg25 = [a25.du > 1500 && a25.du < 3000, l25.du > a25.du]; }   // +25까지 평균 약 400번(쇳가루 약 2,100), 계승 뒤는 확률 0.7배라 더 듦
          const P = G.clsChgPlan(), tot = skGold + wg + 99999;
          out.spent = [Math.round(P.spent.gold) === Math.round(tot), P.spent.gems, P.spent.dust === wd + 77];
          out.back = [P.back.gold === Math.floor(tot * 0.8), P.back.gems, P.back.dust === Math.floor((wd + 77) * 0.8)];
          out.rows = [P.sk.map(x => x.key + x.lv).join(','), P.rf.map(x => x.slot + x.lv + '>' + x.to).join(',')];
          S.gold = 1000; S.gems = 100; S.dust = 10; const q0 = [G.questCur({k:'refineW'}), G.questCur({k:'refineA'})];
          out.same = G.clsChgDo('musa');   // 같은 직업으로는 안 바뀌고 횟수도 그대로
          out.did = !!G.clsChgDo('jagaek'); out.cls = S.cls;
          out.got = [S.gold - 1000 === P.back.gold, S.gems - 100, S.dust - 10 === P.back.dust];
          out.sk = [S.skills.spin, S.skills.bolt, Object.values(S.skills).filter(v => v > 1).length]; out.rf = [S.refine.weapon.lv, S.refine.armor.lv, S.refine.weapon.drops, JSON.stringify(S.refine.armor.sp)];
          out.left1 = G.clsChgLeft(); out.q = [q0, [G.questCur({k:'refineW'}), G.questCur({k:'refineA'})], G.SUB_STATE.refW()];
          // 재련 +25를 이룬 뒤 직업을 바꿔도 첫 환생 조건(무기 +25)은 이룬 것으로
          S.refine.weapon.lv = 25; const rb0 = G.rebirthCheck()[1].ok;
          // 다시 재련하면 그때부터 쓴 재화를 센다
          S.refine.armor = {lv:0, drops:0, t:0, base:0, sp:{g:0, gm:0, du:0}}; S.gold = 1e9; S.dust = 1000; const c0 = G.refineCost('armor', 0); G.refineTry('armor'); out.track = [S.refine.armor.sp.g === c0.g, S.refine.armor.sp.du === c0.du, S.refine.armor.lv];
          // 싸움 중에는 못 바꾼다
          out.dm = G.startDummy();   // 허수아비 수련(싸움)
          out.busy = [G.clsChgBusy(), G.clsChgDo('sulsa'), S.cls]; if (G.raid){ G.raid.time = 0; for (let i = 0; i < 400 && G.raid; i++) G.update(0.05); } G.hideModal();
          out.did2 = !!G.clsChgDo('sulsa'); out.left2 = G.clsChgLeft(); out.rb = [rb0, S.refine.weapon.lv, G.rebirthCheck()[1].ok];
          out.third = G.clsChgDo('doin'); out.cls3 = S.cls;   // 세 번째는 안 됨
          G.addTime(8 * 86400000); out.week = [G.clsChgLeft(), !!G.clsChgDo('doin'), S.cls, G.clsChgLeft()];   // 한 주가 지나면 다시 2번
          G.quiet = false; return out; }""")
        check(j1['new'] == [False, 2, 'musa', True], f"새 캐릭터는 직업 바꾸기가 2번 남아 있고(처음 고른 것은 세지 않음) 바뀐 규칙 알림이 없다 {j1['new']}")
        check(j1['spent'] == [True, 40, True] and j1['back'] == [True, 32, True] and j1['rows'] == ['spin6,bolt4', 'weapon12>0,armor5>0'] and j1['avg'] == [True, True, 3] and j1['avg25'] == [True, True],
              f"직업 바꾸기 계산: 기술에 쓴 엽전 + 재련에 쓴 엽전·보석·쇳가루(세기 전의 단계는 그 단계까지 평균으로 드는 값)의 80%를 돌려준다 {j1['spent']} {j1['back']} {j1['rows']} {j1['avg']} {j1['avg25']}")
        check(j1['same'] is None and j1['did'] and j1['cls'] == 'jagaek' and j1['got'] == [True, 32, True] and j1['sk'] == [1, 1, 0] and j1['rf'][:3] == [0, 0, 0] and j1['rf'][3] == '{"g":0,"gm":0,"du":0}' and j1['left1'] == 1,
              f"직업을 바꾸면 기술은 모두 Lv.1, 재련은 모든 칸 +0, 80%를 돌려받고 남은 횟수가 1번이 된다 {j1['cls']} {j1['got']} {j1['sk']} {j1['rf']} {j1['left1']}")
        check(j1['q'][0] == [12, 5] and j1['q'][1] == [12, 5] and j1['q'][2] == 12 and j1['rb'] == [True, 0, True] and j1['track'] == [True, True, 1],
              f"재련 단계가 조건인 이야기·부탁·환생 조건은 직업을 바꿔도 이룬 것으로 치고, 다시 재련하면 쓴 재화를 센다 {j1['q']} {j1['rb']} {j1['track']}")
        check(j1['dm'] and j1['busy'] == [True, None, 'jagaek'] and j1['did2'] and j1['left2'] == 0 and j1['third'] is None and j1['cls3'] == 'sulsa' and j1['week'] == [2, True, 'doin', 1],
              f"싸움 중에는 못 바꾸고, 한 주 2번을 다 쓰면 못 바꾸며, 월요일이 지나면 다시 2번이 된다 {j1['busy']} {j1['left2']} {j1['third']} {j1['week']}")
        # 예전 저장(3부 끝 무사, 재련 2차 계승): 불러오면 까치가 바뀐 규칙을 알리고, 바꾸면 계승한 칸은 +15로(굳힌 효과·차수는 그대로)
        j2 = await jp.evaluate(r"""(save) => { const G = window.__game, S = G.S, out = {}; G.quiet = true; G.noFork = true; G.closePage();
          const old = JSON.parse(JSON.stringify(save)); delete old.clsChg; delete old.clsNote; delete old.refBest; for (const k in old.refine) delete old.refine[k].sp;
          Object.assign(S, G.mergeState(old)); S.name = '갈림용사'; S.bossAuto = false; S.autoBoss = false; G.migrateStory(); G.applyWorld(); G.refreshStats(); G.setStage(S.stage);
          out.merged = [S.clsNote, S.clsChg.n, G.clsChgLeft(), JSON.stringify(S.refBest)];
          const w = S.refine.weapon, a = S.refine.armor; out.ref0 = [w.t, w.lv, Math.round(w.base), a.t, a.lv]; const eff0 = G.refEffLv('weapon');
          const av = G.refAvgCost('weapon', 15, w.lv, true), sp = G.refSp('weapon'); out.est = [sp.g === av.g && sp.g > 0, sp.du === av.du && sp.du > 1000, sp.gm, !!sp.est];
          const P = G.clsChgPlan(); out.plan = [P.sk.length, P.rf.map(x => x.slot + ':' + x.t + ':' + x.lv + '>' + x.to).join(','), P.back.gold > 0, P.back.gold < P.spent.gold];
          window.__j2 = {gold:S.gold, back:P.back.gold, eff0};
          out.notiK = G.notiList().map(N => N.k);
          G.quiet = false; G.noClsNote = false; G.updateNoti();
          const el = document.querySelector('#inh'); out.noti = el && !el.hidden ? el.textContent.slice(0, 400) : '';
          return out; }""", late)
        await jp.wait_for_timeout(500)
        await jp.screenshot(path=str(OUT / '30_직업바꾸기_까치알림.png'))
        check(j2['merged'][0] is True and j2['merged'][1] == 0 and j2['merged'][2] == 2 and j2['ref0'][0] >= 1 and j2['est'] == [True, True, 0, True],
              f"예전 저장: 바꾼 횟수 0번으로 시작하고, 재련에 쓴 재화는 계승 뒤 단계까지 평균으로 드는 값으로 친다 {j2['merged']} {j2['ref0']} {j2['est']}")
        check('cls' in j2['notiK'] and '직업 바꾸기' in j2['noti'] and '한 주에 2번' in j2['noti'], f"예전 저장으로 들어오면 길잡이 까치가 바뀐 규칙을 알린다 {j2['notiK']} {j2['noti'][:60]}")
        # 화면: [정보] → [직업 바꾸기 (이번 주 2/2)] → 직업 고르기 → [다음] → 경고 창(숫자) → [바꾸기]
        await jp.evaluate("() => { const G = window.__game; const b = document.querySelector('#notiLater'); if (b) b.click(); G.noClsNote = true; G.hideModal(); }")
        await tab(jp, 'rec')
        await jp.wait_for_timeout(400)
        b0 = await jp.inner_text('#clsBtn')
        await jp.evaluate("() => document.querySelector('#clsBtn').scrollIntoView({block:'center'})")
        await jp.click('#clsBtn')
        await jp.wait_for_timeout(300)
        m1 = await jp.evaluate("() => ({title: document.querySelector('#mTitle').textContent, left: (document.querySelector('#clsLeft') || {}).textContent || '', cards: document.querySelectorAll('#mBody .ccard').length, txt: document.querySelector('#mBody').textContent})")
        await jp.screenshot(path=str(OUT / '30b_직업바꾸기_고르기.png'))
        await jp.click('#modal-btn-1')   # 고르지 않고 [다음]: 창이 그대로이고 안내가 붉게
        await jp.wait_for_timeout(200)
        m1b = await jp.evaluate("() => ({open: !document.querySelector('#modal').hidden, title: document.querySelector('#mTitle').textContent, hint: document.querySelector('#clsHint').classList.contains('on')})")
        await jp.click('#cc-sulsa')
        await jp.click('#modal-btn-1')
        await jp.wait_for_timeout(300)
        m2 = await jp.evaluate(r"""() => { const G = window.__game, P = G.clsChgPlan(), b = document.querySelector('#mBody');
          return {title: document.querySelector('#mTitle').textContent, left: document.querySelector('#ccLeft').textContent, sk: document.querySelectorAll('#ccSk .cc-it').length, nsk: P.sk.length,
            rf: document.querySelector('#ccRf').textContent, tb: document.querySelector('#ccTb').textContent, spent: G.fmt(P.spent.gold), back: G.fmt(P.back.gold), lost: G.fmt(P.spent.gold - P.back.gold), dust: G.fmt(P.back.dust),
            txt: b.textContent, est: b.textContent.includes('평균으로 드는 값'), btns: [...document.querySelectorAll('#mBtns button')].map(x => x.textContent), cls: G.S.cls, fits: document.querySelector('.sheet').scrollWidth <= document.querySelector('.sheet').clientWidth + 1}; }""")
        await jp.screenshot(path=str(OUT / '30c_직업바꾸기_경고창.png'))
        await jp.evaluate("() => { const sh = document.querySelector('.sheet'); sh.scrollTop = sh.scrollHeight; }")
        await jp.wait_for_timeout(150)
        await jp.screenshot(path=str(OUT / '30d_직업바꾸기_경고창_아래.png'))
        check('2/2' in b0 and m1['title'] == '직업 바꾸기' and '2번' in m1['left'] and m1['cards'] == 4 and '80%' in m1['txt'] and m1b['open'] and m1b['title'] == '직업 바꾸기' and m1b['hint'],
              f"[정보]의 단추에 이번 주 남은 횟수가 보이고, 직업 고르기 창이 규칙을 알려 주며 지금 직업 그대로는 넘어가지 않는다 {b0} {m1['left']} {m1b}")
        check('꼭 읽어' in m2['title'] and '2번 → 1번' in m2['left'] and m2['sk'] == m2['nsk'] and m2['nsk'] >= 5 and '계승 +' in m2['rf'] and '계승 +15' in m2['rf'] and m2['spent'] in m2['tb'] and m2['back'] in m2['tb'] and m2['lost'] in m2['tb'] and m2['dust'] in m2['tb']
              and m2['est'] and '되돌릴 수 없어요' in m2['txt'] and m2['btns'] == ['취소', '바꾸기'] and m2['cls'] == 'musa' and m2['fits'],
              f"경고 창: 남은 횟수·처음으로 돌아가는 기술과 재련·돌려받는/사라지는 재화를 숫자로 보여 주고, [바꾸기]를 누르기 전에는 바뀌지 않는다 {m2['left']} {m2['nsk']} {m2['rf'][:60]} {m2['tb'][:80]}")
        await jp.click('#modal-btn-1')
        await jp.wait_for_timeout(500)
        j3 = await jp.evaluate(r"""() => { const G = window.__game, S = G.S, k = window.__j2, w = S.refine.weapon, a = S.refine.armor;
          return {title: document.querySelector('#mTitle').textContent, open: !document.querySelector('#modal').hidden, body: document.querySelector('#mBody').textContent, cls: S.cls, job: S.job, lv: S.level, gold: S.gold - k.gold >= k.back * (1 - 1e-9),
            ref: [w.t, w.lv, a.t, a.lv, w.base > 0], sk: Object.values(S.skills).filter(v => v > 1).length, set: S.skSet.length, left: G.clsChgLeft(), note: !!S.clsNote, best: G.refBestOf('weapon') >= k.eff0, eff: G.refEffLv('weapon'),
            sub: G.SUB_STATE.refW() >= k.eff0, btn: (document.querySelector('#clsBtn') || {}).textContent || '', atkDown: G.ST.atk < 1e999}; }""")
        await jp.screenshot(path=str(OUT / '30e_직업바꾸기_결과.png'))
        check(j3['open'] and j3['title'] == '직업을 바꿨어요' and '술사' in j3['body'] and j3['cls'] == 'sulsa' and j3['job'] == late['job'] and j3['lv'] == late['level'] and j3['gold']
              and j3['ref'][1] == 15 and j3['ref'][3] == 15 and j3['ref'][0] == j2['ref0'][0] and j3['ref'][4] and j3['sk'] == 0 and j3['set'] >= 6 and j3['left'] == 1 and not j3['note'] and j3['best'] and j3['sub'] and '1/2' in j3['btn'],
              f"[바꾸기]: 직업이 바뀌고(레벨·전직은 그대로) 계승한 재련은 +15로(굳힌 효과는 그대로), 기술은 Lv.1, 80%를 돌려받고 단추가 1/2가 된다 {j3['cls']} {j3['ref']} {j3['sk']} {j3['left']} {j3['btn']}")
        # 두 번을 다 쓰면 단추를 눌러도 안내만
        j4 = await jp.evaluate(r"""() => { const G = window.__game; G.hideModal(); G.quiet = true; const ok = !!G.clsChgDo('musa'); G.quiet = false; G.chooseClass(true);
          return {ok, left: G.clsChgLeft(), title: document.querySelector('#mTitle').textContent, txt: document.querySelector('#mBody').textContent, cards: document.querySelectorAll('#mBody .ccard').length}; }""")
        check(j4['ok'] and j4['left'] == 0 and j4['cards'] == 0 and '이미 2번' in j4['txt'] and '월요일 0시' in j4['txt'], f"이번 주 두 번을 다 쓰면 [직업 바꾸기]는 다음 주를 안내한다 {j4['left']} {j4['txt'][:50]}")
        await jp.evaluate("() => window.__game.hideModal()")
        # 세로 화면에서도 경고 창이 화면 안에 들어온다
        await jp.set_viewport_size({'width': 390, 'height': 780})
        await jp.wait_for_timeout(400)
        j5 = await jp.evaluate(r"""() => { const G = window.__game; G.addTime(8 * 86400000); G.clsChgAsk('jagaek'); const sh = document.querySelector('.sheet'), r = sh.getBoundingClientRect();
          return {title: document.querySelector('#mTitle').textContent, in: r.left >= -1 && r.right <= innerWidth + 1, nox: sh.scrollWidth <= sh.clientWidth + 1, left: document.querySelector('#ccLeft').textContent}; }""")
        await jp.screenshot(path=str(OUT / '30f_직업바꾸기_경고창_세로.png'))
        check('꼭 읽어' in j5['title'] and j5['in'] and j5['nox'] and '2번 → 1번' in j5['left'], f"세로 화면에서도 경고 창이 옆으로 넘치지 않는다(한 주 뒤 다시 2번) {j5}")
        await ctxJ.close()

        # 9-14) 물의 신화 6단계: 초각성기 2(퀘스트 「두 번째 깨달음」·기운·손컨 보너스·직업 효과·넘길 수 없는 설명 연출·연습) · 환생의 기억(고르기·세 갈래·윤회 구슬·상한·오라·별호) — 56·53장이 없는 지금은 아무에게도 안 보임
        sea1 = json.loads((ROOT / 'tools' / 'beta_saves' / '50_musa_sea1_end.json').read_text(encoding='utf-8'))['save']
        ctxA = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        ap = await ctxA.new_page()
        watch(ap, errors, '6단계 ')
        await fresh(ap)
        await signup(ap, 'awk2test', 'abcd', '깨달음용사')
        a1 = await ap.evaluate(r"""(save) => { const G = window.__game, S = G.S, out = {}; G.quiet = true; G.noFork = true;
          Object.assign(S, G.mergeState(JSON.parse(JSON.stringify(save)))); S.name = '깨달음용사'; G.refreshStats(); G.setStage(S.stage); S.bossAuto = false; S.autoBoss = false;
          // 53장(환생의 기억)·56장(초각성기 2)에 닿기 전에는 닫혀 있고 아무것도 안 보인다 → 닿으면 열린다(물의 신화 7단계에서 그 장이 들어옴)
          S.quest.main = G.PART4A_END - 1;   // 52장 마지막 퀘스트
          out.closed = [G.aw2Has(), G.aw2Open(), G.aw2Quest(), G.memHas(), G.memOpen(), G.notiList().some(N => N.k === 'aw2' || N.k === 'mem'), G.titleShown().some(t => t.k === 'mem3' || t.k === 'memNo')];
          S.quest.main = G.PART4A_END; out.at53 = [G.memOpen(), G.aw2Open()];
          S.quest.main = G.MAIN_Q.findIndex(q => q.ch >= 57) - 1; out.at56 = [G.memOpen(), G.aw2Open()];   // 56장 마지막 퀘스트: 아직
          S.quest.main++; out.after56 = [G.memOpen(), G.aw2Open(), !!G.aw2Quest()];
          S.quest.main = G.PART4A_END - 1;   // 아래 점검은 닫힌 채로(시험 훅으로 연다)
          out.st0 = [JSON.stringify(S.aw2), JSON.stringify(S.mem)];
          // 예전 저장(칸 없음)·이상한 값도 받아 준다
          const old = JSON.parse(JSON.stringify(save)); delete old.aw2; delete old.mem; const m1 = G.mergeState(old); out.merge = [m1.aw2.q, m1.aw2.got, m1.mem.ch, m1.mem.p.join(''), m1.mem.orbs];
          const bad = G.mergeState(Object.assign(JSON.parse(JSON.stringify(save)), {aw2:{q:99, c:-5, got:'x'}, mem:{ch:'zzz', p:[9, -1, 'a'], orbs:999}})); out.bad = [bad.aw2.q, bad.aw2.c, bad.aw2.got, bad.mem.ch, bad.mem.p.join(''), bad.mem.orbs];
          // 열기(시험 훅)
          G.aw2Force = true;
          const q0 = G.aw2Quest(); out.q0 = [q0.i, q0.t, q0.n, G.aw2Cur()];
          out.noti = G.notiList().some(N => N.k === 'aw2');
          out.claim0 = G.aw2Claim();           // 아직 안 들었으니 못 받음
          out.hear = G.aw2Hear(); out.cur0 = G.aw2Cur(); const g0 = S.gems; out.claim1 = G.aw2Claim(); out.gem1 = S.gems - g0; out.q1 = G.aw2Quest().i;
          out.noti2 = G.notiList().some(N => N.k === 'aw2');
          return out; }""", sea1)
        check(a1['closed'] == [True, False, None, True, False, False, False] and a1['at53'] == [True, False] and a1['at56'] == [True, False] and a1['after56'] == [True, True, True],
              f"환생의 기억은 53장, 초각성기 2는 56장을 마쳐야 열리고 그 전에는 알림·별호도 안 보인다 {a1['closed']} {a1['at53']} {a1['at56']} {a1['after56']}")
        check(a1['merge'] == [0, False, '', '000', 0] and a1['bad'] == [5, 0, True, '', '400', 40], f"예전 저장·이상한 값을 불러와도 새 칸이 기본값·범위 안으로 채워진다 {a1['merge']} {a1['bad']}")
        check(a1['q0'] == [0, '다섯 스승의 한마디', 1, 0] and a1['noti'] and not a1['claim0'] and a1['hear'] and a1['cur0'] == 1 and a1['claim1'] and a1['gem1'] == 600 and a1['q1'] == 1 and not a1['noti2'],
              f"「두 번째 깨달음」 ①: 스승들의 말을 들어야 보상을 받고 다음 단계로 {a1['q0']} {a1['gem1']} {a1['q1']}")
        # ②~④: 레이드에서 되받기 · 버팀 깨기 · 맞지 않고 이기기
        a2 = await ap.evaluate(r"""() => { const G = window.__game, S = G.S, out = {}; G.hand = {dodge:0, counter:0}; G.wipeOff = true;
          const run = (sec, f) => { for (let i = 0; i < sec * 10; i++){ G.update(0.1); G.addTime(100); if (f) f(i); } };
          // ② 되받기: 단계 보스에서는 안 세고 레이드에서만(저절로 한 것도)
          S.inv.potion = 500; S.inv.elixir = 50;
          (G.S.raid.tk = 3, G.startRaid(0)); run(1); const B = G.raid.boss; B.hp = B.maxHp = 1e300;
          B.pat = B.pat || {stg:100, cd:99, tel:null, grogT:0, n:0, wipes:[]}; B.pat.wipes = []; B.pat.cd = 99;
          for (let k = 0; k < 30; k++){ B.pat.tel = {kind:'counter', t:0, T:1.1, auto:{ok:false, at:9, done:false}}; G.counterOk(B, k % 2 === 0); B.pat.grogT = 0; B.pat.stg = 100; }
          out.c = S.aw2.c; out.ok2 = G.aw2Cur() >= G.aw2Quest().n; out.claim2 = G.aw2Claim(); out.q2 = G.aw2Quest().i;
          // ③ 버팀 깨기
          for (let k = 0; k < 20; k++){ B.pat.stg = 100; B.pat.grogT = 0; G.patBreak(B); }
          out.g = S.aw2.g; out.claim3 = G.aw2Claim(); out.q3 = G.aw2Quest().i;
          G.raidEnd(false); run(2);
          // ④ 맞지 않고 이기기: 붉은 칸에 맞은 판은 안 세고, 안 맞은 판만
          const fight = hitMe => { (G.S.raid.tk = 3, G.startRaid(0)); run(1); const b = G.raid.boss; if (hitMe){ b.pat = {stg:100, cd:99, tel:null, grogT:0, n:0, wipes:[]}; const [x, y] = [G.hero.tx, G.hero.ty], set = new Set(); for (let dx = -6; dx <= 6; dx++) for (let dy = -6; dy <= 6; dy++) set.add((x + dx) + ',' + (y + dy)); G.hero.rollT = 0; b.hp = b.maxHp = 1e300; b.pat.tel = {kind:'tiles', shape:'ring', t:1.5, T:1.6, set, tiles:[...set].map(s => s.split(',').map(Number)), auto:{ok:false, at:9, done:false}}; run(0.5); }
            b.hp = 1; run(8); return G.raid ? 'still' : 'done'; };
          const p0 = G.patHurt; out.f1 = fight(true); out.hurt = G.patHurt - p0; out.n1 = S.aw2.n;
          out.f2 = [fight(false), fight(false), fight(false)]; out.n2 = S.aw2.n; out.claim4 = G.aw2Claim(); out.q4 = G.aw2Quest().i; out.btn = G.aw2Quest().btn;
          G.hand = null;
          return out; }""")
        check(a2['c'] == 30 and a2['ok2'] and a2['claim2'] and a2['q2'] == 2 and a2['g'] == 20 and a2['claim3'] and a2['q3'] == 3, f"「두 번째 깨달음」 ②③: 레이드에서 되받기 30번 · 버팀 깨기 20번을 세고 보상을 받는다 {a2['c']} {a2['g']} {a2['q3']}")
        check(a2['f1'] == 'done' and a2['hurt'] >= 1 and a2['n1'] == 0 and a2['n2'] == 3 and a2['claim4'] and a2['q4'] == 4 and a2['btn'] == '겨루러 가기',
              f"「두 번째 깨달음」 ④: 붉은 칸에 맞은 판은 안 세고, 한 번도 안 맞고 이긴 판만 3번 센다 {a2['hurt']} {a2['n1']} {a2['n2']} {a2['q4']}")
        # ⑤ 스승과 다시 겨루기 → 익힘(시험 모드에서는 연출·연습을 건너뜀) → 싸움에서 기운이 차고 터진다
        a3 = await ap.evaluate(r"""() => { const G = window.__game, S = G.S, out = {};
          const run = (sec, f) => { for (let i = 0; i < sec * 10; i++){ G.update(0.1); G.addTime(100); if (f) f(i); } };
          out.job = S.job; out.trial = G.aw2Trial(); out.info = G.raid ? [G.raid.info.aw2t, G.raid.info.bossName, !!G.raid.awk2] : null;
          G.raid.boss.hp = 1; run(6); out.got = [S.aw2.got, S.aw2.q, S.aw2.tut, G.aw2Quest()]; out.name = G.AW2_SK[S.cls].name;
          // 자동만: 초당 2 → 50초쯤에 4초 몫
          G.hand = {dodge:0, counter:0}; G.wipeOff = true; G.PAT.off = true;
          G.startDummy = G.startDummy; S.dummy.n = 0;
          const tut = () => { G.startAw2Tut(); const A = G.raid.awk2; A.tut = null; delete A.tut; A.g = 0; A.hand = 0; G.raid.time = G.raid.limit = 200; return A; };   // 연습 허수아비를 빈 기운·제한 200초로 바꿔 시험장으로 쓴다
          let A = tut(); run(1); const B = G.raid.boss; const g1 = A.g; run(10); out.rate = Math.round((A.g - g1) / 10 * 10) / 10;
          let t = 11; while (!A.used && t < 80){ run(1); t++; } out.autoT = t; out.autoSec = A.sec; out.rec = S.rec.aw2;
          run(3); out.oneShot = [A.used, G.castAwaken2(true)]; G.raidEnd(false); run(2);
          // 손컨: 직접 되받기 +30 · 손으로 싸우는 동안 버팀 깨기 +30 · 붉은 칸에서 직접 구르기 +10 → 7초 몫, 저절로 한 되받기는 기운을 안 준다
          A = tut(); run(1); const B2 = G.raid.boss; B2.pat = {stg:100, cd:99, tel:null, grogT:0, n:0, wipes:[]};
          const gA = A.g; B2.pat.tel = {kind:'counter', t:0, T:1.1, auto:{ok:false, at:9, done:false}}; G.counterOk(B2, false); out.autoCtr = Math.round(A.g - gA);
          B2.pat.grogT = 0; B2.pat.stg = 100; B2.stunT = 0;
          const gB = A.g; B2.pat.tel = {kind:'counter', t:0, T:1.1, auto:{ok:false, at:9, done:false}}; G.counterOk(B2, true); out.manCtr = Math.round(A.g - gB); out.handT = G.hero.handT > 0;
          B2.pat.grogT = 0; B2.pat.stg = 100; const gC = A.g; G.patBreak(B2); out.brk = Math.round(A.g - gC);
          B2.pat.grogT = 0; B2.pat.stg = 100; G.hero.handT = 0; const gD = A.g; G.patBreak(B2); out.brkAuto = Math.round(A.g - gD);
          B2.pat.grogT = 0; B2.pat.stg = 100; G.hero.rollCd = 0; G.hero.stunT = 0;
          { const [x, y] = [G.hero.tx, G.hero.ty], set = new Set([x + ',' + y, G.hero.fx + ',' + G.hero.fy]); B2.pat.tel = {kind:'tiles', shape:'rain', t:0, T:3, set, tiles:[[x, y]], auto:{ok:false, at:9, done:false}};
            const gE = A.g; out.roll = G.heroRoll(true); out.dodge = Math.round(A.g - gE); G.hero.rollCd = 0; const gF = A.g; G.heroRoll(true); out.dodge2 = Math.round(A.g - gF); B2.pat.tel = null; }
          out.hand = A.hand; A.g = 100; S.aw2.man = true; run(1); out.manHold = !A.used;   // 수동: 가득 차도 누를 때까지 아껴 둔다
          const dm0 = G.dmgMeterNow ? G.dmgMeterNow() : 0; out.cast = G.castAwaken2(true); out.sec = A.sec; S.aw2.man = false; out.weak = A.weakT > 0;
          G.raidEnd(false); run(2); G.PAT.off = false; G.hand = null;
          return out; }""")
        check(a3['job'] >= 5 and a3['trial'] and a3['info'] and a3['info'][0] and a3['info'][1] == '문무대왕' and not a3['info'][2] and a3['got'] == [True, 5, True, None] and a3['name'] == '대왕암 가르기',
              f"「두 번째 깨달음」 ⑤: 5차 스승과 다시 겨뤄 이기면 초각성기 2를 익힌다 {a3['info']} {a3['got']} {a3['name']}")
        check(a3['rate'] == 2 and 48 <= a3['autoT'] <= 54 and a3['autoSec'] == 4 and a3['rec'] >= 1 and a3['oneShot'] == [True, False],
              f"초각성기 2: 기운은 초당 2 — 저절로만 채우면 약 50초에 4초 몫, 한 판에 한 번 {a3['rate']} {a3['autoT']}초 {a3['autoSec']} {a3['oneShot']}")
        check(a3['autoCtr'] == 0 and a3['manCtr'] == 30 and a3['handT'] and a3['brk'] == 30 and a3['brkAuto'] == 0 and a3['roll'] and a3['dodge'] == 10 and a3['dodge2'] == 0,
              f"초각성기 2 손컨 보너스: 직접 되받기 +30 · 손으로 싸우는 동안 버팀 깨기 +30 · 붉은 칸에서 직접 구르기 +10(예고 하나에 한 번), 저절로 한 것은 0 {a3['autoCtr']} {a3['manCtr']} {a3['brk']} {a3['brkAuto']} {a3['dodge']} {a3['dodge2']}")
        check(a3['hand'] == 60 and a3['manHold'] and a3['cast'] and a3['sec'] == 7 and a3['weak'], f"초각성기 2: 손으로 60을 채우면 7초 몫, 수동이면 누를 때까지 아껴 두고, 무사는 보스가 주는 피해 -30% {a3['hand']} {a3['sec']} {a3['weak']}")
        # 직업 효과 넷 + 피해가 초 몫만큼
        a4 = await ap.evaluate(r"""() => { const G = window.__game, S = G.S, out = {}; G.PAT.off = true; G.wipeOff = true;
          const run = (sec) => { for (let i = 0; i < sec * 10; i++){ G.update(0.1); G.addTime(100); } };
          const c0 = S.cls;
          for (const c of ['musa', 'jagaek', 'sulsa', 'doin']){
            G.setClass(c); G.refreshStats(); (G.S.raid.tk = 3, G.startRaid(0)); run(1); const R = G.raid, B = R.boss, A = R.awk2; B.hp = B.maxHp = 1e300; if (R.awk) R.awk.used = true;
            const hit0 = G.bossHit(B, G.hero); A.g = 100; A.hand = 0; G.hero.hp = G.ST.maxHp * 0.3; for (const a of R.allies){ a.down = true; a.downT = 6; a.hp = 0; }
            const hp0 = B.hp; G.castAwaken2(true);
            out[c] = {name:G.AW2_SK[c].name, weak:Math.round(G.bossHit(B, G.hero) / hit0 * 100), crit:A.critT > 0, stun:Math.round((B.stunT || 0) * 10) / 10, hp:Math.round(G.hero.hp / G.ST.maxHp * 100), up:R.allies.filter(a => !a.down).length, n:R.allies.length};
            G.raidEnd(false); run(2);
          }
          G.setClass(c0); G.refreshStats(); G.PAT.off = false;
          return out; }""")
        check(a4['musa']['weak'] == 70 and not a4['musa']['crit'] and a4['jagaek']['crit'] and a4['jagaek']['weak'] == 100 and a4['sulsa']['stun'] >= 4 and a4['doin']['hp'] >= 78 and a4['doin']['up'] == a4['doin']['n'] and a4['doin']['n'] > 0 and a4['musa']['up'] == 0,
              f"초각성기 2 직업 효과: 무사 보스 피해 -30% · 자객 모든 공격 치명타 · 술사 보스 4초 멈춤 · 도인 체력 50% 회복과 동료 일으킴 {a4}")
        # 화면: 퀘스트 카드 · 기술 화면 카드 · 넘길 수 없는 설명 연출 · 연습 허수아비 · 단추(가로·세로)
        await ap.evaluate("() => { const G = window.__game, S = G.S; G.quiet = false; S.aw2 = {q:3, c:30, g:20, n:1, hear:true, got:false, tut:false, man:false}; G.hideModal(); }")
        await tab(ap, 'quest')
        await ap.wait_for_timeout(400)
        a5 = await ap.evaluate("() => { const c = document.querySelector('#aw2Card'); return [!c.hidden, document.querySelector('#a2Title').textContent, document.querySelector('#a2Prog').textContent, document.querySelector('#a2Claim').disabled]; }")
        check(a5[0] and '두 번째 깨달음 4/5' in a5[1] and a5[2] == '1 / 3' and a5[3], f"[퀘스트]에 「두 번째 깨달음」 카드가 단계·진행과 함께 보인다 {a5}")
        await ap.evaluate("() => document.querySelector('#aw2Card').scrollIntoView({block:'center'})")
        await ap.wait_for_timeout(200)
        await ap.screenshot(path=str(OUT / '31-aw2-quest.png'))
        await ap.evaluate("() => { window.scrollTo(0, 0); document.documentElement.scrollTop = 0; document.body.scrollTop = 0; }")
        await ap.evaluate("() => { const G = window.__game, S = G.S; G.closePage(); S.aw2.q = 4; S.aw2.n = 3; G.aw2Trial(); G.raid.boss.hp = 1; }")
        await ap.wait_for_timeout(3500)
        a6 = await ap.evaluate("() => { const G = window.__game; return [G.S.aw2.got, !!G.cut, G.cut && G.cut.opts.noSkip, getComputedStyle(document.querySelector('#cutSkip')).display, G.cut ? G.cut.shots.length : 0]; }")
        check(a6[0] and a6[1] and a6[2] and a6[3] == 'none' and a6[4] == 2, f"초각성기 2를 익히는 순간 설명 연출이 시작되고 [건너뛰기] 단추가 없다 {a6}")
        await ap.wait_for_timeout(900)
        await ap.screenshot(path=str(OUT / '31b-aw2-tutorial.png'))
        for _ in range(16):
            if not await ap.evaluate('() => !!window.__game.cut'):
                break
            await ap.click('#cut', position={'x': 300, 'y': 200})
            await ap.wait_for_timeout(160)
        await ap.wait_for_timeout(1500)
        a7 = await ap.evaluate("() => { const G = window.__game, b = document.querySelector('#aw2Btn'), R = G.raid; return [!G.cut, !!(R && R.info.aw2tut), R && R.awk2 ? R.awk2.g : -1, !b.hidden, b.classList.contains('full'), document.querySelector('#aw2Txt').textContent, getComputedStyle(document.querySelector('#cutSkip')).display]; }")
        check(a7[0] and a7[1] and a7[2] == 100 and a7[3] and a7[4] and a7[5] == '누르기!', f"설명 연출이 끝나면 연습 허수아비가 나오고, 기운이 가득 찬 초각성 2 단추가 「누르기!」로 반짝인다 {a7}")
        await ap.screenshot(path=str(OUT / '31c-aw2-practice.png'))
        box = await ap.evaluate("() => { const r = e => { const x = document.querySelector(e); if (!x || x.hidden) return null; const b = x.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)]; }; return {a:r('#aw2Btn'), s:r('#soulBtn'), h:r('#handBtn'), mini:r('#mapBtn'), form:r('#formBtn'), sk:r('.ctrl')}; }")
        hitn = lambda p, q: bool(p and q and p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3])
        check(box['a'] and not hitn(box['a'], box['s']) and not hitn(box['a'], box['h']) and not hitn(box['a'], box['mini']) and not hitn(box['a'], box['form']), f"가로 화면: 초각성 2 단추가 넋 부름·구르기·미니맵·변신 칸과 겹치지 않는다 {box}")
        await ap.click('#aw2Btn')
        await ap.wait_for_timeout(700)
        a8 = await ap.evaluate("() => { const G = window.__game, R = G.raid; return [!!(R && R.awk2 && R.awk2.used), document.querySelector('#aw2Txt').textContent]; }")
        await ap.screenshot(path=str(OUT / '31d-aw2-cast.png'))
        await ap.wait_for_timeout(4500)
        a9 = await ap.evaluate("() => { const G = window.__game; return [!G.raid, G.S.aw2.tut, !document.querySelector('#modal').hidden, document.querySelector('#mTitle').textContent]; }")
        check(a8[0] and a8[1] == '씀' and a9[0] and a9[1] and a9[2] and '대왕암 가르기' in a9[3], f"단추를 누르면 초각성기 2가 터지고, 연습이 끝나면 간추린 설명 창이 뜬다 {a8} {a9}")
        await ap.evaluate("() => window.__game.hideModal()")
        await tab(ap, 'skill')
        await ap.wait_for_timeout(300)
        a10 = await ap.evaluate("() => { const c = document.querySelector('#aw2Info'); return [!!c, c ? c.textContent.includes('대왕암 가르기') : false, !!document.querySelector('#aw2Mode'), !!document.querySelector('#aw2Again')]; }")
        check(a10 == [True, True, True, True], f"[기술]에 초각성기 2 카드(자동/수동 바꾸기 · 설명 다시 보기)가 보인다 {a10}")
        await ap.evaluate("() => { const c = document.querySelector('#aw2Info'); if (c) c.scrollIntoView({block:'center'}); }")
        await ap.wait_for_timeout(200)
        await ap.screenshot(path=str(OUT / '31e-aw2-skill.png'))
        await ap.evaluate("() => window.__game.closePage()")

        # 환생의 기억
        m1 = await ap.evaluate(r"""() => { const G = window.__game, S = G.S, out = {}; G.quiet = true; G.memForce = true; G.hideModal();
          out.open = [G.memOpen(), G.memClosed(), G.notiList().some(N => N.k === 'mem'), G.titleShown().some(t => t.k === 'mem3')];
          out.reb0 = [S.reb.pts, S.reb.total, G.rebMax(G.REB_STATS[2]), G.rebMax(G.REB_STATS[4])];
          out.pay0 = G.memPay(0);                       // 아직 고르지 않았으면 못 함
          out.later = G.memPick('later'); out.ch1 = S.mem.ch; out.noti1 = G.notiList().some(N => N.k === 'mem');   // 「나중에」면 알림은 더 안 오고 [수련] → [환생]에서 다시
          out.yes = G.memPick('yes'); out.ch2 = S.mem.ch; out.again = G.memPick('no');   // 한 번 정하면 못 바꿈
          const c0 = G.memCost(0), c1 = G.memCost(1), c2 = G.memCost(2);
          out.cost = [c0.gold > 0 && c0.gems === 0, c1.gems, c2.gems, c0.mat, c1.mat, c2.mat, c2.grudge, c0.mk];
          S.gold = 0; out.poor = [G.memCostOk(0), G.memPay(0)];
          S.gold = c0.gold * 5; S.gems = 100000; S.mat.m3 = 5000; S.grudge = 200; S.inv.potion = 500; S.inv.elixir = 50;
          return out; }""")
        check(m1['open'] == [True, False, True, True] and not m1['pay0'] and m1['later'] and m1['ch1'] == 'later' and not m1['noti1'] and m1['yes'] and m1['ch2'] == 'yes' and not m1['again'],
              f"환생의 기억: 강림도령 알림 → 「나중에」는 다시 열 수 있고, 「떠올린다」를 고르면 바꿀 수 없다 {m1['open']} {m1['ch1']} {m1['ch2']}")
        check(m1['cost'][0] and m1['cost'][1:] == [3000, 6000, 150, 250, 350, 20, 'm3'] and m1['poor'] == [False, False], f"환생의 기억 값: 이승 = 엽전·저승/천계 = 보석 + 지금 땅 재료(+천계는 원한 조각), 모자라면 못 치른다 {m1['cost']} {m1['poor']}")
        m2 = await ap.evaluate(r"""() => { const G = window.__game, S = G.S, out = {}; G.wipeOff = true; G.hand = {dodge:1, counter:1};
          const run = (sec) => { for (let i = 0; i < sec * 10; i++){ G.update(0.1); G.addTime(100); } };
          const g0 = S.gold, e0 = S.gems, m0 = S.mat.m3, r0 = S.reb.pts, t0 = S.reb.total, c0 = G.memCost(0);
          out.start0 = G.startMem(0);                    // 값을 안 치르면 못 싸움
          out.pay = G.memPay(0); out.paid = [Math.round(g0 - S.gold) === c0.gold, m0 - S.mat.m3]; out.pay2 = G.memPay(0);   // 두 번 내지 않음
          out.start = G.startMem(0); const I = G.raid.info; out.info = [I.mem.join(','), I.bossName, I.mw, I.region, !!I.fit, G.raid.allies.length, G.raid.limit];
          // 지면 값을 다시 내지 않고 다시 싸운다
          G.raidEnd(false); run(2); out.lose = [S.mem.p[0], S.mem.paid[0], S.reb.pts - r0];
          const jin0 = S.jin.n;
          const win = b => { if (!S.mem.paid[b] && !G.memPay(b)) return 'nopay'; if (!G.startMem(b)) return 'nostart'; if (G.raid.info.fit) G.raid.info.fit.tgt = 1; run(1.5); if (G.raid) G.raid.boss.hp = 1; run(6); return G.raid ? 'still' : 'ok'; };   // 내 세기에 맞춘 싸움(FIT)은 시간표보다 앞서 못 깎으니 시험에서는 시간표를 1초로 줄인다
          out.w0 = [win(0), win(0), win(0)]; out.p0 = [S.mem.p[0], S.reb.pts - r0, S.mem.orbs];
          out.w0d = win(0); out.p0d = [S.mem.p[0], S.reb.pts - r0]; out.over = G.memPay(0);   // 다 한 갈래는 더 못 함
          const names = [];
          for (let k = 0; k < 4; k++){ G.memPay(1); G.startMem(1); names.push(G.raid.info.bossName + '/' + (G.raid.info.jin ? 'jin' : 'x') + '/' + G.raid.allies.length); run(0.8); G.raid.boss.hp = 1; run(6); }
          out.hell = names; out.p1 = [S.mem.p[1], S.reb.pts - r0, S.jin.n - jin0];
          const n2 = [];
          for (let k = 0; k < 4; k++){ G.memPay(2); G.startMem(2); n2.push(G.raid.info.bossName); G.raid.info.fit.tgt = 1; run(1.5); if (G.raid) G.raid.boss.hp = 1; run(6); }
          out.sky = n2; out.p2 = [S.mem.p[2], S.reb.pts - r0, S.reb.total - t0, S.mem.orbs, S.mem.fin];
          out.title = [!!S.title.own.mem3, !!S.title.own.memNo]; out.cap = [G.rebMax(G.REB_STATS[2]), G.rebMax(G.REB_STATS[4]), G.rebMax(G.REB_STATS[0])];
          out.spent = [e0 - S.gems, m0 - S.mat.m3, 200 - S.grudge];
          // 구슬을 쓰고 상한 너머까지: 신속 10 → 15
          S.reb.pts = 500; let n = 0; while (G.rebUp('spd') && n < 99) n++; out.spd = S.reb.up.spd; const re = G.mergeState(JSON.parse(JSON.stringify(S))); out.re = [re.reb.up.spd, re.mem.ch, re.mem.p.join(''), re.mem.fin, re.mem.orbs];
          G.hand = null; G.quiet = false;
          return out; }""")
        check(not m2['start0'] and m2['pay'] and m2['paid'] == [True, 150] and not m2['pay2'] and m2['start'] and m2['info'] == ['0,0', '멧돼지 대왕', 0, 0, True, 0, 60],
              f"환생의 기억 · 이승: 값을 치르면 내 세기에 맞춘 옛 보스(혼자·옛 땅)와 싸운다 {m2['paid']} {m2['info']}")
        check(m2['lose'] == [0, True, 0] and m2['w0'] == ['ok', 'ok', 'ok'] and m2['p0'] == [3, 6, 6] and m2['w0d'] == 'ok' and m2['p0d'] == [4, 8] and not m2['over'],
              f"환생의 기억: 지면 값을 다시 내지 않고, 이기면 윤회 구슬(이승 2개씩) — 다 한 갈래는 닫힌다 {m2['lose']} {m2['p0']} {m2['p0d']}")
        check(m2['hell'][0].startswith('진 진광대왕/jin/') and m2['hell'][3].startswith('진 오도전륜대왕/jin/') and m2['p1'] == [4, 20, 0] and m2['sky'] == ['전우치', '홍길동', '을지문덕', '이순신 장군의 넋'],
              f"환생의 기억 · 저승은 시왕 진 넷(오늘의 진 횟수는 그대로), 천계는 네 스승의 넋 {m2['hell']} {m2['p1']} {m2['sky']}")
        check(m2['p2'] == [4, 40, 40, 40, True] and m2['title'] == [True, False] and m2['cap'] == [15, 25, 0] and 35800 <= m2['spent'][0] <= 36000 and 2950 <= m2['spent'][1] <= 3000 and 70 <= m2['spent'][2] <= 80 and m2['spd'] == 15 and m2['re'] == [15, 'yes', '444', True, 40],
              f"환생의 기억을 모두 마치면 윤회 구슬 40개(마무리 8 포함) · 별호 「세 번 산 자」 · 신속 15·영안 25까지, 다시 불러와도 그대로 {m2['p2']} {m2['cap']} {m2['spent']} {m2['re']}")
        # 화면: [수련] → [환생]의 카드(고르기 전 · 길을 걷는 중) · 고르기 창 · 세 번째 오라
        await ap.evaluate("() => { const G = window.__game, S = G.S; S.mem = {ch:'', p:[0, 0, 0], paid:[false, false, false], fin:false, orbs:0}; G.growViewSet && G.growViewSet('reb'); G.hideModal(); G.memAsk(); }")
        await ap.wait_for_timeout(400)
        m3 = await ap.evaluate("() => [!document.querySelector('#modal').hidden, document.querySelector('#mTitle').textContent, [...document.querySelectorAll('#mBtns button')].map(b => b.textContent)]")
        check(m3[0] and m3[1] == '환생의 기억' and m3[2] == ['떠올린다', '나중에', '떠올리지 않는다'], f"강림도령의 물음: 떠올린다 · 나중에 · 떠올리지 않는다 {m3}")
        await ap.screenshot(path=str(OUT / '32-mem-ask.png'))
        await ap.click('#mBtns button:nth-child(3)')
        await ap.wait_for_timeout(400)
        m4 = await ap.evaluate("() => [document.querySelector('#mTitle').textContent, [...document.querySelectorAll('#mBtns button')].map(b => b.textContent), window.__game.S.mem.ch]")
        check(m4[0] == '정말 떠올리지 않을까요?' and m4[1] == ['돌아가기', '떠올리지 않는다'] and m4[2] == '', f"「떠올리지 않는다」는 한 번 더 확인한다 {m4}")
        await ap.click('#mBtns button:nth-child(2)')
        await ap.wait_for_timeout(300)
        m5 = await ap.evaluate("() => { const G = window.__game, S = G.S; const r = [S.mem.ch, !!S.title.own.memNo, G.memStart(), G.memPick('yes')]; return r; }")
        check(m5 == ['no', True, False, False], f"떠올리지 않기로 하면 닫히고 별호 「뒤돌아보지 않는 자」를 얻는다 {m5}")
        await ap.evaluate("() => { const G = window.__game, S = G.S; G.hideModal(); S.mem = {ch:'yes', p:[4, 1, 0], paid:[false, true, false], fin:false, orbs:11}; S.gems = 100000; S.mat.m3 = 5000; S.grudge = 200; }")
        await tab(ap, 'grow')
        await ap.evaluate("() => { const b = document.querySelector('#gv-reb'); if (b) b.click(); }")
        await ap.wait_for_timeout(500)
        m6 = await ap.evaluate("() => { const c = document.querySelector('#memCard'); if (!c) return null; c.scrollIntoView({block:'center'}); return [...document.querySelectorAll('#memList .btn')].map(b => b.textContent + (b.disabled ? '(x)' : '')).concat([document.querySelector('#memCard .tag').textContent]); }")
        check(m6 == ['완료(x)', '싸우러 가기', '떠올리기', '윤회 구슬 11/40'], f"[수련] → [환생]의 「환생의 기억」 카드에 세 갈래의 진행·값·단추가 보인다 {m6}")
        await ap.wait_for_timeout(300)
        await ap.screenshot(path=str(OUT / '32b-mem-card.png'))
        await ap.click('#memList [data-mb="2"]')
        await ap.wait_for_timeout(300)
        m7 = await ap.evaluate("() => [document.querySelector('#mTitle').textContent, /보석 .+ · .+ 350 · 원한 조각 20/.test(document.querySelector('#mBody').textContent), [...document.querySelectorAll('#mBtns button')].map(b => b.textContent)]")
        check(m7[0] == '천계의 기억 1/4' and m7[1] and m7[2] == ['아직', '값을 치르고 떠올리기'], f"갈래의 [떠올리기]는 값을 보여 주고 한 번 더 묻는다 {m7}")
        await ap.click('#mBtns button:nth-child(2)')
        await ap.wait_for_timeout(1800)
        m8 = await ap.evaluate("() => { const G = window.__game, R = G.raid; return [!!R, R && R.info.bossName, R && R.info.mem.join(','), G.S.mem.paid[2], 100000 - G.S.gems]; }")
        check(m8[:4] == [True, '전우치', '2,0', True] and 5980 <= m8[4] <= 6000, f"값을 치르면 바로 기억 속 싸움이 시작된다 {m8}")
        await ap.screenshot(path=str(OUT / '32c-mem-fight.png'))
        await ap.evaluate("() => { const G = window.__game, S = G.S; G.raidEnd(false); window.scrollTo(0, 0); document.documentElement.scrollTop = 0; document.body.scrollTop = 0; }")
        await ap.wait_for_timeout(1500)
        await ap.evaluate("() => { const G = window.__game, S = G.S; G.hideModal(); S.mem.fin = true; }")
        await ap.wait_for_timeout(600)
        await ap.screenshot(path=str(OUT / '32d-mem-aura.png'))
        # 세로 화면: 싸움 단추 셋이 한 줄에 나란히 — 서로·위쪽 재화 줄·알림 줄과 겹치지 않는다
        await ap.set_viewport_size({'width': 396, 'height': 800})
        await ap.wait_for_timeout(500)
        await ap.evaluate("() => { const G = window.__game; G.hideModal(); G.closePage(); G.quiet = true; G.PAT.off = false; (G.S.raid.tk = 3, G.startRaid(0)); for (let i = 0; i < 12; i++){ G.update(0.1); G.addTime(100); } G.raid.boss.hp = G.raid.boss.maxHp = 1e300; G.quiet = false; }")
        await ap.wait_for_timeout(900)
        pb = await ap.evaluate("() => { const r = e => { const x = document.querySelector(e); if (!x || x.hidden || getComputedStyle(x).display === 'none') return null; const b = x.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)]; }; return {a:r('#aw2Btn'), s:r('#soulBtn'), h:r('#handBtn'), top:r('.topr'), log:r('.log'), form:r('#formBtn'), ch:r('#charBtn'), port:document.body.classList.contains('portrait')}; }")
        check(pb['port'] and pb['a'] and pb['s'] and pb['h'] and not hitn(pb['a'], pb['s']) and not hitn(pb['a'], pb['h']) and not hitn(pb['s'], pb['h']) and not hitn(pb['a'], pb['top']) and not hitn(pb['a'], pb['log']) and not hitn(pb['s'], pb['log']) and not hitn(pb['a'], pb['form']) and not hitn(pb['a'], pb['ch']) and pb['a'][0] >= 0,
              f"세로 화면: 초각성 2·넋 부름·구르기 단추가 한 줄에 나란히, 재화 줄·알림 줄·변신 칸·[캐릭터 바꾸기]와 겹치지 않는다 {pb}")
        await ap.screenshot(path=str(OUT / '31f-aw2-portrait.png'))
        await ap.evaluate("() => { const G = window.__game; G.raidEnd(false); }")
        await ctxA.close()

        # 9-15) 물의 신화 7단계: 4부 둘째 바다 「남쪽 바다」(53~59장) · 셋째 바다 「깊은 바다」(60~67장) — 건너기·세계 6·7·지역 여섯·레이드 여섯·53~67장 자동 진행·인당수 연꽃·이야기 판 옮기기
        sea7 = json.loads((ROOT / 'tools' / 'beta_saves' / '50_musa_sea1_end.json').read_text(encoding='utf-8'))['save']
        ctxT = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        tp = await ctxT.new_page()
        watch(tp, errors, '7단계 ')
        await fresh(tp)
        await signup(tp, 'sea7test', 'abcd', '깊은물용사')
        t1 = await tp.evaluate(r"""(save) => { const G = window.__game, S = G.S, out = {}; G.quiet = true; G.noFork = true;
          // 이야기 판 옮기기: 첫째 바다까지의 판(6)에서 '끝없는 신화'를 하던 저장 → 53장 첫 퀘스트, 둘째 바다까지의 판(7) → 60장 첫 퀘스트
          const o6 = JSON.parse(JSON.stringify(save)); o6.quest.sv = 6; o6.quest.main = G.PART4A_END + 5; const m6 = G.mergeState(o6);
          const o7 = JSON.parse(JSON.stringify(save)); o7.quest.sv = 7; o7.quest.main = G.PART4B_END + 3; o7.world = 6; o7.best.s6 = 45; o7.best.l6 = 533; o7.level = 533; const m7 = G.mergeState(o7);
          out.mig = [m6.quest.main === G.PART4A_END, m6.quest.sv, G.MAIN_Q[m6.quest.main].t, m7.quest.main === G.PART4B_END, m7.quest.sv, G.MAIN_Q[m7.quest.main].t, m7.world, m7.best.s6, m7.best.l6];
          Object.assign(S, m6); S.name = '깊은물용사'; G.migrateStory(); G.refreshStats(); G.setStage(S.stage);
          out.w0 = S.world; out.ready = G.crossReady(); out.cross = G.doCross(); if (G.inhPending()) G.inhDo(); out.w = S.world; out.cap = G.levelCap(); out.stage = S.stage; out.lv = S.level; out.name = G.WORLD_NAME[S.world];
          G.refreshStats(); out.cum = G.cumLv(); out.atk = isFinite(G.ST.atk) && G.ST.atk > 0 && isFinite(G.power(G.ST));
          out.regs = [1, 11, 21, 40].map(s => G.curRegion(s).name); out.raids = [0, 1, 2].map(i => G.seaRaidInfo(6, i).label); out.keys = [0, 1, 2].map(i => G.seaRaidInfo(S.world, i).key);
          out.caps = G.LV_CAP.slice(5); out.wmax = G.WORLD_MAX; out.ready2 = G.crossReady();
          const re = G.mergeState(JSON.parse(JSON.stringify(S))); out.re = [re.world, re.best.s6, re.best.l6, re.quest.sv, re.quest.main === S.quest.main];
          return out; }""", sea7)
        check(t1['mig'][:7] == [True, 8, '남쪽 바다로', True, 8, '깊은 바다로', 6] and t1['mig'][7] >= 45 and t1['mig'][8] == 533,
              f"이야기 판 옮기기: 첫째·둘째 바다 뒤 '끝없는 신화'를 하던 저장은 새로 이어진 53장·60장 첫 퀘스트로 {t1['mig']}")
        check(t1['w0'] == 5 and t1['ready'] and t1['cross'] and t1['w'] == 6 and t1['cap'] == 533 and t1['stage'] == 1 and t1['lv'] == 516 and t1['name'] == '남쪽 바다' and not t1['ready2'] and t1['re'] == [6, 1, 516, 8, True],
              f"둘째 바다: 동해 이야기를 마치면 남쪽 바다로 건너가고, 레벨은 그대로 단계만 1부터(상한 533), 다시 불러와도 그대로 {t1['w']} {t1['cap']} {t1['re']}")
        check(t1['cum'] == 816 and t1['atk'] and t1['regs'] == ['바람 섬', '인당수', '칠산 바다', '칠산 바다'] and t1['raids'] == ['외눈박이 거인', '칠산의 풍랑', '강철이'] and t1['keys'] == ['n0', 'n1', 'n2'] and t1['caps'] == [516, 533, 550] and t1['wmax'] == 7,
              f"남쪽 바다 지역 셋·레이드 셋, 새 세계에서도 능력치가 멀쩡하다(누적 레벨 표) {t1['regs']} {t1['raids']} {t1['cum']}")
        RUN_SEA = r"""(w) => { const G = window.__game, S = G.S, out = {done:[], bosses:{}, raid:{}, got:{}}; G.quiet = true; G.powK = 60; G.wipeOff = true; G.refreshStats();
          const run = (sec, until) => { for (let i = 0; i < sec * 20 && !until(); i++){ G.update(0.05); G.addTime(50); } };
          const cap = G.LV_CAP[w], sk = 's' + w, lk = 'l' + w, end = w === 6 ? G.PART4B_END : G.MAIN_Q.length;
          for (let guard = 0; guard < 90 && S.quest.main < end; guard++){
            const q = G.MAIN_Q[S.quest.main];
            if (q.k === 'world'){ out.ready = G.crossReady(); out.crossed = G.doCross(); if (G.inhPending()) G.inhDo(); G.refreshStats(); }
            else if (q.k === sk){
              for (let s = Math.max(S.maxStage, q.n - 2); s < q.n; s++){   // 마지막 한두 단계는 진짜 보스
                S.level = Math.max(S.level, Math.min(cap, G.stageLvNeed(s + 1))); S.maxStage = Math.max(S.maxStage, s); S.best[sk] = Math.max(S.best[sk] || 0, s); G.setStage(s); G.refreshStats();
                G.startBoss(); run(3, () => G.bossRef); if (G.bossRef) out.bosses[s] = G.bossRef.name;
                run(40, () => S.maxStage > s); if (S.maxStage <= s){ out.stuck = `${q.t} · ${s}단계 보스`; break; }
              }
            } else if (q.k === lk){ S.level = Math.max(S.level, q.n); S.best[lk] = S.level; G.refreshStats(); }
            else if (q.k === 'raidK'){ const i = +q.key.slice(1), at = G.SEAS[w].at[i];
              out.raid[q.key] = {early:G.raidUnlocked() > i && (S.best[sk] || 0) < at};   // 그 단계에 닿기 전에는 잠겨 있어야 한다
              if ((S.best[sk] || 0) < at){ S.level = Math.max(S.level, Math.min(cap, G.stageLvNeed(at))); S.maxStage = Math.max(S.maxStage, at); S.best[sk] = at; G.setStage(S.maxStage); G.refreshStats(); }
              S.raid.tk = 3; out.raid[q.key].open = G.raidUnlocked() > i; out.raid[q.key].start = G.startRaid(i); run(3, () => false); out.raid[q.key].said = G.raid ? G.raid.said : -1; run(120, () => !G.raid); out.raid[q.key].first = !!S.raid.first[q.key]; }
            if (out.stuck) break;
            const b = S.quest.main; if (q.myth) out.got[q.myth] = [q.t]; G.claimMain(); if (S.quest.main === b){ out.stuck = q.t + ' (조건 안 됨 ' + G.questCur(q) + '/' + q.n + ')'; break; }
            if (q.myth) out.got[q.myth].push(S.myth[q.myth]); out.done.push(q.ch);
          }
          G.powK = 1; G.refreshStats(); if (G.autoClear) G.autoClear();
          out.q = S.quest.main; out.end = end; out.next = G.mainQuest().t; out.nextK = G.mainQuest().k; out.lv = S.level; out.st = S.maxStage; out.w = S.world; out.cap = G.levelCap();
          out.chs = [...new Set(out.done)]; out.title = [!!S.title.own.sea2, !!S.title.own.sea3]; out.mem = G.memOpen(); out.aw2 = G.aw2Open(); out.regs = [1, 11, 21].map(s => G.curRegion(s).name);
          return out; }"""
        TITLES7 = "() => { const S = window.__game.S; return [!!S.title.own.sea2, !!S.title.own.sea3]; }"
        t2 = await tp.evaluate(RUN_SEA, 6)
        await tp.wait_for_timeout(700)
        t2['title'] = await tp.evaluate(TITLES7)
        check(not t2.get('stuck') and t2['q'] == t2['end'] and t2['chs'] == [53, 54, 55, 56, 57, 58, 59] and t2['nextK'] == 'world' and t2['next'] == '깊은 바다로' and t2['lv'] == 533,
              f"53장부터 59장까지 이야기가 이어지고 다음은 60장 「깊은 바다로」(단계 보스·레이드를 실제로 싸움) {t2.get('stuck')} {t2['q']}/{t2['end']} {t2['chs']}")
        check(t2['bosses'].get('10') == '검은 물에 물든 바위 장군' and t2['bosses'].get('20') == '인당수 소용돌이' and t2['bosses'].get('30') == '이어도의 헛그림자' and t2['bosses'].get('35') == '떨어진 해의 불씨' and '수문장' in t2['bosses'].get('39', ''),
              f"남쪽 바다 지역 보스와 이야기 속 보스(30단계 헛그림자·35단계 불씨), 9번째 단계는 수문장 {t2['bosses']}")
        check(all(t2['raid'].get(k, {}).get('start') and t2['raid'][k]['open'] and not t2['raid'][k]['early'] and t2['raid'][k]['first'] and t2['raid'][k]['said'] >= 1 for k in ('n0', 'n1', 'n2')),
              f"남쪽 바다 레이드 셋(외눈박이 거인·칠산의 풍랑·강철이)이 그 단계(1-6·3-4·4-8)에 닿으면 열리고, 보스가 한마디 한다 {t2['raid']}")
        check(t2['got'].get('lotus', [0, 0])[1] == 50 and t2['title'][0] and t2['mem'] and t2['aw2'],
              f"신화 보물 「인당수 연꽃」은 55장 보상으로, 별호 「할머니들의 손주」, 환생의 기억(53장)·초각성기 2(56장)가 열려 있다 {t2['got']} {t2['title']} {t2['mem']} {t2['aw2']}")
        # 인당수 연꽃: 불사약을 쓴 뒤에도 싸움마다 한 번 더 일어난다(세 번째는 쓰러짐)
        t3 = await tp.evaluate(r"""() => { const G = window.__game, S = G.S, out = {}; G.quiet = true; S.bossAuto = false; S.autoBoss = false; G.setStage(S.maxStage); G.startBoss(); for (let i = 0; i < 20; i++) G.update(0.05);
          out.el = S.myth.elixir > 0; out.boss = !!G.bossRef; G.heroDie(); out.a = [G.hero.dead, !!G.hero.elixirUsed, !!G.hero.lotusUsed]; G.heroDie(); out.b = [G.hero.dead, !!G.hero.lotusUsed, Math.round(G.hero.hp / G.ST.maxHp * 100)]; G.heroDie(); out.c = G.hero.dead;
          for (let i = 0; i < 80; i++){ G.update(0.05); G.addTime(50); } S.bossAuto = true; return out; }""")
        check(t3['boss'] and t3['a'] == [False, t3['el'], not t3['el']] and t3['b'][0] is False and t3['b'][1] is True and t3['c'] is True,
              f"인당수 연꽃: 싸움마다 불사약과 따로 한 번 더 되살아나고, 그다음에는 쓰러진다 {t3}")
        for nm, stg in (('40_남쪽바다_바람섬.png', 5), ('40b_남쪽바다_인당수.png', 15), ('40c_남쪽바다_칠산.png', 25)):
            await tp.evaluate("(s) => { const G = window.__game; G.closePage(); G.hideModal && G.hideModal(); G.setStage(s); for (let i = 0; i < 160; i++) G.update(0.05); }", stg)
            await tp.wait_for_timeout(500)
            await tp.screenshot(path=str(OUT / nm))
        await tp.evaluate("() => { const G = window.__game; G.powK = 1e-4; G.refreshStats(); G.setStage(10); G.startBoss(); for (let i = 0; i < 40; i++) G.update(0.05); }")
        await tp.wait_for_timeout(400)
        await tp.screenshot(path=str(OUT / '40d_남쪽바다_바위장군.png'))
        await tp.evaluate("() => { const G = window.__game; G.powK = 1; G.refreshStats(); G.setStage(30); }")
        # 셋째 바다
        t4 = await tp.evaluate(RUN_SEA, 7)
        await tp.wait_for_timeout(700)
        t4['title'] = await tp.evaluate(TITLES7)
        check(not t4.get('stuck') and t4['crossed'] and t4['w'] == 7 and t4['cap'] == 550 and t4['regs'] == ['해녀의 물길', '고래 뱃속', '물 밑 꽃밭'],
              f"셋째 바다: 남쪽 바다 이야기를 마치면 깊은 바다로 건너간다(상한 550, 지역 셋) {t4.get('stuck')} {t4['w']} {t4['cap']} {t4['regs']}")
        check(t4['q'] == t4['end'] and t4['chs'] == [60, 61, 62, 63, 64, 65, 66, 67] and t4['nextK'] == 's7' and '끝없는 신화' in t4['next'] and t4['lv'] == 550 and t4['title'] == [True, True],
              f"60장부터 67장까지 이야기가 끝까지 이어지고(4부 끝) 별호 「물의 신화」를 얻는다 {t4['q']}/{t4['end']} {t4['chs']} {t4['next']} {t4['title']}")
        check(t4['bosses'].get('10') == '깊은 물 아귀' and t4['bosses'].get('20') == '뱃속의 물귀신' and t4['bosses'].get('26') == '식지 않는 불샘' and t4['bosses'].get('30') == '바꿔치기한 꽃' and '수문장' in t4['bosses'].get('39', ''),
              f"깊은 바다 지역 보스와 이야기 속 보스(26단계 불샘·30단계 꽃) {t4['bosses']}")
        check(all(t4['raid'].get(k, {}).get('start') and t4['raid'][k]['open'] and not t4['raid'][k]['early'] and t4['raid'][k]['first'] and t4['raid'][k]['said'] >= 1 for k in ('x0', 'x1', 'x2')),
              f"깊은 바다 레이드 셋(용들의 무덤·첫 거짓·검은 물의 바다)이 그 단계에 닿으면 열린다 {t4['raid']}")
        for nm, stg in (('41_깊은바다_물길.png', 5), ('41b_깊은바다_고래뱃속.png', 15), ('41c_깊은바다_꽃밭.png', 25)):
            await tp.evaluate("(s) => { const G = window.__game; G.closePage(); G.hideModal && G.hideModal(); G.setStage(s); for (let i = 0; i < 160; i++) G.update(0.05); }", stg)
            await tp.wait_for_timeout(500)
            await tp.screenshot(path=str(OUT / nm))
        await tp.evaluate("() => { const G = window.__game; G.powK = 1e-4; G.refreshStats(); G.setStage(30); G.startBoss(); for (let i = 0; i < 40; i++) G.update(0.05); }")
        await tp.wait_for_timeout(400)
        await tp.screenshot(path=str(OUT / '41d_깊은바다_바꿔치기한꽃.png'))
        await tp.evaluate("() => { const G = window.__game; G.powK = 1; G.refreshStats(); G.setStage(30); G.quiet = false; }")
        # 연출: 새 배경(바람 섬·두 개의 해·고래 뱃속·꽃밭)·노래 장면·4부 맺음
        cuts = []
        for nm, ch, a, b2 in (('42_53장_여는연출.png', 53, 3, 5), ('42b_58장_두개의해.png', 58, 2, 3), ('42c_61장_고래뱃속.png', 61, 2, 3), ('42d_64장_꽃피우기내기.png', 64, 2, 4)):
            await tp.evaluate("([ch, a, b]) => { const G = window.__game; G.playCut(G.CH_OPEN[ch].slice(a, b), {title:G.CHAPTERS[ch]}); }", [ch, a, b2])
            await tp.wait_for_timeout(1500)
            cuts.append(await tp.is_visible('#cut'))
            await tp.screenshot(path=str(OUT / nm))
            await tp.click('#cutSkip')
        await tp.evaluate("() => { const G = window.__game, q = G.MAIN_Q.find(x => x.t === '해녀의 노래'); G.playCut(G.qShots(q).slice(0, 1), {title:'57장 · 해녀의 노래'}); }")
        await tp.wait_for_timeout(1500)
        song7 = await tp.evaluate("() => ({song: document.querySelector('#cutBox').classList.contains('song'), txt: document.querySelector('#cutText').textContent})")
        await tp.click('#cutSkip')
        await tp.evaluate("() => { const G = window.__game, q = G.MAIN_Q[G.MAIN_Q.length - 1]; G.playCut(G.qShots(q).slice(8, 10), {title:'67장 · 물의 신화'}); }")
        await tp.wait_for_timeout(1500)
        await tp.screenshot(path=str(OUT / '42e_67장_맺음.png'))
        last = await tp.evaluate("() => ({n: window.__game.qShots(window.__game.MAIN_Q[window.__game.MAIN_Q.length - 1]).length, opens: [53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67].every(c => (window.__game.CH_OPEN[c] || []).length >= 5 && !!window.__game.CHAPTERS[c])})")
        await tp.click('#cutSkip')
        check(all(cuts) and song7['song'] and len(song7['txt']) > 3 and last['n'] >= 10 and last['opens'],
              f"둘째·셋째 바다 연출: 장마다 여는 연출(5컷 이상), 57장 노래 장면, 67장 맺음은 10컷 {cuts} {song7} {last}")
        await tp.evaluate("() => { const G = window.__game; G.quiet = true; G.closePage(); }")
        await tab(tp, 'grow')
        await tp.wait_for_timeout(250)
        await tp.click('#gv-reb')
        await tp.wait_for_timeout(300)
        rc7 = await tp.evaluate("() => [6, 7].map(w => { const c = document.querySelector('#crossCard' + w); return c ? c.textContent : ''; })")
        await tp.screenshot(path=str(OUT / '42f_건너기_카드.png'))
        check(all('건넜어요' in x for x in rc7) and '남쪽 바다' in rc7[0] and '깊은 바다' in rc7[1], f"[수련] → [환생]에 「남쪽 바다로」·「깊은 바다로」 건너기 카드가 보인다 {[x[:24] for x in rc7]}")
        await tab(tp, 'raid')
        await tp.wait_for_timeout(500)
        rl7 = await tp.evaluate("() => ({txt: document.querySelector('#panel').textContent, cards: document.querySelectorAll('#panel .rcard').length})")
        await tp.screenshot(path=str(OUT / '42g_깊은바다_레이드.png'))
        check('용들의 무덤' in rl7['txt'] and '첫 거짓' in rl7['txt'] and '검은 물의 바다' in rl7['txt'], f"[레이드]에 깊은 바다 레이드 셋이 보인다 (카드 {rl7['cards']}개)")
        await tp.evaluate("() => { const G = window.__game; G.closePage(); G.openMap(); }")
        await tp.wait_for_timeout(900)
        jm7 = await tp.evaluate("() => ({bands: document.querySelectorAll('.jm-band').length, w6: !!document.querySelector('.jm-band.w6'), w7: !!document.querySelector('.jm-band.w7'), chips: [...document.querySelectorAll('.jm-wchip')].map(e => e.textContent)})")
        await tp.evaluate("() => { const sc = document.querySelector('#jmScroll'); if (sc) sc.scrollLeft = sc.scrollWidth; }")
        await tp.wait_for_timeout(600)
        await tp.screenshot(path=str(OUT / '42h_여정지도_깊은바다.png'))
        check(jm7['bands'] == 8 and jm7['w6'] and jm7['w7'] and any('남쪽 바다' in c for c in jm7['chips']) and any('깊은 바다' in c for c in jm7['chips']), f"여정 지도에 남쪽 바다·깊은 바다 띠가 있다 {jm7}")
        await ctxT.close()

        # 9-16) 물의 신화 7-2단계: 4부 딸린 콘텐츠 — 천공의 탑 301~400층(4부부터)·4부 펫 다섯·탈것 셋·넋 구슬 여섯·지느러미 날개
        sea3 = json.loads((ROOT / 'tools' / 'beta_saves' / '70_musa_sea3_end.json').read_text(encoding='utf-8'))['save']
        ctxU = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        up = await ctxU.new_page()
        watch(up, errors, '7-2단계 ')
        await fresh(up)
        await signup(up, 'sea72test', 'abcd', '물밑용사')
        u1 = await up.evaluate(r"""(arg) => { const [save, lateS] = arg; const G = window.__game, S = G.S, out = {}; G.quiet = true; G.noFork = true;
          // 3부 끝 용사: 탑은 300층까지 · 4부 넋은 구슬에 안 나옴 · 큰 거북은 못 삼 · 4부 펫은 소환에 안 나옴
          Object.assign(S, G.mergeState(JSON.parse(JSON.stringify(lateS)))); S.name = '물밑용사'; G.refreshStats();
          S.tower.best = 300; S.tower.n = 0; out.cap3 = G.towerCap(); out.start3 = G.startTower();
          S.mount.piece = 999; out.buy3 = G.buyMount('seaturtle');
          let sea = 0; for (let i = 0; i < 300; i++){ G.soulLuck = (i % 100) / 100 + 0.001; if (G.SL[G.soulRoll()].pt === 4) sea++; } out.soul3 = sea;
          let pp = 0; for (let i = 0; i < 400; i++){ const p = G.PETS[G.rollPet()]; if (p.part >= 5) pp++; } out.pet3 = pp;
          out.how3 = [G.petHowText(G.PETS.find(p => p.draw === 'bulgae')), G.petHowText(G.PETS.find(p => p.draw === 'jara'))];
          // 4부 끝 용사: 지난 이야기의 넋 셋·곰새기·불개를 챙겨 받고, 탑은 400층까지
          Object.assign(S, G.mergeState(JSON.parse(JSON.stringify(save)))); S.name = '물밑용사'; G.refreshStats(); G.mountCatchUp();
          out.w = S.world; out.cap = G.towerCap(); out.max = G.TOWER.max;
          out.catch = [!!S.soul.own.munmu, !!S.soul.own.yeongdeung, !!S.soul.own.simcheong, !!S.mount.own.dolphin, S.pets.lv[G.PETS.findIndex(p => p.draw === 'bulgae')] > 0];
          sea = 0; const seen = {}; for (let i = 0; i < 600; i++){ G.soulLuck = (i % 100) / 100 + 0.001; const k = G.soulRoll(); if (G.SL[k].pt === 4){ sea++; seen[k] = 1; } } G.soulLuck = null; out.soul4 = [sea > 0, Object.keys(seen).sort()];
          pp = {}; for (let i = 0; i < 3000; i++){ const p = G.PETS[G.rollPet()]; if (p.part >= 5) pp[p.draw] = 1; } out.pet4 = Object.keys(pp).sort();
          out.parts = [G.PETS.filter(p => G.petPart(p) === 4).length, G.MOUNTS.filter(m => G.mountPart(m) === 4).length, G.SOULS.filter(x => G.soulPart(x) === 4).length];
          S.mount.piece = 999; out.buy = G.buyMount('seaturtle'); out.col = isFinite(G.mountCol()) && G.mountCol() > 0;
          // 그림: 새 펫 다섯·탈것 셋이 오류 없이 그려진다(두 프레임)
          out.art = G.PETS.map((p, i) => [p, i]).filter(([p]) => p.part >= 5).map(([p, i]) => G.petSprite(i, 0).width > 0 && G.petSprite(i, 1).width > 0).concat(['dolphin', 'seaturtle', 'yongma'].map(k => G.mountSprite(k, 0, false).width > 0 && G.mountSprite(k, 1, true).width > 0));
          // 탑: 층 → 세계·단계, 보상 글, 301층 도전
          out.ws = [300, 301, 330, 331, 365, 366, 400].map(f => G.towerWS(f)); out.boss = [301, 340, 380, 400].map(f => !!G.towerBoss(f).name && !!G.towerBoss(f).type);
          out.rw = [G.towerRewardText(305).join('|'), G.towerRewardText(310).join('|'), G.towerRewardText(350).join('|'), G.towerRewardText(400).join('|')];
          S.tower.best = 300; S.tower.n = 0; out.start = G.startTower(); out.info = G.raid ? [G.raid.info.f, G.raid.info.label, isFinite(G.raid.boss.maxHp) && G.raid.boss.maxHp > 0] : null;
          return out; }""", [sea3, late])
        check(u1['cap3'] == 300 and u1['start3'] is False and u1['buy3'] is False and u1['soul3'] == 0 and u1['pet3'] == 0 and '58장' in u1['how3'][0] and '동해' in u1['how3'][1],
              f"4부 전: 탑은 300층까지·4부 넋/펫은 안 나오고 큰 거북도 못 산다 {u1['cap3']} {u1['soul3']} {u1['pet3']} {u1['how3']}")
        check(u1['w'] == 7 and u1['cap'] == 400 and u1['max'] == 400 and all(u1['catch']) and u1['soul4'][0] and len(u1['soul4'][1]) == 6 and len(u1['pet4']) >= 2 and set(u1['pet4']) <= {'gomsaegi', 'jara', 'kkoetoki', 'mulbeom'} and u1['parts'] == [5, 3, 6] and u1['buy'] and u1['col'],
              f"4부: 지난 이야기의 넋 셋·곰새기·불개를 챙겨 받고, 바다의 넋 여섯·펫 넷이 구슬·소환에 나온다 {u1['catch']} {u1['soul4']} {u1['pet4']} {u1['parts']}")
        check(all(u1['art']) and len(u1['art']) == 8, f"4부 펫 다섯·탈것 셋 그림이 오류 없이 그려진다 {u1['art']}")
        check(u1['ws'] == [[4, 95], [5, 21], [5, 62], [6, 35], [6, 55], [7, 50], [7, 83]] and all(u1['boss']) and '호박석' in u1['rw'][0] and '유물' in u1['rw'][1] and '지느러미 날개' in u1['rw'][2] and '용마' in u1['rw'][3],
              f"탑 301~400층: 동해 → 남쪽 바다 → 깊은 바다 띠, 유물 장비·호박석·350층 날개·400층 용마 {u1['ws']} {u1['rw']}")
        check(u1['start'] is True and u1['info'] and u1['info'][0] == 301 and u1['info'][2], f"4부 용사는 301층에 도전할 수 있다 {u1['info']}")
        tw2 = await up.evaluate(r"""() => { const G = window.__game, S = G.S, out = {}; G.wipeOff = true;
          const run = (sec, until) => { for (let i = 0; i < sec * 20 && !until(); i++){ G.update(0.05); G.addTime(50); } };
          const amb0 = G.ambN ? null : null, raw0 = S.amber.raw.slice();
          G.raid.boss.hp = 1; run(8, () => !G.raid); out.best = S.tower.best;
          S.tower.best = 304; S.tower.n = 0; G.startTower(); G.raid.boss.hp = 1; run(8, () => !G.raid); out.b305 = S.tower.best; out.amb = S.amber.raw.map((x, i) => x - raw0[i]);
          S.tower.best = 349; G.startTower(); G.raid.boss.hp = 1; run(8, () => !G.raid); out.b350 = S.tower.best; out.fin = !!S.av.own.w_fin;
          S.tower.best = 399; G.startTower(); G.raid.boss.hp = 1; run(8, () => !G.raid); out.b400 = S.tower.best; out.yong = !!S.mount.own.yongma; out.more = G.startTower();
          const cv = document.createElement('canvas'); cv.width = 480; cv.height = 640; G.drawTowerArt(cv, 340); out.artOk = true;
          const re = G.mergeState(JSON.parse(JSON.stringify(S))); out.re = [re.tower.best, !!re.mount.own.yongma, !!re.av.own.w_fin];
          // 저장 보호 4의 되찾기: 400층인데 용마·날개가 없으면 다시 준다
          delete S.mount.own.yongma; delete S.av.own.w_fin; G.mountCatchUp(); out.back = [!!S.mount.own.yongma, !!S.av.own.w_fin];
          return out; }""")
        check(tw2['best'] == 301 and tw2['b305'] == 305 and sum(tw2['amb']) == 1 and tw2['b350'] == 350 and tw2['fin'] and tw2['b400'] == 400 and tw2['yong'] and tw2['more'] is False and tw2['artOk'] and tw2['re'] == [400, True, True] and tw2['back'] == [True, True],
              f"탑: 301·305(호박석)·350(지느러미 날개)·400층(용마)을 오르고 저장·되찾기가 맞다 {tw2}")
        # 7-2b: 4부 치장 22가지(46~67장)·유물 치장·아바타 여덟·세트 둘·용궁 조합식(10~12단계)
        u2 = await up.evaluate(r"""(lateS) => { const G = window.__game, S = G.S, out = {}; const keep = JSON.parse(JSON.stringify(S));
          out.n = [G.SK_LIST.length, G.SK_LIST.filter(x => x.c >= 46).length, new Set(G.SK_LIST.map(x => x.c)).size, G.SK_GRADES.length, G.AVATARS.filter(a => a.pt === 4 || a.w >= 5).length, G.SETS.length];
          out.parts = ['guard', 'shoe', 'belt', 'tassel', 'foot'].map(p => G.SK_LIST.filter(x => x.c >= 46 && x.p === p).length);
          // 사냥터 드롭: 4부 끝 용사는 46~67장 치장도 나오고 유물은 안 나온다. 한 줄 값은 4부 것이 1.15배까지
          let sea = 0, relic = 0, maxOld = 0, maxSea = 0; S.skin = {eq:{}, inv:[], seq:0, found:{}};
          for (let i = 0; i < 400; i++){ const r = G.skinDrop(null, true); if (!r) continue; const it = r.it; if (it.c >= 46) sea++; if (it.g >= 5) relic++; for (const l of it.l){ if (it.g === 4){ if (it.c >= 46) maxSea = Math.max(maxSea, l[1]); else maxOld = Math.max(maxOld, l[1]); } } }
          out.drop = [sea > 50, relic, maxOld <= 0.40 + 1e-9, maxSea > 0.40 && maxSea <= 0.46 + 1e-9];
          // 유물 치장(수군 야행·용궁 보물고·1일 보스): 4부 치장만, 저장·불러오기에서도 그대로
          G.skRelic = 1e9; const rr = G.skinDrop(null, true, 0, 1, 0.9, 0.05); G.skRelic = null;
          out.relic = [rr.it.g, rr.it.c >= 46, rr.it.l.length, G.skGr(5).name, rr.it.l.every(l => l[1] <= 0.46 * 1.15 + 0.006 && l[1] >= 0.46 * 1.15 * 0.9 - 0.006)];
          const cl = G.skClean(JSON.parse(JSON.stringify(S.skin))); const all = Object.values(cl.eq).concat(cl.inv); out.relicKept = all.some(x => x.g === 5);
          out.relicBad = G.skClean({eq:{}, inv:[{id:1, c:20, g:5, l:[['hp', 0.4]]}], seq:1, found:{}}).inv.length;   // 1~3부 치장은 유물이 될 수 없다
          const dp = G.skinDropPart('guard', 3, true); out.dpart = [dp.it.c >= 46, G.SKC[dp.it.c].p];
          // 3부 끝 용사: 46장 첫 퀘스트를 하는 동안에도 바다 치장은 안 나오고, 용궁 조합식은 안 보인다
          Object.assign(S, G.mergeState(JSON.parse(JSON.stringify(lateS)))); G.refreshStats(); S.skin = {eq:{}, inv:[], seq:0, found:{}};
          let sea3 = 0; for (let i = 0; i < 300; i++){ const r = G.skinDrop(null, true); if (r && r.it.c >= 46) sea3++; }
          S.craft.w.t = 9; out.late = [G.skCh(), G.skChCap(), sea3, G.craftCap(), !!G.craftNeed('w').max, G.avBoxPool ? 0 : 0];
          const cmp3 = G.craftComp(4, 50);
          // 4부: 용궁 조합식 10~12단계
          Object.assign(S, G.mergeState(keep)); G.refreshStats();
          S.craft.w.t = 9; S.craft.w.e = S.craft.w.e || 'power'; const n10 = G.craftNeed('w'); out.c10 = [G.craftCap(), n10.t, n10.mk, n10.mat, n10.open, n10.past, n10.g, n10.n];
          S.mat.m3 = 99999; S.gems += 100000; S.gear.weapon.count[16] += 20; G.craftLuck = 1e9; const atk0 = G.refreshStats() || G.ST.atk;
          out.craft = [G.craft('w'), G.craft('w'), G.craft('w'), S.craft.w.t, !!G.craftNeed('w').max, G.craftName ? 1 : 1]; G.craftLuck = null; G.refreshStats();
          out.atkUp = G.ST.atk > atk0; out.comp = [cmp3 === G.craftComp(4, 50), G.craftComp(5, 10) === G.craftComp(4, 50)];
          const re = G.mergeState(JSON.parse(JSON.stringify(S))); out.reT = re.craft.w.t;
          // 세트: 해녀의 조합(신발 칸 포함) 다섯 조각
          S.equip.weapon = 19; S.gear.weapon.count[19] = Math.max(1, S.gear.weapon.count[19]); S.equip.armor = 19; S.gear.armor.count[19] = Math.max(1, S.gear.armor.count[19]); S.equip.boots = 16; S.gear.boots.count[16] = Math.max(1, S.gear.boots.count[16]);
          G.giveAvatar('c_haenyeo', true); G.equipAvatar('c_haenyeo'); G.giveMount('dolphin', true); G.rideMount('dolphin'); G.pickSet('haenyeo'); G.refreshStats();
          out.set = [G.setCount(G.SETS.find(x => x.k === 'haenyeo')), G.setSum().k || (G.setSum().set && G.setSum().set.k) || ''];
          return out; }""", late)
        check(u2['n'] == [51, 22, 51, 6, 9, 11] and u2['parts'] == [5, 4, 4, 5, 4], f"4부 치장 22가지(46~67장, 부위 다섯에 고르게)·아바타 아홉(날개 포함)·세트 둘 {u2['n']} {u2['parts']}")
        check(u2['drop'] == [True, 0, True, True] and u2['relic'][:4] == [5, True, 4, '유물'] and u2['relic'][4] and u2['relicKept'] and u2['relicBad'] == 0 and u2['dpart'] == [True, 'guard'],
              f"4부 치장: 사냥터에서는 전설까지(한 줄 값 1.15배), 유물은 따로 주는 곳에서만·4부 치장만·저장해도 그대로 {u2['drop']} {u2['relic']} {u2['relicKept']} {u2['relicBad']} {u2['dpart']}")
        check(u2['late'][:5] == [46, 45, 0, 9, True], f"3부 끝 용사: 46장 첫 퀘스트 중에도 바다 치장은 안 나오고 용궁 조합식은 안 보인다 {u2['late']}")
        check(u2['c10'] == [12, 10, 'm3', 1200, True, False, 4, 2] and u2['craft'][:5] == [True, True, True, 12, True] and u2['atkUp'] and u2['comp'] == [True, True] and u2['reT'] == 12,
              f"용궁 조합식: 동해부터 10~12단계(용궁 진주·전설 장비), 몬스터 세기는 그대로 {u2['c10']} {u2['craft']} {u2['comp']}")
        check(u2['set'][0] == 5, f"해녀의 조합: 무기·갑옷·신발·해녀 물옷·곰새기 다섯 조각 {u2['set']}")
        # 7-2c·d: 수군 야행(밀물·대장)·용궁 보물고(방 셋·상자)·용왕 강림·타임 보스 심해·4부 1일 보스·손컨 패턴 「물살」「숨」
        u3 = await up.evaluate(r"""() => { const G = window.__game, S = G.S, out = {}; G.quiet = true; G.wipeOff = true; G.noFork = true; G.hideModal();
          const run = (sec, until) => { for (let i = 0; i < sec * 20 && !until(); i++){ G.update(0.05); G.addTime(50); } };
          S.inv.potion = 999; S.inv.elixir = 99; S.inv.mana = 999; G.refreshStats(); G.hero.hp = G.ST.maxHp;
          // 수군 야행: 밀물 두 번·끝의 대장·덤(고삐 조각·치장·바다의 넋)
          out.sgOpen = [G.sugunOpen(), G.sugunLeft()]; const p0 = S.mount.piece, r0 = S.rec.suguns || 0; G.sgLuck = 1e9; G.skRelic = 1e9;
          out.sgStart = G.startSugun(); let tides = 0, wet = 0, bossSeen = false;
          for (let i = 0; i < 62 * 20 && G.parade; i++){ G.update(0.05); G.addTime(50); const P = G.parade; if (!P) break;
            if (P.tide && P.tide.on){ tides = Math.max(tides, P.tideN); if (P.tide.side ? G.hero.tx >= 14 : G.hero.tx < 14) wet += 0.05; }
            if (P.boss){ bossSeen = true; if (!P.boss.dead) P.boss.hp = Math.min(P.boss.hp, 1); } }
          out.sg = [!G.parade, (S.rec.suguns || 0) - r0, G.seaDay().sugun, G.sugunLeft(), tides, wet < 8, bossSeen, S.mount.piece - p0 >= G.SUGUN.piece, S.sea2.sugunBest >= 10, Object.values(S.skin.eq).concat(S.skin.inv).some(x => x.g === 5)];
          G.sgLuck = null; G.skRelic = null;
          out.sg2 = G.startSugun(); if (G.parade){ G.parade.t = 0.01; G.update(0.05); } out.sg3 = [G.sugunLeft(), G.startSugun()];
          // 용궁 보물고: 방 셋(둘째는 함정 방) → 상자 → 끝까지 가면 야광주(운 고정)
          const relicN = () => G.ALL_SLOTS.reduce((t, sl) => t + S.gear[sl].count.slice(20, 24).reduce((a, x) => a + x, 0), 0), rl0 = relicN();
          G.yvBox = 'gear'; G.yvLuck = 1e9; G.vaultLuck = 1e9; out.yvOpen = [G.yvOpen(), G.yvLeft()]; out.yvStart = G.startYv(); const rooms = [];
          for (let r = 0; r < 3; r++){ if (!G.raid || G.raid.info.room !== r) break; rooms.push([G.raid.info.bossName, !!G.raid.info.trap, !!G.raid.info.yv]); G.raid.boss.hp = 1; run(12, () => !G.raid || G.raid.info.room !== r); }
          out.yv = [rooms.map(x => x[0]), rooms.map(x => x[1]), !G.yvRun, !G.raid, relicN() - rl0, S.myth.yagwang, S.rec.yvs, G.yvLeft()];
          out.yv2 = G.startYv(); if (G.raid){ G.raid.time = 0.05; run(12, () => !G.raid); } out.yvLose = [!G.yvRun, G.yvLeft(), G.startYv()];
          G.yvBox = null; G.yvLuck = null; G.vaultLuck = null;
          // 용왕 강림: 전멸기 두 번·용왕 아바타(운 고정)·이기면 그날 끝
          G.grLuck = 1e9; out.ygrOpen = [G.ygrOpen(), G.ygrLeft()]; out.ygrStart = G.startYgr(); out.ygrInfo = G.raid ? [G.raid.info.label, G.raid.info.wipes, G.raid.allies.length, !!G.raid.info.ygr] : null;
          if (G.raid){ G.raid.info.fit = null; G.raid.boss.hp = 1; } run(40, () => !G.raid);
          out.ygr = [G.seaDay().ygrWon, G.ygrLeft(), G.AVATARS.filter(a => a.src === '용왕 강림' && S.av.own[a.k]).length, S.rec.ygr, G.startYgr()]; G.grLuck = null;
          // 손컨 패턴: 깊은 바다 레이드에서 숨 막대·공기 방울·물살
          S.raid.tk = 3; out.raidStart = G.startRaid(0); const B = G.raid && G.raid.boss; let bub = false, refill = false, flow = null;
          if (B){ B.hp = B.maxHp = B.maxHp * 1e9; run(3, () => !!(B.pat && B.breath)); out.breath0 = !!B.breath && B.breath.v < 100 && G.breathOn(B) && G.patSea(B);
            if (B.breath){ B.breath.v = 30; B.breath.bt = 0; }
            for (let i = 0; i < 25 * 20 && !refill; i++){ G.update(0.05); G.addTime(50); const Q = B.breath; if (Q && Q.bub) bub = true; if (Q && Q.v > 62) refill = true; G.hero.hp = G.ST.maxHp; }
            // 물살: 버티지 못하면 떠밀리고(자동 손 실패), 버티면 제자리
            for (let i = 0; i < 400 && B.pat.tel; i++){ G.update(0.05); G.hero.hp = G.ST.maxHp; }
            G.hero.goal = null; G.hero.dodgeT = 0; G.hero.rollT = 0; G.patFlow(B, B.pat); const T = B.pat.tel;
            if (T && T.flow){ T.auto.ok = false; const x0 = G.hero.tx, y0 = G.hero.ty; let moved = 0; for (let i = 0; i < 60 && B.pat.tel === T; i++){ G.update(0.05); G.hero.goal = null; moved = Math.max(moved, (G.hero.tx - x0) * T.flow[0] + (G.hero.ty - y0) * T.flow[1]); G.hero.hp = G.ST.maxHp; }
              flow = [T.shape, T.set.size > 30, moved >= 1]; }
            G.raid.time = 0.05; run(12, () => !G.raid); }
          out.pat = [bub, refill, flow];
          // 타임 보스 심해: 동해부터 · 전멸기 두 번 · 호박석
          const w = G.tbWindow(); if (!w.open) G.addTime(w.next - G.now() + 60000);
          out.tbWhy = G.tbCan('deep'); out.tbStart = G.startTimeBoss('deep'); out.tbInfo = G.raid ? [G.raid.info.bossName.startsWith('심해 '), G.raid.info.wipes] : null;
          const amb0 = S.amber.raw.reduce((a, x) => a + x, 0); if (G.raid){ G.raid.info.fit = null; G.raid.boss.hp = 1; } run(60, () => !G.raid);
          out.tb = [S.tb.deep === G.tbWindow().id, S.amber.raw.reduce((a, x) => a + x, 0) - amb0 >= 1, !!G.tbCan('deep')];
          // 1일 보스: 4부 용사에게 짝수 날엔 바다 보스
          const even = new Date(G.now()).getDate() % 2 === 0; out.db = [G.dbSea() === even, G.DBOSS_SEA.length, G.DBOSS_SEA.every(x => !!G.bossPortrait(x.type, x.color)), G.dbBoss().name === (even ? G.DBOSS_SEA : G.DBOSS)[new Date(G.now()).getDay()].name];
          // 저장해도 그대로, 3부 용사에게는 모두 닫혀 있다
          const re = G.mergeState(JSON.parse(JSON.stringify(S))); out.re = [re.sea2.day === S.sea2.day, re.sea2.sugunBest === S.sea2.sugunBest, re.tb.deep === S.tb.deep, re.myth.yagwang];
          const w0 = S.world, d0 = S.tb.deep; S.world = 4; S.tb.deep = 0; out.shut = [G.sugunOpen(), G.yvOpen(), G.ygrOpen(), G.tbCan('deep'), G.dbSea(), G.patSea(B || {}), G.breathOn(B || {})]; S.world = w0; S.tb.deep = d0;
          return out; }""")
        check(u3['sgOpen'] == [True, 2] and u3['sgStart'] and u3['sg'][:4] == [True, 1, 1, 1] and u3['sg'][4] >= 2 and all(u3['sg'][5:]) and u3['sg2'] and u3['sg3'] == [0, False],
              f"수군 야행: 밀물이 두 번 들어오고(잠긴 쪽에서 걸어 나옴) 끝에 대장, 잡으면 고삐 조각·유물 치장(운 고정), 하루 2번 {u3['sgOpen']} {u3['sg']} {u3['sg3']}")
        check(u3['yvOpen'] == [True, 2] and u3['yvStart'] and u3['yv'][0] == ['문어 문지기', '가시 덫 복어', '광어 창고지기'] and u3['yv'][1] == [False, True, False] and u3['yv'][2:4] == [True, True] and u3['yv'][4] == 3 and u3['yv'][5] == 60 and u3['yv'][6] == 1 and u3['yv'][7] == 1,
              f"용궁 보물고: 방 셋(둘째는 함정 방)을 지나며 상자 셋(장비 상자 → 유물 장비), 끝까지 가면 용궁 야광주(운 고정) {u3['yv']}")
        check(u3['yv2'] and u3['yvLose'] == [True, 0, False], f"용궁 보물고: 지면 거기서 끝, 하루 2번 {u3['yvLose']}")
        check(u3['ygrOpen'] == [True, 2] and u3['ygrStart'] and u3['ygrInfo'] == ['용왕 강림', [0.7, 0.35], 3, True] and u3['ygr'][:2] == [True, 0] and u3['ygr'][2] == 1 and u3['ygr'][3] == 1 and u3['ygr'][4] is False,
              f"용왕 강림: 넷이 함께·전멸기 두 번·용왕 아바타(운 고정)·이기면 그날 끝 {u3['ygrInfo']} {u3['ygr']}")
        check(u3['raidStart'] and u3.get('breath0') and u3['pat'][0] and u3['pat'][1] and u3['pat'][2] == ['flow', True, True],
              f"손컨 패턴: 깊은 바다에서는 숨이 줄고 공기 방울을 밟아(저절로 걸어가) 채운다 · 물살에 버티지 못하면 떠밀린다 {u3.get('breath0')} {u3['pat']}")
        check(u3['tbWhy'] == '' and u3['tbStart'] and u3['tbInfo'] == [True, [0.7, 0.35]] and u3['tb'] == [True, True, True], f"타임 보스 심해: 4부 용사가 도전(전멸기 두 번), 이기면 호박석 {u3['tbInfo']} {u3['tb']}")
        check(u3['db'] == [True, 7, True, True], f"1일 보스: 4부 용사에게 짝수 날엔 바다 보스 일곱(그림 있음) {u3['db']}")
        check(u3['re'] == [True, True, True, 60] and u3['shut'][:3] == [False, False, False] and '동해' in u3['shut'][3] and u3['shut'][4:] == [False, False, False],
              f"4부 딸린 콘텐츠: 저장해도 그대로, 3부 용사에게는 모두 닫혀 있다 {u3['re']} {u3['shut']}")
        for rv, nm in (('parade', '43d-sugun-card'), ('vault', '43e-yvault-card'), ('gr', '43f-yongwang-card'), ('tb', '43g-tb-deep')):
            await up.evaluate("(rv) => { const G = window.__game; G.hideModal(); G.buildTab('raid'); const b = document.querySelector(`[data-rv=\"${rv}\"]`); if (b) b.click(); }", rv)
            await up.wait_for_timeout(500)
            await up.evaluate("() => { const p = document.querySelector('#panel'); if (p) p.scrollTop = p.scrollHeight; }")
            await up.wait_for_timeout(200)
            await up.screenshot(path=str(OUT / f'{nm}.png'))
        await up.evaluate("""() => { const G = window.__game, S = G.S; G.closePage(); G.seaDay().sugun = 0; G.startSugun(); const P = G.parade; P.t = 30; P.tideN = 1; P.tide = {side:1, t:3, on:true, hurt:0}; }""")
        await up.wait_for_timeout(1500)
        await up.screenshot(path=str(OUT / '43h-sugun-tide.png'))
        await up.evaluate("""() => { const G = window.__game, S = G.S; if (G.parade){ G.parade.t = 0.01; } }""")
        await up.wait_for_timeout(600)
        await up.evaluate("""() => { const G = window.__game, S = G.S; G.hideModal(); S.raid.tk = 3; G.startRaid(0); const B = G.raid.boss; B.hp = B.maxHp = B.maxHp * 1e9; }""")
        await up.wait_for_timeout(2500)
        await up.evaluate("""() => { const G = window.__game, B = G.raid && G.raid.boss; if (B && B.pat){ B.pat.tel = null; G.hero.dodgeT = 0; G.patFlow(B, B.pat); if (B.breath){ B.breath.v = 22; B.breath.bt = 0; } } }""")
        await up.wait_for_timeout(900)
        await up.screenshot(path=str(OUT / '43i-flow-breath.png'))
        await up.evaluate("""() => { const G = window.__game; if (G.raid){ G.raid.time = 0.05; } }""")
        await up.wait_for_timeout(2500)
        await up.evaluate("() => { const G = window.__game; G.hideModal(); G.gearSlotSet && G.gearSlotSet('skin'); }")
        await up.evaluate("() => { const G = window.__game; G.hideModal(); G.S.tower.best = 300; G.buildTab('tower'); }")
        await up.wait_for_timeout(500)
        await up.screenshot(path=str(OUT / '43-tower-sea.png'))
        await up.evaluate("() => { const G = window.__game; G.S.tower.best = 342; G.buildTab('tower'); }")
        await up.wait_for_timeout(500)
        await up.screenshot(path=str(OUT / '43b-tower-sea-342.png'))
        await tab(up, 'pet')
        await up.wait_for_timeout(500)
        await up.evaluate("() => { const b = [...document.querySelectorAll('.pt-tab,[data-pt]')].find(x => /4부/.test(x.textContent)); if (b) b.click(); }")
        await up.wait_for_timeout(400)
        await up.screenshot(path=str(OUT / '43c-pet-part4.png'))
        await ctxU.close()

        # 9-17) 물의 신화 8-1단계: 신규 직업 「궁사」(1~5차) — 아직 직업 고르기 창에는 안 보이고(CLASS_ALL에만), 시험 훅 setClass로 만들어 본다
        ctxG = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        gp = await ctxG.new_page()
        watch(gp, errors, '8-1단계 ')
        await fresh(gp)
        await signup(gp, 'gungtest', 'abcd', '활잡이')
        g1 = await gp.evaluate(r"""(arg) => { const [save] = arg; const G = window.__game, S = G.S, out = {}; G.quiet = true; G.noFork = true; G.PAT.off = true; G.wipeOff = true;
  const run = (sec, f) => { for (let i = 0; i < sec * 20; i++){ G.update(0.05); G.addTime(50); if (f && f(i)) break; } };
  // 아직 플레이어에게 안 보인다: 직업 고르기·직업 바꾸기 창에는 네 직업만
  out.order = [G.CLASS_ORDER.includes('gungsa'), G.CLASS_ALL.includes('gungsa'), G.CLASS_ORDER.length];
  G.clsChgOpen(); out.cards = [document.querySelectorAll('.ccard').length, document.querySelectorAll('.ccard[data-c="gungsa"]').length]; G.hideModal();
  // 4부 끝 무사 저장에서 직업만 궁사로: 기술 13칸이 모두 나간다(반자동 = 기술은 모두 손으로)
  Object.assign(S, G.mergeState(JSON.parse(JSON.stringify(save)))); S.name = '활잡이'; G.setClass('gungsa'); S.mode = 'semi'; S.skManual = {}; S.inv.mana = 9999; G.refreshStats();
  out.stat = [G.CLASSES.gungsa.range, G.heroRange(), Math.round(G.ST.maxHp / G.ST.atk) > 0, G.skillName ? 1 : 0];
  const cast = {}, names = [];
  for (const set of [[0, 1, 2, 3, 4, 5, 6, 7], [5, 6, 7, 8, 9, 10, 11, 12]]){
    S.skSet = set.slice(); S.skSetMan = true; S.skOff = G.SKILLS.map((_, i) => i).filter(i => !set.includes(i));
    G.bench(8, false, t => { const k = Math.round(t / 0.05); if (k >= 12 && k % 6 === 0){ const i = set[(k - 12) / 6]; if (i != null && !cast[i]){ G.hero.mp = 999; cast[i] = G.castNow(i); } } });
  }
  out.cast = G.SKILLS.map((_, i) => !!cast[i]); out.names = G.CLASSES.gungsa.skills.length;
  out.desc = G.SKILLS.map((_, i) => { const d = G.skillDesc(i, 5), g = G.skillGain(i, 5); return typeof d === 'string' && d.length > 8 && !/undefined|NaN/.test(d) && g && isFinite(g.g); });
  out.mp = [G.skMp(3), (S.cls = 'musa', G.skMp(3))]; S.cls = 'gungsa';
  // 조준: 서 있으면 차고(4초), 구르면 줄고, 다시 서면 찬다. 가득 차면 치명타 피해 ×1.6
  S.skSet = []; const aim = {};
  G.bench(14, false, t => { const k = Math.round(t / 0.05); if (k === 20) aim.t1 = G.hero.aim; if (k === 110){ aim.full = G.hero.aim; aim.mul = G.aimMul(true); G.heroRoll(true); } if (k === 116) aim.roll = G.hero.aim; if (k === 270) aim.back = G.hero.aim; });
  out.aim = [aim.t1 > 0.1 && aim.t1 < 0.5, aim.full === 1, Math.round(aim.mul * 100), aim.roll < 1, aim.back === 1];
  S.cls = 'musa'; out.aimMusa = G.aimMul(true); S.cls = 'gungsa';
  // 매의 눈(파티 버프): 치명타 확률 + 사거리 +1, 바람 읽기: 사거리 +1 더
  S.skSet = [10, 12]; G.bench(1, false, t => { if (Math.round(t / 0.05) === 4){ G.hero.mp = 999; G.castNow(10); } if (Math.round(t / 0.05) === 8){ G.hero.mp = 999; G.castNow(12); } if (Math.round(t / 0.05) === 12) out.rng = [G.heroRange(), G.hero.windT > 0, G.pbDesc('gungsa', 1).includes('사거리')]; });
  // 전직 1~5차: 스승과 겨뤄 이기면 전직(망토·기술)
  S.mode = 'auto'; S.job = 0; S.av.cape = ''; for (const k of ['jobA', 'jobB', 'jobC', 'jobD', 'jobE', 'jobF']) S.skills[k] = 0; G.refreshStats();
  const jobs = [];
  for (let tier = 1; tier <= 5; tier++){
    const ready = tier === 2 ? true : G.jobReady(tier), names = [], types = [];
    const st = G.startJobTrial(tier, tier === 2 ? 1 : 0);
    run(60, () => { const R = G.raid; if (R){ if (!names.includes(R.info.bossName)){ names.push(R.info.bossName); types.push(R.info.type); } const B = R.boss; if (B && !B.dead && B.spawnT <= 0 && B.hp > 1) B.hp = 1; } return S.job >= tier && !G.raid; });
    jobs.push({ready, st, names, types, job:S.job, name:G.jobName(), cape:S.av.cape, own:!!S.av.own['j_gungsa_' + tier], sprite:types.every(t => String(G.bossPortrait(t, '#888888')).startsWith('data:image'))});
  }
  out.jobs = jobs; out.jobSk = ['jobA', 'jobB', 'jobC', 'jobD', 'jobE', 'jobF'].map(k => S.skills[k] >= 1); out.mpMax = G.mpMax ? G.mpMax() : 0;
  // 초각성기(이름) · 초각성기 2 「한 화살 만 리」: 10초 동안 보스의 낙인 2배
  G.aw2Force = true; S.aw2 = Object.assign(S.aw2 || {}, {got:true, tut:true, man:false});
  S.raid.tk = 3; G.startRaid(0); run(1); { const R = G.raid, B = R.boss, A = R.awk2; B.hp = B.maxHp = 1e300;
    out.awk = [G.CLASSES.gungsa.awaken, G.CLASSES.gungsa.awaken4, !!R.awk]; if (R.awk && !R.awk.used){ G.castAwaken(); out.awkUsed = R.awk.used; }
    if (A){ A.g = 100; A.hand = 0; B.markT = 0; B.markP = 0; out.aw2 = [G.castAwaken2(true), A.markT > 0, B.markT > 0, B.markP > 0, G.AW2_SK.gungsa.name]; } else out.aw2 = ['no awk2'];
    G.raidEnd(false); run(2); }
  G.aw2Force = false;
  // 저장했다가 다시 불러와도 궁사 그대로
  const re = G.mergeState(JSON.parse(JSON.stringify(S))); out.re = [re.cls, re.job, re.av.cape];
  G.PAT.off = false; G.wipeOff = false; G.hideModal();
  return out; }""", [sea3])
        check(g1['order'] == [False, True, 4] and g1['cards'] == [4, 0], f"궁사: 아직 직업 고르기·직업 바꾸기 창에는 안 보인다(모든 직업 목록 CLASS_ALL에만) {g1['order']} {g1['cards']}")
        check(all(g1['cast']) and all(g1['desc']) and g1['names'] == 13 and g1['stat'][:2] == [5, 5] and g1['mp'][0] * 2 <= g1['mp'][1] + 1,
              f"궁사: 기술 13칸이 모두 나가고 설명·레벨 미리보기가 나온다 · 사거리 5칸 · 마나 절반 {g1['cast']} {g1['desc']} {g1['mp']}")
        check(g1['aim'] == [True, True, 160, True, True] and g1['aimMusa'] == 1, f"궁사 「조준」: 서 있으면 차고(4초) 구르면 줄고 다시 서면 찬다 · 가득 차면 치명타 피해 ×1.6 · 다른 직업은 그대로 {g1['aim']} {g1['aimMusa']}")
        check(g1['rng'] == [7, True, True], f"궁사: 매의 눈(파티 버프)·바람 읽기(5차)가 사거리를 한 칸씩 늘린다 {g1['rng']}")
        gj = g1['jobs']
        check([j['names'] for j in gj] == [['늙은 사냥꾼'], ['강림도령'], ['나스노 요이치'], ['늙은 사냥꾼', '강림도령', '나스노 요이치'], ['거타지']] and all(j['st'] and j['ready'] and j['own'] and j['sprite'] for j in gj)
              and [j['job'] for j in gj] == [1, 2, 3, 4, 5] and [j['name'] for j in gj] == ['명궁', '귀궁', '궁마사', '사일객', '해궁'] and gj[4]['cape'] == 'j_gungsa_5' and all(g1['jobSk']) and g1['mpMax'] == 120,
              f"궁사 전직 1~5차: 스승(늙은 사냥꾼·강림도령·나스노 요이치·세 스승·거타지)과 겨뤄 이기면 전직·망토·기술 {[(j['names'], j['name'], j['cape']) for j in gj]} {g1['jobSk']}")
        check(g1['awk'] == ['일시천리', '사일 구연사', True] and g1.get('awkUsed') and g1['aw2'] == [True, True, True, True, '한 화살 만 리'], f"궁사: 초각성기(일시천리 → 사일 구연사)·초각성기 2 「한 화살 만 리」(보스 낙인 2배 10초) {g1['awk']} {g1['aw2']}")
        check(g1['re'] == ['gungsa', 5, 'j_gungsa_5'], f"궁사: 저장했다가 다시 불러와도 직업·전직·망토 그대로 {g1['re']}")
        gsheet = await gp.evaluate(r"""() => { const G = window.__game, S = G.S, Z = 3, W = 64 * Z;
  const cv = document.createElement('canvas'); cv.width = W * 6; cv.height = W * 5; const g = cv.getContext('2d'); g.imageSmoothingEnabled = false;
  g.fillStyle = '#5a7a5a'; g.fillRect(0, 0, cv.width, cv.height);
  const look = {outfit:'auto', hair:'#241c26', hat:'class', skin:0};
  for (let j = 0; j <= 5; j++){
    const ex = {job:j, capeC:j ? G.JOBS.gungsa[j - 1].capeC : ''}, gr = Math.min(4, j);
    [['right', 0], ['right', 3], ['up', 0], ['down', 1]].forEach(([d, f], r) => { const sp = G.personSprite('gungsa', look, gr, gr, d, f, false, ex); g.drawImage(sp, j * W, r * W, W, W); });
  }
  ['m_gungsa', 'm3_gungsa', 'm5_gungsa'].forEach((t, i) => { for (const f of [0, 1]){ const sp = G.mobSprite(t, '', f, true); g.drawImage(sp, (i * 2 + f) * W, 4 * W, W, W); } });
  return cv.toDataURL(); }""")
        (OUT / '44-gungsa-sheet.png').write_bytes(base64.b64decode(gsheet.split(',')[1]))   # 전직 0~5차 × (앞·쏘기·뒤·걷기) + 스승 셋(늙은 사냥꾼·나스노 요이치·거타지)
        await gp.evaluate("() => { const G = window.__game, S = G.S; G.hideModal(); G.closePage && G.closePage(); S.mode = 'auto'; G.resetRuntime(); G.setStage(S.stage); G.startBoss(); }")
        await gp.wait_for_timeout(4000)
        await gp.screenshot(path=str(OUT / '44b-gungsa-fight.png'))
        await gp.evaluate("() => { const G = window.__game; if (G.raid) G.raidEnd(false); G.hideModal(); }")
        await tab(gp, 'skill')
        await gp.wait_for_timeout(500)
        await gp.screenshot(path=str(OUT / '44c-gungsa-skills.png'))
        await ctxG.close()

        # 10) 앱으로 설치(PWA): 웹서버로 열어 앱 설정·아이콘·오프라인 도우미를 확인하고, 인터넷을 끊고 다시 연다
        srv, base = serve()
        ctxP = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        await ctxP.add_init_script("window.__samhanOnline = {url: ''};")   # 이 점검은 진짜 온라인 서버에 계정을 만들지 않는다
        pp = await ctxP.new_page()
        watch(pp, errors, 'PWA ')
        await pp.goto(base + 'index.html?simtest')
        await pp.wait_for_selector('#lg-id')
        info = await pp.evaluate('''async () => {
          const reg = await Promise.race([navigator.serviceWorker.ready, new Promise(r => setTimeout(() => r(null), 8000))]);
          const man = await (await fetch(document.querySelector('link[rel=manifest]').href)).json();
          const icons = await Promise.all(man.icons.map(i => fetch(i.src).then(r => r.ok && r.headers.get('content-type'))));
          const img = await Promise.all(man.icons.map(i => new Promise(r => { const im = new Image(); im.onload = () => r(im.width); im.onerror = () => r(0); im.src = i.src; })));
          return {sw: !!(reg && reg.active), name: man.name, display: man.display, icons, img, pwa: window.__game.pwa};
        }''')
        check(info['pwa'] and info['sw'] and info['name'] == '삼한 용사 키우기' and info['display'] in ('standalone', 'fullscreen')
              and all(t == 'image/png' for t in info['icons']) and info['img'] == [192, 512, 512], f'앱 설정·아이콘·오프라인 도우미가 준비된다 {info}')
        check(await pp.is_visible('#lg-install'), '로그인 화면에 [앱으로 설치하기]가 보인다')
        await pp.click('#lg-install')
        await pp.wait_for_selector('#mTitle:has-text("앱으로 설치하기")')
        await pp.screenshot(path=str(OUT / '23_앱설치안내.png'))
        await pp.click('#modal-btn-0')
        await pp.wait_for_selector('#lg-id')
        await pp.reload()          # 오프라인 도우미가 이 페이지를 맡게 한 번 더 연다
        await pp.wait_for_selector('#lg-id')
        await pp.wait_for_timeout(500)
        await ctxP.set_offline(True)
        await pp.reload()
        await pp.wait_for_selector('#lg-id', timeout=8000)
        await signup(pp, 'offline1', 'abcd', '산골')
        await pp.wait_for_timeout(1500)
        off = await pp.evaluate('() => ({name: window.__game.S.name, kills: window.__game.S.rec.kills, online: navigator.onLine})')
        check(off['name'] == '산골' and not off['online'], f'인터넷이 끊겨도 게임이 열리고 돌아간다 {off}')
        await pp.screenshot(path=str(OUT / '24_오프라인.png'))
        await ctxP.set_offline(False)
        await tab(pp, 'rec')
        check(await pp.is_visible('#appBtn'), '[정보] 탭에 [앱으로 설치] 단추가 있다')
        await ctxP.close()

        # 11) 베타 테스트 빌드(tools/build.py --beta): 저장 자리가 따로(beta- 머리말)·온라인/앱 설치 끔·베타 띠·시험용 캐릭터, 본 빌드에는 베타 코드가 없음
        bout = ROOT / 'beta' / 'index.html'   # 진짜 주소(…/samhan-hero/beta/)와 같은 자리. patch 브랜치에는 커밋하지 않는다(.gitignore)
        br = subprocess.run([sys.executable, str(ROOT / 'tools' / 'build.py'), '--beta'], capture_output=True, text=True)
        check(br.returncode == 0 and bout.exists(), f'베타 빌드가 만들어진다 {br.stderr[-300:]}')
        main_html = (ROOT / 'index.html').read_text(encoding='utf-8')
        check(all(w not in main_html for w in ('BETA_ONLY', 'BETA_SAVES', 'cs-beta', 'betaTag')) and '/*BETA_BUILD*/false' in main_html, '본 빌드(index.html)에는 베타 전용 코드·시험용 저장이 들어가지 않는다')
        ctxB = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        await ctxB.add_init_script("window.__samhanOnline = {url: 'http://127.0.0.1:9', key: 'sb_publishable_test'};")   # 본 빌드라면 온라인이 켜질 조건(아무 데도 닿지 않는 주소)
        bp = await ctxB.new_page()
        await bp.goto(base + 'index.html?simtest')
        await bp.wait_for_selector('#lg-id')
        m0 = await bp.evaluate('''async () => { await Promise.race([navigator.serviceWorker.ready, new Promise(r => setTimeout(r, 8000))]);
          localStorage.setItem('samhan-accounts-v1', '{"v":1,"accounts":{},"mark":"main"}');
          return {beta: window.__game.beta, on: window.__game.onlineWanted, pwa: window.__game.pwa}; }''')
        await bp.reload(); await bp.wait_for_selector('#lg-id')   # 본 게임의 오프라인 도우미가 이 창을 맡은 상태로
        mk0 = await bp.evaluate("() => Object.fromEntries(Object.keys(localStorage).filter(k => !k.startsWith('beta-')).sort().map(k => [k, localStorage.getItem(k)]))")   # 본 게임이 이 주소에 둔 것(계정 표시 + 이 기기 표 samhan-dev)
        watch(bp, errors, '베타 ')
        await bp.goto(base + 'beta/?simtest')
        await bp.wait_for_selector('#lg-id')
        b0 = await bp.evaluate('''() => ({beta: window.__game.beta, on: window.__game.onlineWanted, pwa: window.__game.pwa, man: !!document.querySelector('link[rel=manifest]'),
          tag: (() => { const e = document.querySelector('#betaTag'); const r = e && e.getBoundingClientRect(); return !!e && r.width > 8 && r.height > 30 && getComputedStyle(e).pointerEvents === 'none'; })(), ver: document.querySelector('.t-ver').textContent, ctl: !!navigator.serviceWorker.controller})''')
        check(m0 == {'beta': False, 'on': True, 'pwa': True} and b0['beta'] and not b0['on'] and not b0['pwa'] and not b0['man'] and b0['tag'] and '베타' in b0['ver'],
              f'베타 빌드는 온라인 서버·앱 설치를 끄고 베타 띠를 보여 준다 {m0} {b0}')
        await bp.screenshot(path=str(OUT / '25_베타_로그인.png'))
        await bp.evaluate('() => { window.__game.noFork = true; }')   # 시험용 캐릭터(후반 저장)에 들어가면 뜨는 갈림길 창은 이 점검에서 끔
        await signup(bp, 'betatest', 'abcd', '베타용사')
        await bp.wait_for_timeout(6500)   # 저장(5초마다)과 본 게임 보관본 되돌리기(6초 뒤)를 기다림
        b1 = await bp.evaluate(r'''async () => {
          const keys = Object.keys(localStorage), ses = Object.keys(sessionStorage);
          const main = JSON.parse(localStorage.getItem('samhan-accounts-v1') || '{}');
          let cached = null;
          try { const ck = (await caches.keys()).find(k => k.startsWith('samhan-')), c = await caches.open(ck || 'samhan-none'), r = await c.match(new URL('../index.html', location.href).href); cached = r ? /\/\*BETA_BUILD\*\/(true|false)/.exec(await r.text())[1] : 'none'; } catch (e) { cached = 'err'; }
          const regs = (await navigator.serviceWorker.getRegistrations()).map(r => new URL(r.scope).pathname);
          return {beta: keys.filter(k => k.startsWith('beta-')).sort(), other: keys.filter(k => !k.startsWith('beta-')).sort(), otherV: Object.fromEntries(keys.filter(k => !k.startsWith('beta-')).sort().map(k => [k, localStorage.getItem(k)])), ses, mainMark: main.mark, mainAcc: Object.keys(main.accounts || {}), cached, regs, name: window.__game.S.name}; }''')
        check(b1['name'] == '베타용사' and any(k == 'beta-samhan-accounts-v1' for k in b1['beta']) and any(k.startswith('beta-samhan-hero-v1:betatest:') for k in b1['beta'])
              and 'samhan-accounts-v1' in b1['other'] and b1.pop('otherV') == mk0 and 'beta-samhan-dev' in b1['beta'] and b1['mainMark'] == 'main' and b1['mainAcc'] == [] and all(k.startswith('beta-') for k in b1['ses']),
              f'베타의 계정·캐릭터·설정은 모두 beta- 자리에 저장되고 본 게임 저장은 건드리지 않는다(본 게임이 둔 것은 글자 하나 안 바뀜) {b1}')
        check(b0['ctl'] and b1['cached'] == 'false' and b1['regs'] == ['/'], f'베타를 열어도 본 게임의 오프라인 보관본은 본 게임 그대로이고, 베타는 오프라인 도우미를 따로 등록하지 않는다 {b0["ctl"]} {b1["cached"]} {b1["regs"]}')
        await bp.screenshot(path=str(OUT / '25b_베타_플레이.png'))
        await bp.click('#charBtn'); await bp.click('#modal-btn-1')
        await bp.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
        check(await bp.is_visible('#cs-beta'), '베타의 캐릭터 고르기 창에 [시험용 캐릭터로 시작]이 있다')
        await bp.click('#cs-beta')
        await bp.wait_for_selector('#mTitle:has-text("시험용 캐릭터")')
        await bp.screenshot(path=str(OUT / '25c_베타_시험용캐릭터.png'))
        nsave = await bp.evaluate('() => document.querySelectorAll("#mBody [data-bi]").length')
        if nsave:
            for bi in range(nsave):
                await bp.click(f'#mBody [data-bi="{bi}"]')
                await bp.wait_for_function('() => window.__game.session && document.querySelector("#modal").hidden')
                await bp.wait_for_timeout(1500)
                bs = await bp.evaluate('''() => { const G = window.__game, S = G.S; G.update(0.05); G.render();
                  return {name: S.name, lv: S.level, w: S.world, q: S.quest.main, atk: G.ST.atk > 0, cut: !!G.cut, n: JSON.parse(localStorage.getItem('beta-samhan-accounts-v1')).accounts.betatest.chars.length}; }''')
                check(bs['lv'] > 1 and bs['atk'] and bs['n'] == 2 and bs['name'] != '베타용사' and bs['q'] >= 113, f'시험용 캐릭터 {bi + 1}번으로 바로 들어간다(이야기 진행도 그대로) {bs}')
                if bi == 0:
                    await bp.screenshot(path=str(OUT / '25d_베타_시험용_시작.png'))
                await bp.click('#charBtn'); await bp.click('#modal-btn-1')
                await bp.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
                await bp.evaluate('''() => { const cards = document.querySelectorAll('#mBody .char[data-cid]'); cards[cards.length - 1].click(); }''')   # 방금 만든 시험용 캐릭터를 지워 다음 것을 받을 자리를 냄
                await bp.click('#cs-del'); await bp.click('#modal-btn-1')
                await bp.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
                await bp.click('#cs-beta')
                await bp.wait_for_selector('#mTitle:has-text("시험용 캐릭터")')
        await ctxB.close()
        srv.shutdown()

        if '--sim' in sys.argv:
            ctx = await browser.new_context(viewport={'width': 844, 'height': 390})
            page = await ctx.new_page()
            watch(page, errors, 'sim ')
            for c in ['musa', 'jagaek', 'sulsa', 'doin']:
                await fresh(page)
                for line in (await page.evaluate(SIM, [30, c]))['log']:
                    print(line)
            await ctx.close()
        await browser.close()
    print(f'캡처: {OUT.relative_to(ROOT)}/')
    print('\n'.join(checks))
    print('오류:', json.dumps(errors, ensure_ascii=False, indent=1) if errors else '없음')
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(run_long() if '--long' in sys.argv else main())
