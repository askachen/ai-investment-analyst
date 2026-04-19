import psycopg

conn = psycopg.connect('postgresql://postgres:postgres@localhost:5432/investment')
with conn, conn.cursor() as cur:
    cur.execute(
        """
        SELECT s.ticker, ds.code, pdr.trading_date, pdr.close_price
        FROM price_daily_raw pdr
        JOIN symbols s ON s.id = pdr.symbol_id
        JOIN data_sources ds ON ds.id = pdr.data_source_id
        WHERE s.ticker IN ('2330', '2454', '2330.TW', '2454.TW')
        ORDER BY s.ticker, pdr.trading_date DESC, ds.code
        LIMIT 20
        """
    )
    raw_rows = cur.fetchall()

    cur.execute(
        """
        SELECT s.ticker, ds.code, pdc.trading_date, pdc.close_price
        FROM price_daily_canonical pdc
        JOIN symbols s ON s.id = pdc.symbol_id
        JOIN data_sources ds ON ds.id = pdc.data_source_id
        WHERE s.ticker IN ('2330', '2454', '2330.TW', '2454.TW')
        ORDER BY s.ticker, pdc.trading_date DESC
        LIMIT 20
        """
    )
    canonical_rows = cur.fetchall()

print('RAW')
for row in raw_rows:
    print(row)

print('CANONICAL')
for row in canonical_rows:
    print(row)
