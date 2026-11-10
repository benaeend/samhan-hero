"""플레이어에게 나눠 줄 간략 안내서(PDF): 이야기·조작·성장 시스템·직업·총 플레이 시간을 몇 쪽으로 요약한다.
이야기의 반전·숨은 요소(숨은 전직 조건, 뒤쪽 장의 결말 등)는 일부러 적지 않는다.

필요: 먼저 python3 tools/make_manual.py 로 캡처(tools/out/manual/*.jpg)를 만들어 둔다.
사용: python3 tools/make_guide.py   → docs/guide.pdf
게임 수치(플레이 시간·직업 특성·조작)를 바꾸면 아래 본문도 같이 고친다.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as tg  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

ROOT = tg.ROOT
SHOTS = ROOT / 'tools' / 'out' / 'manual'
PDF = ROOT / 'docs' / 'guide.pdf'
FONTS = ROOT / 'tools' / 'fonts'


def shot(name):
    p = SHOTS / f'{name}.jpg'
    if not p.exists():
        sys.exit(f'캡처가 없어요: {p} — 먼저 python3 tools/make_manual.py 를 돌려요')
    return p.as_uri()


def fig(name, cap):
    return f'<figure><img src="{shot(name)}"><figcaption>{cap}</figcaption></figure>'


def html():
    f = lambda n: (FONTS / n).as_uri()
    css = f"""
@font-face{{font-family:P;src:url({f('Pretendard-Medium.woff2')});font-weight:500}}
@font-face{{font-family:P;src:url({f('Pretendard-Bold.woff2')});font-weight:700}}
@font-face{{font-family:P;src:url({f('Pretendard-ExtraBold.woff2')});font-weight:800}}
@page{{size:A4;margin:12mm 12mm 14mm}}
*{{box-sizing:border-box}}
body{{font-family:P,sans-serif;font-weight:500;color:#1d2433;font-size:9.8pt;line-height:1.58;margin:0;word-break:keep-all}}
b{{font-weight:800}}
h2{{font-size:14pt;font-weight:800;margin:0 0 6px;color:#0f1a2e;display:flex;align-items:center;gap:8px}}
h2 i{{font-style:normal;font-size:9pt;color:#fff;background:#c8382f;border-radius:6px;padding:1px 7px}}
h3{{font-size:10.5pt;font-weight:800;margin:8px 0 2px;color:#7a4b00}}
p{{margin:3px 0}} ul{{margin:3px 0;padding-left:16px}} li{{margin:1px 0}}
section{{break-inside:avoid;margin:0 0 10px;padding:10px 12px;border:1px solid #e1e5ee;border-radius:12px;background:#fff}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.grid section{{margin:0}}
figure{{margin:6px 0 0}}
figure img{{width:100%;border-radius:8px;border:1px solid #cfd5e1;display:block}}
figcaption{{font-size:7.8pt;color:#5a6378;text-align:center;margin-top:2px}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
table{{border-collapse:collapse;width:100%;font-size:9pt;margin:4px 0}}
th,td{{border:1px solid #d5dae5;padding:3px 6px;text-align:left;vertical-align:top}}
th{{background:#f1f3f8;font-weight:800}}
.tip{{background:#fff8e1;border:1px solid #f0d58a;border-radius:8px;padding:5px 9px;margin:5px 0;font-size:9.2pt}}
.cover{{height:268mm;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;break-after:page;
  background:linear-gradient(180deg,#0e1424,#1f2b4a 60%,#3a2f2a);color:#fff;border-radius:14px;padding:0 14mm}}
.cover h1{{font-size:32pt;font-weight:800;margin:6px 0 0;letter-spacing:-.02em}}
.cover .sub{{color:#ffcc4d;font-weight:800;letter-spacing:.2em;font-size:10pt}}
.cover img{{width:160mm;border-radius:14px;margin:16px 0;box-shadow:0 10px 40px rgba(0,0,0,.5)}}
.cover p{{color:#c9d1e4;margin:2px 0}}
.cover .chips{{display:flex;gap:6px;flex-wrap:wrap;justify-content:center;margin-top:10px}}
.cover .chips span{{border:1px solid rgba(255,204,77,.5);color:#ffe08a;border-radius:999px;padding:2px 10px;font-size:9pt;font-weight:700}}
.cls td:first-child{{font-weight:800;white-space:nowrap}}
"""
    cover = f"""<div class="cover"><p class="sub">한눈에 보는 안내서</p><h1>삼한 용사 키우기</h1>
<img src="{shot('title')}">
<p>옛 한국 신화 속 세상을 지키는 방치형 RPG</p><p><b>benaeend.github.io/samhan-hero</b> · 휴대폰 홈 화면에 앱으로 설치</p>
<div class="chips"><span>알아서 사냥</span><span>직업 4가지</span><span>이야기 182개 + 계속</span><span>레이드 · 타임 보스</span><span>창을 닫아도 12시간 보상</span></div></div>"""

    story = """<section><h2><i>1</i>이야기</h2>
<p>하늘 문에 금이 가던 날, 그 틈으로 요괴가 쏟아져 내려왔어요. 용사는 <b>길잡이 까치</b>와 함께 마을 어귀부터 지키며,
<b>고구려를 세운 주몽</b>과 그 부모님(해모수·유화)의 옛이야기 속을 걸어가요.</p>
<p>이야기는 이승에서 끝나지 않아요. <b>여러 세계를 건너며</b> 우리 옛이야기와 이웃 나라 신화 속 인물들을 만나고, 하늘 문이 갈라진 까닭을 쫓아가요.
어떤 이는 적이 아니라 스승이 되어 용사를 시험해요.</p>
<table><tr><th>부</th><th>무대</th><th>분위기</th></tr>
<tr><td>1부</td><td>이승 → 저승 → 천계</td><td>고구려 건국 신화, 시왕의 저승, 하늘의 신들</td></tr>
<tr><td>2부</td><td>부상(해 뜨는 섬)</td><td>동쪽 바다 건너 옛 신화·민담</td></tr>
<tr><td>3부</td><td>곤륜(서쪽 하늘 끝)</td><td>서쪽 하늘의 옛 기록·민담</td></tr></table>
<p>이야기 퀘스트를 깰 때마다 짧은 <b>연출</b>이, 장이 바뀌면 붓글씨 <b>장 제목</b>이 나와요. [정보]에서 언제든 다시 볼 수 있어요.</p>
<div class="tip">결말과 숨은 이야기는 직접 확인해 보세요! 지나온 길과 앞으로 갈 땅은 <b>여정 지도</b>에서 볼 수 있어요.</div>
</section>"""

    start = """<section><h2><i>2</i>시작하기</h2>
<ul><li>첫 화면에서 <b>[회원가입]</b> → 아이디·비밀번호. 한 계정에 <b>캐릭터 4명</b>까지.</li>
<li>같은 아이디로 <b>다른 폰·PC에서도 이어서</b> 할 수 있어요(온라인 저장).</li>
<li>캐릭터를 만들면 1분 프롤로그 → 까치의 튜토리얼이 손잡고 알려 줘요.</li>
<li><b>앱 설치</b>: 안드로이드는 브라우저 메뉴 → [앱 설치], 아이폰은 Safari [공유] → [홈 화면에 추가]. 주소창 없이 가로 전체 화면으로 열려요.</li></ul>
</section>"""

    controls = f"""<section><h2><i>4</i>화면과 조작</h2>
<div class="two"><div>
<ul><li><b>가로로</b> 들면 사냥 장면이 화면을 가득 채워요.</li>
<li><b>왼쪽 위</b>: 얼굴·레벨·체력·경험치·펫, 그 아래 지금 이야기 퀘스트(다 하면 [보상 받기]).</li>
<li><b>위 가운데</b>: 지역·단계, 보스까지 남은 몹 수 / 보스 체력.</li>
<li><b>오른쪽 위</b>: 엽전·보석·쇳가루, <b>미니맵</b>(누르면 여정 지도). 왼쪽 아래 채팅.</li>
<li><b>아래 메뉴 9칸</b>: 수련·기술·장비·펫·퀘스트·레이드·상점·정보·가방. 누르면 별도 화면, ✕로 닫아요. 오른쪽 아래 <b>큰 보스 단추</b>는 보스까지 남은 처치를 고리로 보여 주고, 다 차면 눌러서 도전해요.</li></ul>
</div><div>
<table><tr><th>단추</th><th>하는 일</th></tr>
<tr><td>기술 칸 누르기</td><td>바로 쓰기</td></tr>
<tr><td>기술 칸 길게</td><td>그 기술만 자동 ↔ 수동</td></tr>
<tr><td><b>자동 / 반자동</b></td><td>자동: 사냥·기술 모두 알아서<br>반자동: 사냥은 알아서, 기술은 직접</td></tr>
<tr><td><b>장면 누르기</b></td><td>땅을 누르면 그 칸으로 걷고, 몬스터를 누르면 그 몬스터부터 쳐요</td></tr>
<tr><td><b>보스 자동 / 수동</b></td><td>자동: 몹을 다 잡으면 알아서 도전(지면 45초 뒤 다시)<br>수동: [보스 도전!]을 눌러야</td></tr>
<tr><td>×1 / ×2</td><td>게임 속도</td></tr></table>
</div></div>
<div class="two">{fig('play', '사냥 화면(가로)')}{fig('map', '여정 지도')}</div>
</section>"""

    growth = """<section><h2><i>5</i>강해지는 방법 한눈에</h2>
<table><tr><th style="width:24%">무엇</th><th>어떻게</th></tr>
<tr><td>사냥·스테이지</td><td>몹 25마리 → 보스(30초 안에). 보스는 <b>이야기·레벨</b>에 맞춰 열려요. 지역 9번째 단계는 <b>수문장</b></td></tr>
<tr><td>수련</td><td>엽전으로 능력치와 <b>수호신</b>(성주신·조왕신…)을 올려요. 길게 누르면 계속</td></tr>
<tr><td>기술</td><td>레벨·전직마다 열리고 엽전으로 강화(<b>몇 % 세지는지</b> 보여 줘요). 레이드에선 <b>초각성기</b></td></tr>
<tr><td>장비</td><td>보석으로 무기·방어구 <b>소환</b> → 같은 것 4개를 <b>합성</b> → <b>재련</b>(무기는 이승 +25, 방어구는 이승 +15·저승 +22·천계 +25, 2부에서 계승해 +15부터 다시. 확률은 모두 공개)</td></tr>
<tr><td>조합 공방</td><td>보스·레이드 재료로 직업 전용 무기·갑옷·노리개. 직업에 맞는 <b>각인</b> 셋이면 조화 보너스. 뒤로 갈수록 꼭 필요해요</td></tr>
<tr><td>펫</td><td>공격·방어·지원 29마리(부상·곤륜 펫과 신화 환수 포함), 소환(60번 천장)·별·강화</td></tr>
<tr><td>신화 보물·장신구·변신</td><td>이야기 보상으로 확정 지급(운에 막히지 않아요) + 가끔 행운</td></tr>
<tr><td>아바타·탈것·별호·치장</td><td>모을수록 공격력·체력이 올라요. 천계부터 장마다 몹이 <b>치장</b>을 떨궈요</td></tr>
<tr><td>전직</td><td>Lv.50에 첫 전직, 스승과 겨뤄 이기면 새 기술·무기 모양·망토. 모두 네 번(숨은 전직도 있어요)</td></tr>
<tr><td>환생·건너기</td><td>세계가 바뀔 때 새 힘(윤회 구슬)이나 레벨을 들고 다음 땅으로</td></tr>
<tr><td>레이드·보스</td><td>90초 레이드·타임 보스·<b>백귀야행</b>. 보스의 <b>붉은 칸</b>은 구르기로 피하고 <b>「!」</b>엔 되받기</td></tr>
<tr><td>넋 부름(2부~)</td><td>옛이야기 속 넋이 싸울 때 도와요. 원한 조각으로 <b>결이야기</b>를 들려주면 더 세져요</td></tr>
<tr><td>매일·쉬는 동안</td><td>오늘의 할 일 6개, 창을 닫아도 <b>최대 12시간</b> 보상(경험치 1.25배, 엽전·보석 0.85배)</td></tr>
<tr><td>배럭</td><td>같은 계정 캐릭터끼리 능력치·경험치·엽전·보석을 올려 줘요</td></tr></table>
</section>"""

    classes = f"""<section><h2><i>6</i>직업 4가지</h2>
<table class="cls"><tr><th>직업</th><th>한마디로</th><th>잘하는 것</th><th>조심할 것</th></tr>
<tr><td>무사</td><td><b>균형</b> · 근접 · 검</td><td>체력이 높고 받는 피해 -10%. 어디서나 무난, 처음 하는 사람에게 추천</td><td>뾰족한 장점은 적어요</td></tr>
<tr><td>자객</td><td><b>보스 사냥꾼</b> · 근접 · 쌍비수</td><td>보스·레이드 피해 +30%, 공격을 가끔 피해요. 공격 펫·장신구와 궁합</td><td>몹 떼는 느려요 → 펫·장신구를 잘 맞추기</td></tr>
<tr><td>술사</td><td><b>늦게 피는 꽃</b> · 원거리 · 지팡이</td><td>레벨이 오를수록 공격력이 커져 후반에 가장 강해요. 넓게 치는 기술</td><td>초반이 느리고 몸이 약해요 → 보스 때 <b>보호막</b>을 직접 눌러 쓰기</td></tr>
<tr><td>도인</td><td><b>한 방</b> · 원거리 · 부채</td><td>공격 기술은 3개뿐이지만 늘 치명타, 준비 기술을 다 건 뒤 터뜨리는 <b>가장 큰 한 방</b></td><td>손으로 조합하면 더 세요 → 반자동과 잘 맞아요</td></tr></table>
{fig('create', '캐릭터 만들기: 직업·옷 색·머리·머리 장식')}
</section>"""

    time = """<section><h2><i>3</i>얼마나 걸릴까?</h2>
<p>쉬지 않고 잘 키웠을 때(자동 시뮬레이션) 대략이에요. 직업·뽑기 운·접속 간격에 따라 달라요.</p>
<table><tr><th>시점</th><th>대략</th></tr>
<tr><td>첫 전직(Lv.50)</td><td>1.5~2시간</td></tr>
<tr><td>이승 100단계 무렵</td><td>4~6시간 — 이때부터 한 단계에 오래 머물러요</td></tr>
<tr><td>첫 환생</td><td>7~15시간</td></tr>
<tr><td><b>1부 끝(신화)</b></td><td><b>약 85~100시간</b></td></tr>
<tr><td><b>2부 끝</b></td><td>그 뒤로 <b>약 70~85시간</b> 더</td></tr>
<tr><td><b>3부 끝</b></td><td>그 뒤로 <b>약 120~160시간</b> 더 (4차 전직은 95~120시간쯤)</td></tr></table>
<p>하루 10~15시간쯤 켜 두고 틈틈이 들어와 키우면 <b>1부는 열흘 안팎, 2부는 일주일쯤, 3부는 열흘 남짓 더</b>예요. 다 깬 뒤에도 '끝없는 신화'가 이어져요.</p>
<p class="tip">직업별로는 무사가 고르게 빠르고, 술사는 처음이 느린 대신 뒤로 갈수록 빨라져요. 자객·도인은 보스·레이드에 강해요.</p>
</section>"""

    tips = """<section><h2><i>7</i>막힐 때 팁</h2>
<ul><li>보스에게 자꾸 지면: 같은 단계에서 조금 더 사냥해 <b>수련·재련</b>을 올리고, <b>조합 공방</b>을 확인해요. 체력·방어 펫·인삼 탕약도 도움이 돼요.</li>
<li><b>보스 수동</b>으로 두고 기술이 모두 준비됐을 때 [보스 도전!]을 누르면 이기기 쉬워요.</li>
<li>이야기 퀘스트(왼쪽 위)를 따라가면 길을 잃지 않아요. 보상으로 보석·보물을 확정으로 줘요.</li>
<li><b>레이드</b> 첫 클리어 보상과 재료를 챙겨요. 토벌패는 15분마다 1개씩 차요.</li>
<li>창을 닫기 전에 부적을 켜 두지 않아도 돼요. 쉬는 동안 보상은 다시 들어오면 받아요.</li></ul>
</section>
<section><h2><i>?</i>자주 묻는 질문</h2>
<p><b>다른 기기에서?</b> 같은 아이디로 로그인하면 이어져요. 인터넷이 끊겨도 그 기기에 저장했다가 다시 올려요.<br>
<b>아이폰 앱?</b> 설치한 앱과 Safari는 저장 공간이 따로라, 앱에서 같은 아이디로 로그인해요.<br>
<b>더 자세히?</b> 전체 매뉴얼(docs/manual.pdf)과 게임 안 [정보] → 업데이트 소식을 봐요.</p>
<p style="font-size:8pt;color:#6a7388">글꼴 Pretendard(SIL OFL 1.1, SamhanSans 이름으로 일부만 담음). 그림·이야기·이름·음악은 이 게임을 위해 새로 만들었어요.</p>
</section>"""

    body = f"""{cover}{story}<div class="grid">{start}{time}</div>{controls}{growth}{classes}{tips}"""
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'


async def main():
    out = SHOTS / 'guide.html'
    out.write_text(html(), encoding='utf-8')
    async with async_playwright() as p:
        browser = await tg.launch(p)
        pg = await browser.new_page()
        await pg.goto(out.as_uri())
        await pg.wait_for_timeout(600)
        PDF.parent.mkdir(parents=True, exist_ok=True)
        await pg.pdf(path=str(PDF), format='A4', print_background=True,
                     display_header_footer=True, header_template='<span></span>',
                     footer_template='<div style="font-size:8px;color:#8a93a6;width:100%;text-align:center">삼한 용사 키우기 · 안내서 <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
                     margin={'top': '12mm', 'bottom': '14mm', 'left': '12mm', 'right': '12mm'})
        await browser.close()
    print('안내서:', PDF.relative_to(ROOT), f'({PDF.stat().st_size:,} bytes)')


if __name__ == '__main__':
    asyncio.run(main())
