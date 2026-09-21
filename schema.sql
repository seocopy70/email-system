-- Supabase SQL Editor에서 한 번 실행하세요.

-- 1) 발신 계정 (허용 목록 = 로그인 허용 계정)
create table if not exists senders (
  email        text primary key,
  display_name text,
  is_active    boolean not null default true,
  is_admin     boolean not null default false,
  created_at   timestamptz not null default now()
);

-- 2) 발송 주제 (캠페인)
create table if not exists topics (
  id         bigint generated always as identity primary key,
  name       text not null unique,
  created_by text,
  created_at timestamptz not null default now()
);

-- 3) 수신자 (이메일 기준 유일)
create table if not exists recipients (
  id         bigint generated always as identity primary key,
  email      text not null unique,
  company    text,
  ceo        text,
  industry   text,
  rating     text,
  updated_at timestamptz not null default now()
);

-- 4) 발송 기록 (주제 x 수신자 = 1건 → 중복발송 차단의 핵심)
create table if not exists send_log (
  id           bigint generated always as identity primary key,
  topic_id     bigint not null references topics(id) on delete cascade,
  recipient_id bigint not null references recipients(id) on delete cascade,
  sender_email text   not null references senders(email),
  sender_name  text,
  status       text   not null default 'pending'
               check (status in ('pending', 'sent', 'failed')),
  subject      text,
  body_html    text,
  error        text,
  claimed_at   timestamptz not null default now(),
  sent_at      timestamptz,
  unique (topic_id, recipient_id)
);

create index if not exists send_log_topic_idx  on send_log (topic_id, status);
create index if not exists send_log_sender_idx on send_log (sender_email, sent_at);

-- 5) 발송 권한 선점: 성공하면 log id, 이미 다른 사람이 발송/진행 중이면 NULL
--    - 실패(failed) 건은 재시도 가능
--    - 30분 넘게 pending인 건(앱이 중간에 종료된 경우)은 다시 선점 가능
create or replace function claim_send(
  p_topic bigint, p_recipient bigint, p_sender text, p_sender_name text
) returns bigint
language plpgsql
as $$
declare
  v_id bigint;
begin
  insert into send_log (topic_id, recipient_id, sender_email, sender_name, status)
  values (p_topic, p_recipient, p_sender, p_sender_name, 'pending')
  on conflict (topic_id, recipient_id) do update
    set sender_email = excluded.sender_email,
        sender_name  = excluded.sender_name,
        status       = 'pending',
        error        = null,
        claimed_at   = now()
    where send_log.status = 'failed'
       or (send_log.status = 'pending'
           and send_log.claimed_at < now() - interval '30 minutes')
  returning id into v_id;
  return v_id;
end;
$$;

-- 6) 앱은 service_role 키로만 접근합니다. RLS를 켜서 anon 키로는 접근 불가하게 막습니다.
alter table senders    enable row level security;
alter table topics     enable row level security;
alter table recipients enable row level security;
alter table send_log   enable row level security;

-- 7) 첫 관리자 등록 (본인 Gmail로 바꿔서 실행)
-- insert into senders (email, display_name, is_admin)
-- values ('example@gmail.com', '서영교 컨설턴트', true);
