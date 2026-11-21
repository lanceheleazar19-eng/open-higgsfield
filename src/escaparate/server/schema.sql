-- Escaparate database schema. Idempotent: safe to run on every deploy with
-- `pnpm escaparate:migrate`.

CREATE TABLE IF NOT EXISTS esc_users (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email               text NOT NULL UNIQUE,
  business_name       text NOT NULL DEFAULT '',
  credits             integer NOT NULL DEFAULT 0 CHECK (credits >= 0),
  plan                text NOT NULL DEFAULT 'gratis',
  stripe_customer_id  text UNIQUE,
  stripe_subscription_id text,
  subscription_status text,
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS esc_login_codes (
  id          bigserial PRIMARY KEY,
  email       text NOT NULL,
  code_hash   text NOT NULL,
  attempts    integer NOT NULL DEFAULT 0,
  used        boolean NOT NULL DEFAULT false,
  expires_at  timestamptz NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS esc_login_codes_email ON esc_login_codes (email, created_at DESC);

CREATE TABLE IF NOT EXISTS esc_sessions (
  token_hash  text PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES esc_users(id) ON DELETE CASCADE,
  expires_at  timestamptz NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS esc_sessions_user ON esc_sessions (user_id);

-- Every change to a balance, so a customer's credits can always be explained.
-- `ref` makes grants idempotent (one row per Stripe invoice, per refund…).
CREATE TABLE IF NOT EXISTS esc_credit_ledger (
  id          bigserial PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES esc_users(id) ON DELETE CASCADE,
  delta       integer NOT NULL,
  reason      text NOT NULL,
  ref         text UNIQUE,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS esc_credit_ledger_user ON esc_credit_ledger (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS esc_generations (
  request_id  text PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES esc_users(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('image', 'video')),
  credits     integer NOT NULL,
  status      text NOT NULL DEFAULT 'queued',
  result_url  text,
  refunded    boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS esc_generations_user ON esc_generations (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS esc_stripe_events (
  id          text PRIMARY KEY,
  type        text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- v2: gallery, saved shop details and the AI copy log.
ALTER TABLE esc_users ADD COLUMN IF NOT EXISTS city text NOT NULL DEFAULT '';
ALTER TABLE esc_generations ADD COLUMN IF NOT EXISTS product_name text NOT NULL DEFAULT '';
ALTER TABLE esc_generations ADD COLUMN IF NOT EXISTS format text NOT NULL DEFAULT 'post';
ALTER TABLE esc_generations ADD COLUMN IF NOT EXISTS source_url text;
ALTER TABLE esc_generations ADD COLUMN IF NOT EXISTS favorite boolean NOT NULL DEFAULT false;
ALTER TABLE esc_generations ADD COLUMN IF NOT EXISTS hidden boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS esc_copy_log (
  id          bigserial PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES esc_users(id) ON DELETE CASCADE,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS esc_copy_log_user ON esc_copy_log (user_id, created_at DESC);
