"""게임 플레이 매뉴얼 PDF 만들기: 빌드된 index.html 화면을 직접 찍어서 설명과 함께 docs/manual.pdf로 묶는다.

필요: pip install playwright (tools/test_game.py와 같음)
사용: python3 tools/make_manual.py   → docs/manual.pdf (캡처는 tools/out/manual/)
게임 수치를 바꾸면 아래 본문(특히 '진행 시간표')도 함께 고친다.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as tg  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

ROOT = tg.ROOT
SHOTS = ROOT / 'tools' / 'out' / 'manual'
PDF = ROOT / 'docs' / 'manual.pdf'
FONTS = ROOT / 'tools' / 'fonts'

# 중반 캐릭터처럼 꾸며 두기(화면 캡처용)
MIDGAME = r"""() => { const G = window.__game, S = G.S;
  G.quiet = true;
  S.level = 58; S.exp = 0; S.stage = 47; S.maxStage = 47; S.best.s0 = 47; S.best.l0 = 58; S.kills = 6;
  S.gold = 3e6; S.gems = 20000;
  Object.assign(S.up, {atk: 70, hp: 66, crit: 24, critDmg: 20, aspd: 14, regen: 10});
  Object.assign(S.skills, {spin: 9, bolt: 6, roar: 4, meteor: 3});
  for (let k = 0; k < 6; k++) { G.summon('weapon', 10); G.summon('armor', 10); }
  G.mergeAll('weapon'); G.mergeAll('armor'); G.equipBest('weapon'); G.equipBest('armor');
  for (let k = 0; k < 4; k++) G.petSummon(10);
  for (const pt of G.PET_TYPE_ORDER) { G.petEquipBest(pt); const pi = G.eqPet(pt); if (pi >= 0) for (let j = 0; j < 8; j++) G.petUpgrade(pi); }
  S.refine.weapon.lv = 12; S.refine.armor.lv = 9; S.refine.weapon.drops = 1;
  S.best.s0 = Math.max(S.best.s0, 55); S.mat.m0 = 48; S.gear.weapon.count[8] += 2;
  G.pickEngr('w', 'vital'); G.craftLuck = 100; S.gear.weapon.count[4] += 2; S.mat.m0 += 20; G.craft('w'); G.craftLuck = null; S.mat.m0 = 48;
  G.pickEngr('n', 'magic'); S.gems += 150; S.mat.m0 += 20; G.craft('n'); S.mat.m0 = 48; G.pickEngr('a', 'wall');
  G.dropMyth(20, 'sword'); G.dropMyth(18, 'bell');
  G.giveAcc('ring', 2); G.giveAcc('ear', 1);
  S.form.own.jujak = true; S.form.eq = 'jujak';
  S.quest.tut = 99; S.quest.main = 15;
  S.gems = 4200; S.gold = 2.4e6;
  G.setStage(47); G.refreshStats(); G.hero.hp = G.ST.maxHp;
  G.quiet = false; }"""


async def capture(page):
    SHOTS.mkdir(parents=True, exist_ok=True)

    async def shot(name, wait=400):
        await page.wait_for_timeout(wait)
        await page.screenshot(path=str(SHOTS / f'{name}.png'))

    async def tab(t, name, seg=None):
        # 이미 열린 메뉴를 다시 누르면 닫히므로, 열려 있지 않을 때만 누른다
        if not await page.evaluate(f"() => !document.querySelector('#page').hidden && document.querySelector('#tab-{t}').getAttribute('aria-selected') === 'true'"):
            if t in ('quest', 'shop', 'rec', 'bag', 'tower', 'pvp') and await page.is_hidden('#moreMenu'):
                await page.click('#tab-more')   # 2026-11 (41): 퀘스트·상점·정보·가방·탑·결투는 [더보기] 안
            await page.click(f'#tab-{t}')
        if seg:
            await page.wait_for_timeout(150)
            await page.click(seg)
        await shot(name)

    await tg.fresh(page)
    await shot('title', 1500)
    await page.click('#lg-tab-signup')
    await page.fill('#lg-id', 'haesol')
    await page.fill('#lg-pw', 'samhan1')
    await page.fill('#lg-pw2', 'samhan1')
    await shot('signup', 200)
    await page.click('#modal-btn-0')
    await page.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
    await page.click('#modal-btn-0')
    await page.wait_for_selector('#cc-name')
    await page.fill('#cc-name', '해솔')
    await page.click('#cc-sulsa')
    await shot('create', 300)
    await page.click('#modal-btn-1')
    await page.wait_for_function('() => window.__game.session && document.querySelector("#modal").hidden')
    await shot('prologue', 4200)
    await tg.skip_cut(page, 200)
    await shot('tutorial', 2500)

    await page.evaluate(MIDGAME)
    await page.evaluate("""() => { const G = window.__game; G.quiet = true; G.grantJob(1); for (const k of ['c_seolbim', 'p_red', 'q_crown', 'q_ribbon']) G.giveAvatar(k, true);
      G.equipAvatar('q_crown'); G.S.gems = 4200; G.quiet = false; }""")
    await shot('play', 3500)
    await page.evaluate("() => window.__game.openMap()")
    await shot('map', 2500)
    await page.evaluate("() => window.__game.closePage()")
    await tab('grow', 'grow')
    await tab('skill', 'skill')
    await tab('gear', 'gear')
    await tab('gear', 'refine', '#seg-refine')
    await page.evaluate("() => window.__game.buildTab('gear')"); await page.wait_for_timeout(150); await page.click('#seg-craft')
    await page.evaluate("() => { document.querySelector('#panel').scrollTop = 330; }")
    await shot('craft')
    await page.evaluate("() => { document.querySelector('#panel').scrollTop = 0; }")
    await tab('gear', 'myth', '#seg-myth')
    await tab('gear', 'acc', '#seg-acc')
    await tab('gear', 'form', '#seg-form')
    await tab('gear', 'avatar', '#seg-av')
    await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true; S.bag = []; G.bagAdd({t:'acc', k:'ring', g:1, p:20}, true); G.bagAdd({t:'acc', k:'ear', g:2, p:36}, true);
      G.bagAdd({t:'myth', k:'pearl', p:18}, true); G.bagAdd({t:'acc', k:'brace', g:3, p:70}, true); G.quiet = false; }""")
    await tab('bag', 'bag')
    await page.evaluate("() => { window.__game.closePage(); window.__game.enterMarket(); }")
    await page.evaluate("""() => { const G = window.__game; for (const [i, n, c, x, y] of [[1, '바람돌이', 'musa', 11, 13], [2, '달빛술사', 'sulsa', 17, 14], [3, '솔바람', 'doin', 15, 9]])
      G.mkRecv({peer:'m' + i, data:{n, c, l:{outfit:'auto', hair:'#241c26', hat:'class', skin:0}, ag:2, wg:3, j:1, x, y}}); }""")
    await shot('market', 2200)
    await page.evaluate("() => { window.__game.buildTab('market'); }")
    await page.wait_for_timeout(200); await page.click('#mk-npc')
    await shot('marketnpc')
    await page.evaluate("() => { const G = window.__game; G.closePage(); G.leaveMarket(); }")
    await tab('grow', 'job', '#gv-job')
    await tab('pet', 'pet')
    await tab('quest', 'quest')
    await tab('raid', 'raid')
    await tab('shop', 'shop')
    await tab('rec', 'rec')
    await page.evaluate("() => window.__game.closePage()")
    await page.click('#chatBtn')
    await page.fill('#chatInput', '안녕하세요! 오늘도 사냥 ㅎㅎ')
    await page.press('#chatInput', 'Enter')
    await shot('chat', 1200)
    await page.click('#chatClose')

    # 이야기 연출
    await page.evaluate("() => { const G = window.__game, q = G.MAIN_Q[14]; G.playCut([q.c], {title: '3장 · ' + q.t}); }")
    await shot('cut', 3200)
    await tg.skip_cut(page, 100)

    # 레이드 전투
    await page.evaluate("() => { const G = window.__game; G.quiet = true; G.startRaid(G.firstReadyRaid()); }")
    await page.evaluate("() => window.__game.closePage()")
    await shot('raidfight', 3500)
    await page.evaluate("() => { const G = window.__game; for (let i = 0; i < 4000 && G.raid; i++) G.update(0.05); }")

    # 환생 화면
    await page.evaluate("""() => { const G = window.__game, S = G.S;
      S.level = 100; S.stage = 101; S.maxStage = 101; S.best.s0 = 101; S.best.l0 = 100; S.refine.weapon.lv = 25; S.quest.trials = [true, true, true, false, true];
      S.quest.main = 42; G.refreshStats(); }""")
    await page.evaluate("() => window.__game.buildTab('grow')")
    await page.wait_for_timeout(150)
    await page.click('#gv-reb')
    await shot('rebirth')
    await page.evaluate("() => { const G = window.__game; G.S.quest.trials = [true, true, true, true, true]; G.doRebirth(); for (let z = 0; z < 8; z++) G.rebUp('atk'); for (let z = 0; z < 5; z++) G.rebUp('hp'); }")
    await page.evaluate("() => window.__game.buildTab('grow')")
    await page.wait_for_timeout(150)
    await page.click('#gv-reb')
    await shot('rebirth2')

    # 저승
    await page.evaluate("""() => { const G = window.__game, S = G.S;
      S.level = 64; S.best.l1 = 64; Object.assign(S.up, {atk: 90, hp: 88, crit: 30, critDmg: 30, aspd: 20, regen: 12});
      S.form.own.cheong = true; S.form.eq = 'cheong'; S.awaken = true; S.quest.main = 49;
      G.setStage(47); G.refreshStats(); G.hero.hp = G.ST.maxHp; }""")
    await page.evaluate("() => window.__game.closePage()")
    await shot('hell', 3500)

    # 천계(신과의 전쟁)
    await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true;
      S.level = 200; S.best.l1 = 200; S.quest.main = G.HELL_END_Q; G.doRebirth(); G.grantJob(2); G.equipAvatar('c_seolbim');
      S.level = 95; Object.assign(S.up, {atk: 160, hp: 150, crit: 40, critDmg: 40, aspd: 30, regen: 15}); S.quest.main = 98;
      G.setStage(52); G.refreshStats(); G.hero.hp = G.ST.maxHp; G.quiet = false; }""")
    await tg.skip_cut(page, 200)
    await page.evaluate("() => window.__game.closePage()")
    await shot('heaven', 3500)
    await page.evaluate("() => { const G = window.__game; G.quiet = true; G.S.raid.tk = 3; G.startRaid(2); }")
    await page.evaluate("() => window.__game.closePage()")
    await shot('godraid', 3000)
    await page.evaluate("() => { const G = window.__game; for (let i = 0; i < 4000 && G.raid; i++) G.update(0.05); G.quiet = false; }")

    # 타임 보스: 이 기기의 다른 계정 캐릭터가 함께 싸운다
    await page.evaluate("""() => { const G = window.__game;
      G.REG.accounts.friend1 = {salt: 'x', hash: 'p:x', t: 1, chars: [{cid: 'cf', name: '벗님', cls: 'doin', level: 80, maxStage: 80, look: {}, armorG: 3, weaponG: 3, ally: {dps: G.ST.atk * 3, maxHp: G.ST.maxHp}}]};
      const w = G.tbWindow(); if (!w.open) G.addTime(w.next - Date.now() + 60000); }""")
    await page.evaluate("() => window.__game.buildTab('raid')")
    await shot('timeboss', 600)
    await page.evaluate("() => { const G = window.__game; G.startTimeBoss('normal'); G.closePage(); }")
    await shot('timefight', 4000)
    await page.evaluate("() => { const G = window.__game; for (let i = 0; i < 4000 && G.raid; i++) G.update(0.05); delete G.REG.accounts.friend1; }")
    await page.wait_for_timeout(300)
    if await page.is_visible('#modal'):   # 타임 보스 결과 창은 닫고 다음 캡처로
        await page.click('#modal-btn-0')

    # 2부 부상: 바다 건너기 → 구라마산, 장 제목 카드
    await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true; G.closePage();
      S.level = 330; Object.assign(S.up, {atk: 260, hp: 250, crit: 60, critDmg: 70, aspd: 40, regen: 25}); S.quest.main = G.CROSS_Q; G.doCross();
      S.quest.main = G.MAIN_Q.findIndex(q => q.ch === 29); G.setStage(26); G.refreshStats(); G.hero.hp = G.ST.maxHp; G.quiet = false; }""")
    await shot('busang', 3500)
    await page.evaluate("() => window.__game.showChapterCard(29)")
    await shot('chcard', 700)

    # 보스 손컨·넋 부름(2부): 붉은 칸 예고, 넋이 나타나는 장면, [기술] → [넋 부름]
    await page.wait_for_timeout(3500)
    await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true; G.giveSoul('bari', true); G.giveSoul('haemosu', true); G.soulEquipBest();
      S.kills = 25; S.autoBoss = true; for (let i = 0; i < 12; i++) G.update(0.05);
      const B = G.patBoss(); if (!B) return; B.maxHp *= 50; B.hp = B.maxHp; G.HAND.dodge = 0; B.pat.cd = 0.01; B.pat.n = 0;
      for (let i = 0; i < 300; i++){ G.update(0.05); G.hero.hp = G.ST.maxHp; const T = B.pat.tel; if (T && T.kind === 'tiles' && T.t > T.T * 0.55) break; }
      G.quiet = false; }""")
    await shot('bosspat', 60)
    await page.evaluate("""() => { const G = window.__game, B = G.patBoss(); G.quiet = true; if (B && B.pat){ B.pat.tel = null; B.pat.cd = 99; } G.HAND.dodge = 0.8;
      G.soulG = 100; G.castSoul(true); for (let i = 0; i < 10; i++) G.update(0.05); G.quiet = false; }""")
    await shot('soulcast', 120)
    await page.evaluate("() => { const G = window.__game; G.buildTab('skill'); }")
    await page.wait_for_timeout(150); await page.click('#kv-soul')
    await shot('soulpage')
    await page.evaluate("() => { const G = window.__game; G.closePage(); G.quiet = true; const B = G.patBoss(); if (B) B.hp = 1; for (let i = 0; i < 200 && G.bossActive; i++) G.update(0.05); G.quiet = false; }")

    # 3부 곤륜: 서쪽 하늘로 건너기 → 서호, 수호신 화면
    await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true; G.closePage(); G.noFork = true;
      S.level = 445; Object.assign(S.up, {atk: 330, hp: 320, crit: 80, critDmg: 95, aspd: 55, regen: 35}); S.job = 3; S.quest.main = G.CROSS_Q4; G.doCross();
      S.quest.main = G.MAIN_Q.findIndex(q => q.ch === 37); G.setStage(28); S.maxStage = 28; S.reb.n = 2;
      for (let i = 0; i < 6; i++){ G.guardUp('seongju'); G.guardUp('jowang'); G.guardUp('samsin'); } G.guardSet('jowang');
      G.refreshStats(); G.hero.hp = G.ST.maxHp; G.quiet = false; }""")
    await shot('kunlun', 3500)
    await page.evaluate("() => { const G = window.__game; G.buildTab('grow'); }")
    await page.wait_for_timeout(200); await page.click('#gv-guard')
    await shot('guard')
    # 2026-11 (48): 계승(대장장이) — 곤륜에 막 건너온 화면처럼 지난 땅 재료·재련 계승 대상이 보이게
    await page.evaluate("""() => { const G = window.__game, S = G.S; G.closePage(); window.__inhKeep = JSON.stringify({mat:S.mat, refine:S.refine, inh:S.inh});
      S.mat.m0 = 38; S.mat.m1 = 112; S.refine.weapon = {lv:25, drops:0, t:1, base:287.5}; S.refine.armor = {lv:24, drops:0, t:1, base:287.5}; S.inh = {w:3}; G.refreshStats(); G.inhShow(); }""")
    await shot('inherit', 500)
    await page.evaluate("() => { const G = window.__game, S = G.S; G.inhClose(); Object.assign(S, JSON.parse(window.__inhKeep)); G.refreshStats(); }")
    # 2026-11 (46): 오장 영약(곤륜: 다섯 장을 몇 번씩 달이고, 신의 처방 하나를 남겨 둠)
    await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true; S.mat.m2 = (S.mat.m2 || 0) + 2000;
      for (const O of G.ORGANS) for (let i = 0; i < (O.k === 'sin' ? 2 : 5); i++){ S.gold += G.elCost(G.elSt(O.k)).gold; if (!G.elBrew(O.k)) break; G.elPick(G.elBestCard()); }
      S.gold += G.elCost(G.elSt('sin')).gold; G.elBrew('sin'); G.quiet = false; }""")
    await page.click('#gv-elix')
    await shot('elix')
    # 장별 치장 화면(곤륜 37장: 지나온 장 것 + 희귀·영웅 몇 개)
    await page.evaluate("""() => { const G = window.__game, S = G.S; G.closePage(); G.quiet = true;
      for (let i = 0; i < 24; i++) G.skinDrop(null, true); G.skGrade = 3; for (let i = 0; i < 4; i++) G.skinDrop(null, true); G.skGrade = null;
      G.refreshStats(); G.quiet = false; G.buildTab('gear'); }""")
    await page.wait_for_timeout(200); await page.click('#seg-skin')
    await page.evaluate("() => { const g = document.querySelector('.skgrid'); if (g) g.previousElementSibling.scrollIntoView({block:'start'}); }")
    await shot('skin')
    await page.evaluate("() => window.__game.closePage()")
    # 2026-11 (41)·(42): 세트·내 정보·천공의 탑·결투
    await page.evaluate("""() => { const G = window.__game, S = G.S; G.quiet = true; S.tower.best = 128; S.av.own.w_cloud = true; S.av.wing = 'w_cloud'; S.av.own.p_kunlun = true; S.av.cape = 'p_kunlun';
      S.form.own.hwang = true; S.form.eq = 'hwang'; S.mount.own.girin = true; S.mount.ride = 'girin'; S.asc = {weapon:1, armor:1}; G.refreshStats(); G.quiet = false; G.buildTab('gear'); }""")
    await page.wait_for_timeout(200); await page.click('#seg-set')
    await shot('setpage')
    await page.evaluate("() => { const G = window.__game; G.buildTab('me'); }")
    await shot('mepage', 600)
    await page.evaluate("() => { const G = window.__game; G.buildTab('tower'); }")
    await shot('towerpage', 700)
    await page.evaluate("() => { const G = window.__game; G.buildTab('pvp'); }")
    await shot('pvppage', 600)
    await page.evaluate("() => { const G = window.__game; G.closePage(); G.quiet = true; G.S.tower.n = 0; G.startTower(); for (let i = 0; i < 30; i++) G.update(0.05); G.quiet = false; }")
    await shot('towerfight', 900)
    await page.evaluate("() => { const G = window.__game; if (G.raid){ G.quiet = true; G.raid.time = 0; for (let i = 0; i < 100 && G.raid; i++) G.update(0.05); G.quiet = false; } G.closePage(); }")


def jpg(name):
    '''PDF가 너무 커지지 않게 캡처를 JPG로 바꿔 쓴다'''
    from PIL import Image
    src, dst = SHOTS / f'{name}.png', SHOTS / f'{name}.jpg'
    Image.open(src).convert('RGB').save(dst, quality=84)
    return dst.as_uri()


def img(name, cap=''):
    return f'<figure><img src="{jpg(name)}"><figcaption>{cap}</figcaption></figure>'


def sec(title, body, *figs, kicker=''):
    figs_html = ''.join(img(*f) for f in figs)
    k = f'<p class="kicker">{kicker}</p>' if kicker else ''
    wide = ' v' if len(figs) >= 3 else ''   # 그림이 3장이면 글 아래에 나란히
    return f'<section>{k}<h2>{title}</h2><div class="row{wide}"><div class="txt">{body}</div><div class="figs n{len(figs)}">{figs_html}</div></div></section>'


def html():
    f = lambda n: (FONTS / n).as_uri()
    css = f"""
@font-face{{font-family:P;src:url({f('Pretendard-Medium.woff2')});font-weight:500}}
@font-face{{font-family:P;src:url({f('Pretendard-Bold.woff2')});font-weight:700}}
@font-face{{font-family:P;src:url({f('Pretendard-ExtraBold.woff2')});font-weight:800}}
@page{{size:A4;margin:14mm 13mm 16mm}}
*{{box-sizing:border-box}}
body{{font-family:P,sans-serif;font-weight:500;color:#1d2433;font-size:10.2pt;line-height:1.62;margin:0;word-break:keep-all}}
h1{{font-size:30pt;font-weight:800;margin:0;letter-spacing:-.02em}}
h2{{font-size:15pt;font-weight:800;margin:0 0 6px;color:#0f1a2e;letter-spacing:-.01em}}
h3{{font-size:11pt;font-weight:800;margin:10px 0 2px;color:#7a4b00}}
p{{margin:4px 0}} ul{{margin:4px 0;padding-left:17px}} li{{margin:1px 0}}
b{{font-weight:800}}
.kicker{{font-size:8.5pt;font-weight:800;color:#b8860b;letter-spacing:.12em;margin:0 0 2px}}
section{{break-inside:avoid;padding:10px 0 14px;border-bottom:1px solid #e4e7ee}}
.row{{display:flex;flex-direction:column;gap:8px}}
.txt{{min-width:0}}
.figs{{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;width:100%}}
.figs.n0{{display:none}}
figure{{margin:0;width:118mm}}
.figs.n2 figure{{width:88mm}}
.figs.n3 figure{{width:58mm}}
figure img{{width:100%;border-radius:9px;border:1px solid #cfd5e1;box-shadow:0 2px 8px rgba(20,30,60,.12);display:block}}
figcaption{{font-size:8pt;color:#5a6378;text-align:center;margin-top:3px}}
table{{border-collapse:collapse;width:100%;font-size:9pt;margin:6px 0}}
th,td{{border:1px solid #d5dae5;padding:3px 6px;text-align:left;vertical-align:top}}
th{{background:#f1f3f8;font-weight:800}}
.tip{{background:#fff8e1;border:1px solid #f0d58a;border-radius:8px;padding:6px 10px;margin:6px 0;font-size:9.4pt}}
.cover{{height:250mm;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;break-after:page;
  background:linear-gradient(180deg,#0e1424,#1f2b4a 60%,#3a2f2a);color:#fff;border-radius:14px}}
.cover img{{width:150mm;border-radius:14px;margin:18px 0;box-shadow:0 10px 40px rgba(0,0,0,.5)}}
.cover .sub{{color:#ffcc4d;font-weight:800;letter-spacing:.2em;font-size:10pt}}
.cover p{{color:#c9d1e4;margin:2px 0}}
.toc{{columns:2;font-size:10pt}}
.toc li{{margin:2px 0}}
"""
    S = []
    S.append(sec('이 게임은요', """
<p><b>삼한 용사 키우기</b>는 옛 한국 신화 속 세상을 지키는 <b>방치형 RPG</b>예요. 용사는 혼자서 알아서 사냥하고, 여러분은 틈틈이 들어와
능력치를 올리고 장비·펫을 키워 주면 돼요. 창을 닫아 두어도 최대 12시간까지 보상이 쌓여요.</p>
<ul><li><b>이야기</b>: 하늘 문에 금이 가 요괴가 내려왔어요. 길잡이 까치와 함께 고구려를 세운 주몽의 이야기(해모수·유화·금와왕·송양왕)를 따라가고,
환생해서 <b>저승</b>의 열 대왕(시왕)을 만나 사신(주작·청룡·백호·현무)을 구하고, 다시 하늘에 올라 <b>신과의 전쟁</b>을 끝내요. 모두 25장 113개.</li>
<li><b>세 세계</b>: 이승(레벨 100까지) → 환생 → 저승(레벨 200까지) → 마지막 환생 → 천계(레벨 300까지, 신과의 전쟁).</li>
<li><b>함께하기</b>: 레이드(나 + NPC 동료 3~10인), 3시간마다 나타나는 타임 보스(서버의 캐릭터 가운데 무작위 10명), 장터 거래, 채팅.</li></ul>
<div class="tip">주소: <b>benaeend.github.io/samhan-hero</b> · 휴대폰 홈 화면에 앱으로 설치할 수 있어요(아래 '앱으로 설치' 참고).</div>
<h3>차례</h3><ol class="toc"><li>시작하기·계정</li><li>화면 보기</li><li>수련·스테이지</li><li>기술·초각성기</li><li>장비·재련·조합 공방</li><li>신화 보물·장신구·변신</li><li>전직</li><li>아바타</li><li>펫</li><li>퀘스트·이야기</li><li>레이드</li><li>타임 보스</li><li>환생·저승</li><li>천계·신과의 전쟁</li><li>제2부 · 부상</li><li>상점·채팅·정보</li><li>진행 시간표·자주 묻는 질문</li></ol>
""", kicker='들어가며'))
    S.append(sec('시작하기 · 계정 만들기', """
<ul><li>첫 화면에서 <b>[회원가입]</b> → 아이디·비밀번호를 정해요. 비밀번호는 기기 안에 암호(해시)로만 저장돼요.</li>
<li>한 계정에 <b>캐릭터 6명</b>까지 만들 수 있어요. 이름은 이 기기 안에서 겹칠 수 없어요.</li>
<li><b>4부부터 시작</b>(물의 신화): 3부(45장)까지 마친 캐릭터가 계정에 있으면, 새 캐릭터를 만들 때 「4부부터 · 바로 건너기」를 고를 수 있어요(한 계정에 2번). 「지난 이야기」와 몸 풀기 싸움 넷, 넋 구슬·수호신·탈것 고르기를 마치면 레벨 500 · 4차 전직에 기본 한 벌과 「길손의 가호」를 받고 동해(46장)에서 시작해요. 1~3부의 이야기 보상은 받지 않아요.</li>
<li>오른쪽 위 <b>♪</b> 단추로 배경음악·효과음을 켜고 꺼요(국악풍 가야금·대금·장구 소리).</li></ul>
<h3>직업 6가지</h3>
<table><tr><th>직업</th><th>특징</th><th>무기</th></tr>
<tr><td>무사</td><td><b>균형</b> — 체력이 높고 받는 피해 -10%. 모든 기술을 고루 써요(근접)</td><td>검</td></tr>
<tr><td>자객</td><td><b>보스 특화</b> — 보스 피해 +30%, 몹 떼는 느려요. 공격 펫·장신구와 궁합이 좋아요(근접)</td><td>단검</td></tr>
<tr><td>술사</td><td><b>늦게 피는 꽃</b> — 처음엔 약하고 레벨이 오를수록 강해져요. 몸이 약해 보호막이 중요(원거리)</td><td>지팡이</td></tr>
<tr><td>도인</td><td><b>한 방</b> — 공격 기술 3개뿐, 준비 기술을 쌓아 가장 큰 한 방. 레이드에서 동료 치유(원거리)</td><td>부채</td></tr>
<tr><td>궁사</td><td><b>조준</b> — 가장 멀리(5칸) 쏘는 명궁. 제자리에 서 있을수록 조준이 차서 치명타 피해가 최대 +60%, 마나는 절반·체력은 낮음(물의 신화 새 직업)</td><td>활</td></tr>
<tr><td>창객</td><td><b>간격</b> — 긴 창으로 두 칸 밖에서 찌름. 두 칸 넘게 떨어진 적 +40%·붙은 적 -20%, 맞은 직후 되찌르기로 밀어냄(물의 신화 새 직업)</td><td>창</td></tr></table>
<p>꾸미기: 옷 색 11가지 · 머리색 · 피부 · 머리 장식(갓·머리띠·복면 등). 미리보기를 누르면 돌려 볼 수 있어요.</p>
""", ('title', '첫 화면'), ('create', '캐릭터 만들기'), kicker='1'))
    S.append(sec('프롤로그와 튜토리얼', """
<p>캐릭터를 처음 만들면 <b>1분짜리 프롤로그</b>가 나와요. 하늘 문에 금이 가고 요괴가 쏟아지는 이야기예요. 화면을 누르면 다음 대사로,
<b>[건너뛰기]</b>로 바로 넘어갈 수 있어요. [정보] → [이야기 다시 보기]에서 언제든 다시 볼 수 있어요.</p>
<p>이어서 <b>길잡이 까치</b>가 7단계 튜토리얼로 안내해요. 눌러야 할 곳이 반짝이고, 단계마다 보석을 줘요.</p>
""", ('prologue', '프롤로그'), ('tutorial', '튜토리얼'), kicker='1'))
    S.append(sec('화면 보기', """
<p>휴대폰을 <b>가로로</b> 들면 사냥 장면이 화면을 가득 채워요(세로로 들어도 할 수 있어요). PC에서는 창 크기에 맞춰 넓게 보여요.</p>
<ul><li><b>왼쪽 위</b>: 용사 얼굴 · 레벨 · 이름 · 직업 · 전투력, 체력·경험치 막대, 데리고 다니는 <b>펫 얼굴</b>(누르면 펫 화면). 그 아래 <b>지금 이야기 퀘스트</b>(누르면 퀘스트 화면, 다 하면 [보상 받기]).</li>
<li><b>위 가운데</b>: 지역과 단계(예: 도깨비 굴 5-7), 보스까지 남은 처치 수. 보스가 나오면 보스 체력과 남은 시간.</li>
<li><b>오른쪽 위</b>: 엽전·보석·쇳가루(2부부터 고삐 조각), <b>장터</b>·업데이트 소식·하는 법 단추. 그 아래 <b>미니맵</b>(사냥판과 용사·몬스터 점, 누르면 여정 지도). 부적을 쓰면 미니맵 아래 남은 시간이 보여요.</li>
<li><b>왼쪽 아래</b>: 말풍선(채팅)과 최근 소식. 용사 머리 위에는 이름표가 떠요.</li>
<li><b>캐릭터 바꾸기</b>: 오른쪽 위 아이콘 줄 맨 앞(사람과 화살표 모양)을 누르면, 한 번 묻고 저장한 뒤 캐릭터 고르기 화면으로 가요. [정보] → [캐릭터 바꾸기]도 같아요.</li>
<li>휴대폰 가로처럼 화면 높이가 낮으면 왼쪽 위 상태창·이야기 칸과 오른쪽 위 재화 줄이 <b>저절로 작아져요</b>(높이 500px 이상이면 그대로). 용사와 몬스터를 덜 가려요.</li>
<li><b>오른쪽 아래</b>: 기술 칸. 저절로 쓰고, <b>누르면 바로</b>, <b>길게 누르면 그 기술만 자동/수동</b>. 그 위 <b>[자동/반자동]</b>·<b>[보스 자동/수동]</b>·[속도] 단추.</li>
<li><b>[자동]</b>은 사냥도 기술도 알아서, <b>[반자동]</b>은 사냥은 알아서 하고 기술은 직접 눌러 써요. <b>[보스 자동]</b>은 몹을 다 잡으면 보스에게 알아서 도전하고(지면 45초 수련 뒤 다시 — 같은 보스에게 질 때마다 <b>도전 기운</b>으로 그 보스 체력이 5%씩, 최대 40% 줄어요), <b>[보스 수동]</b>은 오른쪽 아래 <b>큰 보스 단추</b>가 「도전!」으로 빛날 때 눌러야 보스가 나와요. 큰 보스 단추의 금빛 고리는 보스까지 남은 처치만큼 차오르고, 싸우는 중에는 보스 체력과 남은 시간을 보여 줘요.</li>
<li><b>장면 누르기</b>: 땅을 누르면 용사가 그 칸으로 걸어가요(금빛 마름모 표시). 몬스터를 누르면 그 몬스터부터 쳐요. [반자동]이면 도착한 자리에서 6초 동안 버티며 닿는 적만 치고, 그 뒤로는 다시 알아서 사냥해요.</li>
<li><b>아래 메뉴 9칸</b>: 수련 · 기술 · 장비 · 펫 · 퀘스트 · 레이드 · 상점 · 정보 · 가방. 누르면 장면 위에 <b>별도 화면</b>이 열리고, 같은 메뉴나 ✕로 닫아요. 빨간 점은 받을 보상이나 할 일이 있다는 뜻이에요. (세로로 들면 메뉴가 화면 아래, 기술 칸은 장면 아래에 놓여요)</li>
<li><b>이야기·레벨 문</b>: 단계 보스는 지금 이야기가 요구하는 단계 + 10단계까지, 단계마다 최소 레벨이 되면 도전할 수 있어요. 막히면 큰 보스 단추가 「잠김」으로 바뀌고 이유(이야기 진행 / 필요 레벨)를 알려 줘요. 그 세계 이야기의 단계 퀘스트를 다 지나면 끝까지 열려요.</li>
<li><b>만렙 경험치</b>: 만렙에서 버려지던 경험치를 모아 두었다가(경험치 막대에 「모음」) 환생·건너기 뒤 30%를 레벨로 돌려줘요(최대 30레벨분).</li>
<li>레벨업·재련·소환·조합을 하면 화면에 빛과 글자 연출이 나와요. 기술을 쓰면 바닥 마법진·충격파·빛기둥·유성과 큰 기술 이름이 떠요.</li></ul>
<h3>여정 지도</h3>
<p>오른쪽 위 <b>미니맵</b>(또는 [퀘스트] → 여정 지도)을 누르면 이승 → 저승 → 천계 → 부상 → (3부) 땅이 한 장의 길로 보여요. 깬 땅은 금테·✓, <b>지금 있는 땅</b>에는 내 용사가 서 있고, 앞으로 갈 땅은 어둡거나 자물쇠예요. 땅마다 그곳의 <b>이야기 장 표시</b>가 붙어 있고, 누르면 지역 보스·몬스터·레이드·내 기록이 나와요.</p>
""", ('play', '사냥 화면'), ('map', '여정 지도'), kicker='2'))
    S.append(sec('수련 · 스테이지', """
<p><b>[수련]</b>에서 엽전으로 능력치를 올려요: 공격력 · 체력 · 치명타 확률 · 치명타 피해 · 공격 속도 · 체력 회복. 치명타 확률은 <b>100%</b>까지 오르고, 넘친 만큼은 치명타 피해로 바뀌어요(1% → +2%).
×1 / ×10 / 최대 단추로 한 번에 여러 번 올릴 수 있고, <b>길게 누르면</b> 계속 올라가요.</p>
<p><b>[수련] → [수호신]</b>: 집과 마을을 지켜 준다는 옛 지킴이 신을 모셔요. 성주신(체력, 1차 전직 뒤) · 조왕신(공격력, 첫 환생 뒤) · 터주신(엽전, 두 번째 환생 뒤) · 삼신할미(경험치, 두 번째 환생 뒤) · 칠성신(치명타 피해, 곤륜).
엽전을 바쳐 Lv.20까지 올리고, <b>모신 하나</b>는 효과 전부·나머지는 30%만 받아요(조왕신 Lv.20을 모시면 공격력 +30%).</p>
<p><b>[수련] → [영약]</b>(부상부터): 간·심·비·폐·신 다섯 장기에 영약을 달여요(부상에서 간·심·비, 곤륜에서 폐·신). 장마다 효능 두 줄(0~5단계)이 있고, <b>달이기 7번</b>(엽전 + 지금 세계 재료)마다 <b>처방 세 장 가운데 하나</b>를 골라요 —
한 줄 +1 · 두 줄 모두 +1 · 운이 좋으면 +2 · 효능 바꾸기 · 기운 모으기(다음 처방 +1 더) · 약 식히기(횟수를 쓰지 않고 다시 받기). 횟수를 다 쓰면 굳고, 보석·원한 조각으로 처음부터 다시 달일 수 있어요.
효능 합계(최대 50)가 15·25·35·45·50이 되면 <b>오장 조화</b> 1~5단: 공격력·체력과 <b>경험치 +5~25%</b>. 레벨이 이야기를 막는 2부·3부에서 남는 엽전을 힘과 경험치로 바꾸는 곳이에요.</p>
<ul><li>몬스터를 잡으면 엽전·경험치, 가끔 <b>보석</b>(4.5% 확률로 1~2개)과 <b>조합 재료</b>를 얻어요.</li>
<li>새 단계의 <b>보스는 세게 때려요</b>. 체력·방어 펫·물약·보호막으로 버텨요. 같은 단계에서 더 강해지면 덜 아파요.</li>
<li>단계마다 몬스터 <b>25마리</b> → 보스. 사냥터에는 몹이 7마리부터 많게는 16마리까지 한꺼번에 나와요. 10단계마다 지역이 바뀌어요(마을 어귀 → 대나무 숲 → 바위 고개 → 안개 늪 → 도깨비 굴 → 백두 설원 → …).</li>
<li>각 지역의 <b>9번째 단계</b>는 <b>수문장</b>(서브 보스)이 지켜요. 수문장에게서만 장신구가 잘 떨어져요.</li>
<li>레벨 상한: 이승 <b>100</b>, 저승 <b>200</b>.</li></ul>
<div class="tip"><b>난이도 흐름</b>: 처음 50~60단계까지는 쭉쭉 올라가요. 이승 70단계 무렵부터 한 단계에 수십 분, 100단계 근처부터는
<b>한 단계에 1~2시간</b>, 저승 90단계를 넘으면 <b>2~4시간</b>씩 방치해야 넘을 수 있어요. 막히면 장비·재련·펫·레이드로 힘을 키워요.</div>
""", ('grow', '수련 탭'), kicker='3'))
    S.append(sec('기술 · 초각성기', """
<p>직업마다 기술 8개가 있어요. <b>Lv.5 · 12 · 25 · 40 · 60 · 80</b>에 하나씩, 그리고 <b>1차·2차 전직</b> 때 하나씩 열려요(도인의 6번째 칸은 <b>환생</b>하면). [기술]에서 엽전으로 강화하고, 맨 위에 <b>직업 특성</b>이 나와요. 칸마다 <b>다음 레벨</b>에 숫자가 어떻게 바뀌고 그 기술이 <b>몇 % 세지는지</b> 함께 보여 줘요. 예: 「피해 220% → 242% (+22%p) · 기술 힘 10% 세짐」은 220%의 10%인 22%p가 더해진다는 뜻이에요. 3·4차 전직 기술은 직업마다 보스 피해가 고르게 나오도록 맞춰 두었어요.</p>
<table><tr><th>칸</th><th>무사</th><th>자객</th><th>술사</th><th>도인</th></tr>
<tr><td>1</td><td>회오리 베기</td><td>그림자 베기</td><td>불꽃 고리</td><td><b>천벌 부적</b>(공격)</td></tr>
<tr><td>2</td><td>일섬</td><td>급소 찌르기</td><td>벼락</td><td>봉인 부적(준비)</td></tr>
<tr><td>3</td><td>투혼</td><td>바람 걸음</td><td><b>마력 보호막</b></td><td>회복의 기운(준비)</td></tr>
<tr><td>4</td><td>천지 가르기</td><td>비도 난무</td><td>유성우</td><td><b>도력 일격</b>(공격+도력)</td></tr>
<tr><td>5</td><td>천둥 연격</td><td>그림자 연환</td><td>얼음 창 세례</td><td><b>팔괘진</b>(공격+치명타)</td></tr>
<tr><td>6</td><td>기세 꺾기</td><td>급소 낙인</td><td>마력 저주</td><td><b>하늘의 심판</b>(공격, 환생 뒤)</td></tr>
<tr><td>7</td><td>장군의 호령</td><td>월영 난무</td><td>칠성 낙뢰</td><td><b>오방신장 소환</b>(공격, 1차)</td></tr>
<tr><td>8</td><td>신장 강림</td><td>귀영 천살</td><td>태극 천벌</td><td>만신 대굿(준비, 2차)</td></tr>
<tr><td>파티</td><td>호위 진형</td><td>그믐 맹약</td><td>오행 공명</td><td>축원 굿</td></tr></table>
<p>도인의 공격 기술은 <b>다섯</b>(천벌 부적·도력 일격·팔괘진·하늘의 심판·오방신장), 4차 「오색 보천」은 공격 기술 다섯의 피해를 키우는 준비 기술이에요. <b>파티 버프</b>(Lv.30)는 20초 동안 함께 싸우는 동료 모두를 북돋고, 레이드의 동료들도 저마다 걸어 줘요.</p>
<h3>전투 기술 6칸 · 최대 레벨 · 연계</h3>
<ul><li><b>장착 기술 8칸</b>: 익힌 기술이 많아도 싸움에는 <b>8개</b>만 들고 가요(초각성기·넋 부름·변신은 따로). 처음에는 추천 조합으로 저절로 골라 주고, [기술]에서 기술마다 <b>[빼기]·[넣기]</b>로 바꿔요. 8칸이 찼을 때 [넣기]를 누르면 무엇을 뺄지 물어요. [추천 조합으로 되돌리기]를 누르면 다시 알아서 골라 줘요.</li>
<li><b>레이드별 조합</b>: 레이드·보스 싸움을 시작하기 전에 창이 떠서 그 싸움(함께하는 레이드·혼자 보스·몹 떼)에 맞는 6칸을 보여 줘요. 기술을 눌러 바꾸면 그 싸움 종류에 기억하고, 싸움이 끝나면 사냥 칸으로 돌아와요.</li>
<li><b>마나</b>: 기술마다 재사용 시간과 함께 마나가 들어요(최대 100, 초당 5). 마나가 모자란 칸은 어둡게 보여요. 모자란 몫은 마나 물약 <b>감로수</b>로 채워요(싸우는 동안 마나 30 아래면 저절로 +40).</li>
<li><b>기술 최대 레벨</b>: 처음 10 · 1차 전직 15 · 2차 20 · 3차 25 · 4차 30. 레벨이 낮을 때는 누적 레벨로도 막혀요(누적 레벨 6마다 +1).</li>
<li><b>연계(콤보)</b>: 짝이 되는 두 기술을 모두 칸에 끼우고 4초 안에 이어 쓰면(순서 상관없이) <b>35% 확률</b>로 저절로 「연계!」 — 5초 동안 기술 피해 +10~15%.</li></ul>
<div class="tip"><b>기술 조작</b>: 아래 기술 칸을 <b>누르면 바로</b> 쓰고, <b>길게 누르면 자동/수동</b>을 바꿔요. 수동 기술은 준비되면 반짝여요.
자동으로 쓸 때는 공격력 버프·약점처럼 <b>피해를 키워 주는 기술을 먼저</b> 쓰고 0.1초씩 간격을 두고 큰 기술을 써요.
술사는 보스가 나올 때 <b>마력 보호막</b>을, 도인은 봉인·도력·팔괘를 다 건 뒤 <b>하늘의 심판</b>을 직접 누르면 가장 커요.</div>
<h3>초각성기</h3>
<p>환생 후 <b>저승 Lv.60 + 시왕 레이드 「송제전」 토벌</b>을 이루고 이야기 퀘스트 「각성의 시련」을 깨면 배워요.
레이드·타임 보스에서 <b>한 싸움에 딱 한 번</b>, 싸움 시작 12초 뒤나 보스 체력이 60% 아래로 내려가면 저절로 써요. 피해는 내 보스 피해 <b>5초 몫</b>(4차 전직 뒤 8초)이에요.
무사 「개천 일격」 · 자객 「월하 만영참」 · 술사 「천화 강림」 · 도인 「사신 강림」.</p>
<h3>초각성기 2 — 잘 싸워야 차는 한 방</h3>
<p>4부 <b>56장</b>을 마치면 직업 1차 스승이 찾아와 퀘스트 <b>「두 번째 깨달음」</b>을 줘요(스승 다섯의 한마디 → 레이드에서 되받기 30번 → 버팀 깨기 20번 → 붉은 칸·강타·큰 살에 한 번도 맞지 않고 수문장·레이드 보스 3번 → 5차 스승과 다시 겨루기).
익히는 순간의 설명 연출만은 [건너뛰기]가 없고, 끝나면 연습 허수아비에게 직접 한 번 써 봐요.</p>
<ul><li>레이드가 시작되면 싸움 단추 옆에 <b>물빛 단추</b>가 생겨요. 고리(초각성 기운)는 <b>1초에 2씩 저절로</b> 차고, 손으로 <b>되받기 +30</b> · 손으로 싸우는 동안(직접 기술·되받기·구르기 뒤 8초) <b>버팀 깨기 +30</b> · 붉은 칸에서 <b>직접 굴러 피하기 +10</b>.</li>
<li>100이면 저절로 나가요(길게 누르면 수동, 키보드 R). 피해는 내 보스 피해 <b>4초 몫</b>, 손으로 채운 몫이 클수록 <b>최대 7초 몫</b>. 한 판에 한 번.</li>
<li>무사 「대왕암 가르기」(8초 동안 보스가 주는 피해 -30%) · 자객 「그믐 만 갈래」(8초 동안 모든 공격 치명타) · 술사 「한바다 뒤집기」(보스 4초 멈춤) · 도인 「일만 넋 대굿」(파티 체력 50% 회복, 쓰러진 동료 일으킴).</li></ul>
""", ('skill', '기술 탭'), kicker='4'))
    S.append(sec('장비 · 재련', """
<p><b>[장비] → [무기]/[방어구]</b>: 보석으로 소환(1회 50 · 10회 450)해요. 같은 장비 4개는 한 단계 위로 <b>합성</b>돼요. <b>일괄 합성</b>과 <b>남는 장비 갈기</b>는 조합 공방 다음 단계에 드는 장비(예: 희귀 야행복 4개)를 남겨 둬요.
등급은 일반 · 고급 · 희귀 · 영웅 · 전설(각 Ⅰ~Ⅳ). 가진 장비 전부가 조금씩, 장착한 장비가 크게 능력을 올려요.</p>
<p>장비 등급이 오르면 <b>용사 그림도 바뀌어요</b>(무기 모양·갑옷 무늬·허리띠 색).</p>
<h3>재련 — 세계마다 한도, 확률 공개</h3>
<ul><li>엽전 + 쇳가루로 무기·방어구를 벼려요. +1~+3은 반드시 성공, 그 뒤로 확률이 내려가요(+25는 15%). 화면 아래에 모든 단계의 확률이 나와요.</li>
<li><b>재련 한도</b>: 무기는 이승에서 +25까지. 방어구는 이승 +15 → 저승 +22 → 천계 +25까지 열려요.</li>
<li><b>재련 계승</b>: 부상·곤륜으로 건너가면 <b>대장장이</b>가 무기·방어구를 계승해 줘서 <b>+15부터 다시</b> 벼려요(부상 1차, 곤륜 2차). 그때까지 쌓은 재련 효과는 그대로 남고, 성공 확률은 1부의 70%예요.</li>
<li><b>2부부터 성장의 무게</b>: 계승한 뒤 새로 오르는 재련 몫은 0.75배로 줄고, 대신 <b>아바타·탈것·넋·별호의 모음 효과가 1.5배</b>가 돼요(부상·곤륜). 후반에는 레이드·이야기·꾸미기로 모으는 것이 더 중요해요.</li>
<li>실패하면 보통 <b>그대로</b>지만, +11부터는 <b>한 단계 떨어질</b> 수 있어요(+10·+15·+20에서는 안 떨어짐).</li>
<li>+17부터는 아주 가끔 <b>부서져</b> +15(+21부터는 +20)로 돌아가요. <b>보호</b>를 켜면 +16~+19에서 보석을 두 배 내고 부서짐을 막아요.</li>
<li><b>두 번 연달아 떨어지면</b> 다음 재련은 <b>반드시 성공</b>(기회의 불꽃)!</li>
<li>상점의 <b>숫돌</b>을 함께 쓰면 성공 확률이 1.15배가 돼요. <b>무기 +25는 첫 환생 조건</b>이에요.</li></ul>
""", ('gear', '장비 소환'), ('refine', '재련'), kicker='5'))
    S.append(sec('조합 공방', """
<p>[장비] → <b>[조합]</b>에서 직업 전용 <b>비전 무기 · 비전 갑옷 · 노리개</b>를 만들어요. 이승·저승·천계마다 3단계씩, 모두 <b>9단계</b>예요.</p>
<ul><li><b>조합식</b> = 이전 단계 + 그 세계 <b>재료</b>(요괴 정수 · 망자의 넋 · 하늘 조각) + 소환으로 모은 같은 칸 <b>장비</b>(노리개는 보석).</li>
<li>재료는 보스 2개 · 수문장 6개 · 레이드 8개(첫 토벌 +10) · 타임 보스 15개, 몬스터도 가끔 줘요. 허수아비·백귀야행·보물 동굴·1일 보스·강림·오늘의 할 일·천공의 탑에서도 나오고, <b>[상점] → 재료</b>에서 엽전으로 재료 꾸러미(하루 5번)를 살 수 있어요. <b>재료 이름을 누르면</b> 어디에 쓰고 어디서 얻는지 말풍선으로 알려 줘요.</li>
<li><b>계승</b>: 새 땅(저승·천계·부상·곤륜)에 들어서면 첫 화면에 <b>대장장이 쇠돌</b>이 나타나요. [계승하기]를 누르면 <b>지난 땅의 재료를 이 땅 재료로 그대로</b> 바꿔 주고(요괴 정수 → 망자의 넋 → 하늘 조각), 부상·곤륜에서는 재련도 계승해 줘요. 「나중에」를 눌러도 [조합]·[재련]의 [대장장이] 단추로 언제든 할 수 있어요.
지난 땅에서 <b>밀린 조합식</b>은 재료 절반 · 장비 조건 없음 · 확정 성공(계승 조합)이에요.</li>
<li>더 깊은 단계에 닿으면 <b>다음 조합식</b>이 열려요(이승 21·51·91단계, 저승 1·51·91단계, 천계 1·41·76단계).</li>
<li>성공 확률은 단계마다 100% → 40%. 실패하면 재료 절반만 사라지고, 실패가 쌓이면(천장) 다음은 확정 성공.</li>
<li><b>각인</b>: 칸마다 셋 중 하나(무기: 파쇄·사냥·급소 / 갑옷: 철벽·신속·생기 / 노리개: 술력·도력·공명). <b>직업에 맞는 최적 각인</b>은 1.5배,
세 칸이 모두 최적이면 <b>조화</b>(공격력·체력 +15%).</li>
<li><b>신화·태초 각성</b>([장비] → 무기·방어구 칸 아래): 전설 장비를 낀 채로 부상부터 <b>신화</b>(장착 효과 ×1.5), 곤륜부터 <b>태초</b>(×2.2)로 깨워요. 신화 조각·원한 조각·재료가 들고, 각성은 칸에 남아 다른 전설 장비로 바꿔 껴도 이어져요. 무기 빛·옷 장식 색이 바뀌어요.</li>
<li><b>각인 강화</b>: 칸마다 각인을 +1~+10까지 갈고닦아요(그 칸 조합 단계 + 1까지). 단계마다 각인 효과 <b>+10%</b>, 재료 5·10·15…와 보석 100·200·300…, 늘 성공해요. 각인을 바꿔도 강화는 남아요.</li></ul>
<table><tr><th>직업</th><th>최적 조합</th></tr>
<tr><td>무사</td><td>파쇄(공격력) · 철벽(체력·받는 피해↓) · 도력(재사용↓)</td></tr>
<tr><td>자객</td><td>사냥(보스 피해) · 신속(공격 속도) · 공명(펫 피해)</td></tr>
<tr><td>술사</td><td>급소(치명타 피해) · 철벽 · 술력(기술 피해)</td></tr>
<tr><td>도인</td><td>급소 · 생기(체력 회복) · 도력</td></tr></table>
<div class="tip">보스·레이드 세기는 조합 장비를 <b>제때 만든다고 보고</b> 맞췄어요. 만들지 않으면 같은 곳까지 <b>1.5배 넘게</b> 오래 걸려요.</div>
""", ('craft', '조합 공방'), ('inherit', '계승 · 대장장이'), kicker='5'))
    S.append(sec('신화 보물 · 장신구 · 변신', """
<h3>신화 보물 ([장비] → [신화])</h3>
<p>천부인 검(공격력) · 천부인 거울(체력) · 천부인 방울(치명타 피해) · 여의주(엽전·경험치) · 만파식적(기술 피해).
이야기 퀘스트에서 확정으로 받고, 퀘스트 보상을 받을 때 3% 확률·타임 보스·오프라인(누적 24시간마다 3%)에서도 나와요. 어려운 퀘스트일수록 효과가 커요.
종류마다 가장 센 것만 남고, 약한 것은 가방에 들어가요. 레이드(2%)·타임 보스·보물 동굴에서는 <b>2부·3부 보물까지 어느 것이든</b> 나오지만, 2부 보물은 부상·3부 보물은 곤륜에 가야 낄 수 있어요(그 전엔 가방에 보관).</p>
<h3>신화 제작 장비 ([장비] → [신화] 위쪽)</h3>
<p>재료를 모아 <b>만들고 → 강화</b>하는 장비 셋: <b>금척</b>(장신구 효과, 저승부터) · <b>천사옥대</b>(갑옷 칸 효과, 천계부터) · <b>사인검</b>(무기 칸 효과, 부상부터).
만들면 그 칸 효과가 <b>1.3배</b>, 강화할 때마다 0.1배씩 올라 <b>+5에서 1.8배</b>(그 이상은 없어요). 제작 6~10% · 강화 8%→2%로 아주 낮은 확률이고, 실패하면 재료를 잃는 대신 <b>정성</b>이 쌓여 가득 차면 다음은 꼭 성공해요(단계가 내려가지는 않아요).
재료는 지금 세계 재료·신화 조각·보석(사인검은 원한 조각도). 강화할수록 용사 둘레 <b>오라</b>가 달라져요(+1 고리 · +2 불티 · +3 금빛 고리·불꽃 · +4 빛 조각 · +5 빛살).</p>
<h3>장신구 ([장비] → [장신구])</h3>
<p><b>반지</b>(공격력) · <b>귀걸이</b>(치명타 피해·기술 피해) · <b>팔찌</b>(체력·공격 속도). 등급 5단계.
각 지역 <b>9번째 단계 수문장</b>을 잡을 때 반지 8% · 귀걸이·팔찌 1.5%, 일반 몬스터에게서는 아주 드물게(귀걸이·팔찌 0.08%).
타임 보스에서도 떨어져요. 지금 것보다 약하면 가방에 들어가요.
<b>목걸이</b>(보스 피해, 부상부터)·<b>패옥</b>(경험치·엽전, 곤륜부터)은 그 땅의 수문장 4%·레이드 3%에서 나오고, 이야기(「갓파 대왕」·「가뭄 귀신」)에서도 하나씩 받아요.</p>
<h3>변신 ([장비] → [변신])</h3>
<p>변신 하나를 <b>착용</b>하면 <b>보스 싸움·레이드에서 한 판에 한 번</b>, 전투 화면 기술 줄 위 <b>[변신]</b> 단추로 <b>30초</b> 동안 힘을 빌려요(일반 몹 사냥 중엔 못 쓰고, 싸움이 끝나면 풀려요). <b>자동</b>이면 보스가 나오자마자 변신하고, 단추를 <b>길게 누르면 수동</b>(직접 누름)으로 바뀌어요.
효과는 '몇 단계만큼'이라 어느 땅에서나 비슷하게 세요(지금 땅 기준 %는 [변신] 화면에 나와요).</p>
<ul><li><b>사신(1부, 이야기)</b>: 주작(공격력·엽전/경험치) · 청룡(공격력·기술 피해) · 백호(공격 속도·치명타) · 현무(체력·받는 피해 줄임). 부상·곤륜에서는 힘이 60%로 줄어요.</li>
<li><b>부상의 변신</b>: 까마귀 텐구(이야기 「텐구 장수」) · 여우불 구미 · 붉은 오니.</li>
<li><b>곤륜의 변신</b>: 황룡(이야기 「곤륜 가는 길」) · 촉룡 · 정위.</li>
<li>이야기 것이 아닌 변신은 그 땅에 간 뒤 <b>1일 보스</b>(이기면 4%)·<b>꾸미기 상자</b>(1.5%)에서 나오고, 60번 안에 하나는 꼭 나와요.</li></ul>
""", ('myth', '신화 보물'), ('acc', '장신구'), ('form', '변신'), kicker='6'))
    S.append(sec('전직', """
<ul><li><b>1차 전직</b>: 레벨 50이 되면 [수련] → [전직]에서 직업의 스승과 겨뤄요(동료 둘과 함께 90초). 이기면 전직!</li>
<li>무사 → <b>장군</b> · 자객 → <b>월영</b> · 술사 → <b>방사</b> · 도인 → <b>무당</b>. 공격력·체력 +30%, 기술 피해 +20%.</li>
<li>전직하면 <b>전직 기술</b>이 열리고, 무기 모양이 바뀌고(술 달린 장검·쌍비수·초승달 지팡이·방울 부채), <b>전직 망토</b>를 받아요.</li>
<li><b>2차 전직</b>은 숨겨져 있어요. 저승 이야기를 끝까지 마치면 누군가 찾아온다는 소문이…(장군 → 신장 · 월영 → 귀영 · 방사 → 천사 · 무당 → 만신, 공격력·체력 +80%)</li>
<li>시험은 지면 몇 번이든 다시 볼 수 있어요.</li>
<li><b>직업 바꾸기</b>([정보] → [직업 바꾸기])는 캐릭터마다 <b>한 주에 2번</b>까지예요(월요일 0시에 다시 차요). 바꾸면 <b>기술 레벨이 모두 Lv.1</b>, <b>재련은 모든 장비 칸이 처음</b>(+0, 계승한 칸은 +15 — 계승으로 굳힌 효과는 그대로)으로 돌아가고, 기술·재련에 쓴 엽전·보석·쇳가루는 <b>80%만</b> 돌려받아요. 레벨·전직 단계·장비·펫·장신구·아바타·이야기 진행은 그대로예요. 바꾸기 전에 무엇이 돌아가고 얼마를 돌려받는지 숫자로 보여 주는 경고 창이 떠요. 싸움 중에는 못 바꿔요.</li></ul>
""", ('job', '전직'), kicker='7'))
    S.append(sec('아바타(꾸미기)', """
<ul><li>[장비] → [아바타]: <b>옷</b>(색동 설빔·도깨비 털옷·선녀 날개옷·곤룡포 등) · <b>망토</b>(전직 망토·밤하늘·용비늘 등) · <b>펫 꾸미기</b>(꼬마 갓·리본·꽃관·금관·황금빛 등).</li>
<li>모습만 바뀌지만, 가진 아바타 하나마다 <b>공격력·체력 +2%</b>(도감 효과)예요.</li>
<li>상점·아바타 화면의 <b>꾸미기 상자</b>(보석 1,000)에서 나오고, 이야기(을지문덕·이순신·제천대성·곤륜의 치수 도롱이·오작교 깃 망토 등)와 전직에서도 받아요. 벚꽃 무복·봉황 깃 망토처럼 <b>부상·곤륜에 가야 상자에 나오는</b> 것도 있어요.</li>
<li>꾸미기 상자 확률: 옷 6% · 망토 11% · 펫 꾸미기 28% · 위로품(인삼 탕약 10개) 55%. <b>40번</b> 안에 새 옷·망토가 안 나오면 40번째는 확정이에요.</li></ul>
""", ('avatar', '아바타'), kicker='8'))
    S.append(sec('펫', """
<ul><li>보석으로 소환(1회 100 · 10회 900). <b>공격 · 방어 · 지원</b> 세 종류 × 5등급 = 15마리
(들고양이·해동청·아기 범·새끼 백호·삼족오 / 남생이·반달곰·돌거북·해치·황금 해치 / 까치·업두꺼비·삽살개·두루미·봉황).</li>
<li>종류마다 한 마리씩 데려가요. 공격 펫은 함께 싸우고, 방어 펫은 피해를 줄이고, 지원 펫은 체력을 채우거나 엽전·경험치를 늘려요.</li>
<li>소환 확률: 전설 0.5% · 영웅 3.5% · 희귀 13% · 고급 28% · 일반 55%. <b>60번</b> 안에 영웅 이상이 안 나오면 60번째는 영웅 이상 확정.</li>
<li>같은 펫이 또 나오면 <b>별</b>이 올라요(최대 5개, 별마다 효과 +20%).</li>
<li>엽전 + 보석으로 <b>Lv.30</b>까지 강화해요. 펫 하나를 Lv.20으로 키우는 것이 환생 시련 중 하나예요.</li>
<li><b>부상 · 곤륜의 펫</b>: 부상에 가면 불꼬리 여우·낫족제비·둔갑 너구리·꼬마 갓파, 곤륜에 가면 청란·산 업은 자라·옥토끼·청조가 같은 등급의 소환 후보에 더해져요.</li>
<li><b>신화 펫 · 환수</b>(전설보다 위): 2부 부상의 뇌수·바쿠·아마비에, 3부 곤륜의 필방·백택·비휴. 부마다 한 마리(<b>바쿠·백택</b>)는 이야기 보상으로 확정, 나머지는 그 땅에 들어간 뒤 펫 소환에서 <b>0.3%</b>(200번 안에 확정)로 나와요.</li></ul>
""", ('pet', '펫 탭'), kicker='9'))
    S.append(sec('퀘스트 · 이야기', """
<ul><li><b>이야기 퀘스트 113개</b>(25장): 마을 어귀 → 해모수와 유화 → 알에서 태어난 주몽 → 첫 전직 → 엄리대수 → 졸본과 송양왕 → 다물 → 윤회의 시련 →
환생 → 저승의 열 대왕 → 사신의 귀환 → 하늘의 선전포고 → 영웅들의 시험 → 영소보전 → 신화. 다 깨면 '끝없는 신화'로 이어져요.</li>
<li>이야기를 하나 깰 때마다 <b>15초 이내의 짧은 연출</b>이 나와요. [정보]에서 다시 볼 수 있어요.</li>
<li><b>오늘의 할 일 6개</b>(몬스터 300마리·보스 5번·소환 10번·능력치 30번·재련·강화 3번(재련을 다 올렸으면 펫·기술·각인 강화·탈것 별·각성도 셈)·레이드 1번)와 모두 완료 보너스. 매일 자정에 새로 고쳐져요. 오늘의 할 일·마을 부탁은 보상을 받아도 <b>퀘스트 창이 그대로</b>예요(이야기 퀘스트 보상만 연출을 보러 사냥 화면으로).</li>
<li><b>주간 퀘스트 8개</b>(월요일 0시에 새로): 몬스터 5,000마리 · 보스 40번 · 레이드 10번 · 타임 보스 3번 · 백귀야행 3번 · 소환 50번 · 재련·강화 20번 · 오늘의 할 일 모두 끝내기 5일.
할 일마다 <b>보석 300~600</b>(뒤 세계일수록 최대 4배)과 덤(쇳가루·재료·신화 조각·원한 조각·숫돌·산삼 탕약·고삐 조각)을 주고, 모두 끝내면 <b>큰 상자</b>(보석 3,000×세계 배율 · 신화 조각 30 · 꾸미기 상자 한 번 · 천계부터 치장 · 부상부터 고삐 조각 15).</li>
<li>메뉴 화면의 긴 설명은 처음엔 한 줄만 보여요. <b>[설명 펼치기 ▾]</b>를 누르면 다 보이고, 펼친 것은 기억해요.</li>
<li><b>퀘스트 행운</b>: 보상을 받을 때 20% 확률로 모든 기술 재사용 시간 초기화, 3% 확률로 신화 보물!</li>
<li><b>갈림길</b>(30장·37장): 이야기를 마치면 두 길 가운데 하나를 골라요. 어느 길이든 이야기는 똑같이 이어지고, 고른 길에 따라 <b>별호</b>(체력·엽전·경험치·보스 피해 중)와 짧은 뒷이야기가 달라요. 한 번 고르면 바꿀 수 없고, 「나중에」를 누르면 [퀘스트]에서 골라요.</li>
<li>장면 왼쪽 위의 퀘스트를 <b>누르면 그 퀘스트를 하는 곳</b>(재련·레이드·펫 등, 사냥이면 사냥 화면)으로 바로 가요. 퀘스트를 받거나 보상을 받으면 사냥 화면으로 돌아가고, 이야기 연출이 시작되면 열려 있던 메뉴가 저절로 닫혀요.</li>
<li><b>마을 부탁</b>: 채팅 「마을」의 부탁 ▶을 눌러 받아요(100개, 세계마다 이야기 진행에 맞춰 열림). 재련·단계 조건은 이미 이뤘으면 받자마자 끝나고, 다 한 부탁은 저절로 마쳐요. <b>보스</b> 부탁은 단계 보스·레이드·타임 보스·보물 동굴·전직 시험 어느 것이든, <b>레이드</b> 부탁은 [레이드] 칸의 싸움 어느 것이든 세요. 그 부탁이 열린 <b>이야기 장을 이미 마쳤다면</b> 받으면 바로 끝나고, 아직 그 장을 하고 있다면 꼭 해내야 해요.</li></ul>
""", ('quest', '퀘스트 탭'), ('cut', '이야기 연출'), kicker='10'))
    S.append(sec('레이드', """
<ul><li><b>이승 레이드</b>: 레벨 10마다 하나씩 열려요(붉은 산군 멧돼지 · 천년 묵은 여우 · 천하대장군 · 늪의 이무기 · 외눈 도깨비 왕 ·
쇠먹는 불가사리 · 어둑시니 · 성난 해태, 이후 '2단', '3단').</li>
<li><b>시왕 레이드</b>(저승): 저승 레벨 20마다 열 대왕이 하나씩. 처음 도전할 때 30~60초쯤 걸리게 단단해요(직업에 따라 다르고, 처음엔 질 수도 있어요).</li>
<li><b>이야기 문</b>: 저승·천계·부상·곤륜 레이드는 그 레이드를 깨라는 이야기 퀘스트에 닿아야 열리고, 이승 레이드는 그 레이드 레벨이 이야기 목표가 되는 장에 닿아야 열려요. 한 번 깬 레이드는 계속 열려 있어요.</li>
<li>파티는 <b>나 + 이 기기의 다른 캐릭터 + NPC 동료</b>로 3~10명. 자동으로 싸우고 <b>90초</b> 안에 보스를 쓰러뜨리면 성공!</li>
<li>보상: 보석 · 엽전 · 장비, 처음 깨면 보너스. 이승 레이드 8곳을 모두 깨는 것이 환생 시련 중 하나예요.</li>
<li>입장은 <b>토벌패</b>(최대 3개, 15분마다 1개 충전). 실패하면 돌려받아요.</li>
<li>다른 용사·동료와 함께하는 싸움(레이드·타임 보스)에서는 반자동이어도 <b>모든 기술이 자동</b>이고, 함께 싸우는 다른 용사도 기술과 초각성기를 써요.</li>
<li><b>허수아비 수련</b>(하루 3번): 30초 동안 넣은 피해로 1~5등급 보상. 막힌 단계의 보스를 겨우 잡을 만큼이면 4등급, 조금 앞서면 5등급.</li>
<li><b>보물 동굴</b>(하루 2번): 보물 이무기를 60초 안에 쓰러뜨리면 <b>신화 조각</b>(5 + 세계×2)·재료·보석과 7% 확률로 신화 보물. 신화 조각 30개로 원하는 신화 보물을 하나 만들어요. 신화 조각은 레이드(절반 확률)·타임 보스·수문장·1일 보스·강림·오늘의 할 일에서도 나와요(상점에서는 팔지 않아요).</li>
<li><b>레이드 리셋권</b>([상점] → 묶음, 하루 1번 보석 800): 오늘 쓴 허수아비·백귀야행·보물 동굴·1일 보스·강림 레이드 횟수를 되돌리고 토벌패를 가득 채워요. 레이드 칸 콘텐츠의 보석은 1.5배이고, 타임 보스·강림·보물 동굴도 이기면 보석을 줘요.</li>
<li><b>백귀야행</b>(하루 2번): 60초 동안 몰려오는 요괴를 잡은 수만큼 엽전(3마리분씩)·쇳가루·보석·재료(부상부터 고삐 조각). 그동안 쓰러져도 단계가 내려가지 않아요.</li>
<li><b>상위 레이드 「진(眞)」</b>(하루 3번, 저승부터): 지나온 땅의 레이드마다 하나. 보스의 세기가 정해져 있어 <b>권장 전투력</b>과 내 전투력을 견줘요(모자람·딱 맞음·넉넉함·압도적). 자동 피하기가 절반만 통하고, 붉은 칸·강타에 맞으면 잠깐 기절해요. 금빛 「!」를 되받으면 보스가 바로 휘청여요. 세 번째 쓰러지면 끝, 탕약은 한 판에 10개까지. 그 땅 최고 등급 장비·신화 조각·진 전용 아바타, 레이드마다 주에 한 번 첫 승리 보상. 레이드 리셋권으로는 횟수가 되돌아오지 않아요.</li>
<li><b>강림 레이드</b>(하루 2번, 첫 환생 뒤): 요일마다 다른 신장. 나 + 다른 용사 3명이 저절로 모여(같은 직업 2명까지) 싸우고, 이기면 <b>아바타</b>(강림 전용 25%).</li>
<li><b>전멸기</b>: 함께하는 레이드 보스는 체력이 반쯤이면 전멸기를 써요. 모두 체력 1까지 깎이고, <b>회복약이 있으면 저절로 마셔 버티고 없으면 쓰러져요</b>. 회복약을 꼭 챙기세요.</li></ul>
""", ('raid', '레이드 탭'), ('raidfight', '레이드 전투'), kicker='11'))
    S.append(sec('타임 보스', """
<ul><li><b>0시부터 3시간마다</b>(0·3·6·9·12·15·18·21시) 30분 동안 나타나요. [레이드] 탭 위쪽에 남은 시간이 보여요.</li>
<li><b>서버에 만들어진 모든 캐릭터</b> 가운데 <b>무작위 10명</b>이 함께 싸워요(같은 직업은 나까지 <b>3명까지</b>, 한 번이라도 싸워 본 캐릭터만). 30분 동안은 같은 파티예요. 서버에 연결되지 않으면 이 기기에 만들어 둔 캐릭터에서 같은 규칙으로 뽑아요. 120초 안에 함께 쓰러뜨려요.</li>
<li>보스 체력은 <b>모인 캐릭터들의 피해에 맞춰</b> 제한 시간 언저리에 쓰러질 만큼이에요. 그래서 <b>그냥 두면 이기고 지는 게 반반</b>쯤이고, 손을 잘 쓰면 이겨요(아래 팁). 보스 한 방은 방어와 상관없이 맞는 용사 <b>최대 체력의 3.5%</b>(지옥 5%), 붉은 칸·강타는 그 5~6배라 누구나 똑같이 위협받아요.</li>
<li>난이도 <b>노말</b>(누구나) · <b>지옥</b>(환생해야 도전). 창이 열릴 때마다 난이도별로 한 번씩 보상을 받아요.</li>
<li><b>1일 보스</b>(타임 보스 아래): 요일마다 보스와 치장 부위가 바뀌어요(월 토시·화 버선·수 허리띠·목 무기 술·금 발밑 빛·토 무작위·일 전설만). 이기면 그날 부위의 치장 하나(일반~전설 모든 등급), 일요일엔 전설 치장만 10% 확률로. 이기든 지든 하루 한 번 보석·엽전을 줘요. 하루 3번까지, 60초 혼자 싸움(타임 보스처럼 그냥 두면 반반, 손을 쓰면 이겨요).</li>
<li>기본 보상은 엽전. <b>시간대마다 특산물</b>이 달라요: 0시 장신구 · 3시 쇳가루·숫돌 · 6시 높은 등급 무기 · 9시 치장 · 12시 높은 등급 갑옷 · 15시 신화 · 18시 고삐·변신 · 21시 넋·아바타(지옥은 두 배).</li>
<li>1일 보스는 <b>이야기 17장(천계)</b>부터 열려요.</li></ul>
<div class="tip"><b>이기는 법</b>: 보스 체력은 싸우는 동안 '기본 피해'(되받기·휘청으로 더 넣은 몫은 빼고)에 맞춰지니, 더 넣은 만큼 일찍 쓰러져요. 금빛 「!」에 <b>[되받기]</b>(보스를 묶고 기본 피해 4초 몫을 한 번에, 두 번이면 <b>휘청</b>), 휘청 동안(피해 1.8배)에 기술 넣기, 붉은 칸·강타 <b>피하기</b>(쓰러지면 그동안 못 때리고 타임 보스는 파티 목숨도 줄어요). 보스 체력은 끝까지 맞춰져서 기술을 아꼈다가 몰아 쳐도 쉬워지지 않아요. 그냥 두면 노말 55%·지옥 25%·1일 보스 45%, 다 피하고 거의 다 되받으면 85~95% 이겼어요. 10명이 안 되거나 혼자여도 같은 규칙이에요.</div>
""", ('timeboss', '타임 보스 창'), ('timefight', '타임 보스 전투'), kicker='12'))
    S.append(sec('환생 · 저승', """
<h3>첫 환생 조건</h3>
<ul><li>이승 <b>레벨 100</b> · <b>무기 재련 +25</b> · <b>윤회의 다섯 시련</b>:
활(이승 100단계 넘기) · 물(이승 레이드 8곳 토벌) · 하늘(신화 보물 3종) · 벗(펫 하나 Lv.20) · 인연(장신구 1개)</li></ul>
<h3>환생하면</h3>
<ul><li>레벨·단계·엽전·능력치는 처음으로 돌아가요. <b>장비·재련·펫·신화 보물·장신구·변신·보석은 그대로</b>예요.</li>
<li><b>윤회 구슬</b>을 받아요: 레벨의 1/10 + 최고 단계의 1/20 (Lv.100·101단계면 15개).</li>
<li>윤회 구슬로 영원히 남는 능력을 올려요: 무력(공격력 +15%) · 강골(체력 +15%) · 신속(공격 속도 +3%) · 복덕(엽전·경험치 +10%) · 영안(치명타).</li>
<li>무대가 <b>저승</b>으로 바뀌어요: 도산 → 화탕 → 한빙 → 검수 → 독사 → 흑암지옥. 저승 레벨은 200까지.</li>
<li>환생(과 윤회 구슬)은 <b>두 번까지</b>예요. 두 번째 환생은 저승 레벨 200 + 저승 이야기를 마치면 하늘(천계)로 올라가는 환생이에요.</li>
<li><b>환생의 기억</b>(4부 53장부터, 캐릭터마다 한 번뿐인 선택): 강림도령의 물음에 [떠올린다]를 고르면 [수련] → [환생]에 기억의 길 세 갈래가 열려요. 값(이승 = 엽전, 저승 = 보석 3,000, 천계 = 보석 6,000 + 원한 조각 20, 모두 지금 땅 재료)을 치르고 그 기억 속 싸움을 이기면 윤회 구슬 2·3·3개씩, 다 마치면 마무리 8개를 더해 <b>40개</b> · 푸른 물빛 환생 오라 · 별호 「세 번 산 자」 · 신속 15·영안 25까지. [나중에]는 5부 끝까지 다시 열 수 있고, [떠올리지 않는다]는 되돌릴 수 없어요(별호 「뒤돌아보지 않는 자」). 레벨·단계는 그대로이고 이야기·전직 조건과 상관없어요.</li></ul>
""", ('rebirth', '환생 조건'), ('rebirth2', '윤회 능력'), ('hell', '저승'), kicker='13'))
    S.append(sec('천계 · 신과의 전쟁', """
<p>저승 이야기 끝에 하늘에서 천둥이 그치지 않아요. 하늘 군대가 '저승을 뒤흔든 인간'을 벌하겠다며 내려와요. 두 번째 환생으로 하늘에 올라
옛이야기·역사 속 영웅과 신들의 시험을 이겨 내고, 하늘과 땅을 싸우게 만든 <b>천마</b>를 찾아내요.</p>
<ul><li>무대: 구름 계단 → 반도원 → 살수 강가 → 명량 바다 → 화과산 → 영소보전. 천계 레벨은 300까지.</li>
<li><b>영웅 레이드</b>(천계 레벨 30마다): 전우치 · 홍길동 · 을지문덕 · 이순신 장군의 넋 · 염라대왕 · 제천대성 손오공 · 옥황상제 · 천마.
영웅들은 악당이 아니라 용사의 마음을 시험하는 스승이에요. 이기면 함께 싸워 주고 특별한 아바타를 줘요.</li>
<li>이야기 25장의 끝에서 용사는 이 땅의 <b>신화</b>가 돼요.</li></ul>
""", ('heaven', '천계'), ('godraid', '영웅 레이드'), kicker='14'))
    S.append(sec('제2부 · 부상', """
<p>천계 이야기를 모두 마치면 까치가 검은 깃털을 물고 와요. 천마가 남긴 원한 조각이 동쪽 바다 건너 <b>부상</b>(해 뜨는 섬)으로 날아갔대요.</p>
<ul><li><b>바다 건너기</b>: [수련] → [환생]에서 동해 용왕의 거북을 타고 건너요. 환생과 달리 <b>레벨·장비·능력치·엽전이 그대로</b>이고, 사냥 단계만 1부터예요. 레벨 상한은 400.</li>
<li>지역 6곳: 갓파 강 · 여우불 들판 · 구라마산 · 눈보라 고개 · 오니 섬 · 황천 비탈. 몬스터는 천계 끝자락만큼 세게 시작해요.</li>
<li><b>해돋이 기운</b>: 부상에서는 사냥하지 않고 서 있어도 지금까지 나아간 단계만큼 경험치가 조금씩 쌓여요(자리를 비웠을 때도 쌓여요).</li>
<li><b>탈것</b>([장비] → [탈것]): 부상 마구간(당나귀·누렁소·백마)·이야기·고삐 조각으로 얻어요. 타면 걷는 속도가 빨라지고 고유 능력(엽전·경험치·보스 피해·치명타 등)이 켜져요. 가진 탈것마다 공격력·체력이 오르고(모음 효과), 고삐 조각(부상·곤륜 레이드·타임 보스·허수아비)으로 별을 올려요.</li>
<li><b>부상 레이드</b>(부상 8단계마다): 갓파 대왕 · 다마모노마에 · 대텐구 소조보 · 누에 · 유키온나 · 슈텐도지 · 야마타노오로치 · 이자나미.</li>
<li><b>3차 전직</b>: Lv.350 + 내 직업 스승이 나오는 장(술사 28장 세이메이 · 자객 29장 소조보 · 도인 32장 아메노우즈메 · 무사 33장 스사노오)을 마치면
[수련] → [전직]에서 겨뤄요. 풍뢰장 · 익영 · 식신사 · 신명, 새 기술(팔갈래 폭풍 · 깃바람 분신 · 식신 행렬 · 신명 굿춤).</li>
<li>이야기 26~34장. 신화 보물 4종(구사나기 검 · 야타 거울 · 야사카니 곡옥 · 요술 방망이)은 이야기 보상이에요.</li>
<li>장이 바뀔 때마다 <b>붓글씨 장 제목</b>이 나오고, 2부 장은 여는 연출도 있어요.</li></ul>
<div class="tip">일본 옛 신화·민담(고사기 등)의 줄거리를 바탕으로 대사는 새로 썼어요. 신들은 악당이 아니라 원한에 흔들린 존재로 그렸어요.</div>
""", ('busang', '부상 · 구라마산'), ('chcard', '장 제목 카드'), kicker='15'))
    S.append(sec('제3부 · 곤륜', """
<p>부상 이야기를 마치면 원한 조각이 해가 지는 쪽, 서쪽 하늘 끝 <b>곤륜</b>으로 흩어져요. 활의 사내·우임금·백사·나타 같은 옛 중국 이야기 속 사람들을 만나며 원한을 풀어 줘요.</p>
<ul><li><b>서쪽 하늘로 건너기</b>: [수련] → [환생]에서 건너요. 부상처럼 <b>레벨·장비·능력치·엽전이 그대로</b>, 사냥 단계만 1부터. 레벨 상한 <b>500</b>. 건널 때 주몽의 넋과 탈것 과하마를 받아요.</li>
<li>지역 7곳: 타는 들판 · 황하 강가 · 서호 · 버려진 절 · 곤륜산 · 부주산 · 하늘 틈. 해돋이 기운처럼 서 있어도 경험치가 조금씩 쌓여요.</li>
<li><b>곤륜 레이드</b>(곤륜 8단계마다): 열 개의 해 · 상류 · 뇌봉탑의 원한 · 달기 · 도철 · 궁기 · 도올 · 공공 · 혼돈. 고삐 조각을 부상보다 많이(2개) 줘요.</li>
<li><b>4차 전직</b>: <b>Lv.480</b> + 44장 「세 스승의 시험」(1차 스승 → 강림도령 → 3차 스승, 세 판을 내리 이겨요). 10번째 기술과 4차 망토. 곤륜은 레벨이 4차를 막는 구간이라 직업마다 걸리는 시간이 비슷해요.</li>
<li>신화 보물(이야기 보상): <b>사일궁</b>(열 개의 해) · <b>서왕모의 불사약</b>(싸움마다 한 번 쓰러져도 체력 절반으로 일어남) · <b>반고의 도끼</b> · <b>오색 돌</b>. 탈것 응룡 · 해태 · 백록 · 기린도 이야기에서 받아요.</li>
<li>곤륜에 가면 장신구 <b>패옥</b>(경험치·엽전), 펫 청란 · 산 업은 자라 · 옥토끼 · 청조, 꾸미기 상자의 옥 갑주 · 봉황 깃 망토 · 옥빛이 열려요. 전설 장비를 <b>태초</b>로 깨울 수 있어요.</li>
<li>37장 뒤에는 <b>갈림길</b>이 하나 더 있어요(흰 뱀을 그 사람에게 보낼까, 함께 갈까).</li></ul>
<div class="tip">중국 옛 기록·민담(산해경·회남자·백사전 등)의 줄거리만 쓰고 대사는 새로 썼어요. 지금도 믿는 신은 적으로 내지 않아요.</div>
""", ('kunlun', '곤륜 · 서호'), ('guard', '[수련] → [수호신]'), ('elix', '[수련] → [영약]'), kicker='15'))
    S.append(sec('장별 치장', """
<p>천계 17장부터 곤륜 45장까지 <b>장마다 그 장 이야기의 치장</b>이 하나씩, 모두 29가지 있어요(천병 붉은 술 · 살수 물결신 · 여우불 자취 · 서호 비단 띠 · 오색 빛 …).
그 장을 하는 동안 사냥터 몹을 잡으면 낮은 확률(몹 약 1,200마리에 하나)로 나오고, <b>지나온 장 것도 함께</b> 나와요. 자리를 비운 동안에도 나와요.</p>
<ul><li><b>다섯 부위</b>(옷·망토·펫 꾸미기와 따로): 토시(첫 줄 공격력) · 버선(받는 피해) · 허리띠(체력) · 무기 술(치명타 피해) · 발밑 빛(보스 피해). 끼면 용사 그림에도 보여요.</li>
<li>부위마다 하나씩 끼고, <b>더 좋은 것이 나오면 저절로</b> 바꿔 껴요. 한 치장 안의 능력치는 서로 겹치지 않아요. 보관함 40칸(넘치면 가장 약한 것이 보석으로).</li>
<li><b>줄 수 = 등급</b>: 일반 1줄 · 고급 2줄 · 희귀 3줄 · 영웅 4줄(2부 후반 31장부터, 값은 낮음) · 전설 4줄(3부 중반 40장부터, 엔드템).</li>
<li>한 줄의 세기는 <b>「몇 단계 앞까지 깰 수 있게 하나」</b>로 정해지고, 지금 땅의 몬스터가 세지는 만큼 %로 바뀌어요.
1~2줄로 다섯 부위를 다 채우면 합쳐 <b>3.5단계</b>를 넘지 않고, 전설 4줄로 다 채우면 <b>다섯 부위 효과</b>까지 <b>10단계쯤</b>이에요.</li></ul>
""", ('skin', '[장비] → [치장]'), kicker='15'))
    S.append(sec('보스 손컨트롤 · 넋 부름', """
<h3>보스 손컨트롤 — 미리 보고 피하기</h3>
<ul><li><b>붉은 칸</b>: 땅이 붉게 물들고 안쪽이 차오르면 곧 터져요. <b>땅을 눌러</b> 걸어가거나 기술 칸 왼쪽 <b>[구르기]</b>(키보드 스페이스)로 빠져요.</li>
<li><b>되받기</b>: 보스 머리 위에 <b>금빛 「!」</b>가 뜨면 단추가 <b>[되받기!]</b>로 바뀌어요. 누르면 막고 보스가 잠깐 묶여요. 못 막으면 강타를 맞아요.</li>
<li><b>버팀</b>: 보스 체력 아래 파란 막대. 기술·넋·되받기로 깎아 0이 되면 <b>휘청</b> — 4초 동안 공격을 못 하고 받는 피해 +40%.</li>
<li><b>큰 살</b>: 레이드·수문장 보스가 크게 기를 모아요(검붉은 막대). 다 모으기 전에 버팀을 깨면 <b>끊고</b>, 못 깨면 모두 최대 체력의 절반 넘게 다쳐요.</li>
<li>직접 안 눌러도 용사가 붉은 칸은 80%쯤 피하고 35%쯤 되받아요. <b>직접 하면 늘 성공</b>이라 더 빨리 잡아요. 이승 앞 10단계는 없고, 30단계까지는 붉은 칸만 나와요.</li></ul>
<h3>넋 부름 (2부 부상부터)</h3>
<p>부상으로 건널 때 강림도령에게 <b>넋 주머니</b>를 받아요. 옛이야기 속 넋 <b>17</b>(고급 4 · 희귀 4 · 영웅 4 · 전설 3 · 신화 2)을 모시면, 싸우는 동안 <b>넋의 기운</b>이 25초쯤에 차서 넋이 용사 곁에 나타나 도와요(큰 피해 · 모든 적 피해 · 묶기 · 받는 피해 증가 · 회복 · 보호막 · 치명타 · 기술 재사용 줄이기).
[자동]이면 저절로, [반자동]이면 기술 칸 왼쪽 <b>넋 구슬</b>을 눌러요(키보드 Q).</p>
<ul><li><b>넋 구슬</b>: 부상·곤륜 레이드 4% · 타임 보스 8% · 보물 동굴 5%, <b>40번 안에 하나는 꼭</b>. 이야기에서 강림도령(부상)·주몽(곤륜)을 확정으로 받아요.</li>
<li>같은 넋이 또 오면 별 +1(최대 5, 별마다 +20%), 별이 가득하면 보석 600. 모신 넋마다 공격력·체력 +0.5~3%.</li>
<li>주머니는 1칸, <b>4차 전직 뒤 2칸</b>(차례로 나타나요). [기술] → <b>[넋 부름]</b>에서 모시고 내려요.</li>
<li><b>원한 조각 · 결이야기</b>: 부상부터 단계 보스·레이드·타임 보스·보물 동굴·백귀야행·급보·갈림길에서 <b>원한 조각</b>을 모아요. 넋마다 결이야기 3마디(조각 10·30·60)를 들려주면 조각이 풀리고, 마디마다 그 넋의 힘 <b>+15%</b>·모음 효과 <b>+50%</b>.</li></ul>
""", ('bosspat', '붉은 칸 예고 · 버팀'), ('soulcast', '넋이 나타남'), ('soulpage', '넋 부름 화면'), kicker='15'))
    S.append(sec('가방 · 장터', """
<h3>가방 ([가방] 메뉴)</h3>
<p>수문장·타임 보스·오프라인·퀘스트 행운에서 나온 장신구·신화 보물 가운데 <b>지금 낀 것보다 약한 것</b>과, 더 좋은 것을 끼면서 빠진 <b>옛것</b>이 가방(60칸)에 모여요. 눌러서 <b>끼기</b> · <b>상인에게 팔기</b>(보석) · <b>장터에 올리기</b>. [안 쓰는 것 모두 팔기]는 지금 것보다 약한 물건만 한 번에 팔아요(↑ 표시는 지금 것보다 좋은 물건). 쇳가루·고삐 조각·조합 재료·탕약·숫돌·토벌패도 <b>그림 칸</b>으로 보이고, 누르면 <b>어디에 쓰고 어디서 얻는지</b> 알려 줘요.</p>
<h3>장터 마을</h3>
<p>오른쪽 위 <b>장터 단추</b>(또는 가방의 [장터 마을로 가기])로 들어가요. 돌바닥 광장과 노점·기와집·북 무대가 있는 마을이에요. <b>땅을 누르면 그리로 걸어가고</b>, 온라인이면 지금 장터에 있는 <b>다른 용사들이 이름표를 달고 함께</b> 서 있어요. <b>보부상 덕보</b>(NPC 상인) · <b>장터 알림판</b>(사기) · <b>거간꾼 막동</b>(팔기) · <b>전표 아전</b>(내 물건) 앞으로 가면 거래 화면이 열려요. 장터에 있는 동안은 사냥이 멈추고, 오른쪽 아래 큰 단추 <b>[나가기]</b>로 사냥터에 돌아가요.</p>
<h3>장터 거래 — 사기 · 팔기 · 내 물건 · 상인</h3>
<ul><li><b>사기</b>: 다른 용사가 올린 물건을 <b>보석</b>으로 사요(거래 돈은 보석뿐). 먼저 산 한 사람만 가져가요. 산 치장이 더 좋으면 바로 껴요.</li>
<li><b>팔기</b>: 값을 정해 올리면 <b>다른 용사가 사 가요</b>(NPC가 사 가지 않아요). 한 번에 <b>10개</b>까지, <b>사흘</b> 동안 진열돼요.
올릴 수 있는 것: 장신구·신화 보물·<b>치장</b>·재료·쇳가루·고삐 조각·신화 조각·원한 조각·인삼/산삼 탕약·숫돌. <b>기본 장비(무기·방어구 조각)는 거래할 수 없어요.</b></li>
<li><b>내 물건</b>: 팔린 물건의 값을 <b>수수료 5%</b>를 떼고 받고, 안 팔린 물건은 내려서 돌려받아요.</li>
<li><b>상인</b>: 보부상 덕보가 <b>12시간마다</b>(0시·12시) 바뀌는 다섯 가지 물건을 하나씩 팔아요. 바뀔 때마다 <b>2%</b> 확률로 <b>귀한 물건</b>(전설 치장·전설 장신구) 하나를 <b>보석 2,000</b>에 가져와요(나오면 기록에 알려 줘요). 온라인이 아니어도 거래할 수 있어요.</li>
<li>다른 용사와의 거래는 <b>온라인 서버에 로그인</b>했을 때만 돼요.</li></ul>
""", ('bag', '가방'), ('market', '장터 마을'), ('marketnpc', '장터 · 상인'), kicker='16'))
    S.append(sec('천공의 탑 · 태초의 신 · 결투', """
<h3>천공의 탑 ([더보기] → 천공의 탑, Lv.30부터)</h3>
<ul><li><b>1~300층</b>. 층마다 세기가 정해진 수호자와 혼자 60초(1~40층 이승 · ~100 저승 · ~160 천계 · ~230 부상 · ~300 곤륜만큼). 띠마다 끝 몇 층은 <b>그 세계 이야기 끝보다 더 세서</b> 다음 세계에서 세진 뒤에 넘어요(300층 = 곤륜 95단계만큼). 10층마다 문지기(전멸기). 쓰러지면 바로 실패.</li>
<li><b>기술 조합·장비를 저절로 바꾸지 않아요.</b> 들어가기 전 <b>정비 창</b>에서 지금 기술을 확인하고 저장한 조합(3칸)을 불러와요.</li>
<li>지면 하루 5번 가운데 하나를 써요(이기면 안 씀). 처음 오른 층마다 보석·쇳가루, 10층마다 높은 등급 무기·갑옷, 50·150·250층 날개, 100·200층 탈것(운룡·천마).</li></ul>
<h3>탑 301~400층 (4부 동해부터)</h3>
<ul><li>동해에 들어서면 탑이 <b>물 밑으로</b> 이어져요. 301~330층 동해 · 331~365층 남쪽 바다 · 366~400층 깊은 바다의 보스. 4부를 끝낸 용사도 끝 몇 층은 5부에서 세진 뒤에 넘어요.</li>
<li>10층마다 <b>유물 장비</b>(무기·갑옷·투구·어깨·신발을 돌아가며), 5로 끝나는 층마다 호박석, 350층 날개 「지느러미 날개」, 400층 유물 탈것 「용마」.</li></ul>
<h3>태초의 신 (최종 레이드)</h3>
<p>300층을 오르면 깨어나요. 나 + 다른 용사 3명, 180초, 전멸기 세 번과 창세의 빛. 처음 이기면 엔드 아이템 「태초의 씨앗」·「태초의 날개」·별호, 주마다 처음 이기면 엔드 상자(엔드 아이템 하나는 꼭).</p>
<h3>결투 ([더보기] → 결투)</h3>
<p>상대 목록에서 골라 1:1로 60초(하루 5번). 상대도 용사와 같은 크기로 걸어오며 기본 공격·직업 기술·초각성을 써요. 결투에서는 물약 없이, 회복은 절반, 한 방은 상대 체력의 25%까지 — 세기가 같으면 반쯤 이겨요. 이기면 결투 점수, 점수 구간마다 칭호와 별호.</p>
<h3>4부 바다 · 첫째 바다 「동해 용궁」 (46~52장, 레벨 516)</h3>
<p>곤륜 이야기(45장, 레벨 500)를 마치면 태초의 신이 <b>마지막 시련</b>을 내려요. [수련] → [환생]의 <b>「동해로 건너기」</b>로 대왕암 앞바다에 가요. 부상·곤륜으로 건널 때처럼 레벨·장비·능력치·엽전은 그대로이고 사냥 단계만 1부터예요. 길잡이는 자라 <b>별주</b>.</p>
<ul><li><b>지역 셋</b>(10단계씩): 대왕암 앞바다 · 산호 숲 · 용궁 뜰. 산호 숲부터는 물 밑이에요.</li>
<li><b>이야기 일곱 장</b>: 울지 않는 만파식적, 수로부인과 바다의 노래, 명궁 거타지, 별주와 토끼의 간, 처용의 춤, 연오랑과 세오녀, 동해 용왕의 시험. 장마다 여는 연출·고비·닫는 연출이 있고 노래 장면도 있어요. 언제든 넘길 수 있고 [정보] → 다시 보기에서 다시 볼 수 있어요.</li>
<li><b>레이드 셋</b>: 동해 해룡(47장) · 역신의 밤(50장) · 동해 용왕의 시험(52장). 새 칸 장비(가끔 유물)와 호박석이 나와요. 동해에 들어서면 곤륜 레이드의 「진」도 열려요.</li>
<li><b>5차 전직</b>(동해 · 레벨 505 · 46장 뒤): 무사 해룡장 · 자객 잠영 · 술사 조수사 · 도인 용신무. 공격력·체력 +330%, 기술 피해 +180%, 최대 마나 120, 광역기 하나와 버프기 하나. 싸움에 들고 가는 기술은 그대로 8칸이에요.</li>
<li><b>신화 보물 셋</b>(이야기 보상): 처용 탈(보스 피해) · 세오녀의 비단(치명타 피해·경험치) · 용왕의 옥대(체력·받는 피해 감소).</li>
<li><b>해태 수련</b>([레이드], 46장부터): 30초 동안 돌 해태를 쳐요. 뿔이 빛날 때 친 것은 두 배, 눈이 붉을 때 치면 불이 되돌아오니 [구르기]로 물러서요. 등급 1~7.</li>
<li>진행 시간(쉬지 않고 잘 키운 자동 시뮬): 5차 전직 약 6~8시간, 첫째 바다 끝 약 18~24시간.</li></ul>
<h3>4부 바다의 새 놀거리</h3>
<ul><li><b>수군 야행</b>([레이드] → [백귀야행] 아래, 남쪽 바다부터): 물귀신 행렬을 60초 동안 잡아요(하루 2번). 20초마다 <b>밀물</b>로 판의 절반이 잠기니 마른 쪽으로 걸어요. 끝의 「물어귀 대장」을 잡으면 고삐 조각·치장(드물게 유물)·바다의 넋 구슬 기회.</li>
<li><b>용궁 보물고</b>([레이드] → [보물 동굴] 아래, 52장 뒤): 방 셋(문어 문지기 → 함정 방 → 광어 창고지기). 방을 깰 때마다 상자 하나(호박석·장비·재물)를 골라요. 끝까지 가면 7%로 신화 보물 「용궁 야광주」. 하루 2번.</li>
<li><b>용왕 강림</b>([레이드] → [강림] 아래, 52장 뒤): 요일마다 다른 바다의 용왕, 전멸기 두 번. 호박석과 용왕 아바타 넷(25%, 8번 안에 꼭).</li>
<li><b>타임 보스 「심해」</b>(동해부터): 지옥 위 난이도. 전멸기 두 번, 보상은 지옥의 2배 + 호박석. <b>1일 보스</b>는 4부 용사에게 짝수 날마다 바다 보스(4부 치장, 드물게 유물).</li>
<li><b>손컨 패턴 「물살」·「숨」</b>: 바다 보스가 물살을 일으키면 용사가 떠밀려요 — 붉은 쪽 반대편 땅을 눌러 거슬러 걷거나 [구르기]로 버텨요. 깊은 바다의 보스 싸움에서는 숨 막대가 줄고, 판에 솟는 공기 방울을 밟으면 차요. 가만히 두어도 용사가 알아서 대응해요.</li>
<li><b>새 물건</b>: 펫 다섯(용궁 자라·꾀 많은 토끼·아기 곰새기·점박이 물범·신화 환수 불개), 탈것 셋(곰새기·큰 거북·유물 용마), 넋 구슬 여섯(문무대왕·영등할망·심청·수로부인·연오랑·개양할미), 치장 22가지와 유물 치장, 세트 「해녀」·「용궁」, 조합 공방 10~12단계 「용궁」.</li></ul>
<h3>4부 바다 · 둘째 바다 「남쪽 바다」 (53~59장, 레벨 533) · 셋째 바다 「깊은 바다」 (60~67장, 레벨 550)</h3>
<p>동해 이야기(52장, 레벨 516)를 마치면 [수련] → [환생]의 <b>「남쪽 바다로 건너기」</b>, 남쪽 바다 이야기(59장, 레벨 533)를 마치면 <b>「깊은 바다로 건너기」</b>가 열려요. 건너도 레벨·장비·능력치·엽전은 그대로, 사냥 단계만 1부터예요.</p>
<ul>
<li><b>남쪽 바다 일곱 장</b>: 바다를 지키는 할머니 신들 — 영등할망, 설문대할망과 오백 아들 바위, 인당수의 심청, 개양할미, 이어도, 해가 둘 달이 둘이던 날, 용이 못 된 강철이. 지역은 바람 섬 · 인당수(물 밑) · 칠산 바다.</li>
<li><b>깊은 바다 여덟 장</b>: 숨비소리, 고래의 뱃속 마을, 용들의 무덤, 물과 불의 뿌리, 꽃 피우기 내기, 첫 거짓, 형의 자리, 물의 신화(4부 끝). 지역은 해녀의 물길 · 고래 뱃속 · 물 밑 꽃밭. 까치는 물가에 남고 별주가 길을 잡아요.</li>
<li><b>레이드 여섯</b>: 남쪽 바다 외눈박이 거인(1-6) · 칠산의 풍랑(3-4) · 강철이(4-8), 깊은 바다 용들의 무덤(3-2) · 첫 거짓(4-2) · 검은 물의 바다(4-6). 괄호 안 단계에 닿고 그 이야기가 되면 열려요. 다음 바다에 들어서면 지나온 바다 레이드의 「진」이 열려요.</li>
<li><b>신화 보물 「인당수 연꽃」</b>(55장): 체력 +50%, 보스·레이드 싸움마다 쓰러져도 한 번 더 일어나요(불사약과 따로).</li>
<li>4부 한 바퀴는 쉬지 않고 잘 키우면 약 56~71시간이에요(첫째 바다 18~24 · 둘째 19~23 · 셋째 19~26시간).</li>
</ul>
<h3>투구 · 어깨 · 신발 (4부 바다부터)</h3>
<p>바다에 들어서면 장비에 세 칸이 더 생겨 모두 다섯 칸이 돼요. <b>투구</b>는 체력·기술 피해, <b>어깨</b>는 공격력·보스 피해, <b>신발</b>은 공격·이동 속도와 받는 피해 감소. 무기·방어구처럼 소환·합성·재련(+25까지)하고, 용사 모습에도 등급 색으로 그려져요([장비] → [투구]에서 투구 대신 머리 장식을 보이게 고를 수 있어요). 세 칸의 재련 값은 지금 땅의 엽전 기준이에요.</p>
<ul><li><b>3차 계승</b>: 바다에 들어서면 대장장이 쇠돌이 무기·방어구 재련을 효과 그대로 +15부터 다시 벼리게 해 주고, 곤륜까지의 재료를 바다 재료 <b>용궁 진주</b>로 1:1 바꿔 주고, 새 세 칸에 낄 한 벌(희귀 I)과 호박석 3개를 줘요.</li>
<li><b>유물</b>: 전설 위의 4부 등급(청록빛). 소환·전설 합성으로는 안 나오고 바다의 수문장·레이드, 상위 레이드 「진」에서만 나와요. 유물끼리는 4개 합성.</li></ul>
<h3>호박석 세공 ([장비] → [세공], 4부 바다부터)</h3>
<p>장비 다섯 칸에 <b>호박석</b>을 하나씩 박고 깎아 <b>문양</b>을 새겨요. 호박석 하나에 줄 셋(좋은 문양 둘 + 나쁜 문양 하나)이 있고, 한 번에 한 줄 한 칸씩 깎아요. <b>성공 확률은 75%에서 시작해 성공하면 −10%, 실패하면 +10%</b>(25~75%)라, 확률이 높을 때 좋은 줄을, 낮을 때 나쁜 줄을 깎아요(화면에 「추천」 줄이 보여요). 깎는 데는 엽전만 들어요.</p>
<ul><li>문양: 파도(공격력) · 암초(체력) · 해일(기술 피해) · 작살(보스 피해) · 물때(기술 재사용 감소) · 등대(치명타 피해) · 순풍(경험치·엽전) · 닻(받는 피해 감소)</li>
<li>다섯 호박석의 <b>같은 문양 빛을 합쳐 10 · 20 · 30개에 1 · 2 · 3단</b> 효과. 나쁜 문양(녹·균열·이끼·뻘)은 빛 5개부터 효과가 나오니 4개 아래로 막으면 무해해요.</li>
<li>호박석 등급: 희귀(줄마다 6칸) · 영웅(8칸) · 전설(10칸). 새 호박석을 박으면 있던 돌은 사라지고 처음부터 깎아요.</li></ul>
<h3>장비 공명 · 세트 ([장비] → [세트])</h3>
<p>낀 무기·갑옷 등급이 높을수록 장신구·치장·변신·탈것·아바타 효과가 커져요(전설 1배 · 신화 각성 1.1배 · 태초 1.2배, 영웅 0.93배). 정해진 무기·갑옷 등급 + 아바타·탈것·장신구·변신을 맞추면 세트 효과(한 번에 하나).</p>
""", ('towerpage', '천공의 탑'), ('towerfight', '탑 전투'), ('pvppage', '결투'), kicker='17'))
    S.append(sec('상점 · 채팅 · 정보', """
<h3>상점</h3>
<ul><li>물약: <b>인삼 탕약</b>(체력 30% 아래면 저절로 마셔 40% 회복, 10개·100개 묶음) · <b>산삼 탕약</b>(보스·레이드에서 먼저 마셔 전부 회복) · <b>감로수</b>(마나 물약, 마나 30 아래면 +40). 체력·마나는 저절로 천천히 차니 물약을 넉넉히 사 두세요. 전투 화면 기술 줄 위 <b>물약 칸</b>에 개수가 보이고 누르면 바로 마셔요.</li>
<li>부적(10분, 겹쳐 사면 최대 60분): 범(공격력 +30%) · 바람(공격 속도 +20%) · 거북(받는 피해 -20%) · 복주머니(엽전 +50%) · 글공부 두루마리(경험치 +50%)</li>
<li><b>10+1 묶음</b>: 숫돌·산삼 탕약을 10개 값에 11개(숫돌 묶음 보석 250, 산삼 묶음 120). 가방에 999개까지.</li>
<li>재료: 숫돌 · 토벌패(하루 3개) / 꾸러미: 엽전 꾸러미 · <b>꾸미기 상자</b> · <b>오늘의 선물</b>(하루 한 번 공짜)</li></ul>
<h3>화면 방향</h3><p>오른쪽 위 <b>[화면 돌리기]</b> 아이콘으로 휴대폰을 돌리지 않고 가로·세로 배치를 바꿔요. [정보] → 화면 방향에서 자동(기기 방향)·가로·세로를 고르고, 고른 것은 기억해요. 휴대폰이 화면 방향을 바꿀 수 없으면 게임 화면을 돌려서 보여 줘요.</p>
<h3>채팅</h3><p>지금 접속한 다른 용사들, 그리고 주민들과 이야기해요. 신화 보물·레이드 성공 같은 소식도 받아요. 말하면 용사 머리 위에 말풍선이 뜨고, 용사가 한 말(내 말·다른 용사의 말)은 <b>확성기 공지처럼 게임 화면 위 가운데에 띠로</b> 잠깐 떠요([정보] → 채팅 확성기에서 끌 수 있어요). 나쁜 말은 가려져요. 온라인이면 채팅창 위에 <b>지금 접속 중인 용사</b>(이름·직업·레벨·세계)가 보여요.</p>
<h3>정보</h3><p>꾸미기 · 캐릭터 바꾸기 · 로그아웃 · 업데이트 소식 · 이야기 다시 보기 · 앱으로 설치.</p>
<h3>별호</h3><p>몬스터 1만 마리·레이드 100번·첫 환생·바다 건너기처럼 이룬 일에 따라 별호 18가지를 얻어요. 하나를 달면 이름표 위에 금빛으로 보이고 그 효과가 붙어요. 가진 별호마다 공격력·체력 +0.5%.</p>
<h3>급보</h3><p>사냥 중 10분 안팎마다 금빛 손님(황금 도깨비·보물 너구리·떠도는 넋)이 나타나요. 20초 안에 잡으면 엽전·보석·경험치를 크게 줘요.</p>
<h3>배럭 효과 · 본캐</h3><p>같은 계정의 캐릭터끼리 서로 도와요. 다른 캐릭터 가운데 가장 높은 <b>누적 레벨</b> 50마다 공격력·체력 <b>+1%</b>(최대 15%), 다른 캐릭터 한 명마다 엽전 <b>+2~10%</b>(경험치는 그 35%), 보석은 그 절반. [정보]에서 <b>본캐</b>를 정하면 본캐는 배럭 효과를 받지 않아요.</p>
<h3>내 정보</h3><p>왼쪽 위 상태창(얼굴)을 누르면 낀 장비·장신구·비전 장비·치장·변신·탈것·아바타와 능력치를 한 화면에서 봐요. 아래 메뉴는 다섯 + [더보기](퀘스트·상점·정보·가방·내 정보·천공의 탑·결투).</p>
""", ('shop', '상점'), ('chat', '채팅'), ('rec', '정보'), kicker='17'))
    S.append(sec('진행 시간표 (참고)', """
<p>쉬지 않고 잘 키웠을 때(자동 시뮬레이션 네 직업 평균)의 대략적인 시간이에요. 사람마다, 뽑기 운마다 달라요.</p>
<table><tr><th>시점</th><th>도달</th></tr>
<tr><td>약 1.5~2시간</td><td>레벨 50 · <b>1차 전직</b></td></tr>
<tr><td>약 4~6시간</td><td>이승 100단계 — 이 무렵부터 한 단계에 오래 머물러요</td></tr>
<tr><td>약 7~15시간</td><td>무기 +25 · 다섯 시련 → <b>첫 환생(저승)</b></td></tr>
<tr><td>약 25~40시간</td><td>저승 레벨 200 · 저승 이야기 끝 → 히든 퀘스트 · <b>숨겨진 2차 전직</b> · <b>마지막 환생(천계)</b></td></tr>
<tr><td>약 85~100시간</td><td>신과의 전쟁 끝 · <b>신화</b>(이야기 113개) → 바다 건너 <b>부상</b>(2부). 뽑기 운이 나쁘면 더 걸려요</td></tr>
<tr><td>건넌 뒤 약 30~42시간</td><td>레벨 350 · 스승의 장을 마치면 <b>3차 전직</b> (술사가 가장 빨라요)</td></tr>
<tr><td>건넌 뒤 약 70~85시간</td><td>레벨 400 · <b>부상 이야기 끝</b>(이야기 145개) → 서쪽 하늘 <b>곤륜</b>(3부)</td></tr>
<tr><td>곤륜에서 약 95~120시간</td><td>레벨 480 · 세 스승의 시험 → <b>4차 전직</b></td></tr>
<tr><td>곤륜에서 약 120~160시간</td><td>레벨 500 · <b>곤륜 이야기 끝</b>(이야기 182개) → '끝없는 신화'</td></tr></table>
<p class="small">쉬지 않고 잘 키웠을 때(자동 시뮬레이션) 기준이에요. 하루 10~15시간쯤 방치하면 신화까지 <b>열흘 안팎</b>, 부상 끝까지 <b>일주일쯤 더</b>, 곤륜 끝까지 <b>열흘 남짓 더</b>. 직업·뽑기 운·접속 간격에 따라 달라요.
<b>조합 공방</b>을 쓰지 않으면 저승은 1.5배, 천계는 2배쯤 오래 걸리고 160시간 안에 신화에 닿지 못했어요.</p>
""", kicker='18'))
    S.append(sec('자주 묻는 질문', """
<p><b>Q. 다른 폰에서도 이어서 할 수 있나요?</b><br>네! 계정과 기록이 <b>온라인 서버</b>에 저장돼서, 다른 휴대폰이나 PC에서도 같은 아이디·비밀번호로 로그인하면 이어서 할 수 있어요.
인터넷이 끊겨도 그 기기에 저장해 두었다가 다시 연결되면 서버에 올려요. 서버가 생기기 전에 만든 계정은 로그인할 때 서버로 옮겨져요.</p>
<p><b>Q. 창을 닫아 두면?</b><br>최대 12시간까지 오프라인 보상이 쌓여요. 켜 두고 스킬 자동으로 사냥할 때 잰 속도로 계산해서 <b>경험치는 1.25배</b>, 엽전·보석은 0.85배예요. [보스 자동]이면 그동안에도 처치 25마리마다 <b>단계 보스에 도전</b>해서, 이기면 다음 단계로 오르고 한 단계에서 5번 지면 그 사냥터에서 계속 사냥해요. 오프라인 시간을 모두 더해 24시간이 될 때마다 3% 확률로 신화 보물도 나와요. 부적 시간은 게임을 켜 둘 때만 줄어요.</p>
<p><b>Q. 앱으로 설치하려면?</b><br>안드로이드: Chrome·삼성 인터넷 메뉴(점 세 개) → [앱 설치]/[홈 화면에 추가] · 아이폰: Safari [공유] → [홈 화면에 추가] ·
PC: Chrome·Edge 주소창 오른쪽 설치 단추. 설치하면 주소창 없이 전체 화면으로 열리고 인터넷이 없어도 돌아가요.
(아이폰은 설치한 앱과 Safari의 저장 공간이 따로라 앱에서 계정을 새로 만들어야 해요.)</p>
<p><b>Q. 보스에게 자꾸 쓰러져요.</b><br>새 단계의 보스는 세게 때려요. 체력·방어구 재련·방어 펫·<b>비전 갑옷</b>(조합 공방)으로 버티고, 인삼 탕약을 챙겨요.
술사는 <b>마력 보호막</b>을 보스가 나올 때 직접 눌러 쓰면 좋아요. 붉은 칸을 <b>직접 피하고</b> 금빛 「!」에 <b>되받기</b>를 누르면 훨씬 덜 맞아요. 같은 단계에서 조금 더 키우면 덜 아파요.</p>
<p><b>Q. 사이트 데이터를 지우면?</b><br>온라인 서버에 저장된 기록은 남아요. 같은 아이디로 다시 로그인하면 돼요.</p>
<p class="tip">글꼴: Pretendard(SIL OFL 1.1, 이 게임에서는 SamhanSans라는 이름으로 일부 글자만 담음). 음악·효과음은 게임 안에서 직접 만들어 내는 소리예요.
그림·이야기·이름은 이 게임을 위해 새로 만들었어요.</p>
""", kicker='19'))
    cover = f"""<div class="cover"><div class="sub">플레이 매뉴얼</div><h1>삼한 용사 키우기</h1>
<img src="{jpg('title')}"><p>옛 한국 신화 속 방치형 RPG</p><p>benaeend.github.io/samhan-hero</p></div>"""
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{css}</style></head><body>{cover}{"".join(S)}</body></html>'


async def main():
    async with async_playwright() as p:
        browser = await tg.launch(p)
        ctx = await browser.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2)
        page = await ctx.new_page()
        errors = []
        tg.watch(page, errors)
        await capture(page)
        await ctx.close()
        out = SHOTS / 'manual.html'
        out.write_text(html(), encoding='utf-8')
        pg = await browser.new_page()
        await pg.goto(out.as_uri())
        await pg.wait_for_timeout(800)
        PDF.parent.mkdir(parents=True, exist_ok=True)
        await pg.pdf(path=str(PDF), format='A4', print_background=True,
                     display_header_footer=True, header_template='<span></span>',
                     footer_template='<div style="font-size:8px;color:#8a93a6;width:100%;text-align:center"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
                     margin={'top': '14mm', 'bottom': '16mm', 'left': '13mm', 'right': '13mm'})
        await browser.close()
    print('매뉴얼:', PDF.relative_to(ROOT), f'({PDF.stat().st_size:,} bytes)')
    if errors:
        print('게임 오류:', errors)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
