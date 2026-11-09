"""src/game.html → index.html

게임에 쓰인 글자 + 자주 쓰는 한글 2,350자(사용자가 짓는 캐릭터 이름용)만 Galmuri 글꼴에서 뽑아 woff2로 만든 뒤, base64로 index.html 안에 넣는다.
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


def subset_font(name: str, text: str) -> str:
    font = TTFont(FONTS / name)
    opts = subset.Options()
    opts.flavor = 'woff2'
    opts.layout_features = ['*']
    sub = subset.Subsetter(opts)
    sub.populate(text=text)
    sub.subset(font)
    bio = io.BytesIO()
    font.flavor = 'woff2'
    font.save(bio)
    data = bio.getvalue()
    print(f'  {name}: {len(data):,} bytes')
    return base64.b64encode(data).decode()


def common_hangul() -> set:
    """자주 쓰는 한글 2,350자(KS X 1001 완성형). 사용자가 직접 짓는 캐릭터 이름도 같은 글꼴로 보이게 넣는다."""
    out = set()
    for c in range(0xAC00, 0xD7A4):
        try:
            b = chr(c).encode('cp949')
        except UnicodeEncodeError:
            continue
        if len(b) == 2 and 0xB0 <= b[0] <= 0xC8 and 0xA1 <= b[1] <= 0xFE:
            out.add(chr(c))
    return out


def main() -> None:
    html = SRC.read_text(encoding='utf-8')
    assert '/*FONT_REG*/' in html and '/*FONT_BOLD*/' in html, 'src/game.html 에 글꼴 자리표시(/*FONT_REG*/, /*FONT_BOLD*/)가 없어요'
    chars = set(html) | {chr(c) for c in range(0x20, 0x7F)} | set('…→×·%∞★') | common_hangul()
    text = ''.join(sorted(c for c in chars if c >= ' '))
    print('글꼴 추출 중…')
    html = html.replace('/*FONT_REG*/', subset_font('Galmuri11.woff2', text))
    html = html.replace('/*FONT_BOLD*/', subset_font('Galmuri11-Bold.woff2', text))
    OUT.write_text(html, encoding='utf-8')
    print(f'완료: {OUT.relative_to(ROOT)} ({len(html):,} 글자)')


if __name__ == '__main__':
    main()
