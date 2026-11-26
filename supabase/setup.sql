-- 삼한 용사 키우기 · 온라인 서버 준비 (Supabase SQL Editor에 통째로 붙여 넣고 Run 한 번)
-- 여러 번 실행해도 괜찮다(이미 있으면 그대로 두고, 함수는 새것으로 바꾼다).
--
-- 구조: 표 3개(계정·로그인 표·캐릭터)는 바깥에서 직접 읽고 쓰지 못하게 잠그고(RLS + 권한 회수),
-- 게임은 아래 samhan_* 함수만 부른다. 비밀번호는 bcrypt 해시로만 저장하고, 로그인하면 60일짜리 무작위 표(토큰)를 준다.

create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;

create table if not exists public.samhan_accounts (
  id text primary key check (id ~ '^[a-z0-9_]{4,12}$'),
  pw_hash text not null,
  created_at timestamptz not null default now()
);
create table if not exists public.samhan_sessions (
  token uuid primary key default gen_random_uuid(),
  acc text not null references public.samhan_accounts(id) on delete cascade,
  expires_at timestamptz not null default now() + interval '60 days'
);
create index if not exists samhan_sessions_acc on public.samhan_sessions (acc);
create table if not exists public.samhan_chars (
  acc text not null references public.samhan_accounts(id) on delete cascade,
  cid text not null check (cid ~ '^[a-z0-9]{4,24}$'),
  name text not null check (char_length(name) between 2 and 8),
  summary jsonb not null default '{}'::jsonb,
  save text,
  save_t bigint not null default 0,
  updated_at timestamptz not null default now(),
  primary key (acc, cid)
);
create unique index if not exists samhan_chars_name on public.samhan_chars (name);

alter table public.samhan_accounts enable row level security;
alter table public.samhan_sessions enable row level security;
alter table public.samhan_chars enable row level security;
revoke all on table public.samhan_accounts, public.samhan_sessions, public.samhan_chars from public, anon, authenticated;

-- 토큰 → 아이디 (내부용)
create or replace function public.samhan_acc(p_token uuid) returns text
language plpgsql security definer set search_path = public, extensions as $$
declare a text;
begin
  select acc into a from samhan_sessions where token = p_token and expires_at > now();
  if a is null then raise exception 'bad_token'; end if;
  return a;
end $$;

create or replace function public.samhan_signup(p_id text, p_pw text) returns uuid
language plpgsql security definer set search_path = public, extensions as $$
declare t uuid;
begin
  if p_id is null or p_id !~ '^[a-z0-9_]{4,12}$' then raise exception 'bad_id'; end if;
  if p_pw is null or char_length(p_pw) < 4 or char_length(p_pw) > 64 then raise exception 'bad_pw'; end if;
  begin
    insert into samhan_accounts (id, pw_hash) values (p_id, crypt(p_pw, gen_salt('bf', 8)));
  exception when unique_violation then raise exception 'id_taken';
  end;
  insert into samhan_sessions (acc) values (p_id) returning token into t;
  return t;
end $$;

create or replace function public.samhan_login(p_id text, p_pw text) returns uuid
language plpgsql security definer set search_path = public, extensions as $$
declare h text; t uuid;
begin
  select pw_hash into h from samhan_accounts where id = p_id;
  if h is null or crypt(coalesce(p_pw, ''), h) <> h then raise exception 'bad_login'; end if;
  delete from samhan_sessions where acc = p_id and expires_at < now();
  insert into samhan_sessions (acc) values (p_id) returning token into t;
  return t;
end $$;

create or replace function public.samhan_logout(p_token uuid) returns void
language sql security definer set search_path = public, extensions as $$
  delete from samhan_sessions where token = p_token;
$$;

-- 내 캐릭터 목록(요약만)
create or replace function public.samhan_list(p_token uuid) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token);
begin
  return coalesce((select jsonb_agg(jsonb_build_object('cid', cid, 'name', name, 'summary', summary, 't', save_t) order by updated_at)
    from samhan_chars where acc = a), '[]'::jsonb);
end $$;

-- 캐릭터 하나의 저장 불러오기
create or replace function public.samhan_load(p_token uuid, p_cid text) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token); r record;
begin
  select save, save_t into r from samhan_chars where acc = a and cid = p_cid;
  if not found then return null; end if;
  return jsonb_build_object('save', r.save, 't', r.save_t);
end $$;

-- 하루 한 번 남기는 기록(2026-11-12): 그날 처음 저장이 들어올 때, 그 전까지의 기록을 따로 둔다(14일 치).
-- 잘못 덮어쓴 기록을 되돌릴 때 주인이 SQL Editor에서 꺼내 쓴다. 게임에서는 읽지 못한다(잠금).
create table if not exists public.samhan_chars_hist (
  acc text not null references public.samhan_accounts(id) on delete cascade,
  cid text not null,
  day date not null,
  name text,
  save text,
  save_t bigint not null default 0,
  kept_at timestamptz not null default now(),
  primary key (acc, cid, day)
);
alter table public.samhan_chars_hist enable row level security;
revoke all on public.samhan_chars_hist from public, anon, authenticated;

-- 저장(더 새 기록만 덮어쓴다). 이름이 다른 계정과 겹치면 name_taken
-- 저장 판 번호("saveBuild")가 서버 것보다 낮으면 old_client: 옛 화면이 새 기록을 잘라 덮어쓰지 못하게 한다
create or replace function public.samhan_save(p_token uuid, p_cid text, p_name text, p_summary jsonb, p_save text, p_t bigint) returns bigint
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token); n int; o record; ob int := 0; nb int := 0; d date := (now() at time zone 'Asia/Seoul')::date;
begin
  if p_save is not null and char_length(p_save) > 400000 then raise exception 'too_big'; end if;
  select count(*) into n from samhan_chars where acc = a and cid <> p_cid;
  if n >= 10 then raise exception 'too_many'; end if;   -- 한 계정 캐릭터 10명까지(2026-11 물의 신화: 4 → 6 → 10)
  select name, save, save_t into o from samhan_chars where acc = a and cid = p_cid;
  if found and o.save is not null and p_save is not null then
    ob := coalesce(substring(o.save from '"saveBuild":([0-9]{1,9})')::int, 0);
    nb := coalesce(substring(p_save from '"saveBuild":([0-9]{1,9})')::int, 0);
    if nb < ob then raise exception 'old_client'; end if;
    insert into samhan_chars_hist (acc, cid, day, name, save, save_t) values (a, p_cid, d, o.name, o.save, o.save_t)
      on conflict (acc, cid, day) do nothing;
    delete from samhan_chars_hist where acc = a and cid = p_cid and day < d - 14;
  end if;
  begin
    insert into samhan_chars as c (acc, cid, name, summary, save, save_t, updated_at)
      values (a, p_cid, p_name, coalesce(p_summary, '{}'::jsonb), p_save, coalesce(p_t, 0), now())
    on conflict (acc, cid) do update set
      name = excluded.name,
      summary = case when excluded.save_t >= c.save_t then excluded.summary else c.summary end,
      save = case when excluded.save_t >= c.save_t and excluded.save is not null then excluded.save else c.save end,
      save_t = greatest(c.save_t, excluded.save_t), updated_at = now();
  exception when unique_violation then raise exception 'name_taken';
  end;
  return coalesce(p_t, 0);
end $$;

create or replace function public.samhan_delete(p_token uuid, p_cid text) returns void
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token);
begin
  delete from samhan_chars where acc = a and cid = p_cid;
end $$;

-- 한 계정은 한 화면에서만 접속(2026-11-13): 들어올 때 p_take=true로 이 화면의 표(p_dev)를 적고, 접속 중인 화면은 p_take=false로 지금 적힌 표를 물어 자기 것이 아니면 멈춘다
alter table public.samhan_accounts add column if not exists active_dev text;
alter table public.samhan_accounts add column if not exists active_at timestamptz;
create or replace function public.samhan_claim(p_token uuid, p_dev text, p_take boolean) returns text
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token); cur text;
begin
  if p_take then
    update samhan_accounts set active_dev = left(p_dev, 40), active_at = now() where id = a;
    return left(p_dev, 40);
  end if;
  select active_dev into cur from samhan_accounts where id = a;
  return cur;
end $$;

-- 캐릭터 이름이 비었는지(만들기 전에 확인)
create or replace function public.samhan_name_free(p_name text) returns boolean
language sql security definer set search_path = public, extensions as $$
  select not exists (select 1 from samhan_chars where name = p_name);
$$;

revoke all on function public.samhan_acc(uuid) from public, anon, authenticated;
revoke all on function public.samhan_signup(text, text), public.samhan_login(text, text), public.samhan_logout(uuid),
  public.samhan_list(uuid), public.samhan_load(uuid, text), public.samhan_save(uuid, text, text, jsonb, text, bigint),
  public.samhan_delete(uuid, text), public.samhan_name_free(text), public.samhan_claim(uuid, text, boolean) from public;
grant execute on function public.samhan_signup(text, text), public.samhan_login(text, text), public.samhan_logout(uuid),
  public.samhan_list(uuid), public.samhan_load(uuid, text), public.samhan_save(uuid, text, text, jsonb, text, bigint),
  public.samhan_delete(uuid, text), public.samhan_name_free(text), public.samhan_claim(uuid, text, boolean) to anon, authenticated;

-- ── 장터(2026-11): 기본 장비를 뺀 물건(장신구·신화 보물·치장·재료·조각·소모품)을 보석 값에 올리고 다른 용사가 산다. 거래 돈은 보석뿐 ──
-- 물건(item)은 게임이 다시 확인해서 받는다. 사흘 안 팔리면 목록에서 빠지고 판 사람이 돌려받는다. 판 값은 수수료 5%를 떼고 받는다.
create table if not exists public.samhan_market (
  id bigserial primary key,
  seller text not null references public.samhan_accounts(id) on delete cascade,
  seller_name text not null check (char_length(seller_name) between 1 and 8),
  kind text not null check (kind in ('acc', 'myth', 'gear', 'mat', 'dust', 'piece', 'skin', 'stack')),
  item jsonb not null,
  price bigint not null check (price between 1 and 10000000),
  created_at timestamptz not null default now(),
  buyer text,
  buyer_name text,
  sold_at timestamptz,
  claimed boolean not null default false
);
-- 2026-11 (31): 치장(skin)·조각/소모품(stack)도 거래. 기본 장비(gear)는 새로 올릴 수 없다(이미 올린 것은 내리기·돌려받기만)
alter table public.samhan_market drop constraint if exists samhan_market_kind_check;
alter table public.samhan_market add constraint samhan_market_kind_check check (kind in ('acc', 'myth', 'gear', 'mat', 'dust', 'piece', 'skin', 'stack'));
create index if not exists samhan_market_open on public.samhan_market (created_at desc) where buyer is null;
create index if not exists samhan_market_seller on public.samhan_market (seller);
alter table public.samhan_market enable row level security;
revoke all on table public.samhan_market from public, anon, authenticated;
revoke all on sequence public.samhan_market_id_seq from public, anon, authenticated;

-- 올리기(계정마다 팔고 있거나 판 값을 아직 안 받은 물건 10개까지)
create or replace function public.samhan_market_post(p_token uuid, p_name text, p_kind text, p_item jsonb, p_price bigint) returns bigint
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token); n int; nid bigint;
begin
  if p_kind is null or p_kind not in ('acc', 'myth', 'mat', 'dust', 'piece', 'skin', 'stack') or p_item is null or jsonb_typeof(p_item) <> 'object'
     or char_length(p_item::text) > 300 or (p_item->>'t') is distinct from p_kind then raise exception 'bad_item'; end if;
  if p_price is null or p_price < 1 or p_price > 10000000 then raise exception 'bad_price'; end if;
  select count(*) into n from samhan_market where seller = a and (buyer is null or not claimed);
  if n >= 10 then raise exception 'mk_full'; end if;
  insert into samhan_market (seller, seller_name, kind, item, price)
    values (a, left(coalesce(nullif(p_name, ''), a), 8), p_kind, p_item, p_price) returning id into nid;
  return nid;
end $$;

-- 팔고 있는 물건 목록(최근 60개, 기본 장비는 빼고, 종류 거르기: '' 전체, 'mat'은 재료·쇳가루·고삐 조각·조각/소모품까지)
create or replace function public.samhan_market_list(p_token uuid, p_kind text) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token);
begin
  return coalesce((select jsonb_agg(jsonb_build_object('id', t.id, 'seller_name', t.seller_name, 'kind', t.kind, 'item', t.item, 'price', t.price, 'mine', t.seller = a) order by t.created_at desc)
    from (select * from samhan_market where buyer is null and created_at > now() - interval '3 days' and kind <> 'gear'
          and (coalesce(p_kind, '') = '' or kind = p_kind or (p_kind = 'mat' and kind in ('mat', 'dust', 'piece', 'stack')))
          order by created_at desc limit 60) t), '[]'::jsonb);
end $$;

-- 사기(먼저 산 한 사람만, 내 물건은 못 삼)
create or replace function public.samhan_market_buy(p_token uuid, p_name text, p_id bigint) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token); r record;
begin
  update samhan_market set buyer = a, buyer_name = left(coalesce(nullif(p_name, ''), a), 8), sold_at = now()
    where id = p_id and buyer is null and seller <> a and created_at > now() - interval '3 days'
    returning kind, item, price into r;
  if not found then
    if exists (select 1 from samhan_market where id = p_id and seller = a) then raise exception 'own'; end if;
    raise exception 'gone';
  end if;
  return jsonb_build_object('kind', r.kind, 'item', r.item, 'price', r.price);
end $$;

-- 내리기·돌려받기(안 팔린 내 물건)
create or replace function public.samhan_market_cancel(p_token uuid, p_id bigint) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token); r record;
begin
  delete from samhan_market where id = p_id and seller = a and buyer is null returning kind, item into r;
  if not found then raise exception 'gone'; end if;
  return jsonb_build_object('kind', r.kind, 'item', r.item);
end $$;

-- 내 물건(파는 중·기한 지남·팔렸는데 값을 아직 안 받은 것)
create or replace function public.samhan_market_mine(p_token uuid) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token);
begin
  return coalesce((select jsonb_agg(jsonb_build_object('id', id, 'kind', kind, 'item', item, 'price', price, 'buyer_name', buyer_name,
      'sold', buyer is not null, 'expired', buyer is null and created_at <= now() - interval '3 days') order by created_at desc)
    from samhan_market where seller = a and not (buyer is not null and claimed)), '[]'::jsonb);
end $$;

-- 판 값 받기(수수료 5%를 뗀 보석 합계)
create or replace function public.samhan_market_claim(p_token uuid) returns bigint
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token); g bigint;
begin
  with u as (update samhan_market set claimed = true where seller = a and buyer is not null and not claimed returning price)
  select coalesce(sum(floor(price * 0.95)), 0)::bigint into g from u;
  delete from samhan_market where claimed and sold_at < now() - interval '30 days';
  return g;
end $$;

revoke all on function public.samhan_market_post(uuid, text, text, jsonb, bigint), public.samhan_market_list(uuid, text), public.samhan_market_buy(uuid, text, bigint),
  public.samhan_market_cancel(uuid, bigint), public.samhan_market_mine(uuid), public.samhan_market_claim(uuid) from public;
grant execute on function public.samhan_market_post(uuid, text, text, jsonb, bigint), public.samhan_market_list(uuid, text), public.samhan_market_buy(uuid, text, bigint),
  public.samhan_market_cancel(uuid, bigint), public.samhan_market_mine(uuid), public.samhan_market_claim(uuid) to anon, authenticated;

-- ── 타임 보스 동료(2026-11 (32)): 서버에 만들어진 모든 캐릭터 가운데 무작위 10명 ──
-- 같은 직업은 파티 전체에서 3명까지(부른 사람의 직업은 2명까지 더). 한 번이라도 싸워 본(요약에 ally가 있는) 캐릭터만, 부른 캐릭터 자신은 빼고.
-- 돌려주는 것은 이름과 요약(직업·레벨·모습·전투력)뿐, 계정 아이디는 주지 않는다
create or replace function public.samhan_tb_pick(p_token uuid, p_cid text, p_cls text) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token);
begin
  return coalesce((select jsonb_agg(jsonb_build_object('name', t.name, 'summary', t.summary, 'mine', t.mine))
    from (select x.name, x.summary, x.mine from (
            select c.name, c.summary, c.acc = a as mine,
                   row_number() over (partition by coalesce(c.summary->>'cls', '') order by random()) as k
              from samhan_chars c
             where not (c.acc = a and c.cid = coalesce(p_cid, '')) and jsonb_typeof(c.summary->'ally') = 'object') x
          where x.k <= case when coalesce(x.summary->>'cls', '') = coalesce(p_cls, '') then 2 else 3 end
          order by random() limit 10) t), '[]'::jsonb);
end $$;
revoke all on function public.samhan_tb_pick(uuid, text, text) from public;
grant execute on function public.samhan_tb_pick(uuid, text, text) to anon, authenticated;


-- ── 주간 대요괴 공동 토벌(2026-11-26): 한 주(한국 시간 월요일 0시~일요일 밤)마다 큰 요괴 하나, 서버의 모든 용사 점수를 합쳐 목표 막대를 채운다 ──
-- 표 2개(주간 점수·점수 기록)는 타임 보스·장터와 같이 잠그고(RLS + 권한 회수), 게임은 samhan_wb_hit · samhan_wb_state · samhan_wb_claim만 부른다.
-- 서버가 하는 일: 점수 범위·판 길이(secs) 앞뒤 맞추기, 캐릭터 하루 3번·계정 하루 6번(한국 날짜), 보내는 사이 (판 길이 − 3초) 이상(최소 8초), 그 계정의 캐릭터인지, 화면 판 번호(p_build ≥ 5), 단계 보상은 캐릭터마다 한 번(비트 25=1·50=2·75=4·100=8).
-- 목표 = 1000 × max(3, 지난주 참가 캐릭터 수). 이번 주 보스는 주 번호 % 4(2024-01-01 월요일 기준). 점수는 화면이 보내므로 마음먹고 속이는 것까지는 못 막지만, 보상은 겉모습 별호뿐이고 남에게 해를 주지 않는다.
-- 이상한 기록은 SQL Editor에서 지운다 → docs/주간_대요괴_운영.md
create table if not exists public.samhan_wb (
  wk text not null check (wk ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'),
  acc text not null references public.samhan_accounts(id) on delete cascade,
  cid text not null,
  name text not null default '',
  score int not null default 0 check (score >= 0),
  n int not null default 0,
  best int not null default 0,
  got int not null default 0,
  last_at timestamptz not null default now(),
  primary key (wk, acc, cid)
);
create index if not exists samhan_wb_rank on public.samhan_wb (wk, score desc, last_at);
create table if not exists public.samhan_wb_log (
  id bigserial primary key,
  wk text not null,
  acc text not null references public.samhan_accounts(id) on delete cascade,
  cid text not null,
  day date not null,
  score int not null,
  secs int not null,
  at timestamptz not null default now()
);
create index if not exists samhan_wb_log_c on public.samhan_wb_log (cid, day);
create index if not exists samhan_wb_log_a on public.samhan_wb_log (acc, day);
alter table public.samhan_wb enable row level security;
alter table public.samhan_wb_log enable row level security;
revoke all on table public.samhan_wb, public.samhan_wb_log from public, anon, authenticated;
revoke all on sequence public.samhan_wb_log_id_seq from public, anon, authenticated;

-- 이번 주(0)·지난주(-1)의 월요일 날짜(한국 시간) (내부용)
create or replace function public.samhan_wb_wk(p_off int default 0) returns text
language sql stable security definer set search_path = public, extensions as $$
  select to_char((date_trunc('week', now() at time zone 'Asia/Seoul') + p_off * interval '7 days')::date, 'YYYY-MM-DD')
$$;

-- 이번 주 상태(내부용): 합계·목표·상위 10·지난주 1~3등·이 캐릭터의 점수와 남은 횟수
create or replace function public.samhan_wb_view(p_acc text, p_cid text) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare cw text := samhan_wb_wk(0); pw text := samhan_wb_wk(-1); d date := (now() at time zone 'Asia/Seoul')::date;
  s bigint; pn int; m record; lc int; la int; wi int;
begin
  select coalesce(sum(score), 0) into s from samhan_wb where wk = cw;
  select count(*) into pn from samhan_wb where wk = pw and score > 0;
  select * into m from samhan_wb where wk = cw and acc = p_acc and cid = p_cid;
  select count(*) into lc from samhan_wb_log where cid = p_cid and acc = p_acc and day = d;
  select count(*) into la from samhan_wb_log where acc = p_acc and day = d;
  wi := (floor((cw::date - date '2024-01-01') / 7.0)::int % 4 + 4) % 4;
  return jsonb_build_object(
    'wk', cw, 'boss', wi, 'sum', s, 'target', 1000 * greatest(3, pn),
    'top', coalesce((select jsonb_agg(jsonb_build_object('name', t.name, 'cls', coalesce(t.cls, ''), 'score', t.score) order by t.score desc, t.last_at)
      from (select w.name, c.summary->>'cls' as cls, w.score, w.last_at from samhan_wb w left join samhan_chars c on c.acc = w.acc and c.cid = w.cid
             where w.wk = cw and w.score > 0 order by w.score desc, w.last_at limit 10) t), '[]'::jsonb),
    'prev_top', coalesce((select jsonb_agg(t.name order by t.score desc, t.last_at)
      from (select w.name, w.score, w.last_at from samhan_wb w where w.wk = pw and w.score > 0 order by w.score desc, w.last_at limit 3) t), '[]'::jsonb),
    'me', jsonb_build_object('score', coalesce(m.score, 0), 'n', coalesce(m.n, 0), 'best', coalesce(m.best, 0), 'got', coalesce(m.got, 0)),
    'left_c', greatest(0, 3 - lc), 'left', greatest(0, least(3 - lc, 6 - la)));
end $$;

create or replace function public.samhan_wb_state(p_token uuid, p_cid text) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token);
begin
  return samhan_wb_view(a, coalesce(p_cid, ''));
end $$;

create or replace function public.samhan_wb_hit(p_token uuid, p_cid text, p_score int, p_secs int, p_build int) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token); c record; cw text := samhan_wb_wk(0); d date := (now() at time zone 'Asia/Seoul')::date; lc int; la int; lastat timestamptz;
begin
  perform pg_advisory_xact_lock(hashtext('samhan_wb:' || a));
  if p_build is null or p_build < 5 then raise exception 'old_client'; end if;
  select name into c from samhan_chars where acc = a and cid = coalesce(p_cid, '') and updated_at > now() - interval '1 day';   -- 내 캐릭터이고 하루 안에 저장된 적이 있어야 함
  if not found then raise exception 'wb_char'; end if;
  if p_score is null or p_secs is null or p_score < 0 or p_score > 120 or p_secs < 8 or p_secs > 60 then raise exception 'wb_bad'; end if;
  -- 쓰러뜨린 판(100점~)은 남은 시간 보너스(최대 20)가 판 길이와 맞아야 한다: 100 + min(20, floor((60 - secs) / 2))
  if p_score >= 100 and p_score > 100 + least(20, floor((60 - p_secs) / 2.0)) then raise exception 'wb_bad'; end if;
  select max(at) into lastat from samhan_wb_log where acc = a and cid = p_cid;
  if lastat is not null and now() - lastat < make_interval(secs => greatest(8, p_secs - 3)) then raise exception 'wb_fast'; end if;   -- 진짜 한 판은 p_secs초가 걸리므로 앞 점수와 그만큼(−3초) 떨어져야 한다. 일찍 쓰러져 곧바로 다시 한 판은 통과
  select count(*) into lc from samhan_wb_log where acc = a and cid = p_cid and day = d;
  select count(*) into la from samhan_wb_log where acc = a and day = d;
  if lc >= 3 or la >= 6 then raise exception 'wb_many'; end if;
  insert into samhan_wb_log (wk, acc, cid, day, score, secs) values (cw, a, p_cid, d, p_score, p_secs);
  insert into samhan_wb as w (wk, acc, cid, name, score, n, best, last_at) values (cw, a, p_cid, c.name, p_score, 1, p_score, now())
    on conflict (wk, acc, cid) do update set name = excluded.name, score = w.score + excluded.score, n = w.n + 1, best = greatest(w.best, excluded.best), last_at = now();
  delete from samhan_wb where wk < samhan_wb_wk(-4);
  delete from samhan_wb_log where day < d - 35;
  return samhan_wb_view(a, p_cid);
end $$;

-- 단계 보상(25·50·75·100%): 캐릭터마다 한 번. 받을 수 있으면 true(그 단계 표시를 서버에 적음), 아니면 false
create or replace function public.samhan_wb_claim(p_token uuid, p_cid text, p_step int) returns boolean
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token); cw text := samhan_wb_wk(0); bit int; s bigint; pn int; n int;
begin
  perform pg_advisory_xact_lock(hashtext('samhan_wb:' || a));
  bit := case p_step when 25 then 1 when 50 then 2 when 75 then 4 when 100 then 8 else 0 end;
  if bit = 0 then return false; end if;
  select coalesce(sum(score), 0) into s from samhan_wb where samhan_wb.wk = cw;
  select count(*) into pn from samhan_wb where samhan_wb.wk = samhan_wb_wk(-1) and score > 0;
  if s * 100 < 1000 * greatest(3, pn) * p_step then return false; end if;
  update samhan_wb set got = got | bit where samhan_wb.wk = cw and acc = a and cid = coalesce(p_cid, '') and score > 0 and (got & bit) = 0;
  get diagnostics n = row_count;
  return n > 0;
end $$;

revoke all on function public.samhan_wb_wk(int), public.samhan_wb_view(text, text) from public, anon, authenticated;
revoke all on function public.samhan_wb_state(uuid, text), public.samhan_wb_hit(uuid, text, int, int, int), public.samhan_wb_claim(uuid, text, int) from public;
grant execute on function public.samhan_wb_state(uuid, text), public.samhan_wb_hit(uuid, text, int, int, int), public.samhan_wb_claim(uuid, text, int) to anon, authenticated;
