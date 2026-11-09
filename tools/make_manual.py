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
  S.refine.weapon.lv = 12; S.refine.armor.lv = 9; S.refine.weapon.energy = 38; S.refine.weapon.fails = 3;
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
    await shot('play', 3500)
    await tab('grow', 'grow')
    await tab('skill', 'skill')
    await tab('gear', 'gear')
    await tab('gear', 'refine', '#seg-refine')
    await tab('gear', 'myth', '#seg-myth')
    await tab('gear', 'acc', '#seg-acc')
    await tab('gear', 'form', '#seg-form')
    await tab('pet', 'pet')
    await tab('quest', 'quest')
    await tab('raid', 'raid')
    await tab('shop', 'shop')
    await tab('rec', 'rec')
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
    await page.click('#tab-raid')
    await shot('raidfight', 3500)
    await page.evaluate("() => { const G = window.__game; for (let i = 0; i < 4000 && G.raid; i++) G.update(0.05); }")

    # 환생 화면
    await page.evaluate("""() => { const G = window.__game, S = G.S;
      S.level = 100; S.stage = 101; S.maxStage = 101; S.best.s0 = 101; S.best.l0 = 100; S.refine.weapon.lv = 25; S.quest.trials = [true, true, true, false, true];
      S.quest.main = 35; G.refreshStats(); }""")
    await page.click('#tab-grow')
    await page.wait_for_timeout(150)
    await page.click('#gv-reb')
    await shot('rebirth')
    await page.evaluate("() => { const G = window.__game; G.S.quest.trials = [true, true, true, true, true]; G.doRebirth(); for (let z = 0; z < 8; z++) G.rebUp('atk'); for (let z = 0; z < 5; z++) G.rebUp('hp'); }")
    await page.click('#tab-grow')
    await page.wait_for_timeout(150)
    await page.click('#gv-reb')
    await shot('rebirth2')

    # 저승
    await page.evaluate("""() => { const G = window.__game, S = G.S;
      S.level = 64; S.best.l1 = 64; Object.assign(S.up, {atk: 90, hp: 88, crit: 30, critDmg: 30, aspd: 20, regen: 12});
      S.form.own.cheong = true; S.form.eq = 'cheong'; S.awaken = true; S.quest.main = 49;
      G.setStage(47); G.refreshStats(); G.hero.hp = G.ST.maxHp; }""")
    await page.click('#tab-gear')
    await page.wait_for_timeout(150)
    await page.click('#seg-form')
    await shot('hell', 3500)

    # 타임 보스: 이 기기의 다른 계정 캐릭터가 함께 싸운다
    await page.evaluate("""() => { const G = window.__game;
      G.REG.accounts.friend1 = {salt: 'x', hash: 'p:x', t: 1, chars: [{cid: 'cf', name: '벗님', cls: 'doin', level: 80, maxStage: 80, look: {}, armorG: 3, weaponG: 3, ally: {dps: G.ST.atk * 3, maxHp: G.ST.maxHp}}]};
      const w = G.tbWindow(); if (!w.open) G.addTime(w.next - Date.now() + 60000); }""")
    await page.click('#tab-raid')
    await shot('timeboss', 600)
    await page.evaluate("() => { const G = window.__game; G.startTimeBoss('normal'); }")
    await shot('timefight', 4000)
    await page.evaluate("() => { const G = window.__game; for (let i = 0; i < 4000 && G.raid; i++) G.update(0.05); delete G.REG.accounts.friend1; }")


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
.row{{display:flex;gap:14px;align-items:flex-start}}
.txt{{flex:1;min-width:0}}
.figs{{display:flex;gap:8px;flex:none}}
.figs.n0{{display:none}}
figure{{margin:0;width:47mm}}
.figs.n2 figure{{width:40mm}}
.row.v{{flex-direction:column}} .row.v .figs{{justify-content:center;width:100%;gap:14px}} .row.v figure{{width:50mm}}
figure img{{width:100%;border-radius:9px;border:1px solid #cfd5e1;box-shadow:0 2px 8px rgba(20,30,60,.12);display:block}}
figcaption{{font-size:8pt;color:#5a6378;text-align:center;margin-top:3px}}
table{{border-collapse:collapse;width:100%;font-size:9pt;margin:6px 0}}
th,td{{border:1px solid #d5dae5;padding:3px 6px;text-align:left;vertical-align:top}}
th{{background:#f1f3f8;font-weight:800}}
.tip{{background:#fff8e1;border:1px solid #f0d58a;border-radius:8px;padding:6px 10px;margin:6px 0;font-size:9.4pt}}
.cover{{height:250mm;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;break-after:page;
  background:linear-gradient(180deg,#0e1424,#1f2b4a 60%,#3a2f2a);color:#fff;border-radius:14px}}
.cover img{{width:62mm;border-radius:14px;margin:18px 0;box-shadow:0 10px 40px rgba(0,0,0,.5)}}
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
환생해서 <b>저승</b>의 열 대왕(시왕)을 만나 사신(주작·청룡·백호·현무)을 구해요. 모두 80장.</li>
<li><b>두 세계</b>: 이승(레벨 100까지) → 환생 → 저승(레벨 200까지).</li>
<li><b>함께하기</b>: 레이드(나 + NPC 동료 3~10인), 3시간마다 나타나는 타임 보스(2명 이상), 채팅.</li></ul>
<div class="tip">주소: <b>benaeend.github.io/samhan-hero</b> · 휴대폰 홈 화면에 앱으로 설치할 수 있어요(아래 '앱으로 설치' 참고).</div>
<h3>차례</h3><ol class="toc"><li>시작하기·계정</li><li>화면 보기</li><li>수련(능력치)·스테이지</li><li>기술·초각성기</li><li>장비·재련</li><li>신화 보물·장신구·변신</li>
<li>펫</li><li>퀘스트·이야기</li><li>레이드</li><li>타임 보스</li><li>환생·저승</li><li>상점·채팅·정보</li><li>진행 시간표·자주 묻는 질문</li></ol>
""", kicker='들어가며'))
    S.append(sec('시작하기 · 계정 만들기', """
<ul><li>첫 화면에서 <b>[회원가입]</b> → 아이디·비밀번호를 정해요. 비밀번호는 기기 안에 암호(해시)로만 저장돼요.</li>
<li>한 계정에 <b>캐릭터 4명</b>까지 만들 수 있어요. 이름은 이 기기 안에서 겹칠 수 없어요.</li>
<li>오른쪽 위 <b>♪</b> 단추로 배경음악·효과음을 켜고 꺼요(국악풍 가야금·대금·장구 소리).</li></ul>
<h3>직업 4가지</h3>
<table><tr><th>직업</th><th>특징</th><th>무기</th></tr>
<tr><td>무사</td><td>체력이 높고 앞에서 베어요(근접)</td><td>검</td></tr>
<tr><td>자객</td><td>공격 속도·치명타가 높아요(근접)</td><td>단검</td></tr>
<tr><td>술사</td><td>공격력·기술 피해가 높고 멀리서 쏴요(원거리)</td><td>지팡이</td></tr>
<tr><td>도인</td><td>체력 회복이 빠르고 레이드에서 동료를 치유해요(원거리)</td><td>부채</td></tr></table>
<p>꾸미기: 옷 색 11가지 · 머리색 · 피부 · 머리 장식(갓·머리띠·복면 등). 미리보기를 누르면 돌려 볼 수 있어요.</p>
""", ('title', '첫 화면'), ('create', '캐릭터 만들기'), kicker='1'))
    S.append(sec('프롤로그와 튜토리얼', """
<p>캐릭터를 처음 만들면 <b>1분짜리 프롤로그</b>가 나와요. 하늘 문에 금이 가고 요괴가 쏟아지는 이야기예요. 화면을 누르면 다음 대사로,
<b>[건너뛰기]</b>로 바로 넘어갈 수 있어요. [정보] → [이야기 다시 보기]에서 언제든 다시 볼 수 있어요.</p>
<p>이어서 <b>길잡이 까치</b>가 7단계 튜토리얼로 안내해요. 눌러야 할 곳이 반짝이고, 단계마다 보석을 줘요.</p>
""", ('prologue', '프롤로그'), ('tutorial', '튜토리얼'), kicker='1'))
    S.append(sec('화면 보기', """
<ul><li><b>맨 위</b>: 레벨 · 이름 · 직업 · 전투력, 엽전·보석, 경험치 막대.</li>
<li><b>장면</b>: 용사가 가장 가까운 몬스터에게 걸어가 싸워요. 위쪽에 지역 이름과 단계(예: 도깨비 굴 5-7), 처치 수가 보여요.</li>
<li><b>기술 칸</b>: 레벨이 오르면 기술이 열리고, 재사용 시간이 지나면 저절로 써요.</li>
<li><b>[보스]</b> 단추: 몬스터 10마리를 잡으면 보스에 도전해요(자동 도전이 기본). 보스는 30초 안에 잡아야 해요.
실패하면 그 단계에서 사냥하며 더 강해진 뒤 다시 도전해요.</li>
<li><b>[속도]</b> 단추: 게임 속도를 바꿔요.</li>
<li><b>아래 메뉴 8칸</b>: 수련 · 기술 · 장비 · 펫 · 퀘스트 · 레이드 · 상점 · 정보. 빨간 점은 받을 보상이나 할 일이 있다는 뜻이에요.</li>
<li><b>말풍선 단추</b>: 채팅창을 열어요.</li></ul>
""", ('play', '사냥 화면'), kicker='2'))
    S.append(sec('수련 · 스테이지', """
<p><b>[수련]</b>에서 엽전으로 능력치를 올려요: 공격력 · 체력 · 치명타 확률 · 치명타 피해 · 공격 속도 · 체력 회복.
×1 / ×10 / 최대 단추로 한 번에 여러 번 올릴 수 있고, <b>길게 누르면</b> 계속 올라가요.</p>
<ul><li>몬스터를 잡으면 엽전·경험치, 가끔 <b>보석</b>(10% 확률로 1~2개)을 얻어요.</li>
<li>단계마다 몬스터 10마리 → 보스. 10단계마다 지역이 바뀌어요(마을 어귀 → 대나무 숲 → 바위 고개 → 안개 늪 → 도깨비 굴 → 백두 설원 → …).</li>
<li>각 지역의 <b>9번째 단계</b>는 <b>수문장</b>(서브 보스)이 지켜요. 수문장에게서만 장신구가 잘 떨어져요.</li>
<li>레벨 상한: 이승 <b>100</b>, 저승 <b>200</b>.</li></ul>
<div class="tip"><b>난이도 흐름</b>: 처음 50~60단계까지는 쭉쭉 올라가요. 이승 70단계 무렵부터 한 단계에 수십 분, 100단계 근처부터는
<b>한 단계에 1~2시간</b>, 저승 90단계를 넘으면 <b>2~4시간</b>씩 방치해야 넘을 수 있어요. 막히면 장비·재련·펫·레이드로 힘을 키워요.</div>
""", ('grow', '수련 탭'), kicker='3'))
    S.append(sec('기술 · 초각성기', """
<p>직업마다 기술 6개가 있어요. <b>Lv.5 · 12 · 25 · 40 · 60 · 80</b>에 하나씩 열리고, [기술]에서 엽전으로 강화해요.</p>
<table><tr><th>칸</th><th>종류</th><th>무사</th><th>자객</th><th>술사</th><th>도인</th></tr>
<tr><td>1</td><td>주변 광역</td><td>회오리 베기</td><td>그림자 베기</td><td>불꽃 고리</td><td>부적 폭발</td></tr>
<tr><td>2</td><td>단일 강타</td><td>일섬</td><td>급소 찌르기</td><td>벼락</td><td>천벌</td></tr>
<tr><td>3</td><td>강화(버프)</td><td>투혼</td><td>바람 걸음</td><td>마력 집중</td><td>회복의 기운</td></tr>
<tr><td>4</td><td>전체 공격</td><td>천지 가르기</td><td>비도 난무</td><td>유성우</td><td>하늘의 심판</td></tr>
<tr><td>5</td><td>연타</td><td>천둥 연격</td><td>그림자 연환</td><td>얼음 창 세례</td><td>팔괘 연타</td></tr>
<tr><td>6</td><td>낙인(약점)</td><td>기세 꺾기</td><td>급소 낙인</td><td>마력 저주</td><td>봉인 부적</td></tr></table>
<h3>초각성기</h3>
<p>환생 후 <b>저승 Lv.60 + 시왕 레이드 「송제전」 토벌</b>을 이루고 이야기 퀘스트 「각성의 시련」을 깨면 배워요.
레이드·타임 보스마다 <b>한 번</b>, 싸움 시작 12초 뒤나 보스 체력이 60% 아래로 내려가면 저절로 써요(공격력의 150배 피해).
무사 「개천 일격」 · 자객 「월하 만영참」 · 술사 「천화 강림」 · 도인 「사신 강림」.</p>
""", ('skill', '기술 탭'), kicker='4'))
    S.append(sec('장비 · 재련', """
<p><b>[장비] → [무기]/[방어구]</b>: 보석으로 소환(1회 50 · 10회 450)해요. 같은 장비 4개는 한 단계 위로 <b>합성</b>돼요.
등급은 일반 · 고급 · 희귀 · 영웅 · 전설(각 Ⅰ~Ⅳ). 가진 장비 전부가 조금씩, 장착한 장비가 크게 능력을 올려요.</p>
<p>장비 등급이 오르면 <b>용사 그림도 바뀌어요</b>(무기 모양·갑옷 무늬·허리띠 색).</p>
<h3>재련 (+25까지)</h3>
<ul><li>엽전 + 보석으로 무기·방어구를 벼려요. +1~+3은 반드시 성공, 그 뒤로 확률이 내려가 +24·+25는 1%.</li>
<li><b>실패해도 단계는 그대로</b>. 실패할 때마다 다음 확률이 조금씩 올라요(최대 2배).</li>
<li><b>담금질 기운</b>이 실패할 때마다 쌓이고, 100%가 되면 다음 재련은 <b>반드시 성공</b>해요.</li>
<li>상점의 <b>숫돌</b>을 함께 쓰면 확률이 기본 확률의 절반만큼 더 올라요.</li>
<li><b>무기 +25는 첫 환생 조건</b>이에요.</li></ul>
""", ('gear', '장비 소환'), ('refine', '재련'), kicker='5'))
    S.append(sec('신화 보물 · 장신구 · 변신', """
<h3>신화 보물 ([장비] → [신화])</h3>
<p>천부인 검(공격력) · 천부인 거울(체력) · 천부인 방울(치명타 피해) · 여의주(엽전·경험치) · 만파식적(기술 피해).
이야기 퀘스트에서 확정으로 받고, 퀘스트 보상을 받을 때 6% 확률·타임 보스에서도 나와요. 어려운 퀘스트일수록 효과가 커요.
종류마다 가장 센 것만 남고 약한 것은 보석 30개로 바뀌어요.</p>
<h3>장신구 ([장비] → [장신구])</h3>
<p><b>반지</b>(공격력) · <b>귀걸이</b>(치명타 피해·기술 피해) · <b>팔찌</b>(체력·공격 속도). 등급 5단계.
각 지역 <b>9번째 단계 수문장</b>을 잡을 때 반지 8% · 귀걸이·팔찌 1.5%, 일반 몬스터에게서는 아주 드물게(귀걸이·팔찌 0.08%).
타임 보스에서도 떨어져요. 이미 더 좋은 것이 있으면 보석 50개로 바뀌어요.</p>
<h3>변신 ([장비] → [변신])</h3>
<p>이야기에서 사신의 힘을 얻어요: <b>주작</b>(공격력 +25%·엽전/경험치 +30%) · <b>청룡</b>(공격력 +40%·기술 피해 +30%) ·
<b>백호</b>(공격 속도 +25%·치명타 +10%) · <b>현무</b>(받는 피해 -30%·체력 +60%). 하나를 골라 두르면 모습이 바뀌어요.</p>
""", ('myth', '신화 보물'), ('acc', '장신구'), ('form', '변신'), kicker='6'))
    S.append(sec('펫', """
<ul><li>보석으로 소환(1회 100 · 10회 900). <b>공격 · 방어 · 지원</b> 세 종류 × 5등급 = 15마리
(들고양이·해동청·아기 범·새끼 백호·삼족오 / 남생이·반달곰·돌거북·해치·황금 해치 / 까치·업두꺼비·삽살개·두루미·봉황).</li>
<li>종류마다 한 마리씩 데려가요. 공격 펫은 함께 싸우고, 방어 펫은 피해를 줄이고, 지원 펫은 체력을 채우거나 엽전·경험치를 늘려요.</li>
<li>같은 펫이 또 나오면 <b>별</b>이 올라요(최대 5개, 별마다 효과 +20%).</li>
<li>엽전 + 보석으로 <b>Lv.30</b>까지 강화해요. 펫 하나를 Lv.20으로 키우는 것이 환생 시련 중 하나예요.</li></ul>
""", ('pet', '펫 탭'), kicker='7'))
    S.append(sec('퀘스트 · 이야기', """
<ul><li><b>이야기 퀘스트 80장</b>(17장 구성): 마을 어귀 → 해모수와 유화 → 알에서 태어난 주몽 → 엄리대수 → 졸본과 송양왕 → 다물 →
환생 → 저승의 열 대왕(진광·초강·송제·오관·염라·변성·태산·평등·도시·전륜) → 사신의 귀환. 다 깨면 '끝없는 윤회'로 이어져요.</li>
<li>이야기를 하나 깰 때마다 <b>15초 이내의 짧은 연출</b>이 나와요. [정보]에서 다시 볼 수 있어요.</li>
<li><b>오늘의 할 일 6개</b>(몬스터 200마리·보스 5번·소환 10번·능력치 30번·재련 3번·레이드 1번)와 모두 완료 보너스. 매일 자정에 새로 고쳐져요.</li>
<li><b>퀘스트 행운</b>: 보상을 받을 때 20% 확률로 모든 기술 재사용 시간 초기화, 6% 확률로 신화 보물!</li></ul>
""", ('quest', '퀘스트 탭'), ('cut', '이야기 연출'), kicker='8'))
    S.append(sec('레이드', """
<ul><li><b>이승 레이드</b>: 레벨 10마다 하나씩 열려요(붉은 산군 멧돼지 · 천년 묵은 여우 · 천하대장군 · 늪의 이무기 · 외눈 도깨비 왕 ·
쇠먹는 불가사리 · 어둑시니 · 성난 해태, 이후 '2단', '3단').</li>
<li><b>시왕 레이드</b>(저승): 저승 레벨 20마다 열 대왕이 하나씩.</li>
<li>파티는 <b>나 + 이 기기의 다른 캐릭터 + NPC 동료</b>로 3~10명. 자동으로 싸우고 <b>90초</b> 안에 보스를 쓰러뜨리면 성공!</li>
<li>보상: 보석 · 엽전 · 장비, 처음 깨면 보너스. 이승 레이드 8곳을 모두 깨는 것이 환생 시련 중 하나예요.</li>
<li>입장은 <b>토벌패</b>(최대 3개, 15분마다 1개 충전). 실패하면 돌려받아요.</li></ul>
""", ('raid', '레이드 탭'), ('raidfight', '레이드 전투'), kicker='9'))
    S.append(sec('타임 보스', """
<ul><li><b>0시부터 3시간마다</b>(0·3·6·9·12·15·18·21시) 30분 동안 나타나요. [레이드] 탭 위쪽에 남은 시간이 보여요.</li>
<li><b>2명 이상</b> 모여야 도전할 수 있어요. 120초 안에 함께 쓰러뜨려요.</li>
<li>난이도 <b>노말</b>(누구나) · <b>지옥</b>(환생해야 도전). 창이 열릴 때마다 난이도별로 한 번씩 보상을 받아요.</li>
<li>기본 보상은 엽전. <b>아주 드물게</b> 귀걸이 · 팔찌 · 신화 보물이 떨어져요(지옥이 더 잘 나와요).</li></ul>
<div class="tip">지금은 서버가 없어서 '함께하는 사람'은 이 기기의 다른 계정 캐릭터, claude.ai에서 열면 같은 페이지에서 [참가]한 사람이에요.
온라인 서버를 붙이면 다른 플레이어와 바로 함께할 수 있게 되어 있어요.</div>
""", ('timeboss', '타임 보스 창'), ('timefight', '타임 보스 전투'), kicker='10'))
    S.append(sec('환생 · 저승', """
<h3>첫 환생 조건</h3>
<ul><li>이승 <b>레벨 100</b> · <b>무기 재련 +25</b> · <b>윤회의 다섯 시련</b>:
활(이승 100단계 넘기) · 물(이승 레이드 8곳 토벌) · 하늘(신화 보물 3종) · 벗(펫 하나 Lv.20) · 인연(장신구 1개)</li></ul>
<h3>환생하면</h3>
<ul><li>레벨·단계·엽전·능력치는 처음으로 돌아가요. <b>장비·재련·펫·신화 보물·장신구·변신·보석은 그대로</b>예요.</li>
<li><b>윤회 구슬</b>을 받아요: 레벨의 1/10 + 최고 단계의 1/20 (Lv.100·101단계면 15개).</li>
<li>윤회 구슬로 영원히 남는 능력을 올려요: 무력(공격력 +15%) · 강골(체력 +15%) · 신속(공격 속도 +3%) · 복덕(엽전·경험치 +10%) · 영안(치명타).</li>
<li>무대가 <b>저승</b>으로 바뀌어요: 도산 → 화탕 → 한빙 → 검수 → 독사 → 흑암지옥. 저승 레벨은 200까지.</li>
<li>저승 레벨 200에 닿으면 다시 환생해서 구슬을 더 모을 수 있어요.</li></ul>
""", ('rebirth', '환생 조건'), ('rebirth2', '윤회 능력'), ('hell', '저승'), kicker='11'))
    S.append(sec('상점 · 채팅 · 정보', """
<h3>상점</h3>
<ul><li>물약: <b>인삼 탕약</b>(체력 30% 아래면 저절로 마셔 40% 회복) · <b>산삼 탕약</b>(보스·레이드에서 먼저 마셔 전부 회복)</li>
<li>부적(10분, 겹쳐 사면 최대 60분): 범(공격력 +30%) · 바람(공격 속도 +20%) · 거북(받는 피해 -20%) · 복주머니(엽전 +50%) · 글공부 두루마리(경험치 +50%)</li>
<li>재료: 숫돌 · 토벌패(하루 3개) / 꾸러미: 엽전 꾸러미 · <b>오늘의 선물</b>(하루 한 번 공짜)</li></ul>
<h3>채팅</h3><p>주민들과 이야기하고 신화 보물·레이드 성공 같은 소식을 받아요. 말하면 용사 머리 위에 말풍선이 떠요. 나쁜 말은 가려져요.</p>
<h3>정보</h3><p>꾸미기 · 캐릭터 바꾸기 · 로그아웃 · 업데이트 소식 · 이야기 다시 보기 · 앱으로 설치.</p>
""", ('shop', '상점'), ('chat', '채팅'), ('rec', '정보'), kicker='12'))
    S.append(sec('진행 시간표 (참고)', """
<p>쉬지 않고 잘 키웠을 때(자동 시뮬레이션 네 직업 평균)의 대략적인 시간이에요. 사람마다, 뽑기 운마다 달라요.</p>
<table><tr><th>시점</th><th>도달</th></tr>
<tr><td>약 15~25분</td><td>이승 50단계 · 레벨 50</td></tr>
<tr><td>약 30분~2시간</td><td>이승 70단계 — 여기부터 한 단계가 점점 오래 걸려요</td></tr>
<tr><td>약 5~6시간</td><td>이승 90단계 · 이승 이야기(7장) 대부분</td></tr>
<tr><td>약 6~8시간</td><td>레벨 100(이승 만렙) · 주작 변신</td></tr>
<tr><td>약 6~12시간</td><td>이승 100단계(활의 시련) — 이제 한 단계에 1~2시간</td></tr>
<tr><td>약 24~34시간</td><td>무기 +25 · 다섯 시련 → 첫 환생</td></tr>
<tr><td>환생 후 1시간 안팎</td><td>저승 70단계까지 빠르게(청룡·백호 변신, 초각성기)</td></tr>
<tr><td>환생 후 6~20시간</td><td>저승 90단계 — 이 뒤로 한 단계에 2~4시간</td></tr>
<tr><td>약 58~75시간</td><td>저승 레벨 200 · 이야기 80장 마무리 → '끝없는 윤회'</td></tr></table>
<p class="small">실제로는 들어와서 강화하는 간격, 뽑기 운, 오프라인 보상(절반 효율)에 따라 더 걸릴 수 있어요.</p>
""", kicker='13'))
    S.append(sec('자주 묻는 질문', """
<p><b>Q. 다른 폰에서도 이어서 할 수 있나요?</b><br>지금은 계정과 기록이 <b>그 기기(브라우저) 안에</b> 저장돼요. 다른 기기에서는 새로 만들어야 해요
(claude.ai에서 열면 같은 Claude 계정끼리 이어져요). 온라인 서버를 붙이면 어디서나 이어서 할 수 있게 바뀔 예정이에요.</p>
<p><b>Q. 창을 닫아 두면?</b><br>최대 12시간까지 오프라인 보상(직접 할 때의 절반 효율, 보석 포함)이 쌓여요. 부적 시간은 게임을 켜 둘 때만 줄어요.</p>
<p><b>Q. 앱으로 설치하려면?</b><br>안드로이드: Chrome·삼성 인터넷 메뉴(점 세 개) → [앱 설치]/[홈 화면에 추가] · 아이폰: Safari [공유] → [홈 화면에 추가] ·
PC: Chrome·Edge 주소창 오른쪽 설치 단추. 설치하면 주소창 없이 전체 화면으로 열리고 인터넷이 없어도 돌아가요.
(아이폰은 설치한 앱과 Safari의 저장 공간이 따로라 앱에서 계정을 새로 만들어야 해요.)</p>
<p><b>Q. 사이트 데이터를 지우면?</b><br>계정과 기록도 함께 지워져요.</p>
<p class="tip">글꼴: Pretendard(SIL OFL 1.1, 이 게임에서는 SamhanSans라는 이름으로 일부 글자만 담음). 음악·효과음은 게임 안에서 직접 만들어 내는 소리예요.
그림·이야기·이름은 이 게임을 위해 새로 만들었어요.</p>
""", kicker='14'))
    cover = f"""<div class="cover"><div class="sub">플레이 매뉴얼</div><h1>삼한 용사 키우기</h1>
<img src="{jpg('title')}"><p>옛 한국 신화 속 방치형 RPG</p><p>benaeend.github.io/samhan-hero</p></div>"""
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{css}</style></head><body>{cover}{"".join(S)}</body></html>'


async def main():
    async with async_playwright() as p:
        browser = await tg.launch(p)
        ctx = await browser.new_context(viewport={'width': 390, 'height': 800}, device_scale_factor=2)
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
