-- Upgrade an existing surf database; source tables must already exist.
-- Re-runnable on installations already using station validity periods.
-- No provider identifiers or observations are rewritten by this migration.
BEGIN;
SET LOCAL lock_timeout = '10s';
LOCK TABLE raw.tide_stations IN ACCESS EXCLUSIVE MODE;

ALTER TABLE raw.tide_stations
    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS valid_from timestamptz,
    ADD COLUMN IF NOT EXISTS valid_to timestamptz;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'raw.tide_stations'::regclass
          AND conname = 'tide_station_valid_period'
    ) THEN
        ALTER TABLE raw.tide_stations ADD CONSTRAINT tide_station_valid_period
            CHECK (valid_from IS NULL OR valid_to IS NULL OR valid_from < valid_to);
    END IF;
END $$;

ALTER TABLE raw.tide_stations DROP CONSTRAINT IF EXISTS uq_tide_station_spot;
CREATE UNIQUE INDEX IF NOT EXISTS uq_tide_station_active_spot
    ON raw.tide_stations (spot_id) WHERE is_active;
COMMIT;
