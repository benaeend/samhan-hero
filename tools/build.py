"""src/game.html → index.html

게임에 쓰인 글자만 Galmuri 글꼴에서 뽑아 woff2로 만든 뒤, base64로 index.html 안에 넣는다.
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


def main() -> None:
    html = SRC.read_text(encoding='utf-8')
    assert '/*FONT_REG*/' in html and '/*FONT_BOLD*/' in html, 'src/game.html 에 글꼴 자리표시(/*FONT_REG*/, /*FONT_BOLD*/)가 없어요'
    chars = set(html) | {chr(c) for c in range(0x20, 0x7F)} | set('…→×·%∞')
    text = ''.join(sorted(c for c in chars if c >= ' '))
    print('글꼴 추출 중…')
    html = html.replace('/*FONT_REG*/', subset_font('Galmuri11.woff2', text))
    html = html.replace('/*FONT_BOLD*/', subset_font('Galmuri11-Bold.woff2', text))
    OUT.write_text(html, encoding='utf-8')
    print(f'완료: {OUT.relative_to(ROOT)} ({len(html):,} 글자)')


if __name__ == '__main__':
    main()
