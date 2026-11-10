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
<li><b>함께하기</b>: 레이드(나 + NPC 동료 3~10인), 3시간마다 나타나는 타임 보스(2명 이상), 채팅.</li></ul>
<div class="tip">주소: <b>benaeend.github.io/samhan-hero</b> · 휴대폰 홈 화면에 앱으로 설치할 수 있어요(아래 '앱으로 설치' 참고).</div>
<h3>차례</h3><ol class="toc"><li>시작하기·계정</li><li>화면 보기</li><li>수련·스테이지</li><li>기술·초각성기</li><li>장비·재련·조합 공방</li><li>신화 보물·장신구·변신</li><li>전직</li><li>아바타</li><li>펫</li><li>퀘스트·이야기</li><li>레이드</li><li>타임 보스</li><li>환생·저승</li><li>천계·신과의 전쟁</li><li>제2부 · 부상</li><li>상점·채팅·정보</li><li>진행 시간표·자주 묻는 질문</li></ol>
""", kicker='들어가며'))
    S.append(sec('시작하기 · 계정 만들기', """
<ul><li>첫 화면에서 <b>[회원가입]</b> → 아이디·비밀번호를 정해요. 비밀번호는 기기 안에 암호(해시)로만 저장돼요.</li>
<li>한 계정에 <b>캐릭터 4명</b>까지 만들 수 있어요. 이름은 이 기기 안에서 겹칠 수 없어요.</li>
<li>오른쪽 위 <b>♪</b> 단추로 배경음악·효과음을 켜고 꺼요(국악풍 가야금·대금·장구 소리).</li></ul>
<h3>직업 4가지</h3>
<table><tr><th>직업</th><th>특징</th><th>무기</th></tr>
<tr><td>무사</td><td><b>균형</b> — 체력이 높고 받는 피해 -10%. 모든 기술을 고루 써요(근접)</td><td>검</td></tr>
<tr><td>자객</td><td><b>보스 특화</b> — 보스 피해 +30%, 몹 떼는 느려요. 공격 펫·장신구와 궁합이 좋아요(근접)</td><td>단검</td></tr>
<tr><td>술사</td><td><b>늦게 피는 꽃</b> — 처음엔 약하고 레벨이 오를수록 강해져요. 몸이 약해 보호막이 중요(원거리)</td><td>지팡이</td></tr>
<tr><td>도인</td><td><b>한 방</b> — 공격 기술 3개뿐, 준비 기술을 쌓아 가장 큰 한 방. 레이드에서 동료 치유(원거리)</td><td>부채</td></tr></table>
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
<li><b>오른쪽 아래</b>: 기술 칸. 저절로 쓰고, <b>누르면 바로</b>, <b>길게 누르면 그 기술만 자동/수동</b>. 그 위 <b>[자동/반자동]</b>·<b>[보스 자동/수동]</b>·[속도] 단추.</li>
<li><b>[자동]</b>은 사냥도 기술도 알아서, <b>[반자동]</b>은 사냥은 알아서 하고 기술은 직접 눌러 써요. <b>[보스 자동]</b>은 몹을 다 잡으면 보스에게 알아서 도전하고(지면 45초 수련 뒤 다시), <b>[보스 수동]</b>은 오른쪽 아래 <b>큰 보스 단추</b>가 「도전!」으로 빛날 때 눌러야 보스가 나와요. 큰 보스 단추의 금빛 고리는 보스까지 남은 처치만큼 차오르고, 싸우는 중에는 보스 체력과 남은 시간을 보여 줘요.</li>
<li><b>장면 누르기</b>: 땅을 누르면 용사가 그 칸으로 걸어가요(금빛 마름모 표시). 몬스터를 누르면 그 몬스터부터 쳐요. [반자동]이면 도착한 자리에서 6초 동안 버티며 닿는 적만 치고, 그 뒤로는 다시 알아서 사냥해요.</li>
<li><b>아래 메뉴 9칸</b>: 수련 · 기술 · 장비 · 펫 · 퀘스트 · 레이드 · 상점 · 정보 · 가방. 누르면 장면 위에 <b>별도 화면</b>이 열리고, 같은 메뉴나 ✕로 닫아요. 빨간 점은 받을 보상이나 할 일이 있다는 뜻이에요. (세로로 들면 메뉴가 화면 아래, 기술 칸은 장면 아래에 놓여요)</li>
<li>레벨업·재련·소환·조합을 하면 화면에 빛과 글자 연출이 나와요. 기술을 쓰면 바닥 마법진·충격파·빛기둥·유성과 큰 기술 이름이 떠요.</li></ul>
<h3>여정 지도</h3>
<p>오른쪽 위 <b>미니맵</b>(또는 [퀘스트] → 여정 지도)을 누르면 이승 → 저승 → 천계 → 부상 → (3부) 땅이 한 장의 길로 보여요. 깬 땅은 금테·✓, <b>지금 있는 땅</b>에는 내 용사가 서 있고, 앞으로 갈 땅은 어둡거나 자물쇠예요. 땅마다 그곳의 <b>이야기 장 표시</b>가 붙어 있고, 누르면 지역 보스·몬스터·레이드·내 기록이 나와요.</p>
""", ('play', '사냥 화면'), ('map', '여정 지도'), kicker='2'))
    S.append(sec('수련 · 스테이지', """
<p><b>[수련]</b>에서 엽전으로 능력치를 올려요: 공격력 · 체력 · 치명타 확률 · 치명타 피해 · 공격 속도 · 체력 회복.
×1 / ×10 / 최대 단추로 한 번에 여러 번 올릴 수 있고, <b>길게 누르면</b> 계속 올라가요.</p>
<ul><li>몬스터를 잡으면 엽전·경험치, 가끔 <b>보석</b>(4.5% 확률로 1~2개)과 <b>조합 재료</b>를 얻어요.</li>
<li>새 단계의 <b>보스는 세게 때려요</b>. 체력·방어 펫·물약·보호막으로 버텨요. 같은 단계에서 더 강해지면 덜 아파요.</li>
<li>단계마다 몬스터 <b>25마리</b> → 보스. 사냥터에는 몹이 7마리부터 많게는 16마리까지 한꺼번에 나와요. 10단계마다 지역이 바뀌어요(마을 어귀 → 대나무 숲 → 바위 고개 → 안개 늪 → 도깨비 굴 → 백두 설원 → …).</li>
<li>각 지역의 <b>9번째 단계</b>는 <b>수문장</b>(서브 보스)이 지켜요. 수문장에게서만 장신구가 잘 떨어져요.</li>
<li>레벨 상한: 이승 <b>100</b>, 저승 <b>200</b>.</li></ul>
<div class="tip"><b>난이도 흐름</b>: 처음 50~60단계까지는 쭉쭉 올라가요. 이승 70단계 무렵부터 한 단계에 수십 분, 100단계 근처부터는
<b>한 단계에 1~2시간</b>, 저승 90단계를 넘으면 <b>2~4시간</b>씩 방치해야 넘을 수 있어요. 막히면 장비·재련·펫·레이드로 힘을 키워요.</div>
""", ('grow', '수련 탭'), kicker='3'))
    S.append(sec('기술 · 초각성기', """
<p>직업마다 기술 8개가 있어요. <b>Lv.5 · 12 · 25 · 40 · 60 · 80</b>에 하나씩, 그리고 <b>1차·2차 전직</b> 때 하나씩 열려요(도인의 6번째 칸은 <b>환생</b>하면). [기술]에서 엽전으로 강화하고, 맨 위에 <b>직업 특성</b>이 나와요.</p>
<table><tr><th>칸</th><th>무사</th><th>자객</th><th>술사</th><th>도인</th></tr>
<tr><td>1</td><td>회오리 베기</td><td>그림자 베기</td><td>불꽃 고리</td><td><b>천벌 부적</b>(공격)</td></tr>
<tr><td>2</td><td>일섬</td><td>급소 찌르기</td><td>벼락</td><td>봉인 부적(준비)</td></tr>
<tr><td>3</td><td>투혼</td><td>바람 걸음</td><td><b>마력 보호막</b></td><td>회복의 기운(준비)</td></tr>
<tr><td>4</td><td>천지 가르기</td><td>비도 난무</td><td>유성우</td><td>도력 모으기(준비)</td></tr>
<tr><td>5</td><td>천둥 연격</td><td>그림자 연환</td><td>얼음 창 세례</td><td>팔괘진(준비)</td></tr>
<tr><td>6</td><td>기세 꺾기</td><td>급소 낙인</td><td>마력 저주</td><td><b>하늘의 심판</b>(공격, 환생 뒤)</td></tr>
<tr><td>7</td><td>장군의 호령</td><td>월영 난무</td><td>칠성 낙뢰</td><td><b>오방신장 소환</b>(공격, 1차)</td></tr>
<tr><td>8</td><td>신장 강림</td><td>귀영 천살</td><td>태극 천벌</td><td>만신 대굿(준비, 2차)</td></tr></table>
<div class="tip"><b>기술 조작</b>: 아래 기술 칸을 <b>누르면 바로</b> 쓰고, <b>길게 누르면 자동/수동</b>을 바꿔요. 수동 기술은 준비되면 반짝여요.
술사는 보스가 나올 때 <b>마력 보호막</b>을, 도인은 봉인·도력·팔괘를 다 건 뒤 <b>하늘의 심판</b>을 직접 누르면 가장 커요.</div>
<h3>초각성기</h3>
<p>환생 후 <b>저승 Lv.60 + 시왕 레이드 「송제전」 토벌</b>을 이루고 이야기 퀘스트 「각성의 시련」을 깨면 배워요.
레이드·타임 보스마다 <b>한 번</b>, 싸움 시작 12초 뒤나 보스 체력이 60% 아래로 내려가면 저절로 써요(공격력의 150배 피해).
무사 「개천 일격」 · 자객 「월하 만영참」 · 술사 「천화 강림」 · 도인 「사신 강림」.</p>
""", ('skill', '기술 탭'), kicker='4'))
    S.append(sec('장비 · 재련', """
<p><b>[장비] → [무기]/[방어구]</b>: 보석으로 소환(1회 50 · 10회 450)해요. 같은 장비 4개는 한 단계 위로 <b>합성</b>돼요.
등급은 일반 · 고급 · 희귀 · 영웅 · 전설(각 Ⅰ~Ⅳ). 가진 장비 전부가 조금씩, 장착한 장비가 크게 능력을 올려요.</p>
<p>장비 등급이 오르면 <b>용사 그림도 바뀌어요</b>(무기 모양·갑옷 무늬·허리띠 색).</p>
<h3>재련 — 세계마다 한도, 확률 공개</h3>
<ul><li>엽전 + 쇳가루로 무기·방어구를 벼려요. +1~+3은 반드시 성공, 그 뒤로 확률이 내려가요(+25는 15%). 화면 아래에 모든 단계의 확률이 나와요.</li>
<li><b>재련 한도</b>: 무기는 이승에서 +25까지. 방어구는 이승 +15 → 저승 +22 → 천계 +25까지 열려요.</li>
<li><b>2부 계승</b>: 바다를 건너면 무기·방어구가 계승되어 <b>+15부터 다시</b> 벼려요. 1부에서 쌓은 재련 효과는 그대로 남고, 성공 확률은 1부의 70%예요.</li>
<li>실패하면 보통 <b>그대로</b>지만, +11부터는 <b>한 단계 떨어질</b> 수 있어요(+10·+15·+20에서는 안 떨어짐).</li>
<li>+17부터는 아주 가끔 <b>부서져</b> +15(+21부터는 +20)로 돌아가요. <b>보호</b>를 켜면 +16~+19에서 보석을 두 배 내고 부서짐을 막아요.</li>
<li><b>두 번 연달아 떨어지면</b> 다음 재련은 <b>반드시 성공</b>(기회의 불꽃)!</li>
<li>상점의 <b>숫돌</b>을 함께 쓰면 성공 확률이 1.15배가 돼요. <b>무기 +25는 첫 환생 조건</b>이에요.</li></ul>
""", ('gear', '장비 소환'), ('refine', '재련'), kicker='5'))
    S.append(sec('조합 공방', """
<p>[장비] → <b>[조합]</b>에서 직업 전용 <b>비전 무기 · 비전 갑옷 · 노리개</b>를 만들어요. 이승·저승·천계마다 3단계씩, 모두 <b>9단계</b>예요.</p>
<ul><li><b>조합식</b> = 이전 단계 + 그 세계 <b>재료</b>(요괴 정수 · 망자의 넋 · 하늘 조각) + 소환으로 모은 같은 칸 <b>장비</b>(노리개는 보석).</li>
<li>재료는 보스 1개 · 수문장 3개 · 레이드 4개(첫 토벌 +6) · 타임 보스 8개, 몬스터도 가끔 줘요.</li>
<li>더 깊은 단계에 닿으면 <b>다음 조합식</b>이 열려요(이승 21·51·91단계, 저승 1·51·91단계, 천계 1·41·76단계).</li>
<li>성공 확률은 단계마다 100% → 40%. 실패하면 재료 절반만 사라지고, 실패가 쌓이면(천장) 다음은 확정 성공.</li>
<li><b>각인</b>: 칸마다 셋 중 하나(무기: 파쇄·사냥·급소 / 갑옷: 철벽·신속·생기 / 노리개: 술력·도력·공명). <b>직업에 맞는 최적 각인</b>은 1.5배,
세 칸이 모두 최적이면 <b>조화</b>(공격력·체력 +15%).</li></ul>
<table><tr><th>직업</th><th>최적 조합</th></tr>
<tr><td>무사</td><td>파쇄(공격력) · 철벽(체력·받는 피해↓) · 도력(재사용↓)</td></tr>
<tr><td>자객</td><td>사냥(보스 피해) · 신속(공격 속도) · 공명(펫 피해)</td></tr>
<tr><td>술사</td><td>급소(치명타 피해) · 철벽 · 술력(기술 피해)</td></tr>
<tr><td>도인</td><td>급소 · 생기(체력 회복) · 도력</td></tr></table>
<div class="tip">보스·레이드 세기는 조합 장비를 <b>제때 만든다고 보고</b> 맞췄어요. 만들지 않으면 같은 곳까지 <b>1.5배 넘게</b> 오래 걸려요.</div>
""", ('craft', '조합 공방'), kicker='5'))
    S.append(sec('신화 보물 · 장신구 · 변신', """
<h3>신화 보물 ([장비] → [신화])</h3>
<p>천부인 검(공격력) · 천부인 거울(체력) · 천부인 방울(치명타 피해) · 여의주(엽전·경험치) · 만파식적(기술 피해).
이야기 퀘스트에서 확정으로 받고, 퀘스트 보상을 받을 때 3% 확률·타임 보스·오프라인(누적 24시간마다 3%)에서도 나와요. 어려운 퀘스트일수록 효과가 커요.
종류마다 가장 센 것만 남고 약한 것은 보석 30개로 바뀌어요.</p>
<h3>장신구 ([장비] → [장신구])</h3>
<p><b>반지</b>(공격력) · <b>귀걸이</b>(치명타 피해·기술 피해) · <b>팔찌</b>(체력·공격 속도). 등급 5단계.
각 지역 <b>9번째 단계 수문장</b>을 잡을 때 반지 8% · 귀걸이·팔찌 1.5%, 일반 몬스터에게서는 아주 드물게(귀걸이·팔찌 0.08%).
타임 보스에서도 떨어져요. 이미 더 좋은 것이 있으면 보석 50개로 바뀌어요.</p>
<h3>변신 ([장비] → [변신])</h3>
<p>이야기에서 사신의 힘을 얻어요: <b>주작</b>(공격력 +25%·엽전/경험치 +30%) · <b>청룡</b>(공격력 +40%·기술 피해 +30%) ·
<b>백호</b>(공격 속도 +25%·치명타 +10%) · <b>현무</b>(받는 피해 -30%·체력 +60%). 하나를 골라 두르면 모습이 바뀌어요.</p>
""", ('myth', '신화 보물'), ('acc', '장신구'), ('form', '변신'), kicker='6'))
    S.append(sec('전직', """
<ul><li><b>1차 전직</b>: 레벨 50이 되면 [수련] → [전직]에서 직업의 스승과 겨뤄요(동료 둘과 함께 90초). 이기면 전직!</li>
<li>무사 → <b>장군</b> · 자객 → <b>월영</b> · 술사 → <b>방사</b> · 도인 → <b>무당</b>. 공격력·체력 +30%, 기술 피해 +20%.</li>
<li>전직하면 <b>전직 기술</b>이 열리고, 무기 모양이 바뀌고(술 달린 장검·쌍비수·초승달 지팡이·방울 부채), <b>전직 망토</b>를 받아요.</li>
<li><b>2차 전직</b>은 숨겨져 있어요. 저승 이야기를 끝까지 마치면 누군가 찾아온다는 소문이…(장군 → 신장 · 월영 → 귀영 · 방사 → 천사 · 무당 → 만신, 공격력·체력 +80%)</li>
<li>직업을 바꿔도 전직 단계는 그대로예요. 시험은 지면 몇 번이든 다시 볼 수 있어요.</li></ul>
""", ('job', '전직'), kicker='7'))
    S.append(sec('아바타(꾸미기)', """
<ul><li>[장비] → [아바타]: <b>옷</b>(색동 설빔·도깨비 털옷·선녀 날개옷·곤룡포 등) · <b>망토</b>(전직 망토·밤하늘·용비늘 등) · <b>펫 꾸미기</b>(꼬마 갓·리본·꽃관·금관·황금빛 등).</li>
<li>모습만 바뀌지만, 가진 아바타 하나마다 <b>공격력·체력 +2%</b>(도감 효과)예요.</li>
<li>상점·아바타 화면의 <b>꾸미기 상자</b>(보석 1,000)에서 나오고, 이야기(을지문덕·이순신·제천대성 등)와 전직에서도 받아요.</li>
<li>꾸미기 상자 확률: 옷 6% · 망토 11% · 펫 꾸미기 28% · 위로품(인삼 탕약 10개) 55%. <b>40번</b> 안에 새 옷·망토가 안 나오면 40번째는 확정이에요.</li></ul>
""", ('avatar', '아바타'), kicker='8'))
    S.append(sec('펫', """
<ul><li>보석으로 소환(1회 100 · 10회 900). <b>공격 · 방어 · 지원</b> 세 종류 × 5등급 = 15마리
(들고양이·해동청·아기 범·새끼 백호·삼족오 / 남생이·반달곰·돌거북·해치·황금 해치 / 까치·업두꺼비·삽살개·두루미·봉황).</li>
<li>종류마다 한 마리씩 데려가요. 공격 펫은 함께 싸우고, 방어 펫은 피해를 줄이고, 지원 펫은 체력을 채우거나 엽전·경험치를 늘려요.</li>
<li>소환 확률: 전설 0.5% · 영웅 3.5% · 희귀 13% · 고급 28% · 일반 55%. <b>60번</b> 안에 영웅 이상이 안 나오면 60번째는 영웅 이상 확정.</li>
<li>같은 펫이 또 나오면 <b>별</b>이 올라요(최대 5개, 별마다 효과 +20%).</li>
<li>엽전 + 보석으로 <b>Lv.30</b>까지 강화해요. 펫 하나를 Lv.20으로 키우는 것이 환생 시련 중 하나예요.</li>
<li><b>신화 펫 · 환수</b>(전설보다 위): 2부 부상의 뇌수·바쿠·아마비에, 3부 곤륜의 필방·백택·비휴. 부마다 한 마리(<b>바쿠·백택</b>)는 이야기 보상으로 확정, 나머지는 그 땅에 들어간 뒤 펫 소환에서 <b>0.3%</b>(200번 안에 확정)로 나와요.</li></ul>
""", ('pet', '펫 탭'), kicker='9'))
    S.append(sec('퀘스트 · 이야기', """
<ul><li><b>이야기 퀘스트 113개</b>(25장): 마을 어귀 → 해모수와 유화 → 알에서 태어난 주몽 → 첫 전직 → 엄리대수 → 졸본과 송양왕 → 다물 → 윤회의 시련 →
환생 → 저승의 열 대왕 → 사신의 귀환 → 하늘의 선전포고 → 영웅들의 시험 → 영소보전 → 신화. 다 깨면 '끝없는 신화'로 이어져요.</li>
<li>이야기를 하나 깰 때마다 <b>15초 이내의 짧은 연출</b>이 나와요. [정보]에서 다시 볼 수 있어요.</li>
<li><b>오늘의 할 일 6개</b>(몬스터 300마리·보스 5번·소환 10번·능력치 30번·재련 3번·레이드 1번)와 모두 완료 보너스. 매일 자정에 새로 고쳐져요.</li>
<li><b>퀘스트 행운</b>: 보상을 받을 때 20% 확률로 모든 기술 재사용 시간 초기화, 3% 확률로 신화 보물!</li>
<li>장면 왼쪽 위의 퀘스트를 <b>누르면 그 퀘스트를 하는 곳</b>(재련·레이드·펫 등, 사냥이면 사냥 화면)으로 바로 가요. 퀘스트를 받거나 보상을 받으면 사냥 화면으로 돌아가고, 이야기 연출이 시작되면 열려 있던 메뉴가 저절로 닫혀요.</li>
<li><b>마을 부탁</b>: 채팅 「마을」의 부탁 ▶을 눌러 받아요(100개, 세계마다 이야기 진행에 맞춰 열림). 재련·단계 조건은 이미 이뤘으면 받자마자 끝나고, 다 한 부탁은 저절로 마쳐요.</li></ul>
""", ('quest', '퀘스트 탭'), ('cut', '이야기 연출'), kicker='10'))
    S.append(sec('레이드', """
<ul><li><b>이승 레이드</b>: 레벨 10마다 하나씩 열려요(붉은 산군 멧돼지 · 천년 묵은 여우 · 천하대장군 · 늪의 이무기 · 외눈 도깨비 왕 ·
쇠먹는 불가사리 · 어둑시니 · 성난 해태, 이후 '2단', '3단').</li>
<li><b>시왕 레이드</b>(저승): 저승 레벨 20마다 열 대왕이 하나씩.</li>
<li>파티는 <b>나 + 이 기기의 다른 캐릭터 + NPC 동료</b>로 3~10명. 자동으로 싸우고 <b>90초</b> 안에 보스를 쓰러뜨리면 성공!</li>
<li>보상: 보석 · 엽전 · 장비, 처음 깨면 보너스. 이승 레이드 8곳을 모두 깨는 것이 환생 시련 중 하나예요.</li>
<li>입장은 <b>토벌패</b>(최대 3개, 15분마다 1개 충전). 실패하면 돌려받아요.</li>
<li>다른 용사·동료와 함께하는 싸움(레이드·타임 보스)에서는 반자동이어도 <b>모든 기술이 자동</b>이고, 함께 싸우는 다른 용사도 기술과 초각성기를 써요.</li>
<li><b>허수아비 수련</b>(하루 3번): 30초 동안 넣은 피해로 1~5등급 보상.</li>
<li><b>보물 동굴</b>(하루 2번): 보물 이무기를 60초 안에 쓰러뜨리면 <b>신화 조각</b>(3 + 세계)과 7% 확률로 신화 보물. 신화 조각 30개로 원하는 신화 보물을 하나 만들어요.</li></ul>
""", ('raid', '레이드 탭'), ('raidfight', '레이드 전투'), kicker='11'))
    S.append(sec('타임 보스', """
<ul><li><b>0시부터 3시간마다</b>(0·3·6·9·12·15·18·21시) 30분 동안 나타나요. [레이드] 탭 위쪽에 남은 시간이 보여요.</li>
<li><b>2명 이상</b> 모여야 도전할 수 있어요. 120초 안에 함께 쓰러뜨려요.</li>
<li>난이도 <b>노말</b>(누구나) · <b>지옥</b>(환생해야 도전). 창이 열릴 때마다 난이도별로 한 번씩 보상을 받아요.</li>
<li>기본 보상은 엽전. <b>아주 드물게</b> 귀걸이 · 팔찌 · 신화 보물이 떨어져요(지옥이 더 잘 나와요).</li></ul>
<div class="tip">[참가한다고 알리기]를 누르면 지금 접속한 다른 용사들에게 알려져요. 다른 용사가 참가하면 2명이 되어 도전할 수 있어요(이 기기의 다른 계정 캐릭터도 함께할 수 있어요).</div>
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
<li>환생(과 윤회 구슬)은 <b>두 번까지</b>예요. 두 번째 환생은 저승 레벨 200 + 저승 이야기를 마치면 하늘(천계)로 올라가는 환생이에요.</li></ul>
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
    S.append(sec('가방 · 장터', """
<h3>가방 ([가방] 메뉴)</h3>
<p>수문장·타임 보스·오프라인·퀘스트 행운에서 나온 장신구·신화 보물 가운데 <b>지금 낀 것보다 약한 것</b>과, 더 좋은 것을 끼면서 빠진 <b>옛것</b>이 가방(60칸)에 모여요. 눌러서 <b>끼기</b> · <b>상인에게 팔기</b>(보석) · <b>장터에 올리기</b>. [안 쓰는 것 모두 팔기]는 지금 것보다 약한 물건만 한 번에 팔아요(↑ 표시는 지금 것보다 좋은 물건). 쇳가루·고삐 조각·조합 재료·탕약·숫돌·토벌패 개수도 여기서 한눈에 봐요.</p>
<h3>장터 마을</h3>
<p>오른쪽 위 <b>장터 단추</b>(또는 가방의 [장터 마을로 가기])로 들어가요. 돌바닥 광장과 노점·기와집·북 무대가 있는 마을이에요. <b>땅을 누르면 그리로 걸어가고</b>, 온라인이면 지금 장터에 있는 <b>다른 용사들이 이름표를 달고 함께</b> 서 있어요. <b>보부상 덕보</b>(NPC 상인) · <b>장터 알림판</b>(사기) · <b>거간꾼 막동</b>(팔기) · <b>전표 아전</b>(내 물건) 앞으로 가면 거래 화면이 열려요. 장터에 있는 동안은 사냥이 멈추고, 오른쪽 아래 큰 단추 <b>[나가기]</b>로 사냥터에 돌아가요.</p>
<h3>장터 거래 — 사기 · 팔기 · 내 물건 · 상인</h3>
<ul><li><b>사기</b>: 다른 용사가 올린 물건(장신구·신화 보물·장비 조각·재료·쇳가루·고삐 조각)을 <b>보석</b>으로 사요. 먼저 산 한 사람만 가져가요.</li>
<li><b>팔기</b>: 가방 물건·남는 장비 조각·재료를 골라 값을 정해 올려요. 한 번에 <b>10개</b>까지, <b>사흘</b> 동안 진열돼요.</li>
<li><b>내 물건</b>: 팔린 물건의 값을 <b>수수료 5%</b>를 떼고 받고, 안 팔린 물건은 내려서 돌려받아요.</li>
<li><b>상인</b>: 보부상 덕보가 날마다 다섯 가지 물건을 하나씩 팔아요(자정에 바뀜). 온라인이 아니어도 거래할 수 있어요.</li>
<li>다른 용사와의 거래는 <b>온라인 서버에 로그인</b>했을 때만 돼요.</li></ul>
""", ('bag', '가방'), ('market', '장터 마을'), ('marketnpc', '장터 · 상인'), kicker='16'))
    S.append(sec('상점 · 채팅 · 정보', """
<h3>상점</h3>
<ul><li>물약: <b>인삼 탕약</b>(체력 30% 아래면 저절로 마셔 40% 회복) · <b>산삼 탕약</b>(보스·레이드에서 먼저 마셔 전부 회복)</li>
<li>부적(10분, 겹쳐 사면 최대 60분): 범(공격력 +30%) · 바람(공격 속도 +20%) · 거북(받는 피해 -20%) · 복주머니(엽전 +50%) · 글공부 두루마리(경험치 +50%)</li>
<li>재료: 숫돌 · 토벌패(하루 3개) / 꾸러미: 엽전 꾸러미 · <b>꾸미기 상자</b> · <b>오늘의 선물</b>(하루 한 번 공짜)</li></ul>
<h3>채팅</h3><p>지금 접속한 다른 용사들, 그리고 주민들과 이야기해요. 신화 보물·레이드 성공 같은 소식도 받아요. 말하면 용사 머리 위에 말풍선이 떠요. 나쁜 말은 가려져요.</p>
<h3>정보</h3><p>꾸미기 · 캐릭터 바꾸기 · 로그아웃 · 업데이트 소식 · 이야기 다시 보기 · 앱으로 설치.</p>
""", ('shop', '상점'), ('chat', '채팅'), ('rec', '정보'), kicker='17'))
    S.append(sec('진행 시간표 (참고)', """
<p>쉬지 않고 잘 키웠을 때(자동 시뮬레이션 네 직업 평균)의 대략적인 시간이에요. 사람마다, 뽑기 운마다 달라요.</p>
<table><tr><th>시점</th><th>도달</th></tr>
<tr><td>약 1~2.5시간</td><td>레벨 50 · <b>1차 전직</b> (술사는 초반이 느려요)</td></tr>
<tr><td>약 5~7시간</td><td>이승 100단계 — 이 무렵부터 한 단계에 1~2시간</td></tr>
<tr><td>약 8~13시간</td><td>레벨 100(이승 만렙) · 주작 변신 · 조합 3단계</td></tr>
<tr><td>약 10~18시간</td><td>무기 +25 · 다섯 시련 → <b>첫 환생(저승)</b></td></tr>
<tr><td>약 40~47시간</td><td>저승 레벨 200 · 저승 이야기 끝 → 히든 퀘스트 · <b>마지막 환생(천계)</b></td></tr>
<tr><td>약 42~50시간</td><td>숨겨진 <b>2차 전직</b></td></tr>
<tr><td>약 90~105시간</td><td>신과의 전쟁 끝 · <b>신화</b>(이야기 113개) → 바다 건너 <b>부상</b>(2부). 뽑기 운이 나쁘면 160시간 넘게도 걸려요</td></tr>
<tr><td>건넌 뒤 약 37~45시간</td><td>레벨 350 · 스승의 장을 마치면 <b>3차 전직</b> (술사가 가장 빨라요)</td></tr>
<tr><td>건넌 뒤 약 80~100시간</td><td>레벨 400 · <b>부상 이야기 끝</b>(이야기 145개) → '끝없는 신화'</td></tr></table>
<p class="small">쉬지 않고 잘 키웠을 때(자동 시뮬레이션) 기준이에요. 하루 10~15시간쯤 방치하면 신화까지 <b>열흘 안팎</b>, 부상까지 <b>일주일쯤 더</b>. 직업·뽑기 운·접속 간격에 따라 달라요.
<b>조합 공방</b>을 쓰지 않으면 저승은 1.5배, 천계는 2배쯤 오래 걸리고 160시간 안에 신화에 닿지 못했어요.</p>
""", kicker='18'))
    S.append(sec('자주 묻는 질문', """
<p><b>Q. 다른 폰에서도 이어서 할 수 있나요?</b><br>네! 계정과 기록이 <b>온라인 서버</b>에 저장돼서, 다른 휴대폰이나 PC에서도 같은 아이디·비밀번호로 로그인하면 이어서 할 수 있어요.
인터넷이 끊겨도 그 기기에 저장해 두었다가 다시 연결되면 서버에 올려요. 서버가 생기기 전에 만든 계정은 로그인할 때 서버로 옮겨져요.</p>
<p><b>Q. 창을 닫아 두면?</b><br>최대 12시간까지 오프라인 보상이 쌓여요. 켜 두고 스킬 자동으로 사냥할 때 잰 속도로 계산해서 <b>경험치는 1.25배</b>, 엽전·보석은 0.85배예요. 오프라인 시간을 모두 더해 24시간이 될 때마다 3% 확률로 신화 보물도 나와요. 부적 시간은 게임을 켜 둘 때만 줄어요.</p>
<p><b>Q. 앱으로 설치하려면?</b><br>안드로이드: Chrome·삼성 인터넷 메뉴(점 세 개) → [앱 설치]/[홈 화면에 추가] · 아이폰: Safari [공유] → [홈 화면에 추가] ·
PC: Chrome·Edge 주소창 오른쪽 설치 단추. 설치하면 주소창 없이 전체 화면으로 열리고 인터넷이 없어도 돌아가요.
(아이폰은 설치한 앱과 Safari의 저장 공간이 따로라 앱에서 계정을 새로 만들어야 해요.)</p>
<p><b>Q. 보스에게 자꾸 쓰러져요.</b><br>새 단계의 보스는 세게 때려요. 체력·방어구 재련·방어 펫·<b>비전 갑옷</b>(조합 공방)으로 버티고, 인삼 탕약을 챙겨요.
술사는 <b>마력 보호막</b>을 보스가 나올 때 직접 눌러 쓰면 좋아요. 같은 단계에서 조금 더 키우면 덜 아파요.</p>
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
