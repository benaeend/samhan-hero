"""src/game.html → index.html

게임에 쓰인 글자 + 한글 자모(채팅의 ㅋㅋ·ㅎㅎ)만 Pretendard 글꼴(3가지 굵기)에서 뽑아 woff2로 만든 뒤, base64로 index.html 안에 넣는다.
뽑아낸 글꼴은 '수정본'이라 OFL 규칙(예약된 이름 사용 금지)에 따라 이름을 SamhanSans로 바꿔 넣는다.
게임에 없는 글자(사용자가 지은 캐릭터 이름의 드문 글자 등)는 휴대폰 기본 한글 글꼴로 보인다.
필요: pip install fonttools brotli
사용: python3 tools/build.py          # 본 게임 index.html
      python3 tools/build.py --beta   # 베타 테스트 빌드 beta/index.html (저장 자리 분리·온라인/앱 설치 끔·베타 띠·시험용 캐릭터 tools/beta_saves/*.json)
        → beta/index.html 은 patch 브랜치에 커밋하지 않고 main 의 beta/ 폴더에만 올린다(https://benaeend.github.io/samhan-hero/beta/)
"""
import argparse
import base64
import io
import json
import re
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src' / 'game.html'
OUT = ROOT / 'index.html'
FONTS = ROOT / 'tools' / 'fonts'
FAMILY = 'SamhanSans'
WEIGHTS = [('/*FONT_MED*/', 'Pretendard-Medium.woff2', 'Medium'),
           ('/*FONT_BOLD*/', 'Pretendard-Bold.woff2', 'Bold'),
           ('/*FONT_XB*/', 'Pretendard-ExtraBold.woff2', 'ExtraBold')]


def subset_font(name: str, style: str, text: str) -> str:
    font = TTFont(FONTS / name)
    opts = subset.Options()
    opts.flavor = 'woff2'
    opts.layout_features = ['*']
    opts.name_IDs = ['*']
    sub = subset.Subsetter(opts)
    sub.populate(text=text)
    sub.subset(font)
    # 수정본이므로 글꼴 안의 이름도 바꾼다(저작권 표기·라이선스 항목은 그대로 둔다)
    names = {1: FAMILY, 2: 'Regular', 4: f'{FAMILY} {style}', 6: f'{FAMILY}-{style}', 16: FAMILY, 17: style}
    for rec in font['name'].names:
        if rec.nameID in names:
            rec.string = names[rec.nameID]
    bio = io.BytesIO()
    font.flavor = 'woff2'
    font.save(bio)
    data = bio.getvalue()
    print(f'  {name} → {FAMILY} {style}: {len(data):,} bytes')
    return base64.b64encode(data).decode()


BETA_RE = re.compile(r'/\*BETA_ONLY_BEGIN\*/.*?/\*BETA_ONLY_END\*/\n?', re.S)
BETA_FLAG = '/*BETA_BUILD*/false'
BETA_SAVES_PH = '/*BETA_SAVES*/[]'
BETA_SAVES = ROOT / 'tools' / 'beta_saves'


def beta_saves() -> str:
    """tools/beta_saves/*.json(시험용 캐릭터: {name, label, desc, save})을 이름 순서로 모아 JS 배열 글자로"""
    out = []
    for f in sorted(BETA_SAVES.glob('*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        assert {'name', 'label', 'desc', 'save'} <= set(d) and d['save'].get('v') == 1, f'{f.name}: 시험용 저장 형식이 달라요'
        out.append({k: d[k] for k in ('name', 'label', 'desc', 'save')})
    return json.dumps(out, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')


def main() -> None:
    ap = argparse.ArgumentParser(description='src/game.html → index.html (또는 --beta: beta/index.html)')
    ap.add_argument('--beta', action='store_true', help='베타 테스트 빌드: 저장 자리 분리(beta- 머리말)·온라인/앱 설치 끔·베타 띠·시험용 캐릭터')
    ap.add_argument('--out', help='결과 파일 경로(기본: index.html, --beta면 beta/index.html)')
    args = ap.parse_args()
    out = Path(args.out).resolve() if args.out else (ROOT / 'beta' / 'index.html' if args.beta else OUT)
    html = SRC.read_text(encoding='utf-8')
    for ph, _, _ in WEIGHTS:
        assert ph in html, f'src/game.html 에 글꼴 자리표시 {ph} 가 없어요'
    assert html.count(BETA_FLAG) == 1 and html.count(BETA_SAVES_PH) == 1 and BETA_RE.search(html), 'src/game.html 에 베타 자리표시가 없어요'
    jamo = {chr(c) for c in range(0x3131, 0x3164)}  # ㄱ~ㅣ
    chars = set(html) | {chr(c) for c in range(0x20, 0x7F)} | set('…→×·%∞★☆') | jamo
    if args.beta:
        saves = beta_saves()
        html = html.replace(BETA_FLAG, '/*BETA_BUILD*/true').replace(BETA_SAVES_PH, saves)
        chars |= set(json.dumps([[d['name'], d['label'], d['desc']] for d in json.loads(saves.replace('<\\/', '</'))], ensure_ascii=False))
    else:
        html = BETA_RE.sub('', html)   # 본 빌드에는 베타 전용 코드(시험용 캐릭터 등)를 넣지 않는다
        assert 'BETA_ONLY' not in html and 'BETA_SAVES' not in html
    text = ''.join(sorted(c for c in chars if c >= ' '))
    print('글꼴 추출 중…')
    for ph, file, style in WEIGHTS:
        html = html.replace(ph, subset_font(file, style, text))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')
    shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f'완료: {shown} ({len(html):,} 글자)' + (' · 베타 테스트 빌드' if args.beta else ''))


if __name__ == '__main__':
    main()
