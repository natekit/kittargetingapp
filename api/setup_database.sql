-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Create advertisers table
CREATE TABLE advertisers (
    advertiser_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100)
);

CREATE INDEX ix_advertisers_advertiser_id ON advertisers(advertiser_id);
CREATE INDEX ix_advertisers_name ON advertisers(name);

-- Create campaigns table
CREATE TABLE campaigns (
    campaign_id SERIAL PRIMARY KEY,
    advertiser_id INTEGER NOT NULL REFERENCES advertisers(advertiser_id),
    name VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    notes TEXT
);

CREATE INDEX ix_campaigns_campaign_id ON campaigns(campaign_id);

-- Create insertions table
CREATE TABLE insertions (
    insertion_id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    month_start DATE NOT NULL,
    month_end DATE NOT NULL,
    cpc NUMERIC(10,4) NOT NULL
);

CREATE INDEX ix_insertions_insertion_id ON insertions(insertion_id);

-- Create creators table
CREATE TABLE creators (
    creator_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    acct_id VARCHAR(100) NOT NULL UNIQUE,
    owner_email CITEXT NOT NULL UNIQUE,
    topic TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_creators_creator_id ON creators(creator_id);
CREATE INDEX ix_creators_acct_id ON creators(acct_id);
CREATE INDEX ix_creators_owner_email ON creators(owner_email);

-- Create placements table
CREATE TABLE placements (
    placement_id SERIAL PRIMARY KEY,
    insertion_id INTEGER NOT NULL REFERENCES insertions(insertion_id),
    creator_id INTEGER NOT NULL REFERENCES creators(creator_id),
    notes TEXT
);

CREATE INDEX ix_placements_placement_id ON placements(placement_id);

-- Create perf_uploads table
CREATE TABLE perf_uploads (
    perf_upload_id SERIAL PRIMARY KEY,
    insertion_id INTEGER NOT NULL REFERENCES insertions(insertion_id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    filename TEXT NOT NULL
);

CREATE INDEX ix_perf_uploads_perf_upload_id ON perf_uploads(perf_upload_id);

-- Create click_uniques table
CREATE TABLE click_uniques (
    click_id SERIAL PRIMARY KEY,
    perf_upload_id INTEGER NOT NULL REFERENCES perf_uploads(perf_upload_id),
    creator_id INTEGER NOT NULL REFERENCES creators(creator_id),
    execution_date DATE NOT NULL,
    unique_clicks INTEGER NOT NULL,
    raw_clicks INTEGER,
    flagged BOOLEAN,
    status VARCHAR(50)
);

CREATE INDEX ix_click_uniques_click_id ON click_uniques(click_id);

-- Create conv_uploads table
CREATE TABLE conv_uploads (
    conv_upload_id SERIAL PRIMARY KEY,
    advertiser_id INTEGER NOT NULL REFERENCES advertisers(advertiser_id),
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    insertion_id INTEGER NOT NULL REFERENCES insertions(insertion_id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    filename TEXT NOT NULL,
    range_start DATE NOT NULL,
    range_end DATE NOT NULL,
    tz VARCHAR(50) NOT NULL DEFAULT 'America/New_York'
);

CREATE INDEX ix_conv_uploads_conv_upload_id ON conv_uploads(conv_upload_id);

-- Create conversions table
CREATE TABLE conversions (
    conversion_id SERIAL PRIMARY KEY,
    conv_upload_id INTEGER NOT NULL REFERENCES conv_uploads(conv_upload_id),
    insertion_id INTEGER NOT NULL REFERENCES insertions(insertion_id),
    creator_id INTEGER NOT NULL REFERENCES creators(creator_id),
    period DATERANGE NOT NULL,
    conversions INTEGER NOT NULL
);

CREATE INDEX ix_conversions_conversion_id ON conversions(conversion_id);

-- Create GiST exclusion constraint for conversions table
-- This prevents overlapping periods per (creator_id, insertion_id)
CREATE TABLE conversions_exclusion_constraint AS
SELECT 1 WHERE FALSE; -- This will be replaced by the actual constraint

-- Drop the dummy table and create the actual constraint
DROP TABLE conversions_exclusion_constraint;

-- Add the exclusion constraint
ALTER TABLE conversions 
ADD CONSTRAINT conversions_creator_id_insertion_id_period_excl 
EXCLUDE USING gist (
    creator_id WITH =,
    insertion_id WITH =,
    period WITH &&
);



