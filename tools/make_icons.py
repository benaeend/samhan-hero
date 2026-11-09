"""앱 아이콘(icons/*.png)을 게임 속 도트 용사 그림으로 만든다.

빌드된 index.html을 헤드리스 크롬으로 열어 용사 그림을 꺼낸 뒤, 나무색 바탕에 정수 배율로 키워 붙인다.
용사 모습(직업·옷)을 바꾸고 싶을 때만 다시 돌리면 된다.
사용: python3 tools/build.py && python3 tools/make_icons.py
"""
import asyncio
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_game import URL, launch  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'icons'

DRAW = r"""
async ([size, mask]) => {
  const G = window.__game;
  G.S.cls = 'musa';
  G.S.look = {outfit:'#b8382f', hair:'#241c26', hat:'sulsa', skin:0};
  const url = G.sheet().hero[0][0][0];
  const im = await new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = url; });
  const c = document.createElement('canvas'); c.width = c.height = size;
  const g = c.getContext('2d'); g.imageSmoothingEnabled = false;
  const u = size / 32, F = (x, y, w, h, col) => { g.fillStyle = col; g.fillRect(Math.round(x * u), Math.round(y * u), Math.round(w * u), Math.round(h * u)); };
  F(0, 0, 32, 32, '#2b1f17');
  for (let y = 1; y < 32; y += 3) F(0, y, 32, 1, '#31241a');
  if (!mask){ F(1, 1, 30, 30, '#5e4532'); F(2, 2, 28, 28, '#3d2c20'); for (let y = 3; y < 30; y += 3) F(2, y, 28, 1, '#43301f'); }
  // 금빛 해와 땅
  const sun = mask ? [16, 12, 7] : [16, 11, 9];
  g.fillStyle = '#e0b03c'; g.globalAlpha = 0.9;
  for (let dy = -sun[2]; dy <= sun[2]; dy++){ const w = Math.round(Math.sqrt(sun[2] * sun[2] - dy * dy)); F(sun[0] - w, sun[1] + dy, w * 2, 1, '#e0b03c'); }
  g.globalAlpha = 1;
  F(mask ? 7 : 5, mask ? 23 : 25, mask ? 18 : 22, mask ? 2 : 2, '#7a5a3a');
  F(mask ? 9 : 7, mask ? 25 : 27, mask ? 14 : 18, 1, '#5e4532');
  // 용사: 정수 배율
  const s = Math.max(1, Math.floor(size * (mask ? 0.62 : 0.8) / im.width));
  const w = im.width * s, h = im.height * s;
  const x = Math.round(size / 2 - 13.5 * s), y = Math.round((mask ? 24.2 : 26.2) * u - h);
  g.drawImage(im, x, y, w, h);
  return c.toDataURL('image/png');
}
"""


async def main():
    OUT.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await launch(p)
        page = await browser.new_page()
        await page.goto(URL)
        await page.wait_for_timeout(500)
        for name, size, mask in [('icon-192.png', 192, False), ('icon-512.png', 512, False), ('icon-maskable-512.png', 512, True)]:
            data = await page.evaluate(DRAW, [size, mask])
            (OUT / name).write_bytes(base64.b64decode(data.split(',')[1]))
            print('  만듦:', (OUT / name).relative_to(ROOT))
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
