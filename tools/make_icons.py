"""앱 아이콘(icons/*.png)을 삼족오(세 발 까마귀) 문양으로 만든다.

빌드된 index.html을 헤드리스 크롬으로 열어 게임이 직접 그린 삼족오 문양(samjokEmblem: 금빛 해 안에 날개를 편 검은 세 발 까마귀,
펫 그림과 같은 화풍으로 새로 그린 것)을 어두운 남색 밤하늘 위에 붙인다. 마스크용(maskable)은 가운데 80% 안에 들어가게 조금 작게.
문양을 바꿨을 때만 다시 돌리면 된다. 파일 이름·경로는 그대로(manifest·sw.js의 CORE를 안 건드림) — 대신 이미 설치한 앱도 새 아이콘을 받게 sw.js의 CACHE 숫자를 올린다.
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
  const c = document.createElement('canvas'); c.width = c.height = size;
  const g = c.getContext('2d'), k = size / 32;
  // 어두운 남색 밤하늘 + 별 몇 개
  const bg = g.createLinearGradient(0, 0, 0, size); bg.addColorStop(0, '#27345c'); bg.addColorStop(1, '#0c1222');
  g.fillStyle = bg; g.fillRect(0, 0, size, size);
  for (const [x, y, r] of [[3.5, 4.5, .45], [7, 2.2, .3], [27.5, 3.2, .4], [29.5, 9, .3], [2.6, 12, .28], [29, 27, .34], [3.4, 27.6, .3], [6.5, 30, .26], [25.5, 30, .26]]){
    g.fillStyle = 'rgba(255,255,255,.7)'; g.beginPath(); g.arc(x * k, y * k, r * k, 0, 7); g.fill(); }
  // 금빛 해 + 삼족오(게임이 그린 문양). 마스크용은 가운데 80% 안에
  const em = G.samjokEmblem(Math.round(size * (mask ? 0.9 : 1)));
  g.drawImage(em, Math.round((size - em.width) / 2), Math.round((size - em.height) / 2));
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
