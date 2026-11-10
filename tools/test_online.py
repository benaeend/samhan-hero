"""온라인 서버(Supabase) 연결을 이 컴퓨터 안에서 끝까지 확인한다.

진짜 Supabase 대신: 로컬 PostgreSQL에 supabase/setup.sql을 그대로 깔고, Supabase의 함수 호출 창구(PostgREST)를
흉내 내는 작은 서버를 띄운다. 게임은 진짜 supabase-js(vendor/supabase.js)로 그 서버를 부른다.
실시간 채널(채팅·타임 보스)은 페이지끼리 메시지를 이어 주는 가짜 채널로 바꿔 끼운다.

필요: PostgreSQL 16(+pgcrypto), pip install psycopg2-binary playwright
사용: python3 tools/build.py && python3 tools/test_online.py
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as tg  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

import psycopg2  # noqa: E402

ROOT = tg.ROOT
OUT = ROOT / 'tools' / 'out'
VENDOR = (ROOT / 'vendor' / 'supabase.js').read_text(encoding='utf-8')


# ── 1) 임시 PostgreSQL ──
def pg_bin():
    for d in sorted(Path('/usr/lib/postgresql').glob('*/bin'), reverse=True):
        if (d / 'initdb').exists():
            return d
    raise SystemExit('PostgreSQL이 없어요')


def as_pg(cmd):
    if os.geteuid() == 0:
        return subprocess.run(['su', 'postgres', '-c', cmd], check=True, capture_output=True, text=True)
    return subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)


class TempPg:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix='samhan-pg-')
        if os.geteuid() == 0:
            shutil.chown(self.dir, 'postgres')
        self.port = 55000 + os.getpid() % 900
        b = pg_bin()
        as_pg(f'{b}/initdb -D {self.dir}/data -A trust -U postgres')
        as_pg(f"{b}/pg_ctl -D {self.dir}/data -o '-k {self.dir} -p {self.port} -c listen_addresses=' -l {self.dir}/log -w start")
        self.b = b

    def conn(self):
        return psycopg2.connect(host=self.dir, port=self.port, user='postgres', dbname='postgres')

    def stop(self):
        try:
            as_pg(f'{self.b}/pg_ctl -D {self.dir}/data -m fast stop')
        finally:
            shutil.rmtree(self.dir, ignore_errors=True)


# ── 2) Supabase 함수 호출 창구 흉내(POST /rest/v1/rpc/<함수>, anon 권한으로) ──
def make_rpc_server(pg):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def cors(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

        def do_OPTIONS(self):
            self.send_response(204); self.cors(); self.end_headers()

        def reply(self, code, body):
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code); self.cors()
            self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)

        def do_POST(self):
            m = re.fullmatch(r'/rest/v1/rpc/(samhan_[a-z_]+)', self.path.split('?')[0])
            if not m:
                return self.reply(404, {'message': 'not found'})
            args = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
            if not all(re.fullmatch(r'p_[a-z]+', k) for k in args):
                return self.reply(400, {'message': 'bad args'})
            sql = f'select public.{m.group(1)}(' + ', '.join(f'{k} := %s' for k in args) + ')'
            vals = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in args.values()]
            try:
                with pg.conn() as c, c.cursor() as cur:
                    cur.execute('set role anon')
                    cur.execute(sql, vals)
                    v = cur.fetchone()[0]
                return self.reply(200, str(v) if hasattr(v, 'hex') else v)
            except psycopg2.Error as e:
                msg = e.diag.message_primary or str(e)
                return self.reply(400, {'code': e.pgcode, 'message': msg, 'details': None, 'hint': None})

    srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{srv.server_address[1]}'


# ── 3) 페이지끼리 이어 주는 가짜 실시간 채널 ──
FAKE_CHANNEL = r"""
(() => {
  const real = window.supabase.createClient;
  window.supabase.createClient = (...a) => {
    const c = real(...a);
    c.channel = (name, cfg) => {
      const hs = [], me = (cfg && cfg.config && cfg.config.presence && cfg.config.presence.key) || 'k' + Math.random(), pres = {};
      const sync = () => { for (const [type, f, fn] of hs) if (type === 'presence' && f.event === 'sync') fn(); };
      const ch = {
        on(type, filter, fn){ hs.push([type, filter, fn]); return ch; },
        subscribe(cb){ setTimeout(() => cb('SUBSCRIBED'), 30); return ch; },
        track(meta){ pres[me] = [meta]; window.__relaySend(JSON.stringify({presence: true, key: me, meta})); setTimeout(sync, 0); return Promise.resolve('ok'); },
        presenceState(){ return pres; },
        send(m){ window.__relaySend(JSON.stringify(m)); return Promise.resolve('ok'); },
      };
      // 가짜 presence: track을 받으면 그 키를 목록에 넣고, 처음 본 키에는 내 것도 한 번 돌려준다
      window.__relayRecv = s => { const m = JSON.parse(s);
        if (m.presence){ const fresh = !pres[m.key]; pres[m.key] = [m.meta]; if (fresh && pres[me]) window.__relaySend(JSON.stringify({presence: true, key: me, meta: pres[me][0]})); sync(); return; }
        for (const [type, f, fn] of hs) if (type === 'broadcast' && f.event === m.event) fn({type: 'broadcast', event: m.event, payload: m.payload}); };
      return ch;
    };
    return c;
  };
})();
"""


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    errors, checks = [], []

    def check(ok, msg):
        checks.append(('통과' if ok else '실패') + ' · ' + msg)
        if not ok:
            errors.append('check: ' + msg)

    pg = TempPg()
    try:
        with pg.conn() as c, c.cursor() as cur:
            cur.execute('create role anon nologin; create role authenticated nologin;')
            cur.execute((ROOT / 'supabase' / 'setup.sql').read_text(encoding='utf-8'))
        rpc_srv, api = make_rpc_server(pg)
        web, base = tg.serve()
        url = base + 'index.html?simtest'
        pages = []

        async with async_playwright() as p:
            browser = await tg.launch(p)

            async def device(api_url, shared_ctx=None):
                ctx = shared_ctx or await browser.new_context(viewport={'width': 390, 'height': 800}, device_scale_factor=2)
                await ctx.add_init_script(f'window.__samhanOnline = {json.dumps({"url": api_url, "key": "test-publishable-key"})};')
                await ctx.add_init_script(VENDOR + '\n;window.supabase = supabase;')
                await ctx.add_init_script(FAKE_CHANNEL)
                page = await ctx.new_page()
                tg.watch(page, errors, f'[{len(pages)}] ')

                async def relay(s):
                    for q in pages:
                        if q is not page and not q.is_closed():
                            asyncio.ensure_future(q.evaluate('s => window.__relayRecv && window.__relayRecv(s)', s))
                await page.expose_function('__relaySend', relay)
                pages.append(page)
                await page.goto(url)
                await page.wait_for_timeout(1500)
                return ctx, page

            def db(sql, *a):
                with pg.conn() as c, c.cursor() as cur:
                    cur.execute(sql, a)
                    return cur.fetchall()

            # A: 새 계정 → 캐릭터 → 서버 저장
            ctxA, A = await device(api)
            check('온라인 서버' in await A.inner_text('#mBody'), '로그인 화면에 온라인 서버 안내가 보인다')
            await tg.signup(A, 'online1', 'pass1234', '온라인용사', 'sulsa')
            await A.evaluate("() => { const G = window.__game; G.S.gold = 123456; G.S.level = 7; }")
            await A.evaluate('() => window.__game.pushOnline()')
            await A.wait_for_timeout(500)
            rows = db("select acc, name, save_t > 0, summary->>'cls' from samhan_chars")
            check(rows == [('online1', '온라인용사', True, 'sulsa')], f'계정·캐릭터가 서버에 저장된다 {rows}')
            check(db("select count(*) from samhan_accounts where pw_hash like '$2%%'")[0][0] == 1, '서버에는 비밀번호가 bcrypt 해시로만 있다')
            await A.screenshot(path=str(OUT / '30_온라인_A.png'))

            # B: 다른 기기에서 같은 아이디로 로그인 → 서버 기록으로 이어 하기
            ctxB, B = await device(api)
            await B.click('#lg-tab-login')
            await B.fill('#lg-id', 'online1'); await B.fill('#lg-pw', 'wrongpw1')
            await B.click('#modal-btn-0'); await B.wait_for_timeout(1200)
            check('맞지 않아요' in await B.inner_text('#lg-err'), '다른 기기에서 틀린 비밀번호는 막는다')
            await B.fill('#lg-pw', 'pass1234')
            await B.click('#modal-btn-0')
            await B.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            check('온라인용사' in await B.inner_text('#mBody'), '다른 기기에서 로그인하면 서버의 캐릭터가 목록에 나온다')
            await B.screenshot(path=str(OUT / '31_온라인_B_목록.png'))
            await B.click('#modal-btn-1')
            await B.wait_for_function('() => window.__game.session && document.querySelector("#modal").hidden', timeout=15000)
            st = await B.evaluate('() => ({gold: Math.floor(window.__game.S.gold), name: window.__game.S.name, cls: window.__game.S.cls})')
            check(st['gold'] >= 123456 and st['name'] == '온라인용사' and st['cls'] == 'sulsa', f'다른 기기에서 서버의 저장을 불러온다 {st}')

            # 채팅·타임 보스: 두 기기가 실시간으로 이어진다
            await A.evaluate("() => window.__game.sendChat('안녕하세요 온라인')")
            await B.wait_for_timeout(600)
            got = await B.evaluate("() => window.__game.chatMsgs.filter(m => m.kind === 'player').map(m => m.name + ':' + m.text)")
            check(any('안녕하세요 온라인' in g for g in got), f'채팅이 다른 기기로 간다 {got}')
            tb = await A.evaluate("""async () => { const G = window.__game; const w = G.tbWindow(); if (!w.open) G.addTime(w.next - Date.now() + 60000); return G.tbWindow().open; }""")
            await B.evaluate("""() => { const G = window.__game; const w = G.tbWindow(); if (!w.open) G.addTime(w.next - Date.now() + 60000); }""")
            # 타임 보스 동료: 서버에 만들어진 모든 캐릭터 가운데 무작위 10명(같은 직업은 나까지 3명), 계정 아이디는 안 줌
            with pg.conn() as c, c.cursor() as cur:
                cur.execute("insert into samhan_accounts (id, pw_hash) values ('tbfill', 'x') on conflict do nothing")
                for i in range(4):
                    cur.execute("insert into samhan_accounts (id, pw_hash) values (%s, 'x') on conflict do nothing", (f'tbacc{i}',))
                    for j, cl in enumerate(['musa', 'musa', 'sulsa', 'sulsa'] if i < 2 else ['jagaek', 'doin', 'doin', 'jagaek']):
                        cur.execute("insert into samhan_chars (acc, cid, name, summary) values (%s, %s, %s, %s::jsonb) on conflict do nothing",
                                    (f'tbacc{i}', f'tbc{i}x{j}', f'동료{i}{j}', json.dumps({'cls': cl, 'level': 50, 'look': {}, 'ally': {'dps': 100, 'maxHp': 1000, 'rd': 800}})))
                cur.execute("insert into samhan_chars (acc, cid, name, summary) values ('tbfill', 'tbnone', '안싸운캐', '{}'::jsonb) on conflict do nothing")
            why = await B.evaluate("() => window.__game.tbCan('normal')")
            pick = await B.evaluate("""async () => { const G = window.__game; const L = await G.tbFetchPick(true) || []; const n = {}; for (const o of L) n[o.cls] = (n[o.cls] || 0) + 1;
              return {n: L.length, users: G.tbUsers(), byCls: n, me: G.S.cls, self: L.some(o => o.name === G.S.name), none: L.some(o => o.name === '안싸운캐'), acc: L.some(o => 'acc' in o), srv: !!G.tbPick.srv}; }""")
            capOk = all(v <= (2 if k == pick['me'] else 3) for k, v in pick['byCls'].items())
            check(tb and why == '' and pick['n'] == 10 and pick['users'] == 11 and capOk and not pick['self'] and not pick['none'] and not pick['acc'] and pick['srv'],
                  f'타임 보스: 서버의 모든 캐릭터 가운데 무작위 10명이 함께(같은 직업은 3명까지, 나·안 싸워 본 캐릭터는 빼고) {why!r} {pick}')

            # 이름은 서버 전체에서 하나만
            ctxC, C = await device(api)
            await C.click('#lg-tab-signup')
            await C.fill('#lg-id', 'online2'); await C.fill('#lg-pw', 'pass5678'); await C.fill('#lg-pw2', 'pass5678')
            await C.click('#modal-btn-0')
            await C.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            await C.click('#modal-btn-0'); await C.wait_for_selector('#cc-name')
            await C.fill('#cc-name', '온라인용사'); await C.click('#modal-btn-1'); await C.wait_for_timeout(1200)
            check('이미 쓰는 이름' in await C.inner_text('#cc-err'), '다른 사람이 쓰는 캐릭터 이름은 막는다')

            # 장터: 다른 계정끼리 물건을 올리고 사고, 판 값을 받는다. 장터 마을에서는 서로 보인다
            await C.fill('#cc-name', '장터손님'); await C.click('#modal-btn-1')
            await C.wait_for_function('() => window.__game.session', timeout=15000)
            await tg.skip_cut(C, 300)
            post = await A.evaluate("""async () => { const G = window.__game, S = G.S; S.bag = []; G.bagAdd({t:'acc', k:'ring', g:2, p:50}, true); const id = S.bag[0].id;
              const r = await G.mkPost({t:'bag', id}, 1, 120); return {r, left: S.bag.length}; }""")
            lst = await C.evaluate("""async () => { const G = window.__game; G.S.gems = 1000; G.S.bag = []; const L = await G.mkList(''); const row = (L.rows || []).find(r => r.it.t === 'acc');
              const b = row ? await G.mkBuy(row) : null; const again = row ? await G.mkBuy(Object.assign({}, row)) : null;
              return {n: (L.rows || []).length, seller: row && row.name, b, again, gems: G.S.gems, bag: G.S.bag.map(x => x.k + x.g + ':' + x.p)}; }""")
            check(post['r'].get('id') and post['left'] == 0 and lst['seller'] == '온라인용사' and lst['b'] == {'ok': True} and (lst['again'] or {}).get('err') == 'gone'
                  and lst['gems'] == 880 and lst['bag'] == ['ring2:50'], f'장터: 올린 물건을 다른 계정이 보석으로 사고, 두 번은 못 산다 {post} {lst}')
            mine = await A.evaluate("""async () => { const G = window.__game, S = G.S; const m = await G.mkMine(); const g0 = S.gems; const c = await G.mkClaim();
              S.dust = Math.max(S.dust, 100); const d0 = S.dust; const p = await G.mkPost({t:'dust'}, 50, 10); const d1 = S.dust;
              const m2 = await G.mkMine(); const row = (m2.rows || []).find(r => r.it.t === 'dust'); const x = row ? await G.mkCancel(row.id) : null;
              return {sold: (m.rows || []).filter(r => r.sold).length, claim: c.gems, gemsUp: S.gems - g0, post: p, dustOut: d0 - d1, dustBack: S.dust - d1, cancel: x}; }""")
            check(mine['sold'] == 1 and mine['claim'] == 114 and mine['gemsUp'] == 114 and mine['dustOut'] == 50 and mine['dustBack'] == 50 and mine['cancel'] == {'ok': True},
                  f'장터: 판 값(수수료 5%)을 받고, 안 팔린 물건은 내려서 돌려받는다 {mine}')
            # 장터: 치장·신화 조각도 다른 용사와 보석으로 거래, 기본 장비는 못 올린다
            sk = await A.evaluate("""async () => { const G = window.__game, S = G.S; S.skin.inv = []; const it = G.skMake(G.SKC[30], 3); S.skin.inv.push(it);
              const p1 = await G.mkPost({t:'skin', id:it.id}, 1, 500); S.mythShard = 40; const p2 = await G.mkPost({t:'stack', k:'shard'}, 25, 90);
              S.gear.weapon.count[2] = 3; const gearSrc = G.mkSources().some(x => x.src.t === 'gear'); const p3 = await G.mkPost({t:'gear', s:'weapon', it:2}, 1, 10);
              return {p1, p2, p3, gearSrc, inv: S.skin.inv.length, shard: S.mythShard, lines: it.l.length}; }""")
            sb = await C.evaluate("""async () => { const G = window.__game, S = G.S; S.gems = 2000; S.skin = {eq:{}, inv:[], seq:0, found:{}}; S.mythShard = 0;
              const L = await G.mkList('skin'); const row = (L.rows || []).find(r => r.it.t === 'skin'); const b1 = row ? await G.mkBuy(row) : null;
              const L2 = await G.mkList('mat'); const r2 = (L2.rows || []).find(r => r.it.t === 'stack'); const b2 = r2 ? await G.mkBuy(r2) : null;
              const eq = S.skin.eq.shoe; return {b1, b2, gems: S.gems, shoe: eq ? [eq.c, eq.g, eq.l.length] : null, shard: S.mythShard, gearRows: (await G.mkList('')).rows.filter(r => r.it.t === 'gear').length}; }""")
            check(sk['p1'].get('id') and sk['p2'].get('id') and sk['p3'].get('err') == 'bad_item' and not sk['gearSrc'] and sk['inv'] == 0 and sk['shard'] == 15
                  and sb['b1'] == {'ok': True} and sb['b2'] == {'ok': True} and sb['gems'] == 1410 and sb['shoe'] == [30, 3, 4] and sb['shard'] == 25 and sb['gearRows'] == 0,
                  f'장터: 치장·신화 조각도 다른 용사가 보석으로 사 가고(산 치장은 바로 낌), 기본 장비는 올릴 수 없다 {sk} {sb}')
            await A.evaluate("async () => { await window.__game.mkClaim(); }")
            await A.evaluate("() => window.__game.enterMarket()"); await C.evaluate("() => window.__game.enterMarket()")
            await A.wait_for_timeout(3800)
            seen = await A.evaluate("() => [...window.__game.market.peers.values()].map(p => p.n)")
            check('장터손님' in seen, f'장터 마을: 접속한 다른 용사가 이름표를 달고 함께 보인다 {seen}')
            await A.screenshot(path=str(OUT / '33_온라인_장터.png'))
            await A.evaluate("() => window.__game.leaveMarket()")
            # 채팅창 「지금 접속 중」: 다른 기기의 용사 이름·직업·레벨이 보인다
            await A.evaluate("() => { window.__game.roomTrack(true); window.__game.setChat(true); }"); await C.evaluate("() => window.__game.roomTrack(true)")
            await A.wait_for_timeout(1500)
            on = await A.evaluate("() => ({names: window.__game.roomList.map(p => p.n), me: window.__game.roomList.filter(p => p.me).map(p => p.n), shown: !document.querySelector('#chatOn').hidden, text: document.querySelector('#chatOnList').textContent})")
            check('장터손님' in on['names'] and '온라인용사' in on['me'] and on['shown'] and '장터손님' in on['text'], f'채팅창: 지금 접속 중인 용사(이름·직업·레벨)가 보인다 {on}')
            await A.screenshot(path=str(OUT / '34_온라인_접속중.png'))
            await A.evaluate("() => window.__game.setChat(false)")

            # 서버가 생기기 전(또는 연결이 안 될 때) 만든 계정은 다음 로그인 때 서버로 옮겨진다
            ctxD, D = await device('http://127.0.0.1:9')
            await tg.signup(D, 'local1', 'pass0000', '옮길용사', 'doin')
            st = await D.evaluate('() => ({inGame: !!window.__game.session, online: !!window.__game.online})')
            check(st['inGame'] and not st['online'], f'서버가 안 닿아도 이 기기 계정으로 시작한다 {st}')
            await D.close()
            ctxD2 = await browser.new_context(viewport={'width': 390, 'height': 800}, storage_state=await ctxD.storage_state())
            _, D2 = await device(api, ctxD2)
            if await D2.evaluate('() => !!window.__game.session'):   # 로그인 유지로 바로 들어왔으면 로그아웃
                await tg.skip_cut(D2, 300)
                await D2.click('#tab-rec'); await D2.wait_for_timeout(200)
                await D2.click('#outBtn'); await D2.wait_for_timeout(200)
                await D2.click('#mBtns .primary, #mBtns .danger'); await D2.wait_for_timeout(500)
            await D2.click('#lg-tab-login')
            await D2.fill('#lg-id', 'local1'); await D2.fill('#lg-pw', 'pass0000')
            await D2.click('#modal-btn-0')
            await D2.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            msg = await D2.inner_text('#mBody')
            await D2.wait_for_timeout(800)
            rows = db("select acc, name from samhan_chars where acc = 'local1'")
            check('서버로 옮겼어요' in msg and rows == [('local1', '옮길용사')], f'이 기기에만 있던 계정·캐릭터가 서버로 옮겨진다 {rows}')
            await D2.screenshot(path=str(OUT / '32_온라인_계정옮김.png'))
            await browser.close()
        web.shutdown(); rpc_srv.shutdown()
    finally:
        pg.stop()
    print('\n'.join(checks))
    # 틀린 비밀번호·겹친 이름은 서버가 400으로 답하고, '서버가 안 닿는 기기'는 일부러 닫힌 주소를 쓴다(정상)
    errs = [e for e in errors if 'status of 400' not in e and 'ERR_UNSAFE_PORT' not in e]
    print('오류:', json.dumps(errs, ensure_ascii=False, indent=1) if errs else '없음')
    if errs:
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
