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
  if (opts.late) Object.assign(G.LATE_K, opts.late);
  if (opts.load) { Object.assign(G.S, G.mergeState(JSON.parse(opts.load)));   // 예전 저장도 새 칸을 채워서
    G.S.cls = cls; if (G.S.world >= 3) G.refineInherit(); G.refreshStats(); G.setStage(G.S.stage); }   // 저장 시점부터 이어서
  G.S.buyMode = 1;
  const dt = opts.dt || 0.05, steps = Math.round(minutes * 60 / dt);
  const marks = new Set((opts.marks || [5, 10, 20, 30]).map(m => Math.round(m * 60 / dt)));
  const log = [], first = {}, snaps = {};
  let jobPend = null, jobHold = 0, nextShop = 0, nextRetry = 60, raidPend = null, raidHold = [0, 0], goldIn = 0, gemIn = 0;
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
      { const fb = G.formBest(); if (fb && G.S.form.eq !== fb) G.S.form.eq = fb; }   // 변신: 가장 센 것을 착용(보스·레이드에서 자동으로 한 번)
      for (const sl of ['weapon', 'armor']) G.ascend(sl);   // 신화·태초 각성(되면 바로)
      { const keepG = ['weapon', 'armor'].reduce((a, sl) => { const N = G.ascNeed(sl); return a + (!N.max && N.world ? N.A.grudge : 0); }, 0);   // 결이야기: 각성에 쓸 원한 조각은 남기고 낮은 마디부터
        const so = G.SOULS.filter(x => G.S.soul.own[x.k] && G.soulBond(x.k) < 3).sort((a, b) => G.soulBond(a.k) - G.soulBond(b.k) || b.g - a.g);
        for (const x of so) { if (G.S.grudge - [10, 30, 60][G.soulBond(x.k)] < keepG || !G.bondUp(x.k)) break; } }
      for (let g = 0; g < 400; g++) {
        let best = null, bs = Infinity;
        for (const k of Object.keys(Wt)) { const b = G.buyInfo(k); if (!b.n) continue; const sc = b.cost * Wt[k]; if (sc < bs) { bs = sc; best = k; } }
        let bsk = null, sc2 = Infinity;
        G.SKILLS.forEach((sk, i) => { const lv = G.skLv(i); if (lv && G.skIn(i) && lv < G.skCap(i)) { const c = G.skillCost(sk, lv) * 2; if (c < sc2) { sc2 = c; bsk = sk.key; } } });   // 전투 칸에 낀 기술만, 최대 레벨까지
        if (bsk && sc2 < bs) { if (!G.upgradeSkill(bsk)) break; }
        else if (best) { if (!G.buyStat(best)) break; }
        else break;
      }
      while (G.S.gems >= 450 + 400) {   // 재련·조합에 쓸 보석은 남겨 둔다
        if (G.S.rec.psum * 2 < G.S.rec.summons) { if (G.S.gems < 900) break; G.petSummon(10); }
        else G.summon(Math.random() < 0.5 ? 'weapon' : 'armor', 10);
      }
      for (let q = 0; q < 5; q++) G.claimTrial(q);
      if (jobPend && !G.raid) { if (G.S.job < jobPend[0]) { jobHold = t + 1200; first['JF' + jobPend[0]] = (first['JF' + jobPend[0]] || 0) + 1; } jobPend = null; }   // 전직 시험에 지면 20분 뒤에 다시
      if (!G.raid && t >= jobHold && (G.jobReady(1) || G.jobReady(2) || G.jobReady(3) || G.jobReady(4)) && G.startJobTrial(G.S.job + 1)) jobPend = [G.S.job + 1];
      if (G.crossReady()) G.doCross();   // 2부: 바다 건너 부상으로
      if (G.S.gems >= 6000 && G.AVATARS.some(a => a.src === 'box' && !G.S.av.own[a.k])) G.openAvatarBox();   // 남는 보석으로 꾸미기 상자
      G.buyShop('gift');
      if (G.S.inv.potion < 20) { const pp = G.SHOP.find(x => x.id === 'potion').price(); if (pp < G.S.gold * 0.05) G.buyShop('potion'); }
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
        for (let j = r; j >= 0; j--) if (!G.S.raid.first[['', 'h', 'g', 'b', 'k'][G.S.world] + j]) { r = j; break; }
        if (r >= 0 && G.startRaid(r)) raidPend = [G.S.rec.raids, r];
      }
    }
    if (t >= nextRetry) { nextRetry = t + 60; G.S.autoBoss = true; }
    mark(G.S.world + ':' + G.S.stage, t); mark('L' + G.S.world + ':' + G.S.level, t); if (G.S.job) mark('J' + G.S.job, t); for (const k of ['w', 'a', 'n']) if (G.S.craft[k].t) mark('C' + k + G.S.craft[k].t, t); if (G.S.quest.hid) mark('H' + G.S.quest.hid, t);
    for (let q = 0; q <= G.S.quest.main; q++) mark('Q' + q, t);
    if (opts.snaps && G.S.world === 3 && !('cross' in snaps)) snaps.cross = JSON.stringify(G.S);
    if (opts.snapQ && !('q' in snaps) && G.S.quest.main >= opts.snapQ && !G.raid) snaps.q = JSON.stringify(G.S);   // 이야기 n번째에 닿은 저장(다음 부 시뮬 출발점)
    if (opts.snaps) { const mm = Math.round(t / 60); if (opts.snaps.includes(mm) && !(mm in snaps) && !G.raid) snaps[mm] = JSON.stringify(G.S); }
    if (marks.has(i)) log.push(`${cls} ${Math.round(t / 60)}분: ${['이승', '저승', '천계', '부상', '곤륜'][G.S.world]} ${G.S.stage}단계, Lv ${G.S.level}, 전직 ${G.S.job}, 환생 ${G.S.reb.n}, 이야기 ${G.S.quest.main}/${G.MAIN_Q.length}, 히든 ${G.S.quest.hid}, 레이드 ${G.S.rec.raids}회, `
      + `재련 +${G.S.refine.weapon.lv}/+${G.S.refine.armor.lv}, 펫 Lv ${G.PET_TYPE_ORDER.map(pt => { const pi = G.eqPet(pt); return pi < 0 ? '-' : G.S.pets.lv[pi]; }).join('/')}, `
      + `번 엽전 ${G.fmt(goldIn)}·보석 ${G.fmt(gemIn)}`);
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
        await page.click('#lg-tab-signup')
        await page.fill('#lg-id', 'tester')
        await page.fill('#lg-pw', '1234')
        await page.fill('#lg-pw2', '9999')
        await page.click('#modal-btn-0')
        check('달라요' in await page.inner_text('#lg-err'), '비밀번호 확인이 다르면 막는다')
        await page.fill('#lg-pw2', '1234')
        await page.click('#modal-btn-0')
        await page.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
        await page.click('#modal-btn-0')
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
        await page.click('#tab-quest')
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
        await page.click('#tab-rec')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '12_정보.png'), full_page=True)

        await page.evaluate('() => window.__game.showNotes()')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '22_업데이트소식.png'))
        await page.click('#modal-btn-0')

        # 4-2) 상점·물약·부적
        await page.click('#tab-shop')
        await page.click('.shop-cats [data-c="pack"]')
        await page.click('#shb-gift')
        await page.click('.shop-cats [data-c="potion"]')
        await page.click('#shb-potion')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '16_상점.png'))
        inv = await page.evaluate('() => window.__game.S.inv')
        check(inv['potion'] == 15, f'오늘의 선물·인삼 탕약 10개를 산다 {inv}')
        await page.click('.shop-cats [data-c="charm"]')
        await page.click('#shb-b_atk')
        st = await page.evaluate('() => ({buff: window.__game.S.buff.atk})')
        check(st['buff'] > 590, f'범 부적을 사면 10분 동안 공격력이 오른다 {st}')
        drank = await page.evaluate('''() => { const G = window.__game; const n = G.S.inv.potion; G.hero.hp = G.ST.maxHp * 0.1; G.update(0.05);
          return {before: n, after: G.S.inv.potion, hp: G.hero.hp / G.ST.maxHp}; }''')
        check(drank['after'] == drank['before'] - 1 and drank['hp'] > 0.4, f'체력이 낮으면 탕약을 저절로 마신다 {drank}')
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

        # 5) 다시 열면 로그인 유지 → 로그아웃 → 틀린/맞는 비밀번호
        await page.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
        await page.goto(URL)
        await page.wait_for_function('() => window.__game.session', timeout=8000)
        await page.evaluate("() => { window.__game.gateOff = true; window.__game.noFork = true; }")
        check(await page.evaluate('() => window.__game.S.name') == '홍길동', '다시 열면 같은 캐릭터로 이어진다')
        check(await page.evaluate('() => window.__game.S.refine.weapon.lv') >= 3, '재련 결과가 저장된다')
        await page.click('#tab-rec'); await page.click('#outBtn'); await page.click('#modal-btn-1')
        await page.fill('#lg-id', 'tester'); await page.fill('#lg-pw', '0000'); await page.click('#modal-btn-0')
        await page.wait_for_timeout(600)
        check('맞지 않아요' in await page.inner_text('#lg-err'), '틀린 비밀번호는 막는다')
        await page.fill('#lg-pw', '1234'); await page.click('#modal-btn-0')
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
        await page.click('#tab-quest'); await page.wait_for_timeout(300)
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
        check(jm['title'] == '여정 지도' and jm['nodes'] == 34 and jm['now'] and jm['hero'] and jm['painted'] == jm['cvs'] and jm['tags'] >= 30
              and '천계' in jinfo and '구름 계단' in jinfo, f'여정 지도: 땅 29곳·지금 위치·이야기 장 표시, 땅을 누르면 정보 {jm} / {jinfo[:40]}')
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
          const atk = [0, 1, 2, 3, 4, 5, 6, 7].filter(i => G.skDef(i).atk).length; return {before, after, atk}; }""")
        check(dn['before'] == 0 and dn['after'] > 0 and dn['atk'] == 3, f'도인은 공격 기술이 3개이고, 세 번째는 환생해야 열린다 {dn}')
        sh = await page.evaluate("""() => { const G = window.__game; G.setClass('sulsa'); G.S.level = 120; G.unlockSkills(); G.skillCd.roar = 0; G.hero.dead = false; G.hero.hp = G.ST.maxHp; G.castNow(2);
          return {shield: G.hero.shield / G.ST.maxHp}; }""")
        check(sh['shield'] >= 0.399, f'술사의 마력 보호막이 최대 체력의 40% 이상을 막는다 {sh}')
        await page.click('#tab-skill'); await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '29_기술_직업특성.png'))
        cf = await page.evaluate("""() => { const G = window.__game, S = G.S; G.setClass('jagaek'); G.refreshStats();
          S.best.s0 = Math.max(S.best.s0, 60); const mk = 'm' + S.world; S.mat[mk] = 200; S.gems = 5000; S.gear.weapon.count[4] += 3; S.gear.weapon.count[8] += 4; S.gear.armor.count[4] += 3;
          const a0 = G.ST.atk, best = G.ENGR_BEST.jagaek.w;
          G.pickEngr('w', best); const t1 = G.craft('w') === true;
          G.craftLuck = 0.0001; const f = G.craft('w'); const fails = S.craft.w.f, mat1 = S.mat[mk];
          G.craftLuck = null; S.craft.w.f = 5; const ok = G.craft('w') === true;
          G.pickEngr('a', G.ENGR_BEST.jagaek.a); G.pickEngr('n', G.ENGR_BEST.jagaek.n); G.craft('a'); G.craft('n');
          G.refreshStats(); return {t1, f, fails, mat1, ok, t: S.craft.w.t, best, up: G.ST.atk / a0, harm: G.harmonyOn()}; }""")
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
          const ok = G.startDBoss(); const B = G.raid && G.raid.boss; if (B){ G.raid.info.fit = null; B.hp = 1; } for (let i = 0; i < 400 && G.raid; i++) G.update(0.05);
          const got = S.skin.inv.concat(Object.values(S.skin.eq)), parts = got.map(it => G.SKC[it.c].p);
          // 여러 날 흉내: 월~토는 그 부위, 일요일은 전설만
          const grades = [0, 0, 0, 0, 0], partOk = [];
          for (let k = 0; k < 300; k++){ const r = G.skinDropPart('belt', [0, 1, 2, 3, 4][k % 5]); grades[r.it.g]++; partOk.push(G.SKC[r.it.c].p === 'belt'); }
          const sunAll = G.skinDropPart('all', 4).it.g;
          Object.assign(S, JSON.parse(keep)); G.refreshStats(); G.quiet = false;
          return {day, part, loseOut: lose.out.length, gemsLose: gemsLose > 0, lose2: lose2.out.length, ok, won: S.dboss ? true : false, got: got.length, parts, sun: day === 0, allGrades: grades.every(n => n > 0), partOk: partOk.every(Boolean), sunAll}; }""")
        check(db['loseOut'] == 2 and db['gemsLose'] and db['lose2'] == 0 and db['ok'] and (db['sun'] or (db['got'] == 1 and db['parts'][0] == db['part'])) and db['allGrades'] and db['partOk'] and db['sunAll'] == 4,
              f'1일 보스: 참가 보상(하루 한 번)·이기면 오늘 부위 치장·모든 등급·일요일은 전설 {db}')

        # 6-4g2) 타임 보스·1일 보스 손맛: 공격은 방어 빼고 최대 체력의 %, 되받기는 기본 피해 FIT.ctr초 몫(기본 피해로는 안 셈), 막대는 거꾸로 안 참
        fh = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          if (G.raid){ G.raid.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05); }
          S.dboss = {day:'', n:0, paid:false, won:false}; S.buff.def = 600; G.refreshStats(); G.dbCheck();
          const ok = G.startDBoss(), R = G.raid, B = R.boss; let rise = 0, last = 1;
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
          const ok = G.startDBoss(), R = G.raid; R.info.day = '1999-1-1'; R.info.paid0 = false; const g0 = S.gems;
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
          const fx1 = G.formFx(G.FM.cheong).atk; S.world = 3; const fx3 = G.formFx(G.FM.cheong).atk, tg3 = G.formFx(G.FM.tengu).atk; S.world = 1;
          // 기술: 최대 레벨·6칸·연계
          S.job = 1; S.level = 100; const cap1 = G.skCap(0); S.job = 3; S.level = 200; S.world = 3; const cap3 = G.skCap(0); S.world = 1; S.job = 1; S.level = 120;
          S.skills.spin = 30; const lvEff = G.skLv(0); S.skills.spin = 5;
          G.unlockSkills(); S.skSetMan = false; S.skSet = []; G.skSetFix(); const set = S.skSet.slice();
          const t1 = G.skToggle(set[0]), full = S.skSet.length;
          S.skSetMan = true; S.skSet = [0, 1, 2, 3, 4, 5]; for (const k in G.skillCd) G.skillCd[k] = 0; G.hero.dead = false;
          G.hero.dead = false; S.mode = 'semi'; S.kills = G.FIELD.kills; G.startBoss(); const B3 = G.bossRef; if (B3){ B3.hp = B3.maxHp = 1e300; B3.atk = 0; } for (let i = 0; i < 30; i++) G.update(0.05); for (const k in G.skillCd) G.skillCd[k] = 0;
          const c0 = S.rec.combos || 0, k0 = G.castNow(2), k1 = G.castNow(3), combo = (S.rec.combos || 0) - c0, cm = G.comboMul();
          if (G.bossActive && B3){ B3.hp = 0.0001; for (let i = 0; i < 60 && G.bossActive; i++) G.update(0.05); }
          const out = {noHunt, ok1, up: +(a1 / a0).toFixed(3), again, ended, still, again2, autoOn, endAfter, fx1: +fx1.toFixed(3), fx3: +fx3.toFixed(3), tg3: +tg3.toFixed(3), cap1, cap3, lvEff, set, t1, full, combo, cm: +cm.toFixed(2), k0, k1};
          G.PAT.off = false; Object.assign(S, JSON.parse(keep)); G.refreshStats(); G.quiet = false; return out; }""")
        check(nf['noHunt'] and nf['ok1'] and nf['up'] > 1.3 and not nf['again'] and nf['ended'] and nf['still'] and not nf['again2'] and nf['autoOn'] and nf['endAfter']
              and abs(nf['fx1'] - 1.24 ** 1.5) < 0.01 and abs(nf['fx3'] - 1.0709 ** (1.5 * 0.6)) < 0.005 and nf['tg3'] > nf['fx3']
              and nf['cap1'] == 15 and nf['cap3'] == 25 and nf['lvEff'] == 15 and len(nf['set']) == 6 and nf['t1'] and nf['full'] == 5 and nf['combo'] == 1 and nf['cm'] == 1.35 and nf['k0'] and nf['k1'],
              f'변신: 사냥 중엔 못 쓰고 보스 싸움에서 한 번만 30초(자동이면 시작하자마자)·단계 값(부상에선 사신 60%)·기술 최대 레벨(1차 15·3차 25)·전투 칸 6개·연계 {nf}')
        aw = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true;
          if (G.raid){ G.raid.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05); }
          S.awaken = true; S.level = 60; S.raid.tk = 3; S.rec.rdpsK = 50; G.refreshStats(); const ok = G.startRaid(0), R = G.raid, B = R.boss; B.hp = B.maxHp = 1e300;
          const d0 = R.tbDone || 0, m0 = S.rec.maxHit || 0; let dmg = 0; const h0 = B.hp;
          G.castAwaken(); for (let i = 0; i < 20; i++) G.update(0.05);
          const want = G.realDps() * G.AWAKEN_SEC, used = R.awk.used; R.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05);
          Object.assign(S, JSON.parse(keep)); G.refreshStats(); G.quiet = false; return {ok, used, want: want > 0}; }""")
        check(aw['ok'] and aw['used'] and aw['want'], f'초각성은 한 싸움에 한 번, 내 실제 보스 피해 몇 초 몫으로 {aw}')

        # 6-5) 2부 부상: 바다 건너기(레벨 이어 감), 부상 레이드, 3차 전직, 장 제목 카드
        bs = await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true; G.closePage(); G.setClass('musa');
          if (S.world < 2){ S.world = 2; S.reb.n = 2; }
          S.level = 290; S.best.l2 = Math.max(S.best.l2, 290); Object.assign(S.up, {atk: 900, hp: 900, crit: 80, critDmg: 120, aspd: 60, regen: 40});
          S.refine.weapon.lv = 25; S.refine.weapon.t = 0; const effW0 = G.refineEff('weapon');
          const before = G.crossReady(); S.quest.main = G.CROSS_Q; const ready = G.crossReady(); const ok = G.doCross(); G.refreshStats();
          const after = {world: S.world, lv: S.level, st: S.stage, region: G.BUSANG_REGIONS[0].name};
          const inh = {t: S.refine.weapon.t, lv: S.refine.weapon.lv, keep: Math.abs(G.refineEff('weapon') - effW0) < 1e-6, cap: G.refineCap('armor')};
          S.best.s3 = 8; S.raid.tk = 3; const r0 = G.startRaid(0); const name = G.raid && G.raid.info.bossName;
          for (let i = 0; i < 4000 && G.raid; i++) G.update(0.05);
          S.level = 360; S.quest.main = G.MAIN_Q.findIndex(q => q.ch === 34);
          const jr = G.jobReady(3); const tr = G.startJobTrial(3); for (let i = 0; i < 4000 && G.raid; i++) G.update(0.05);
          return {before, ready, ok, after, inh, r0, name, b0: !!S.raid.first.b0, jr, tr, job: S.job, jobC: S.skills.jobC, cape: S.av.cape}; }""")
        check(bs['inh']['t'] == 1 and bs['inh']['lv'] == 15 and bs['inh']['keep'] and bs['inh']['cap'] == 25, f'2부: 바다를 건너면 무기·방어구가 계승되어 +15부터(효과는 그대로) {bs["inh"]}')
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
          S.best.s4 = 8; S.raid.tk = 3; const r0 = G.startRaid(0); const name = G.raid && G.raid.info.bossName;
          for (let i = 0; i < 4000 && G.raid; i++) G.update(0.05);
          S.level = G.JOB4_LV || 480; S.quest.main = G.MAIN_Q.findIndex(q => q.ch === 44);
          const jr = G.jobReady(4); const tr = G.startJobTrial(4); const steps = [];
          for (let i = 0; i < 12000 && (G.raid || S.job < 4); i++){ G.update(0.05); if (G.raid && !steps.includes(G.raid.info.bossName)) steps.push(G.raid.info.bossName); }
          return {ready, ok, after, r0, name, k0: !!S.raid.first.k0, jr, tr, steps, job: S.job, jobD: S.skills.jobD, cape: S.av.cape}; }""")
        check(kl['ready'] and kl['ok'] and kl['after']['world'] == 4 and kl['after']['lv'] == 400 and kl['after']['st'] == 1,
              f'3부: 부상 이야기를 마치면 곤륜으로 건너가고, 레벨은 그대로 단계만 1부터 {kl["after"]}')
        check(kl['r0'] and kl['k0'], f'3부: 곤륜 레이드(열 개의 해)를 토벌한다 {kl["name"]}')
        check(kl['jr'] and kl['tr'] and len(kl['steps']) == 3 and kl['job'] == 4 and kl['jobD'] >= 1 and kl['cape'] == 'j_musa_4',
              f'3부: 세 스승의 시험(세 판)을 넘으면 4차 전직(개천왕)과 10번째 기술 {kl}')

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
          S.craft.a.t = 2; S.gear.armor.count = Array(20).fill(0); S.gear.armor.count[8] = 9; S.gear.armor.seen[8] = true; S.equip.armor = -1;
          G.mergeAll('armor'); const afterMerge = have();
          S.gear.armor.count[8] = 9; S.gear.armor.count[9] = 0; S.equip.armor = 16; S.gear.armor.count[16] = 1; G.grindGear('armor', 3); const afterGrind = have();
          S.craft.a.t = 9; S.gear.armor.count[8] = 9; S.equip.armor = -1; G.mergeAll('armor'); const free = have();
          Object.assign(S, JSON.parse(keep)); G.refreshStats();
          return {afterMerge, afterGrind, free}; }""")
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
        check(ao['order'][:2] == ['roar', 'mark'] and 3 <= len(ao['order']) <= 7,
              f'자동 기술: 보스 앞에서 공격력 버프·약점을 먼저 쓰고 0.1초 간격으로 하나씩 쓴다 {ao}')
        # 6-8e) 숫돌 10+1·배럭 효과·만렙 경험치 모으기·단계 보스/레이드 이야기·레벨 문
        nw = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S); G.quiet = true; G.gateOff = false;
          S.gems = 1000; const w0 = S.inv.whet; G.buyShop('whet10'); const whet = S.inv.whet - w0, paid = 1000 - S.gems;
          const A = G.REG.accounts[G.session.acc], n0 = A.chars.length; G.refreshStats(); const atk0 = G.ST.atk, g0 = G.barrack().gain;
          A.chars.push({cid:'zz_test', name:'배럭', cls:'doin', level:400, cum:700, world:3}); G.refreshStats();
          const br = G.barrack(), atkUp = G.ST.atk / atk0; A.chars = A.chars.filter(c => c.cid !== 'zz_test'); G.refreshStats();
          S.world = 0; S.level = 100; S.exp = 0; S.expBank = 0; G.gainExp(G.expNeed(100) * 10);
          const bank = S.expBank; S.world = 1; S.level = 1; const up = G.useExpBank(); const bankAfter = S.expBank, lvAfter = S.level;
          S.world = 0; S.level = 1; S.quest.main = 0; const g1 = G.stageGate(), b1 = G.bossGate(25).ok, b2 = G.bossGate(3).ok;
          S.level = 5; const lvGate = !G.bossGate(15).ok && G.bossGate(15).why.includes('Lv');
          S.world = 1; S.level = 200; S.raid.first = {}; S.quest.main = G.MAIN_Q.findIndex(q => q.key === 'h0'); const rOpen = [G.raidUnlockedBase(), G.raidUnlocked()];
          S.quest.main = G.MAIN_Q.length + 3; const free = G.stageGate();
          Object.assign(S, JSON.parse(keep)); G.setStage(S.stage); G.refreshStats(); G.gateOff = true;
          return {whet, paid, n0, stat: br.stat, gain: br.gain - g0, atkUp: +atkUp.toFixed(3), bank: +bank.toFixed(2), up, bankAfter, lvAfter, g1, b1, b2, lvGate, rOpen, free: free === Infinity}; }""")
        check(nw['whet'] == 11 and nw['paid'] == 250, f'상점: 숫돌 10+1 묶음은 250보석에 11개 {nw}')
        check(nw['stat'] == 35 and abs(nw['atkUp'] - 1.35) < 0.02 and nw['gain'] >= 9, f'배럭 효과: 다른 캐릭터(누적 Lv700)가 있으면 공격력·체력 +35%, 경험치·엽전도 오른다 {nw}')
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
        check(np_['n'] == 29 and np_['none0'] and np_['some4'] >= 6 and np_['imgs'], f'부상·곤륜 펫: 1부 소환엔 안 나오고 곤륜에선 새 펫들이 나온다(그림도 그려짐) {np_}')
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
          let picked = false; if (m){ const mm = Object.assign({}, at(m.tx, m.ty)); mm.clientY -= 6 * G.scale; G.fieldClick(mm); picked = h.target === m; }
          S.mode = 'auto'; return {goal, mkMoved, fg, arrived, picked}; }""")
        check(tp['mkMoved'] and tp['fg'] and tp['arrived'] and tp['picked'], f'눌러서 움직이기: 장터에서 걸어가고, 사냥터 땅을 누르면 그 칸으로·몬스터를 누르면 그 몬스터를 {tp}')
        # 6-10) 신화 펫·환수: 1부엔 소환에 안 나오고, 부상에 가면 그 땅의 환수(이야기 환수는 빼고)가 소환에 나온다. 보물 동굴·신화 조각. 함께하는 싸움은 늘 자동 기술
        mp = await page.evaluate("""() => { const G = window.__game, S = G.S, w0 = S.world; G.quiet = true;
          S.world = 0; const pool0 = G.mythPetPool().length; S.world = 3; const pool3 = G.mythPetPool().map(i => G.PETS[i].name);
          S.gems = 1e7; G.petLuck = 400; const r = G.petSummon(1); G.petLuck = null; const got = G.PETS[r[0].i];
          const bk = G.PETS.findIndex(p => p.draw === 'baku'); S.pets.lv[bk] = 0; const gp = G.givePet('baku');
          S.vault = {day:'', n:0}; S.mythShard = 0; const v = G.startVault(); G.raid.boss.hp = 1e-9; for (let i = 0; i < 400 && G.raid; i++) G.update(0.05);
          const shard = S.mythShard; S.mythShard = 30; const cm = G.craftMyth('flute');
          S.mode = 'semi'; G.startFight({label:'시험', bossName:'시험 보스', type:'oni', color:'#c83a2a', region:0, party:3, ref:1, g:0}, G.raidParty({party:3, g:0, ref:1}), {hp:1e9, atk:0, aoe:0, time:5});
          const auto = G.coopFight() && G.skAuto(0) && G.skAuto(5); for (let i = 0; i < 200; i++) G.update(0.05); S.mode = 'auto';
          S.world = w0; return {pool0, pool3, got: got.g, gotName: got.name, gp, baku: S.pets.lv[bk], v, shard, cm: !!cm, shardLeft: S.mythShard, auto}; }""")
        check(mp['pool0'] == 0 and mp['pool3'] == ['뇌수', '아마비에'] and mp['got'] == 5 and mp['gp'] and mp['baku'] == 1,
              f'신화 펫: 1부엔 안 나오고, 부상에서는 그 땅의 환수가 소환에 나오며 이야기 환수(바쿠)는 이야기 보상으로 {mp}')
        check(mp['v'] and mp['shard'] >= 4 and mp['cm'] and mp['shardLeft'] == 0 and mp['auto'],
              f'보물 동굴: 이기면 신화 조각, 조각 30개로 신화 보물을 만들고, 함께하는 싸움은 반자동이어도 기술이 자동 {mp}')
        # 6-11) 기술 레벨업 미리보기·넋 부름·보스 손컨(붉은 칸·되받기·버팀·큰 살)
        so = await page.evaluate("""() => { const G = window.__game, S = G.S, keep = JSON.stringify(S), H = Object.assign({}, G.HAND); G.quiet = true;
          const g1 = G.skillGain(0, 1).g, gMax = G.SKILLS.every((sk, i) => G.skillGain(i, 5).g > 0);
          S.world = 0; S.soul = {own:{}, star:{}, eq:['', ''], pity:0}; const d0 = G.soulDrop('raid');
          G.setWorld(3); S.stage = 15; S.maxStage = 20; S.level = 320; S.job = 3; S.up.atk = 200; S.up.hp = 400; G.refreshStats();
          S.soul.pity = 39; const d1 = G.soulDrop('raid'); const k1 = d1 && d1.k; const d2 = G.giveSoul(k1, true);
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
        check(so['d0'] is None and so['k1'] and so['star'] == 1 and so['col'] and so['eq'], f'넋 부름: 1부엔 넋 구슬이 안 나오고, 2부에선 40번 천장·같은 넋은 별·주머니에 저절로 모심 {so}')
        check(so['lv'] == 2 and so['tA']['seen'] and not so['tA']['hit'] and so['tB']['hit'] and so['ctr'] == 'counter' and so['stun'] and so['grog'] and so['back'],
              f'보스 손컨: 붉은 칸(피하면 안 맞고 못 피하면 맞음)·되받기 단추·버팀을 깨면 휘청 {so}')
        check(so['wiping'] and so['low'] <= 0.5 and so['casted'], f'큰 살을 못 끊으면 체력이 크게 깎이고, 넋의 기운이 차면 넋이 나타나 돕는다 {so}')
        await page.evaluate("() => { const G = window.__game; G.quiet = false; G.enterMarket(); }")
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(OUT / '34_장터마을.png'))
        await page.evaluate("() => window.__game.leaveMarket()")
        await page.evaluate("() => { const G = window.__game; G.quiet = false; G.buildTab('gear'); }")
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
        await pp.click('#tab-rec')
        check(await pp.is_visible('#appBtn'), '[정보] 탭에 [앱으로 설치] 단추가 있다')
        await ctxP.close()
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
