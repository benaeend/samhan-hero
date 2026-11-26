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
                await ctx.add_init_script('window.__samhanNoKick = true;')   # 접속 끊기는 맨 끝 점검에서만 켠다(앞의 기기 둘 점검은 그대로)
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

            # 캐릭터 10칸: 서버는 한 계정 10명까지 받고 11번째는 거절한다
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
            r6 = [srv_save(f'cxsix{i}', f'여섯칸{i}') for i in range(1, 11)]   # 이미 1명 + 9명 = 10명, 그다음은 11번째
            n6 = db("select count(*) from samhan_chars where acc = 'online1'")[0][0]
            check(r6 == ['ok'] * 9 + ['too_many'] and n6 == 10, f'캐릭터 10칸: 서버가 한 계정 10명까지 저장하고 11번째는 막는다 {r6} {n6}')
            # 서버가 아직 6칸이면(주인이 setup.sql을 다시 실행하기 전): 7번째 캐릭터는 이 기기에만 저장하고 게임은 그대로, 서버가 10칸이 되면 저절로 올라간다
            setup = (ROOT / 'supabase' / 'setup.sql').read_text(encoding='utf-8')
            f0 = setup.index('create or replace function public.samhan_save'); fn6 = setup[f0:setup.index('end $$;', f0) + len('end $$;')]
            assert 'n >= 10' in fn6
            dbx("delete from samhan_chars where acc = 'online1' and cid in ('cxsix6', 'cxsix7', 'cxsix8', 'cxsix9')")   # 서버에 6명(예전 한도)
            dbx(fn6.replace('n >= 10', 'n >= 6'))
            await A.evaluate('() => window.__game.switchChar()')
            await A.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            await tg.create_char(A, '일곱째', 'musa')
            await A.evaluate('() => window.__game.pushOnline()'); await A.wait_for_timeout(700)
            if await A.is_hidden('#moreMenu'): await A.click('#tab-more')
            await A.click('#tab-rec'); await A.wait_for_timeout(400)
            m1 = await A.evaluate("""() => { const G = window.__game, ch = G.REG.accounts.online1.chars.find(c => c.name === '일곱째');
              return {err: ch && ch.srvErr, inGame: !!G.session && G.S.name === '일곱째', note: document.querySelector('#r-save').textContent}; }""")
            srv1 = db("select count(*) from samhan_chars where acc = 'online1' and name = '일곱째'")[0][0]
            await A.screenshot(path=str(OUT / '35_온라인_서버6칸.png'))
            dbx(fn6)                                                                           # 서버가 10칸이 됨(setup.sql 다시 실행)
            await A.evaluate('() => window.__game.pushOnline()'); await A.wait_for_timeout(700)
            m2 = await A.evaluate("""() => { const G = window.__game, ch = G.REG.accounts.online1.chars.find(c => c.name === '일곱째'); return {err: (ch && ch.srvErr) || '', note: document.querySelector('#r-save').textContent}; }""")
            srv2 = db("select count(*) from samhan_chars where acc = 'online1' and name = '일곱째'")[0][0]
            check(m1['err'] == 'many' and m1['inGame'] and '이 기기에만 저장 중' in m1['note'] and srv1 == 0 and m2['err'] == '' and '서버에 자동 저장' in m2['note'] and srv2 == 1,
                  f'서버가 아직 6칸이어도 7번째 캐릭터로 게임이 되고(이 기기에만 저장 중이라고 알림), 서버가 10칸이 되면 저절로 서버에 올라간다 {m1} {srv1} {m2} {srv2}')
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
            # 화면이 갑자기 다시 열린 뒤(2026-11-12): 이 기기에 더 새 기록이 있으면 서버의 내 옛 기록으로 돌아가지 않는다
            await B.evaluate('async () => { const G = window.__game; await G.pushOnline(); await G.pushOnline(); }')
            await B.wait_for_timeout(400)
            await B.evaluate("() => { const G = window.__game, ch = G.REG.accounts[G.session.acc].chars.find(c => c.cid === G.session.cid); ch.syncT -= 120000; G.saveReg(); G.S.pets.lv[21] = 9; G.S.gems += 4321; G.saveLocal(); window.__g = G.S.gems; }")
            await B.wait_for_timeout(2200)
            await B.evaluate("async () => { const G = window.__game; await G.enterChar(G.session.cid); }")
            await B.wait_for_timeout(800)
            await B.evaluate("() => { const m = document.querySelector('#modal'); if (m && !m.hidden){ const b = document.querySelector('#modal-btn-0'); if (b) b.click(); } }")
            back3 = await B.evaluate('() => ({pet: window.__game.S.pets.lv[21], same: window.__game.S.gems >= window.__g - 1})')   # (이름 주의: re는 정규식 모듈이라 변수 이름으로 쓰지 않는다)
            check(back3 == {'pet': 9, 'same': True}, f'다시 들어올 때 이 기기의 더 새 기록을 서버의 내 옛 기록으로 되돌리지 않는다 {back3}')
            # 옛 화면이 서버에 덮어쓴 기록(판 번호 없음·시각은 더 새것)을 켜 둔 새 화면이 불러오지 않고 다시 올린다
            await B.evaluate('async () => { const G = window.__game; await G.pushOnline(); await G.pushOnline(); }')
            await B.wait_for_timeout(400)
            with pg.conn() as c, c.cursor() as cur:
                cur.execute("update samhan_chars set save = (((save::jsonb - 'saveBuild' - 'saveDev' - 'saveDev2') || '{\"level\":2}'::jsonb))::text, save_t = save_t + 30000 where name = '온라인용사'")
            await B.evaluate('async () => { const G = window.__game; await G.pushOnline(); await G.pushOnline(); }')
            await B.wait_for_timeout(1500)
            lvB = await B.evaluate('() => window.__game.S.level')
            srvL = db("select save::json->>'level', save::json->>'saveBuild' from samhan_chars where name = '온라인용사'")
            SB = int(re.search(r'const SAVE_BUILD = (\d+)', (ROOT / 'src' / 'game.html').read_text(encoding='utf-8')).group(1))   # 게임의 저장 판 번호(패치마다 오른다)
            check(lvB == 33 and srvL == [('33', str(SB))], f'옛 화면이 덮어쓴 기록은 불러오지 않고 내 기록을 다시 올린다 {lvB} {srvL}')
            # 사라진 탑 이정표 보상 되찾기(2026-11-12)
            await B.evaluate("async () => { const G = window.__game, S = G.S; S.tower.best = 160; delete S.av.own.w_phoenix; delete S.av.own.w_cloud; delete S.mount.own.unryong; G.saveLocal(); await G.pushOnline(); await G.enterChar(G.session.cid); }")
            await B.wait_for_timeout(800)
            await B.evaluate("() => { const m = document.querySelector('#modal'); if (m && !m.hidden){ const b = document.querySelector('#modal-btn-0'); if (b) b.click(); } }")
            tw = await B.evaluate("() => { const S = window.__game.S; const r = [!!S.av.own.w_phoenix, !!S.av.own.w_cloud, !!S.mount.own.unryong, !!S.av.own.w_galaxy]; S.tower.best = 0; return r; }")
            check(tw == [True, True, True, False], f'올라간 층까지의 탑 날개·탈것이 빠져 있으면 들어올 때 되찾는다 {tw}')
            # 운영 보상(2026-11-12): 정해 둔 이름의 캐릭터가 서버에 로그인해 들어오면 한 번만 받는다
            g = await B.evaluate("""async () => { const G = window.__game, S = G.S; const n0 = S.name, g0 = S.gems, f0 = S.gifts; S.name = '가을비'; S.gifts = {};
              G.giveGifts(); const g1 = S.gems; G.giveGifts(); const g2 = S.gems; S.name = n0; S.gems = g0; S.gifts = f0;
              return [g1 - g0, g2 - g1, G.GIFTS.filter(x => x.name === '가을비').reduce((a, x) => a + x.gems, 0)]; }""")
            await B.wait_for_timeout(1800)
            await B.evaluate("() => { const G = window.__game; if (!document.querySelector('#modal').hidden) G.hideModal(); }")   # 운영 보상 창(1.5초 뒤에 뜸)을 닫아 둔다
            check(g[0] == g[2] and g[0] >= 150000 and g[1] == 0, f'운영 보상은 그 이름의 캐릭터가 한 번만 받는다(그 이름에 걸린 보상 모두) {g}')
            # 저장 보호(2026-11-12): 옛 화면(저장 판 번호가 낮음)이 새 기록을 덮어쓰지 못한다 · 하루 한 번 기록을 따로 남긴다
            await B.evaluate('async () => { const G = window.__game; await G.pushOnline(); await G.pushOnline(); }')
            await B.wait_for_timeout(600)
            sb = db("select save::json->>'saveBuild', save::json->>'level' from samhan_chars where name = '온라인용사'")
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

            # 한 계정은 한 화면에서만(2026-11-13): 새 기기가 접속하면 켜져 있던 기기는 저장하지 않고 멈춘다
            await B.evaluate("() => { window.__samhanNoKick = false; }")
            await B.evaluate('async () => { await window.__game.claimActive(true); }')
            kb = await B.evaluate('async () => await window.__game.checkKick()')
            check(kb is False, f'내가 마지막으로 접속한 화면은 멈추지 않는다 {kb}')
            with pg.conn() as c, c.cursor() as cur:   # 앞 점검이 올려 둔 「더 새 판」 기록을 되돌려, 새 기기가 정상으로 들어오게 한다
                cur.execute("update samhan_chars set save = replace(save, %s, %s) where name = '온라인용사'", (f'"saveBuild":{SB}', f'"saveBuild":{SB - 1}'))
            ctxF, F = await device(api)
            await F.evaluate("() => { window.__samhanNoKick = false; }")
            await F.click('#lg-tab-login')
            await F.fill('#lg-id', 'online1'); await F.fill('#lg-pw', 'pass1234')
            await F.click('#modal-btn-0')
            await F.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            await F.click('#modal-btn-1')
            try:
                await F.wait_for_function('() => window.__game.session && document.querySelector("#modal").hidden', timeout=15000)
            except Exception:
                print('DEBUG F', await F.inner_text('#mTitle'), '|', (await F.inner_text('#mBody'))[:200], '|', await F.evaluate('() => !!window.__game.session'))
                raise
            lvBefore = db("select save::json->>'level' from samhan_chars where name = '온라인용사'")
            # 20초마다 도는 자동 확인이 먼저 멈춰 놓았으면 checkKick()은 「이미 멈춤」이라 false를 돌려준다 → 멈춤 창이 떠 있어도 멈춘 것으로 본다
            kk = await B.evaluate('async () => !!(await window.__game.checkKick()) || /다른 기기에서 접속/.test(document.querySelector("#mTitle").textContent)')
            ttlB = await B.inner_text('#mTitle')
            await B.evaluate("() => { window.__game.S.level = 4; }")
            await B.evaluate('async () => { await window.__game.pushOnline(); }')
            await B.wait_for_timeout(600)
            lvAfter = db("select save::json->>'level' from samhan_chars where name = '온라인용사'")
            kf = await F.evaluate('async () => await window.__game.checkKick()')
            check(kk is True and '다른 기기에서 접속' in ttlB and lvAfter == lvBefore and kf is False,
                  f'다른 기기가 접속하면 먼저 켜진 기기는 멈추고 저장하지 않는다 {kk} {ttlB} {lvBefore} {lvAfter} {kf}')
            await B.screenshot(path=str(OUT / '34_온라인_접속끊김.png'))
            # 캐릭터 순서(2026-11-17): 서버 SQL은 그대로, 캐릭터 요약(summary)의 ordl·ordT로 다른 기기에도 같은 순서. 가장 최근에 바꾼 쪽을 따른다
            names_js = "() => [...document.querySelectorAll('#mBody .char[data-cid] b')].map(b => b.textContent).join()"
            ctxP, P = await device(api)
            await tg.signup(P, 'order1', 'pass1234', '첫째', 'musa')
            for nm, cl in (('둘째', 'jagaek'), ('셋째', 'sulsa')):
                await P.evaluate('() => window.__game.pushOnline()'); await P.wait_for_timeout(500)
                await P.evaluate('() => window.__game.switchChar()')
                await P.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
                await tg.create_char(P, nm, cl)
            await P.evaluate('() => window.__game.pushOnline()'); await P.wait_for_timeout(500)
            await P.evaluate('() => window.__game.switchChar()')
            await P.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            check(await P.evaluate(names_js) == '첫째,둘째,셋째', f'순서: 처음엔 만든 순서(새 캐릭터는 맨 아래) {await P.evaluate(names_js)}')
            before = db("select name, save_t, md5(save) from samhan_chars where acc = 'order1' order by name")
            cid3 = db("select cid from samhan_chars where name = '셋째'")[0][0]
            await P.click(f'#mBody .mvb[data-cid="{cid3}"][data-mv="-1"]'); await P.click(f'#mBody .mvb[data-cid="{cid3}"][data-mv="-1"]')
            await P.wait_for_timeout(2500)
            after = db("select name, save_t, md5(save) from samhan_chars where acc = 'order1' order by name")
            ordl = db("select name, summary->'ordl', (summary->>'ordT')::bigint from samhan_chars where acc = 'order1' order by name")
            check(await P.evaluate(names_js) == '셋째,첫째,둘째' and before == after, f'순서를 바꿔도 서버의 저장 기록(save·save_t)은 그대로다 {before} {after}')
            check(len(ordl) == 3 and len({json.dumps(r[1]) for r in ordl}) == 1 and len({r[2] for r in ordl}) == 1 and ordl[0][2] > 0, f'서버의 캐릭터마다 같은 순서(ordl·ordT)가 적힌다 {ordl}')
            await P.screenshot(path=str(OUT / '35_온라인_캐릭터순서.png'))
            # 다른 기기에서 같은 아이디로 로그인해도 같은 순서
            ctxQ, Q = await device(api)
            await Q.click('#lg-tab-login'); await Q.fill('#lg-id', 'order1'); await Q.fill('#lg-pw', 'pass1234'); await Q.click('#modal-btn-0')
            await Q.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            check(await Q.evaluate(names_js) == '셋째,첫째,둘째', f'다른 기기에서도 같은 순서로 나온다 {await Q.evaluate(names_js)}')
            # 그 기기에서 다시 바꾸면(더 최근) 처음 기기도 그 순서를 따른다
            cid2 = db("select cid from samhan_chars where name = '둘째'")[0][0]
            await Q.wait_for_timeout(50)
            await Q.click(f'#mBody .mvb[data-cid="{cid2}"][data-mv="-1"]'); await Q.wait_for_timeout(2000)
            await P.evaluate('() => window.__game.REG.accounts.order1 && 0')
            await P.goto(url); await P.wait_for_selector('#lg-id'); await P.click('#lg-tab-login'); await P.fill('#lg-id', 'order1'); await P.fill('#lg-pw', 'pass1234'); await P.click('#modal-btn-0')
            await P.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            check(await P.evaluate(names_js) == '셋째,둘째,첫째', f'가장 최근에 바꾼 순서를 따른다(P가 다시 로그인) {await P.evaluate(names_js)}')
            # 이 기기에서 오프라인으로 더 새 순서를 만들었다면 서버가 그 순서로 바뀐다
            await P.evaluate("""async () => { const G = window.__game, A = G.REG.accounts.order1; A.chars.reverse(); A.ordT = Date.now() + 60000; await G.syncChars('order1'); }""")
            await P.wait_for_timeout(2500)
            srvFirst = db("select summary->'ordl'->>0 from samhan_chars where name = '첫째'")
            cid1 = db("select cid from samhan_chars where name = '첫째'")[0][0]
            check(srvFirst == [(cid1,)], f'이 기기의 순서가 더 새것이면 서버에 알린다(맨 앞이 첫째) {srvFirst}')
            # 서버가 순서 정보를 모르는 옛 요약이면(없음) 오류 없이 이 기기 순서를 유지
            dbx("update samhan_chars set summary = summary - 'ordl' - 'ordT' where acc = 'order1'")
            await P.evaluate("""async () => { const A = window.__game.REG.accounts.order1; A.ordT = 0; await window.__game.syncChars('order1'); }""")
            await P.evaluate("() => window.__game.showCharSelect()"); await P.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            check(await P.evaluate(names_js) == '첫째,둘째,셋째', f'서버에 순서 정보가 없으면 이 기기 순서를 그대로 둔다 {await P.evaluate(names_js)}')
            await ctxP.close(); await ctxQ.close()

            # ───────────── 주간 대요괴 W1~W14 (서버 함수 samhan_wb_hit·state·claim) ─────────────
            async def wb_play(page, cut=0.0, win=False):
                """대요괴 한 판을 진짜 게임 흐름(startWb → 싸움 끝 → finishWb → 서버 제출)으로 돌린다. cut = 보스 체력을 깎은 몫"""
                return await page.evaluate("""async ([cut, win]) => { const G = window.__game; G.wbForce = true; G.quiet = true; await G.wbRefresh(true);
                  const n0 = G.wbV ? G.wbV.me.n : 0, why = G.wbCan(); if (why) return {err: why};
                  G.startWb(); const R = G.raid; R.boss.hp = R.boss.maxHp * (1 - cut); G.raidEnd(win);
                  for (let i = 0; i < 80 && G.raid; i++) await new Promise(r => setTimeout(r, 100));
                  for (let i = 0; i < 40 && !(G.wbV && G.wbV.me.n > n0); i++) await new Promise(r => setTimeout(r, 100));
                  return {ok: true, src: G.wbV && G.wbV.src, sum: G.wbV && G.wbV.sum, me: G.wbV && G.wbV.me, left: G.wbV && G.wbV.left}; }""", [cut, win])

            def sql_err(sql, *a):
                try:
                    db(sql, *a)
                    return 'ok'
                except Exception as e:
                    return str(e).split('\n')[0].strip()

            async def wb_acct(uid, name, cls='musa'):
                ctx, pg_ = await device(api)
                await tg.signup(pg_, uid, 'pass1234', name, cls)
                await pg_.evaluate('() => window.__game.pushOnline()'); await pg_.wait_for_timeout(500)
                tk = await pg_.evaluate('() => window.__game.online.token'); cd = await pg_.evaluate('() => window.__game.session.cid')
                return ctx, pg_, tk, cd
            WBS = "select (samhan_wb_state(%s::uuid, %s))"
            ctxWA, WA, tokA, cidA = await wb_acct('wbaaaa', '대요괴가', 'musa')
            ctxWB, WB_, tokB, cidB = await wb_acct('wbbbbb', '대요괴나', 'sulsa')
            ctxWC, WC, tokC, cidC = await wb_acct('wbcccc', '대요괴다', 'doin')
            wkNow = db("select samhan_wb_wk(0)")[0][0]
            # 이번 주 보스는 서버와 화면이 같은 칸(주 번호 % 4)
            bossSrv = db(WBS, tokA, cidA)[0][0]['boss']
            bossCli = await WA.evaluate("(w) => window.__game.wbBossIdx(w)", wkNow)
            check(bossSrv == bossCli, f'W0 이번 주({wkNow}) 대요괴: 서버와 화면이 같은 보스 칸을 쓴다 {bossSrv} {bossCli}')

            # W1: 두 기기가 각각 한 판 → 서버 합 = 두 점수의 합, 두 화면의 막대가 같다
            rA = await wb_play(WA, 0.925); rB = await wb_play(WB_, 0.705)
            sumDb = db("select coalesce(sum(score), 0) from samhan_wb where wk = %s", wkNow)[0][0]
            await WA.evaluate("() => window.__game.wbRefresh(true)"); await WB_.evaluate("() => window.__game.wbRefresh(true)")
            sa = await WA.evaluate("() => window.__game.wbV.sum"); sb = await WB_.evaluate("() => window.__game.wbV.sum")
            for pg_ in (WA, WB_):
                await pg_.evaluate("() => { const G = window.__game; G.hideModal(); G.closePage(); G.wbForce = true; G.buildTab('raid'); const b = document.querySelector('[data-rv=\"wb\"]'); if (b) b.click(); }")
            await WA.wait_for_timeout(700); await WB_.wait_for_timeout(300)
            bar = lambda pg_: pg_.evaluate("() => { const e = document.querySelector('#wbBox .bar i'); return e ? e.style.width : null; }")
            barA, barB = await bar(WA), await bar(WB_)
            check(rA.get('ok') and rB.get('ok') and rA['me']['score'] == 92 and rB['me']['score'] == 70 and sumDb == 162 and sa == 162 and sb == 162 and barA == barB and barA == '5.4%',
                  f'W1 두 기기가 각각 한 판(92점·70점) → 서버 합 162, 두 화면 막대가 같다 {rA} {rB} {sumDb} {sa} {sb} {barA} {barB}')
            await WA.screenshot(path=str(OUT / '36_대요괴_온라인A.png'))
            await WB_.screenshot(path=str(OUT / '36_대요괴_온라인B.png'))
            wbtxt = await WA.inner_text('#wbBox')
            check('서버 전체' in wbtxt and '162' in wbtxt, f'W1 화면에 「서버 전체」 합계와 목표(1000 × 3명)가 보인다 {wbtxt[:200]!r}')

            # W2: A가 하루 세 번을 채우고, 4번째는 서버가 wb_many, 게임은 「오늘은 다 쳤어요」
            dbx("update samhan_wb_log set at = at - interval '2 minutes'")
            r2 = await wb_play(WA, 0.5)
            dbx("update samhan_wb_log set at = at - interval '2 minutes'")
            r3 = await wb_play(WA, 0.4)
            dbx("update samhan_wb_log set at = at - interval '2 minutes'")
            r4 = await wb_play(WA, 0.3)
            e4 = sql_err("select samhan_wb_hit(%s::uuid, %s, 50, 60, 5)", tokA, cidA)
            check(r2.get('ok') and r3.get('ok') and 'wb_many' in e4 and r4.get('err') == '오늘은 다 쳤어요' and r4.get('left') is None,
                  f'W2 하루 3번까지만: 서버가 4번째를 wb_many로 막고 게임은 「오늘은 다 쳤어요」 {r2.get("me")} {r3.get("me")} {r4} {e4}')
            sumNow = db("select sum(score) from samhan_wb where wk = %s", wkNow)[0][0]

            # W3: 점수 150·−5·걸린 초 3초는 서버가 거절, 합은 그대로
            dbx("update samhan_wb_log set at = at - interval '2 minutes'")
            e3 = [sql_err("select samhan_wb_hit(%s::uuid, %s, %s, %s, 5)", tokC, cidC, s, t) for s, t in ((150, 60), (-5, 60), (50, 3), (50, 61))]
            e3b = sql_err("select samhan_wb_hit(%s::uuid, %s, 119, 60, 5)", tokC, cidC)   # 쓰러뜨린 판 보너스가 판 길이와 안 맞음(60초 다 쓰고 119점)
            check(all('wb_bad' in x for x in e3) and 'wb_bad' in e3b and db("select count(*) from samhan_wb where acc = 'wbcccc'")[0][0] == 0 and db("select sum(score) from samhan_wb where wk = %s", wkNow)[0][0] == sumNow,
                  f'W3 점수 150·−5·걸린 초 3초·61초·앞뒤가 안 맞는 119점은 모두 거절, 합은 그대로 {e3} {e3b}')

            # W4: 같은 캐릭터가 곧바로 또 보내면 wb_fast(진짜 한 판이 걸리는 초만큼 떨어져야 함), 시간이 지나면 통과
            ok1 = sql_err("select samhan_wb_hit(%s::uuid, %s, 10, 60, 5)", tokC, cidC)
            e5 = sql_err("select samhan_wb_hit(%s::uuid, %s, 10, 60, 5)", tokC, cidC)
            e5b = sql_err("select samhan_wb_hit(%s::uuid, %s, 10, 8, 5)", tokC, cidC)
            dbx("update samhan_wb_log set at = at - interval '2 minutes' where acc = 'wbcccc'")
            ok2 = sql_err("select samhan_wb_hit(%s::uuid, %s, 10, 8, 5)", tokC, cidC)
            check('ok' == ok1 and 'wb_fast' in e5 and 'wb_fast' in e5b and ok2 == 'ok', f'W4 같은 캐릭터가 곧바로 또 보내면 wb_fast, 시간이 지나면 통과(일찍 쓰러진 짧은 판은 짧게) {ok1} {e5} {e5b} {ok2}')

            # W5: 남의 캐릭터 id로 보냄·없는 캐릭터 → 거절(wb_char), W6: 옛 화면 → old_client
            e6 = sql_err("select samhan_wb_hit(%s::uuid, %s, 30, 60, 5)", tokB, cidA)
            e6b = sql_err("select samhan_wb_hit(%s::uuid, 'nosuchcid1', 30, 60, 5)", tokB)
            e6c = sql_err("select samhan_wb_hit(%s::uuid, %s, 30, 60, 5)", '00000000-0000-0000-0000-000000000000', cidB)
            e7 = sql_err("select samhan_wb_hit(%s::uuid, %s, 30, 60, 4)", tokB, cidB)
            check('wb_char' in e6 and 'wb_char' in e6b and 'bad_token' in e6c, f'W5 남의 캐릭터 id·없는 캐릭터는 wb_char, 없는 토큰은 bad_token {e6} {e6b} {e6c}')
            check('old_client' in e7, f'W6 판 번호가 낮은 옛 화면은 old_client {e7}')
            # 계정 하루 6번: 계정 B가 오늘 5번을 더 쳤다고 치고(다른 캐릭터), B의 캐릭터가 또 보내면 wb_many
            dbx(f"insert into samhan_wb_log (wk, acc, cid, day, score, secs, at) select '{wkNow}', 'wbbbbb', 'fakechar' || g, (now() at time zone 'Asia/Seoul')::date, 10, 60, now() - interval '3 hours' from generate_series(1, 5) g")
            dbx("update samhan_wb_log set at = at - interval '2 minutes' where acc = 'wbbbbb' and cid = '" + cidB + "'")
            e8 = sql_err("select samhan_wb_hit(%s::uuid, %s, 30, 60, 5)", tokB, cidB)
            vB = db(WBS, tokB, cidB)[0][0]
            check('wb_many' in e8 and vB['left'] == 0 and vB['left_c'] == 2, f'W5b 한 계정은 하루 6번: 캐릭터는 2번 남았어도 계정 한도로 막힌다 {e8} left={vB["left"]} left_c={vB["left_c"]}')
            dbx("delete from samhan_wb_log where cid like 'fakechar%'")

            # W7: 합이 25%를 넘으면 A·B 모두 받기 가능, 한 번 받은 뒤에는 false, 다른 기기에서 같은 캐릭터로도 false
            dbx("update samhan_wb set score = 1000 where acc = 'wbaaaa'")   # 합 ≥ 750(= 3000의 25%)
            await WA.evaluate("() => window.__game.wbRefresh(true)"); await WB_.evaluate("() => window.__game.wbRefresh(true)")
            g0 = await WA.evaluate("() => window.__game.S.gems")
            oA = await WA.evaluate("async () => { const G = window.__game; const o = await G.wbClaim(25); return {o, g: G.S.gems}; }")
            oB = await WB_.evaluate("async () => { const G = window.__game; const o = await G.wbClaim(25); return {o, g: G.S.gems}; }")
            oA2 = await WA.evaluate("async () => { const G = window.__game; const o = await G.wbClaim(25); return o; }")
            sq = db("select samhan_wb_claim(%s::uuid, %s, 25)", tokA, cidA)[0][0]
            ctxWA2 = await browser.new_context(viewport={'width': 390, 'height': 800}, device_scale_factor=2)   # 다른 기기: 같은 아이디로 로그인
            await ctxWA2.add_init_script('window.__samhanNoKick = true;'); await ctxWA2.add_init_script(f'window.__samhanOnline = {json.dumps({"url": api, "key": "test-publishable-key"})};')
            await ctxWA2.add_init_script(VENDOR + '\n;window.supabase = supabase;'); await ctxWA2.add_init_script(FAKE_CHANNEL)
            WA2 = await ctxWA2.new_page(); tg.watch(WA2, errors, '[wa2] ')
            async def noop_relay(s):
                return None
            await WA2.expose_function('__relaySend', noop_relay)
            await WA2.goto(url); await WA2.wait_for_selector('#lg-id'); await WA2.click('#lg-tab-login'); await WA2.fill('#lg-id', 'wbaaaa'); await WA2.fill('#lg-pw', 'pass1234'); await WA2.click('#modal-btn-0')
            await WA2.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            await WA2.click('#modal-btn-1'); await WA2.wait_for_function('() => window.__game.session && document.querySelector("#modal").hidden', timeout=15000); await tg.skip_cut(WA2)
            oA3 = await WA2.evaluate("async () => { const G = window.__game; G.wbForce = true; await G.wbRefresh(true); return {ready: !!G.wbV && G.wbV.src === 'srv', got: G.wbV && G.wbV.me.got, o: await G.wbClaim(25)}; }")
            check(oA['o'] and oA['g'] > g0 and oB['o'] and oA2 is None and sq is False and oA3['o'] is None and oA3['ready'] and (oA3['got'] & 1) == 1,
                  f'W7 25% 단계: A·B 모두 한 번 받고, 다시 누르면 받을 게 없고(서버도 false), 다른 기기의 같은 캐릭터도 못 받는다 {oA} {oB} {oA2} {sq} {oA3}')
            await WA.evaluate("() => { const G = window.__game; G.hideModal(); G.buildTab('raid'); document.querySelector('[data-rv=\"wb\"]').click(); }"); await WA.wait_for_timeout(500)
            await WA.screenshot(path=str(OUT / '36_대요괴_단계보상.png'))
            await ctxWA2.close()

            # W8: 한 번도 안 친 캐릭터는 받기 불가(화면·서버)
            dbx("delete from samhan_wb where acc = 'wbcccc'"); dbx("delete from samhan_wb_log where acc = 'wbcccc'")
            await WC.evaluate("() => { window.__game.wbForce = true; return window.__game.wbRefresh(true); }")
            oC = await WC.evaluate("async () => { const G = window.__game; const o = await G.wbClaim(25); return {o, sum: G.wbV.sum, ready: G.wbV.me.score}; }")
            sqC = db("select samhan_wb_claim(%s::uuid, %s, 25)", tokC, cidC)[0][0]
            check(oC['o'] is None and oC['ready'] == 0 and oC['sum'] > 750 and sqC is False, f'W8 한 번도 안 친 C는 합이 넘어도 받을 수 없다 {oC} {sqC}')

            # W10: 위 10명 목록에는 계정 아이디가 없다(이름·직업·점수만)
            stt = db(WBS, tokA, cidA)[0][0]
            check(all(set(t) == {'name', 'cls', 'score'} for t in stt['top']) and 'wbaaaa' not in json.dumps(stt) and 'wbbbbb' not in json.dumps(stt) and len(stt['top']) == 2 and stt['top'][0]['name'] == '대요괴가',
                  f'W10 위 10명에는 이름·직업·점수만 있다(계정 아이디 없음) {stt["top"]}')

            # W11: 바깥(anon)에서 표를 직접 읽거나 쓰면 거절
            def anon_try(sql):
                with pg.conn() as c, c.cursor() as cur:
                    cur.execute('set role anon')
                    try:
                        cur.execute(sql)
                        return 'ok'
                    except Exception as e:
                        return str(e).split('\n')[0]
            tries = [anon_try('select * from samhan_wb'), anon_try('select * from samhan_wb_log'), anon_try("update samhan_wb set score = 99999"), anon_try('select samhan_wb_view(\'wbaaaa\', \'x\')'), anon_try('select samhan_wb_wk(0)')]
            check(all('permission denied' in x for x in tries), f'W11 표 2개와 내부 함수는 바깥에서 permission denied {tries}')

            # W12: 실시간 소식은 화면에 글자로만 뜨고 합계는 바뀌지 않는다
            s_before = db("select sum(score) from samhan_wb where wk = %s", wkNow)[0][0]
            await WB_.evaluate("() => { window.__wbSeen = ''; new MutationObserver(ms => { for (const m of ms) for (const n of m.addedNodes) window.__wbSeen += n.textContent + '|'; }).observe(document.getElementById('log'), {childList: true}); }")
            await WA.evaluate("() => window.__game.room.emit('wb', {n:'대요괴가', s:92})"); await WB_.wait_for_timeout(1200)
            lg = await WB_.evaluate("() => window.__wbSeen")
            fake = await WB_.evaluate("() => { const G = window.__game; G.wbRecv({data:{n:'<b>가짜</b>', s:9999}}); G.wbRecv({data:{n:'x', s:-1}}); return window.__wbSeen; }")
            await WB_.evaluate("() => window.__game.wbRefresh(true)")
            s_after = db("select sum(score) from samhan_wb where wk = %s", wkNow)[0][0]
            check('대요괴가님이 주간 대요괴에게 92점' in lg and '9999' not in fake and s_before == s_after and await WB_.evaluate("() => window.__game.wbV.sum") == s_after,
                  f'W12 B 화면에 A의 「92점」 소식이 뜨고(이상한 점수는 무시), 소식만으로는 서버 합이 안 바뀐다 {lg!r} {fake!r}')

            # W9: 주가 바뀌면 이번 주 합 0, 목표 = 1000 × max(3, 지난주 참가 수), 지난주 1~3등이 이번 주 별호
            dbx("update samhan_wb set wk = samhan_wb_wk(-1)"); dbx("update samhan_wb_log set wk = samhan_wb_wk(-1)")
            st0 = db(WBS, tokA, cidA)[0][0]
            dbx("insert into samhan_accounts (id, pw_hash) select 'wbfake' || g, 'x' from generate_series(1, 5) g")
            dbx("insert into samhan_wb (wk, acc, cid, name, score, n, best) select samhan_wb_wk(-1), 'wbfake' || g, 'fk' || g, '가짜용사' || g, 10 + g, 1, 10 from generate_series(1, 5) g")
            st1 = db(WBS, tokA, cidA)[0][0]
            await WA.evaluate("() => { const G = window.__game; G.wbForce = true; G.S.wb.ti = ''; return G.wbRefresh(true); }")
            ti = await WA.evaluate("() => { const G = window.__game; G.titleCheck(); return {on: G.wbTitleOn(), own: !!G.S.title.own.wbhunt, prev: G.wbV.prevTop}; }")
            await WC.evaluate("() => { const G = window.__game; G.wbNoFn = false; G.S.wb.ti = ''; return G.wbRefresh(true); }")
            tiB = await WC.evaluate("() => { const G = window.__game; G.titleCheck(); return {on: G.wbTitleOn(), own: !!G.S.title.own.wbhunt, src: G.wbV.src, prev: G.wbV.prevTop}; }")
            gone = await WA.evaluate("() => { const G = window.__game; G.S.wb.ti = '2020-01-06'; G.titleCheck(); return {on: G.wbTitleOn(), own: !!G.S.title.own.wbhunt, eq: G.S.title.eq}; }")
            check(st0['sum'] == 0 and st0['target'] == 3000 and st1['sum'] == 0 and st1['target'] == 7000 and st1['wk'] == wkNow and ti['on'] and ti['own'] and not tiB['on'] and not tiB['own'] and not gone['own'] and gone['eq'] != 'wbhunt',
                  f'W9 주가 바뀌면 합 0·목표 = 1000 × max(3, 지난주 참가 {st1["target"]}), 지난주 1~3등만 이번 주 별호(한 주 지나면 빠짐) {st0["sum"]} {st0["target"]} {st1["target"]} {ti} {tiB} {gone} {st1["prev_top"]}')
            await WA.evaluate("() => { const G = window.__game; G.hideModal(); G.buildTab('raid'); document.querySelector('[data-rv=\"wb\"]').click(); }"); await WA.wait_for_timeout(500)
            await WA.screenshot(path=str(OUT / '36_대요괴_새주.png'))

            # W13: 서버에 대요괴 함수가 없으면(setup.sql 다시 실행 전) 오류 없이 혼자 모드
            dbx("drop function samhan_wb_state(uuid, text); drop function samhan_wb_hit(uuid, text, int, int, int); drop function samhan_wb_claim(uuid, text, int)")
            await WC.evaluate("() => { const G = window.__game; G.wbNoFn = false; G.wbV = null; return 1; }")
            r13 = await wb_play(WC, 0.85)
            r13b = await WC.evaluate("() => { const G = window.__game; return {src: G.wbV.src, sum: G.wbV.sum, target: G.wbV.target, noFn: G.wbNoFn, modal: !document.querySelector('#modal').hidden, solo: G.wbSoloLoad().chars}; }")
            check(r13.get('ok') and r13['src'] == 'solo' and r13b['noFn'] and not r13b['modal'] and r13b['sum'] == 85 and r13b['target'] == 1000 and len(r13b['solo']) == 1,
                  f'W13 서버 함수가 없으면 오류 창 없이 「내 계정 대요괴」 혼자 모드로 돈다(목표 1000 × 1명) {r13} {r13b}')
            await WC.evaluate("() => { const G = window.__game; G.hideModal(); G.closePage(); G.buildTab('raid'); document.querySelector('[data-rv=\"wb\"]').click(); }"); await WC.wait_for_timeout(500)
            await WC.screenshot(path=str(OUT / '36_대요괴_혼자모드.png'))

            # W14: setup.sql을 다시(두 번) 실행해도 된다 — 기록은 그대로, 사라졌던 함수가 돌아온다
            before14 = db("select count(*), coalesce(sum(score), 0) from samhan_wb")[0]
            for _ in range(2):
                with pg.conn() as c, c.cursor() as cur:
                    cur.execute(setup)
            after14 = db("select count(*), coalesce(sum(score), 0) from samhan_wb")[0]
            back = db(WBS, tokA, cidA)[0][0]
            check(before14 == after14 and back['target'] == 7000 and db("select count(*) from pg_proc where proname like 'samhan_wb%%'")[0][0] == 5,
                  f'W14 setup.sql을 두 번 더 실행해도 기록은 그대로이고 함수가 돌아온다 {before14} {after14}')
            for ctx_ in (ctxWA, ctxWB, ctxWC):
                await ctx_.close()
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
