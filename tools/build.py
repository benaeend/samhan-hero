"""src/game.html → index.html

게임에 쓰인 글자 + 한글 자모(채팅의 ㅋㅋ·ㅎㅎ)만 Pretendard 글꼴(3가지 굵기)에서 뽑아 woff2로 만든 뒤, base64로 index.html 안에 넣는다.
뽑아낸 글꼴은 '수정본'이라 OFL 규칙(예약된 이름 사용 금지)에 따라 이름을 SamhanSans로 바꿔 넣는다.
게임에 없는 글자(사용자가 지은 캐릭터 이름의 드문 글자 등)는 휴대폰 기본 한글 글꼴로 보인다.
필요: pip install fonttools brotli
사용: python3 tools/build.py
"""
import base64
import io
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


def main() -> None:
    html = SRC.read_text(encoding='utf-8')
    for ph, _, _ in WEIGHTS:
        assert ph in html, f'src/game.html 에 글꼴 자리표시 {ph} 가 없어요'
    jamo = {chr(c) for c in range(0x3131, 0x3164)}  # ㄱ~ㅣ
    chars = set(html) | {chr(c) for c in range(0x20, 0x7F)} | set('…→×·%∞★☆') | jamo
    text = ''.join(sorted(c for c in chars if c >= ' '))
    print('글꼴 추출 중…')
    for ph, file, style in WEIGHTS:
        html = html.replace(ph, subset_font(file, style, text))
    OUT.write_text(html, encoding='utf-8')
    print(f'완료: {OUT.relative_to(ROOT)} ({len(html):,} 글자)')


if __name__ == '__main__':
    main()
