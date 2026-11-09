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

-- 저장(더 새 기록만 덮어쓴다). 이름이 다른 계정과 겹치면 name_taken
create or replace function public.samhan_save(p_token uuid, p_cid text, p_name text, p_summary jsonb, p_save text, p_t bigint) returns bigint
language plpgsql security definer set search_path = public, extensions as $$
declare a text := samhan_acc(p_token); n int;
begin
  if p_save is not null and char_length(p_save) > 400000 then raise exception 'too_big'; end if;
  select count(*) into n from samhan_chars where acc = a and cid <> p_cid;
  if n >= 4 then raise exception 'too_many'; end if;
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

-- 캐릭터 이름이 비었는지(만들기 전에 확인)
create or replace function public.samhan_name_free(p_name text) returns boolean
language sql security definer set search_path = public, extensions as $$
  select not exists (select 1 from samhan_chars where name = p_name);
$$;

revoke all on function public.samhan_acc(uuid) from public, anon, authenticated;
revoke all on function public.samhan_signup(text, text), public.samhan_login(text, text), public.samhan_logout(uuid),
  public.samhan_list(uuid), public.samhan_load(uuid, text), public.samhan_save(uuid, text, text, jsonb, text, bigint),
  public.samhan_delete(uuid, text), public.samhan_name_free(text) from public;
grant execute on function public.samhan_signup(text, text), public.samhan_login(text, text), public.samhan_logout(uuid),
  public.samhan_list(uuid), public.samhan_load(uuid, text), public.samhan_save(uuid, text, text, jsonb, text, bigint),
  public.samhan_delete(uuid, text), public.samhan_name_free(text) to anon, authenticated;
