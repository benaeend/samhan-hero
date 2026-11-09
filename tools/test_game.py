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
  const [minutes, cls, opts = {}] = args;
  const G = window.__game;
  G.quiet = true;
  G.setClass(cls);
  if (opts.curve) Object.assign(G.CURVE, opts.curve);
  G.S.buyMode = 1;
  const dt = opts.dt || 0.05, steps = Math.round(minutes * 60 / dt);
  const marks = new Set((opts.marks || [5, 10, 20, 30]).map(m => Math.round(m * 60 / dt)));
  const log = [], first = {};
  let nextShop = 0, nextRetry = 60, raidPend = null, raidHold = [0, 0], goldIn = 0, gemIn = 0;
  const Wt = {atk:1, hp:1.3, crit:1.5, critDmg:1.8, aspd:1.5, regen:3};
  const mark = (k, t) => { if (!(k in first)) first[k] = Math.round(t / 60); };
  for (let i = 1; i <= steps; i++) {
    const g0 = G.S.gold, e0 = G.S.gems;
    G.update(dt); G.addTime(dt * 1000);
    goldIn += Math.max(0, G.S.gold - g0); gemIn += Math.max(0, G.S.gems - e0);
    const t = i * dt;
    if (t >= nextShop) {
      nextShop = t + 2;
      const e1 = G.S.gems; G.claimAll(); gemIn += Math.max(0, G.S.gems - e1);
      for (let k = 0; k < 20; k++) {
        const slot = G.S.refine.weapon.lv < G.REFINE_MAX && G.S.refine.weapon.lv <= G.S.refine.armor.lv + 3 ? 'weapon' : 'armor', lv = G.S.refine[slot].lv;
        if (lv >= G.REFINE_MAX || G.refineGold(lv) > G.S.gold * 0.25 || G.refineGems(lv) > G.S.gems * 0.2) break;
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
      for (let g = 0; g < 400; g++) {
        let best = null, bs = Infinity;
        for (const k of Object.keys(Wt)) { const b = G.buyInfo(k); if (!b.n) continue; const sc = b.cost * Wt[k]; if (sc < bs) { bs = sc; best = k; } }
        let bsk = null, sc2 = Infinity;
        for (const sk of G.SKILLS) { const lv = G.S.skills[sk.key]; if (lv && lv < sk.max) { const c = G.skillCost(sk, lv) * 2; if (c < sc2) { sc2 = c; bsk = sk.key; } } }
        if (bsk && sc2 < bs) { if (!G.upgradeSkill(bsk)) break; }
        else if (best) { if (!G.buyStat(best)) break; }
        else break;
      }
      while (G.S.gems >= 450) {
        if (G.S.rec.psum * 2 < G.S.rec.summons) { if (G.S.gems < 900) break; G.petSummon(10); }
        else G.summon(Math.random() < 0.5 ? 'weapon' : 'armor', 10);
      }
      for (let q = 0; q < 5; q++) G.claimTrial(q);
      if (!G.raid && (G.jobReady(1) || G.jobReady(2))) G.startJobTrial(G.S.job + 1);   // 전직 시험
      if (G.S.gems >= 2500 && G.AVATARS.some(a => a.src === 'box' && !G.S.av.own[a.k])) G.openAvatarBox();   // 남는 보석으로 꾸미기 상자
      if (G.rebirthReady()) {
        G.doRebirth();
        for (const k of ['atk', 'hp', 'luck', 'spd', 'eye']) for (let z = 0; z < 50; z++) if (!G.rebUp(k)) break;
      }
      G.mergeAll('weapon'); G.mergeAll('armor'); G.equipBest('weapon'); G.equipBest('armor');
      if (!G.raid && !G.bossActive) {
        // 실패하면 30분 동안은 그보다 낮은 레이드를 돌고, 첫 클리어 보상이 남은 레이드를 먼저 한다
        if (raidPend && G.S.rec.raids === raidPend[0]) raidHold = [raidPend[1], t + 1800];
        raidPend = null;
        let r = G.firstReadyRaid();
        if (r >= 0 && t < raidHold[1]) r = Math.min(r, raidHold[0] - 1);
        for (let j = r; j >= 0; j--) if (!G.S.raid.first[['', 'h', 'g'][G.S.world] + j]) { r = j; break; }
        if (r >= 0 && G.startRaid(r)) raidPend = [G.S.rec.raids, r];
      }
    }
    if (t >= nextRetry) { nextRetry = t + 60; G.S.autoBoss = true; }
    mark(G.S.world + ':' + G.S.stage, t); mark('L' + G.S.world + ':' + G.S.level, t); if (G.S.job) mark('J' + G.S.job, t); if (G.S.quest.hid) mark('H' + G.S.quest.hid, t);
    for (let q = 0; q <= G.S.quest.main; q++) mark('Q' + q, t);
    if (marks.has(i)) log.push(`${cls} ${Math.round(t / 60)}분: ${['이승', '저승', '천계'][G.S.world]} ${G.S.stage}단계, Lv ${G.S.level}, 전직 ${G.S.job}, 환생 ${G.S.reb.n}, 이야기 ${G.S.quest.main}/${G.MAIN_Q.length}, 히든 ${G.S.quest.hid}, 레이드 ${G.S.rec.raids}회, `
      + `재련 +${G.S.refine.weapon.lv}/+${G.S.refine.armor.lv}, 펫 Lv ${G.PET_TYPE_ORDER.map(pt => { const pi = G.eqPet(pt); return pi < 0 ? '-' : G.S.pets.lv[pi]; }).join('/')}, `
      + `번 엽전 ${G.fmt(goldIn)}·보석 ${G.fmt(gemIn)}`);
  }
  return {log, first};
}
"""

# --long: 이정표(처음 닿은 시각) 표
LONG_S0 = [31, 51, 61, 71, 81, 86, 91, 94, 97, 101]
LONG_S1 = [11, 31, 51, 71, 81, 91, 97]
LONG_S2 = [11, 16, 31, 46, 61, 76, 86, 91]
LONG_L = [('L0', 50), ('L0', 100), ('L1', 100), ('L1', 200), ('L2', 100), ('L2', 200), ('L2', 240)]
LONG_Q = [17, 42, 43, 60, 86, 87, 100, 110, 112, 113]


def long_table(cls, first):
    h = lambda m: '-' if m is None else (f'{m / 60:.1f}h' if m >= 60 else f'{m}m')
    print(f'[{cls}] 이승 ' + ' '.join(f'{x}:{h(first.get(f"0:{x}"))}' for x in LONG_S0))
    print(f'        저승 ' + ' '.join(f'{x}:{h(first.get(f"1:{x}"))}' for x in LONG_S1))
    print(f'        천계 ' + ' '.join(f'{x}:{h(first.get(f"2:{x}"))}' for x in LONG_S2))
    print(f'        전직 1차:{h(first.get("J1"))} 2차:{h(first.get("J2"))} · 히든 시작:{h(first.get("H1"))}')
    print('        레벨 ' + ' '.join(f'{ {"L0": "이승", "L1": "저승", "L2": "천계"}[k]}{v}:{h(first.get(f"{k}:{v}"))}' for k, v in LONG_L))
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
    marks = [m for m in (60, 240, 720, 1440, 2880, 4320, 5760, 7200, 8640, 10080, 11520, 12960) if m <= hours * 60]
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
        ctx = await browser.new_context(viewport={'width': 390, 'height': 800}, device_scale_factor=2)
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
        await page.evaluate("""() => { const G = window.__game; G.S.gold = 1e7; G.S.gems = 5000; G.S.level = 32; G.S.up.atk = 60; G.S.up.hp = 60;
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
        await page.click('#tab-raid')
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(OUT / '8_레이드목록.png'))
        await page.click('#raid-2 .btn')
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
          for (let i = 0; i < 3000 && G.raid; i++) G.update(0.05);
          const res = {why, ok, gold: G.S.gold > g0, done: G.S.tb.normal === G.tbWindow().id};
          delete G.REG.accounts.friend1; return res; }""")
        check(tb['ok'] and tb['gold'] and tb['done'], f'타임 보스: 2명 이상이면 도전하고 엽전을 받는다 {tb}')
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
          const r = G.openAvatarBox(); G.equipAvatar(r.a.k); return {got: !!r, n: G.AVATARS.filter(a => G.S.av.own[a.k]).length - n0, eq: G.S.av[r.a.type] === r.a.k}; }""")
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
        ctxA = await browser.new_context(viewport={'width': 390, 'height': 800})
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
        ctxB = await browser.new_context(viewport={'width': 390, 'height': 800})
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
        check(len(room['sent']) == 1 and room['sent'][0][1]['t'] == '같이 레이드 가요', f'claude.ai에서는 채팅이 다른 사람에게 나간다 {room["sent"]}')
        check('바람돌이' in room['html'] and '&lt;b&gt;' in room['html'], '다른 사람의 채팅이 들어오고, 글자로만 보인다')
        await pb.screenshot(path=str(OUT / '21_채팅_여럿.png'))
        await ctxB.close()

        # 9) 예전(계정 없던 때) 저장을 새 캐릭터로 이어받기
        ctxC = await browser.new_context(viewport={'width': 390, 'height': 800})
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
        ctxP = await browser.new_context(viewport={'width': 390, 'height': 800}, device_scale_factor=2)
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
        check(info['pwa'] and info['sw'] and info['name'] == '삼한 용사 키우기' and info['display'] == 'standalone'
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
            ctx = await browser.new_context(viewport={'width': 390, 'height': 800})
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
