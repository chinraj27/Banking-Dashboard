-- PostgreSQL schema. Runs automatically on first start of the postgres container.
-- The API also calls SQLAlchemy create_all(), which skips tables that already exist.

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    full_name       VARCHAR(120) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role            VARCHAR(20)  NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS banking_products (
    id        SERIAL PRIMARY KEY,
    user_id   INTEGER      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    category  VARCHAR(20)  NOT NULL CHECK (category IN ('savings', 'credit_card', 'loan', 'investment')),
    name      VARCHAR(120) NOT NULL,
    status    VARCHAR(20)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'closed')),
    opened_at DATE         NOT NULL DEFAULT CURRENT_DATE
);
CREATE INDEX IF NOT EXISTS ix_banking_products_user_id  ON banking_products (user_id);
CREATE INDEX IF NOT EXISTS ix_banking_products_category ON banking_products (category);
CREATE INDEX IF NOT EXISTS ix_banking_products_status   ON banking_products (status);
CREATE INDEX IF NOT EXISTS ix_products_user_category    ON banking_products (user_id, category);

CREATE TABLE IF NOT EXISTS savings_accounts (
    id             SERIAL PRIMARY KEY,
    product_id     INTEGER NOT NULL UNIQUE REFERENCES banking_products (id) ON DELETE CASCADE,
    account_number VARCHAR(20) NOT NULL,
    balance        NUMERIC(14, 2) NOT NULL DEFAULT 0,
    interest_rate  NUMERIC(5, 2)  NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS credit_cards (
    id                 SERIAL PRIMARY KEY,
    product_id         INTEGER NOT NULL UNIQUE REFERENCES banking_products (id) ON DELETE CASCADE,
    card_number        VARCHAR(19) NOT NULL,
    credit_limit       NUMERIC(14, 2) NOT NULL DEFAULT 0,
    outstanding_amount NUMERIC(14, 2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS loans (
    id            SERIAL PRIMARY KEY,
    product_id    INTEGER NOT NULL UNIQUE REFERENCES banking_products (id) ON DELETE CASCADE,
    loan_amount   NUMERIC(14, 2) NOT NULL,
    interest_rate NUMERIC(5, 2)  NOT NULL,
    emi_amount    NUMERIC(14, 2) NOT NULL,
    next_due_date DATE,
    tenure_months INTEGER NOT NULL DEFAULT 12
);

CREATE TABLE IF NOT EXISTS investments (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER NOT NULL UNIQUE REFERENCES banking_products (id) ON DELETE CASCADE,
    invested_amount NUMERIC(14, 2) NOT NULL,
    current_value   NUMERIC(14, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES banking_products (id) ON DELETE CASCADE,
    txn_type    VARCHAR(10) NOT NULL CHECK (txn_type IN ('credit', 'debit')),
    amount      NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    description VARCHAR(200) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_transactions_product_id ON transactions (product_id);
CREATE INDEX IF NOT EXISTS ix_txn_user_created        ON transactions (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS product_applications (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    category         VARCHAR(20)  NOT NULL,
    product_name     VARCHAR(120) NOT NULL,
    requested_amount NUMERIC(14, 2),
    notes            TEXT,
    status           VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_product_applications_user_id ON product_applications (user_id);
CREATE INDEX IF NOT EXISTS ix_product_applications_status  ON product_applications (status);
