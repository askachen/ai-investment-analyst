INSERT INTO markets (code, name, region, currency_code, timezone)
VALUES
    ('TW', 'Taiwan Stock Market', 'Taiwan', 'TWD', 'Asia/Taipei'),
    ('US', 'United States Market', 'United States', 'USD', 'America/New_York')
ON CONFLICT (code) DO UPDATE
SET
    name = EXCLUDED.name,
    region = EXCLUDED.region,
    currency_code = EXCLUDED.currency_code,
    timezone = EXCLUDED.timezone,
    updated_at = NOW();
