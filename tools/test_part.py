"""자동 점검(tools/test_game.py)의 한 대목만 따로 돌린다 — 새 점검을 쓰거나 고칠 때 4~5분짜리 전체 점검을 기다리지 않으려고.

사용: python3 tools/build.py && python3 tools/test_part.py '# 9-13)' '# 10)'
  · 첫 인자 = 시작 줄의 주석 머리(그 줄부터), 둘째 인자 = 끝 줄의 머리(그 줄 앞까지). 둘 다 main() 안의 8칸 들여쓴 줄이어야 한다.
  · 예: 앱 설치·베타 점검만 → python3 tools/test_part.py '# 10)' 'srv.shutdown()'
  · 대목이 앞 대목에서 만든 변수(page 등)를 쓰면 못 돈다. browser · errors · check · late(후반 저장) · test_game.py의 함수들은 쓸 수 있다.
커밋하기 전에는 꼭 전체 점검(python3 tools/test_game.py)을 한 번 돌린다.
"""
import asyncio
import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as tg  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

ROOT = tg.ROOT


def part_code(start, end):
    src = (ROOT / 'tools' / 'test_game.py').read_text(encoding='utf-8')
    a = src.index('        ' + start)
    b = src.index('        ' + end, a + 1)
    return 'async def __part(browser, errors, check, late):\n' + textwrap.indent(textwrap.dedent(src[a:b]), '    ')


async def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    ns = dict(vars(tg))
    exec(compile(part_code(sys.argv[1], sys.argv[2]), 'test_game.py(part)', 'exec'), ns)
    errors, checks = [], []

    def check(ok, msg):
        checks.append(('통과' if ok else '실패') + ' · ' + msg)
        if not ok:
            errors.append('check: ' + msg)

    # 후반 저장(곤륜 끝 4차 무사): 전체 점검의 late와 같은 것
    saves = (json.loads(f.read_text(encoding='utf-8')) for f in sorted((ROOT / 'tools' / 'beta_saves').glob('*.json')))
    late = max((d for d in saves if not d['save'].get('seaPreview') and d['save'].get('world', 0) <= 4), key=lambda d: d['save'].get('level', 0))['save']
    tg.OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await tg.launch(p)
        try:
            await ns['__part'](browser, errors, check, late)
        finally:
            print('\n'.join(checks))
            print('오류:', json.dumps(errors, ensure_ascii=False, indent=1) if errors else '없음')
            await browser.close()
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
