"""권사 시안 캡처(배포 아님): 스프라이트 시트·비교 시트·연속 프레임·사냥 장면.
사용: python3 tools/gwon_shots.py [출력폴더]   (index.html이 빌드되어 있어야 함)"""
import asyncio, base64, sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = (ROOT / 'index.html').as_uri() + '?simtest'
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else '/home/claude/report/gwon_proto'); OUT.mkdir(parents=True, exist_ok=True)

SHEET = r"""
([kind]) => {
  const NAMES = ['서기','걷기1','걷기2','주먹','발차기','발차기 준비','주먹 준비'], FR = [0,1,2,3,4,5,6];
  const Z = 4, W = 64 * Z, H = 64 * Z;
  const mk = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
  const look = {outfit:'auto', hair:'#241c26', hat:'class', skin:0};
  const spr = (sx, br, dir, f) => window.__game.personSprite('musa', look, -1, -1, dir, f, false, {gwon:{sx, br}});
  const cell = (g, sp, x, y, bg) => {
    g.fillStyle = bg || '#2b3a4e'; g.fillRect(x, y, W, H);
    g.fillStyle = 'rgba(255,255,255,0.05)'; for (let i = 0; i < 8; i++) for (let j = 0; j < 8; j++) if ((i + j) % 2) g.fillRect(x + i * 32, y + j * 32, 32, 32);
    g.strokeStyle = 'rgba(255,200,80,.55)'; g.lineWidth = 1; g.beginPath(); g.moveTo(x + 32 * Z / 2 * 1, y + 60 * Z / 2 * 2 / 2 * 1); g.stroke();
    g.imageSmoothingEnabled = false; g.drawImage(sp, x, y, W, H);
    // 발 기준점(32,60) 표시
    g.fillStyle = '#ff3b6b'; g.fillRect(x + 32 * Z / 1 * 1 - 2, y + 60 * Z - 2, 4, 4);
  };
  const lab = (g, t, x, y, sz = 18, c = '#ffe9a8') => { g.fillStyle = c; g.font = 'bold ' + sz + 'px sans-serif'; g.fillText(t, x, y); };
  if (kind === 'frames'){   // 남·여 × 앞/뒤 × 7프레임 (기본 갈래)
    const rows = [['남 · 앞', 'm', 'right'], ['남 · 뒤', 'm', 'up'], ['여 · 앞', 'f', 'right'], ['여 · 뒤', 'f', 'up']];
    const c = mk(110 + FR.length * W, 40 + rows.length * (H + 30)), g = c.getContext('2d');
    g.fillStyle = '#10161f'; g.fillRect(0, 0, c.width, c.height);
    FR.forEach((f, i) => lab(g, NAMES[i], 110 + i * W + 10, 26));
    rows.forEach(([t, sx, d], r) => { lab(g, t, 8, 40 + r * (H + 30) + H / 2); FR.forEach((f, i) => cell(g, spr(sx, 0, d, f), 110 + i * W, 40 + r * (H + 30))); });
    return c.toDataURL();
  }
  if (kind === 'base'){   // 남·여 기본 모습 확대 비교 (앞·뒤, 서기) — 8배
    const Z2 = 8, S = 64 * Z2, c = mk(S * 4 + 40, S + 80), g = c.getContext('2d');
    g.fillStyle = '#10161f'; g.fillRect(0, 0, c.width, c.height);
    [['남 앞', 'm', 'right'], ['남 뒤', 'm', 'up'], ['여 앞', 'f', 'right'], ['여 뒤', 'f', 'up']].forEach(([t, sx, d], i) => {
      g.fillStyle = '#2b3a4e'; g.fillRect(10 + i * S, 50, S - 10, S); g.imageSmoothingEnabled = false; g.drawImage(spr(sx, 0, d, 0), 10 + i * S - 5, 50, S, S); lab(g, t, 20 + i * S, 34, 22); });
    return c.toDataURL();
  }
  if (kind === 'branch'){   // 갈래 비교: 기본/주먹/발 × 남·여 × (서기, 주먹 or 발차기)
    const rows = [['남', 'm'], ['여', 'f']], cols = [['기본 서기', 0, 0], ['주먹 갈래 서기', 1, 0], ['주먹 갈래 주먹', 1, 3], ['발 갈래 서기', 2, 0], ['발 갈래 발차기', 2, 4]];
    const c = mk(70 + cols.length * W, 40 + rows.length * (H + 10)), g = c.getContext('2d');
    g.fillStyle = '#10161f'; g.fillRect(0, 0, c.width, c.height);
    cols.forEach(([t], i) => lab(g, t, 70 + i * W + 8, 26, 16));
    rows.forEach(([t, sx], r) => { lab(g, t, 14, 40 + r * (H + 10) + H / 2, 22); cols.forEach(([_, br, f], i) => cell(g, spr(sx, br, 'right', f), 70 + i * W, 40 + r * (H + 10))); });
    return c.toDataURL();
  }
  if (kind === 'strip'){   // 연속 프레임 스트립: 준비 → 공격 → 서기 (주먹/발차기 × 남·여, 앞모습)
    const seqs = [['남 주먹', 'm', 1, [0, 6, 3, 3, 0]], ['여 주먹', 'f', 1, [0, 6, 3, 3, 0]], ['남 발차기', 'm', 2, [0, 5, 4, 4, 0]], ['여 발차기', 'f', 2, [0, 5, 4, 4, 0]]];
    const Z3 = 3, S = 64 * Z3, c = mk(110 + 5 * S, seqs.length * (S + 8) + 10), g = c.getContext('2d');
    g.fillStyle = '#10161f'; g.fillRect(0, 0, c.width, c.height);
    seqs.forEach(([t, sx, br, fs], r) => { lab(g, t, 8, 10 + r * (S + 8) + S / 2, 16); fs.forEach((f, i) => { g.fillStyle = '#2b3a4e'; g.fillRect(110 + i * S, 10 + r * (S + 8), S - 2, S); g.imageSmoothingEnabled = false; g.drawImage(spr(sx, br, 'right', f), 110 + i * S, 10 + r * (S + 8), S, S); g.fillStyle = '#ff3b6b'; g.fillRect(110 + i * S + 32 * Z3 - 1, 10 + r * (S + 8) + 60 * Z3 - 1, 3, 3); }); });
    return c.toDataURL();
  }
}
"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 780}, device_scale_factor=2)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        for kind, name in [('frames', '2_프레임시트'), ('base', '1_남여_기본모습_비교'), ('branch', '2b_갈래_비교'), ('strip', '4_연속프레임_스트립')]:
            u = await pg.evaluate(SHEET, [kind])
            (OUT / f'{name}.png').write_bytes(base64.b64decode(u.split(',')[1])); print('저장', name)
        print('오류', errs)
        await b.close()
asyncio.run(main())
