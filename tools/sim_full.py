"""한 직업을 처음부터 3부 끝(이야기 182)까지 한 번에 돌려 이정표 표와 부별 저장을 남긴다(물의 신화 1단계에서 만듦).

사용: python3 tools/sim_full.py <직업: musa|jagaek|sulsa|doin> [최대 시간=420] [저장 폴더=docs/patch-sea/sim]
- tools/test_game.py 의 SIM(사람처럼 굴리는 진행 시뮬)에 '이야기 n번에 닿으면 저장'(snapQs)과 '끝나면 멈춤'(stopQ)만 더했다.
- 빌드된 index.html 을 쓴다(먼저 python3 tools/build.py). 한 직업에 실제 시간 5~12분, 코어 하나를 쓴다.
- 남는 저장: save_<직업>_q113.json(1부를 마치고 부상에 막 건넌 때) · _q145.json(곤륜에 막 들어선 때) · _end.json(3부 끝).
  다음 부(4부·5부) 시뮬의 출발점, 추천 조합 재기(tools/sim_skpre.py), 베타 시험용 캐릭터(tools/beta_save.py)에 쓴다.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

cls = sys.argv[1]
hours = float(sys.argv[2]) if len(sys.argv) > 2 else 420
out = Path(sys.argv[3]) if len(sys.argv) > 3 else T.ROOT / 'docs' / 'patch-sea' / 'sim'
ANCHOR = "if (opts.snapQ && !('q' in snaps)"
SIM = T.SIM.replace(ANCHOR,
    "for (const q of (opts.snapQs || [])) if (!('q' + q in snaps) && G.S.quest.main >= q && !G.raid) snaps['q' + q] = JSON.stringify(G.S);\n"
    "    if (opts.stopQ && G.S.quest.main >= opts.stopQ && !G.raid) { snaps.end = JSON.stringify(G.S); first.END = Math.round(t / 60); break; }\n"
    "    " + ANCHOR)
assert SIM != T.SIM


async def main():
    t0 = time.time()
    async with async_playwright() as p:
        b = await T.launch(p)
        page = await (await b.new_context()).new_page()
        await T.fresh(page)
        marks = list(range(600, int(hours * 60) + 1, 600))
        r = await page.evaluate(SIM, [hours * 60, cls, {'dt': 0.2, 'marks': marks, 'snapQs': [113, 145], 'stopQ': 182}])
        await b.close()
    print('\n'.join(r['log']))
    T.long_table(cls, r['first'])
    end = r['first'].get('END')
    print(f'3부 끝: {end / 60:.1f}시간' if end else f'{hours:.0f}시간 안에 3부 끝에 못 닿음', f'· 걸린 시간 {time.time() - t0:.0f}초')
    out.mkdir(parents=True, exist_ok=True)
    for k, v in r['snaps'].items():
        (out / f'save_{cls}_{k}.json').write_text(v, encoding='utf-8')
        print('저장:', (out / f'save_{cls}_{k}.json'))


asyncio.run(main())
