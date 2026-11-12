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

            # 기기를 오가며(2026-11 (43) 버그): B에서 키워 올린 뒤, 켜진 채 있던 A가 옛 기록을 올리기 전에 B의 새 기록을 불러온다(덮어쓰지 않음)
            await B.evaluate("() => { const G = window.__game; G.S.gold = 777777; G.S.level = 33; }")
            await B.evaluate('async () => { const G = window.__game; await G.pushOnline(); await G.pushOnline(); }')   # 들어올 때 올리던 것이 끝난 뒤 한 번 더
            await B.wait_for_timeout(600)
            await A.evaluate("() => { window.__game.S.level = 8; }")
            await A.evaluate('() => window.__game.pushOnline()')
            await A.wait_for_timeout(1500)
            stA = await A.evaluate('() => ({gold: Math.floor(window.__game.S.gold), level: window.__game.S.level})')
            srvLv = db("select save::json->>'level' from samhan_chars where name = '온라인용사'")
            check(stA['level'] == 33 and stA['gold'] >= 777777 and srvLv == [('33',)], f'켜 둔 다른 기기는 옛 기록으로 덮어쓰지 않고 새 기록을 불러온다 {stA} {srvLv}')
            await A.evaluate("() => { const m = document.querySelector('#modal'); if (m && !m.hidden){ const b = document.querySelector('#modal-btn-0'); if (b) b.click(); } }")
            await B.evaluate("() => { const m = document.querySelector('#modal'); if (m && !m.hidden){ const b = document.querySelector('#modal-btn-0'); if (b) b.click(); } }")

            # 채팅·타임 보스: 두 기기가 실시간으로 이어진다
            await A.evaluate("() => window.__game.sendChat('안녕하세요 온라인')")
            await B.wait_for_timeout(600)
            got = await B.evaluate("() => window.__game.chatMsgs.filter(m => m.kind === 'player').map(m => m.name + ':' + m.text)")
            check(any('안녕하세요 온라인' in g for g in got), f'채팅이 다른 기기로 간다 {got}')
            mega = await B.evaluate("() => { const G = window.__game, c = G.megaCur, e = document.querySelector('#mega'); return {cur: c ? c.m.kind + ':' + c.m.name + ':' + c.m.text : '', q: G.megaQ.map(m => m.text), hidden: e.hidden, who: document.querySelector('#megaWho').textContent, tx: document.querySelector('#megaTx').textContent}; }")
            megaA = await A.evaluate("() => { const G = window.__game, c = G.megaCur; return c ? c.m.kind + ':' + c.m.text : G.megaQ.map(m => m.kind + ':' + m.text).join('|'); }")
            check(('안녕하세요 온라인' in mega['cur'] and mega['cur'].startswith('player:') and not mega['hidden'] and mega['tx'] == '안녕하세요 온라인') or any('안녕하세요 온라인' in t for t in mega['q']), f'다른 용사의 채팅이 확성기(화면 위 띠)로 뜬다 {mega}')
            check('me:안녕하세요 온라인' in megaA, f'내가 한 말도 내 화면에 확성기로 뜬다 {megaA}')
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
            mine = await A.evaluate("""async () => { const G = window.__game, S = G.S; const m = await G.mkMine(); const g0 = S.gems; const c = await G.mkClaim(); const g1 = S.gems;   // 받은 직후에 바로 잼(그 뒤 올리고 내리는 동안 사냥으로 번 보석이 섞이지 않게)
              S.dust = Math.max(S.dust, 100); const d0 = S.dust; const p = await G.mkPost({t:'dust'}, 50, 10); const d1 = S.dust;
              const m2 = await G.mkMine(); const row = (m2.rows || []).find(r => r.it.t === 'dust'); const x = row ? await G.mkCancel(row.id) : null;
              return {sold: (m.rows || []).filter(r => r.sold).length, claim: c.gems, gemsUp: g1 - g0, post: p, dustOut: d0 - d1, dustBack: S.dust - d1, cancel: x}; }""")
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

            # 캐릭터 6칸(물의 신화 2단계): 서버는 한 계정 6명까지 받고 7번째는 거절한다
            tok = await A.evaluate('() => window.__game.online.token')

            def dbx(sql):
                with pg.conn() as c, c.cursor() as cur:
                    cur.execute(sql)

            def srv_save(cid, name):
                try:
                    db("select samhan_save(%s::uuid, %s, %s, '{}'::jsonb, %s, 1)", tok, cid, name, '{"v":1}')
                    return 'ok'
                except Exception as e:
                    return 'too_many' if 'too_many' in str(e) else str(e)[:80]
            r6 = [srv_save(f'cxsix{i}', f'여섯칸{i}') for i in range(1, 7)]   # 이미 1명 + 5명 = 6명, 그다음은 7번째
            n6 = db("select count(*) from samhan_chars where acc = 'online1'")[0][0]
            check(r6 == ['ok'] * 5 + ['too_many'] and n6 == 6, f'캐릭터 6칸: 서버가 한 계정 6명까지 저장하고 7번째는 막는다 {r6} {n6}')
            # 서버가 아직 4칸이면(주인이 setup.sql을 다시 실행하기 전): 5번째 캐릭터는 이 기기에만 저장하고 게임은 그대로, 서버가 6칸이 되면 저절로 올라간다
            setup = (ROOT / 'supabase' / 'setup.sql').read_text(encoding='utf-8')
            f0 = setup.index('create or replace function public.samhan_save'); fn6 = setup[f0:setup.index('end $$;', f0) + len('end $$;')]
            assert 'n >= 6' in fn6
            dbx("delete from samhan_chars where acc = 'online1' and cid in ('cxsix4', 'cxsix5')")   # 서버에 4명(예전 한도)
            dbx(fn6.replace('n >= 6', 'n >= 4'))
            await A.evaluate('() => window.__game.switchChar()')
            await A.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            await tg.create_char(A, '다섯째', 'musa')
            await A.evaluate('() => window.__game.pushOnline()'); await A.wait_for_timeout(700)
            if await A.is_hidden('#moreMenu'): await A.click('#tab-more')
            await A.click('#tab-rec'); await A.wait_for_timeout(400)
            m1 = await A.evaluate("""() => { const G = window.__game, ch = G.REG.accounts.online1.chars.find(c => c.name === '다섯째');
              return {err: ch && ch.srvErr, inGame: !!G.session && G.S.name === '다섯째', note: document.querySelector('#r-save').textContent}; }""")
            srv1 = db("select count(*) from samhan_chars where acc = 'online1' and name = '다섯째'")[0][0]
            await A.screenshot(path=str(OUT / '35_온라인_서버4칸.png'))
            dbx(fn6)                                                                           # 서버가 6칸이 됨(setup.sql 다시 실행)
            await A.evaluate('() => window.__game.pushOnline()'); await A.wait_for_timeout(700)
            m2 = await A.evaluate("""() => { const G = window.__game, ch = G.REG.accounts.online1.chars.find(c => c.name === '다섯째'); return {err: (ch && ch.srvErr) || '', note: document.querySelector('#r-save').textContent}; }""")
            srv2 = db("select count(*) from samhan_chars where acc = 'online1' and name = '다섯째'")[0][0]
            check(m1['err'] == 'many' and m1['inGame'] and '이 기기에만 저장 중' in m1['note'] and srv1 == 0 and m2['err'] == '' and '서버에 자동 저장' in m2['note'] and srv2 == 1,
                  f'서버가 아직 4칸이어도 5번째 캐릭터로 게임이 되고(이 기기에만 저장 중이라고 알림), 서버가 6칸이 되면 저절로 서버에 올라간다 {m1} {srv1} {m2} {srv2}')
            await A.evaluate("() => window.__game.closePage()")

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
                if await D2.is_hidden('#moreMenu'): await D2.click('#tab-more')   # 정보는 [더보기] 안(2026-11 (41))
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

            # 내 저장을 다른 기기 것으로 잘못 보지 않는다(2026-11-12): 서버엔 저장됐는데 답을 못 받아 syncT가 옛 시각으로 남은 상황
            await B.evaluate('async () => { const G = window.__game; await G.pushOnline(); await G.pushOnline(); }')
            await B.wait_for_timeout(400)
            await B.evaluate("() => { const G = window.__game, ch = G.REG.accounts[G.session.acc].chars.find(c => c.cid === G.session.cid); ch.syncT -= 120000; G.S.gold += 5000000; G.S.pets.lv[20] = 7; }")
            await B.evaluate('async () => { const G = window.__game; await G.pushOnline(); await G.pushOnline(); }')
            await B.wait_for_timeout(600)
            keep = await B.evaluate('() => ({gold: Math.floor(window.__game.S.gold), pet: window.__game.S.pets.lv[20]})')
            srvP = db("select (save::json->'pets'->'lv'->>20) from samhan_chars where name = '온라인용사'")
            check(keep['gold'] >= 5000000 and keep['pet'] == 7 and srvP == [('7',)], f'서버 답을 못 받은 내 저장을 다른 기기 것으로 보고 되돌리지 않는다 {keep} {srvP}')
            # 운영 보상(2026-11-12): 정해 둔 이름의 캐릭터가 서버에 로그인해 들어오면 한 번만 받는다
            g = await B.evaluate("""async () => { const G = window.__game, S = G.S; const n0 = S.name, g0 = S.gems; S.name = '가을비'; delete S.gifts['g1112-pet']; G.giveGifts(); const g1 = S.gems; G.giveGifts(); const g2 = S.gems; S.name = n0; S.gems = g0; delete S.gifts['g1112-pet']; return [g1 - g0, g2 - g1]; }""")
            check(g == [150000, 0], f'운영 보상은 그 이름의 캐릭터가 한 번만 받는다 {g}')
            # 저장 보호(2026-11-12): 옛 화면(저장 판 번호가 낮음)이 새 기록을 덮어쓰지 못한다 · 하루 한 번 기록을 따로 남긴다
            await B.evaluate('async () => { const G = window.__game; await G.pushOnline(); await G.pushOnline(); }')
            await B.wait_for_timeout(600)
            sb = db("select save::json->>'saveBuild', save::json->>'level' from samhan_chars where name = '온라인용사'")
            SB = int(re.search(r'const SAVE_BUILD = (\d+)', (ROOT / 'src' / 'game.html').read_text(encoding='utf-8')).group(1))   # 게임의 저장 판 번호(패치마다 오른다)
            tok = db("select token::text from samhan_sessions where acc = 'online1' order by expires_at desc limit 1")[0][0]
            err = ''
            try:
                db("select samhan_save(%s::uuid, (select cid from samhan_chars where name = '온라인용사'), '온라인용사', '{}'::jsonb, %s, 9999999999999)", tok, '{"v":1,"level":1,"pets":{"lv":[1]}}')
            except Exception as e:  # noqa: BLE001
                err = str(e)
            after = db("select save::json->>'level' from samhan_chars where name = '온라인용사'")
            check(sb and sb[0][0] == str(SB) and 'old_client' in err and after == [(sb[0][1],)], f'저장 판 번호가 없는 옛 화면의 저장은 서버가 받지 않는다 {sb} {err[:40]} {after}')
            hist = db("select count(*), min(char_length(save)) from samhan_chars_hist where acc = 'online1'")
            check(hist[0][0] >= 1 and hist[0][1] > 100, f'서버에 그날의 기록이 따로 남는다 {hist}')
            locked = ''
            try:
                with pg.conn() as c, c.cursor() as cur:
                    cur.execute('set role anon'); cur.execute('select count(*) from samhan_chars_hist')
            except Exception as e:  # noqa: BLE001
                locked = str(e)
            check('permission denied' in locked, f'따로 남긴 기록은 바깥에서 읽지 못한다 {locked[:50]}')
            # 서버 기록이 더 새 판이면(다른 기기가 새 버전) 이 화면은 불러오지 않고 저장을 멈춘 뒤 새로 고침을 안내한다
            # (A는 위 「캐릭터 6칸」 확인에서 다른 캐릭터로 바꿔 들어와 있으므로, A가 지금 하는 캐릭터의 서버 기록을 새 판으로 바꾼다)
            await A.evaluate('async () => { const G = window.__game; G.hideModal(); await G.pushOnline(); await G.pushOnline(); }')
            await A.wait_for_timeout(600)
            nameA = await A.evaluate('() => window.__game.S.name')
            sbA = db("select save::json->>'saveBuild', save::json->>'level' from samhan_chars where name = %s", nameA)
            with pg.conn() as c, c.cursor() as cur:
                cur.execute("update samhan_chars set save = replace(save, %s, %s), save_t = save_t + 600000 where name = %s", (f'"saveBuild":{SB}', f'"saveBuild":{SB + 1}', nameA))
            await A.evaluate("() => { window.__game.S.level = 5; }")
            await A.evaluate('() => window.__game.pushOnline()')
            await A.wait_for_timeout(1500)
            ttl = await A.inner_text('#mTitle') if await A.is_visible('#modal') else ''
            await A.evaluate('async () => { window.__game.saveLocal && window.__game.saveLocal(); await window.__game.pushOnline(); }')
            await A.wait_for_timeout(600)
            srv2 = db("select save::json->>'saveBuild', save::json->>'level' from samhan_chars where name = %s", nameA)
            check(sbA and sbA[0][0] == str(SB) and '새 버전' in ttl and srv2 == [(str(SB + 1), sbA[0][1])], f'더 새 판의 기록을 만나면 덮어쓰지 않고 새로 고침을 안내한다 {nameA} {sbA} {ttl} {srv2}')
            await A.screenshot(path=str(OUT / '33_온라인_새버전안내.png'))
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
