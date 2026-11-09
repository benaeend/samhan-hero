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
    c.channel = () => {
      const hs = [];
      const ch = {
        on(type, filter, fn){ hs.push([type, filter, fn]); return ch; },
        subscribe(cb){ setTimeout(() => cb('SUBSCRIBED'), 30); return ch; },
        track(){ return Promise.resolve('ok'); },
        presenceState(){ return {a: [], b: []}; },
        send(m){ window.__relaySend(JSON.stringify(m)); return Promise.resolve('ok'); },
      };
      window.__relayRecv = s => { const m = JSON.parse(s); for (const [type, f, fn] of hs) if (type === 'broadcast' && f.event === m.event) fn({type: 'broadcast', event: m.event, payload: m.payload}); };
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
            await A.click('#tab-raid'); await A.wait_for_timeout(300)
            await A.click('[data-tb="join"]', timeout=5000); await A.wait_for_timeout(600)
            why = await B.evaluate("() => window.__game.tbCan('normal')")
            check(tb and why == '', f'타임 보스: 다른 기기의 참가가 보이면 2명이 되어 도전할 수 있다 ({why!r})')

            # 이름은 서버 전체에서 하나만
            ctxC, C = await device(api)
            await C.click('#lg-tab-signup')
            await C.fill('#lg-id', 'online2'); await C.fill('#lg-pw', 'pass5678'); await C.fill('#lg-pw2', 'pass5678')
            await C.click('#modal-btn-0')
            await C.wait_for_selector('#mTitle:has-text("캐릭터 고르기")')
            await C.click('#modal-btn-0'); await C.wait_for_selector('#cc-name')
            await C.fill('#cc-name', '온라인용사'); await C.click('#modal-btn-1'); await C.wait_for_timeout(1200)
            check('이미 쓰는 이름' in await C.inner_text('#cc-err'), '다른 사람이 쓰는 캐릭터 이름은 막는다')

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
