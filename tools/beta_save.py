"""진행 시뮬이 남긴 저장(JSON)을 베타 테스트 빌드의 「시험용 캐릭터」로 다듬어 tools/beta_saves/ 에 넣는다.

사용: python3 tools/beta_save.py <시뮬 저장.json> <파일 이름(예: 10_musa_heaven)> <캐릭터 이름> <목록 제목> <설명>
- 시뮬은 시계를 빨리 감아 돌리므로 날짜·시각이 들어간 칸(오늘의 할 일·상점·레이드 횟수·부적·토벌패 시각 등)을 비운다.
  빠진 칸은 게임의 mergeState가 기본값으로 채운다.
- 그 뒤 python3 tools/build.py --beta 로 beta/index.html 을 다시 만든다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAY_KEYS = ('dummy', 'vault', 'dboss', 'gr', 'parade', 'mkNpc', 'shop', 'week', 'pvp')   # 통째로 지워 기본값으로(오늘 횟수·주간 기록)


def clean(s: dict) -> dict:
    s = json.loads(json.dumps(s))
    for k in DAY_KEYS:
        s.pop(k, None)
    s['lastSave'] = 0
    s['buff'] = {k: 0 for k in s.get('buff', {})}
    if isinstance(s.get('raid'), dict):
        s['raid']['tk'] = 3
        s['raid']['tkT'] = 0
    if isinstance(s.get('quest'), dict):
        s['quest'].update(day='', dp={}, dgot=[], dall=False)
    if isinstance(s.get('tower'), dict):
        s['tower'].update(day='', n=0, gday='', gn=0, gweek='')
    if isinstance(s.get('off'), dict):
        s['off']['acc'] = 0
    s['speed'] = 1
    s['mode'] = 'auto'
    s['bossAuto'] = True
    s['name'] = ''
    return s


def main() -> None:
    src, stem, name, label, desc = sys.argv[1:6]
    save = clean(json.loads(Path(src).read_text(encoding='utf-8')))
    assert save.get('v') == 1 and save.get('cls'), '게임 저장이 아니에요'
    out = ROOT / 'tools' / 'beta_saves' / f'{stem}.json'
    out.write_text(json.dumps({'name': name, 'label': label, 'desc': desc, 'save': save}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'{out.relative_to(ROOT)}: {out.stat().st_size:,} bytes · Lv.{save.get("level")} · 세계 {save.get("world")} · 이야기 {save.get("quest", {}).get("main")}')


if __name__ == '__main__':
    main()
