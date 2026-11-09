"""앱 아이콘(icons/*.png)을 게임 속 용사 그림(2~3등신)으로 만든다.

빌드된 index.html을 헤드리스 크롬으로 열어 용사 그림을 꺼낸 뒤, 달밤 바탕에 정수 배율로 키워 붙인다.
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
  const url = G.sheet().hero[0][2][0];          // 오른쪽 아래를 보는 앞모습(2~3등신, 64×64)
  const im = await new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = url; });
  const c = document.createElement('canvas'); c.width = c.height = size;
  const g = c.getContext('2d');
  // 밤하늘 + 금빛 달(타이틀 화면과 같은 느낌)
  const bg = g.createLinearGradient(0, 0, 0, size); bg.addColorStop(0, '#26335a'); bg.addColorStop(1, '#0e1424');
  g.fillStyle = bg; g.fillRect(0, 0, size, size);
  const k = size / 32;
  for (const [x, y, r] of [[5, 6, .5], [9, 3, .35], [25, 4, .4], [28, 12, .35], [4, 14, .3]]){ g.fillStyle = 'rgba(255,255,255,.75)'; g.beginPath(); g.arc(x * k, y * k, r * k, 0, 7); g.fill(); }
  const mx = (mask ? 21 : 22) * k, my = (mask ? 11 : 9) * k, mr = (mask ? 5.5 : 7) * k;
  const glow = g.createRadialGradient(mx, my, mr * .6, mx, my, mr * 2); glow.addColorStop(0, 'rgba(255,214,110,.45)'); glow.addColorStop(1, 'rgba(255,214,110,0)');
  g.fillStyle = glow; g.fillRect(0, 0, size, size);
  const moon = g.createRadialGradient(mx - mr * .3, my - mr * .3, mr * .2, mx, my, mr); moon.addColorStop(0, '#fff4c8'); moon.addColorStop(1, '#ffc94a');
  g.fillStyle = moon; g.beginPath(); g.arc(mx, my, mr, 0, 7); g.fill();
  // 언덕
  g.fillStyle = '#1a2a3a'; g.beginPath(); g.moveTo(0, size); g.lineTo(0, 24 * k); g.quadraticCurveTo(8 * k, 20 * k, 16 * k, 23 * k); g.quadraticCurveTo(25 * k, 20 * k, size, 22 * k); g.lineTo(size, size); g.fill();
  // 용사: 그림 부분만 잘라 정수 배율로
  g.imageSmoothingEnabled = false;
  const sx = 6, sy = 2, sw = 52, sh = 60;
  const s = Math.max(1, Math.floor(size * (mask ? 0.6 : 0.8) / sh));
  const w = sw * s, h = sh * s, x = Math.round(size / 2 - w / 2), y = Math.round(size * (mask ? 0.86 : 0.96) - h);
  g.globalAlpha = .35; g.fillStyle = '#000'; g.beginPath(); g.ellipse(size / 2, y + h - 2 * s, w * .3, 3 * s, 0, 0, 7); g.fill(); g.globalAlpha = 1;
  g.drawImage(im, sx, sy, sw, sh, x, y, w, h);
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
