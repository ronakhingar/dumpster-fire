#!/usr/bin/env python3
"""Show all tables and row counts in the trading database."""

import psycopg2
import os

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://trading_agent:tr4d1ng_s3cur3_2026@localhost:25433/trading')

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get all tables with row counts
cur.execute("""
    SELECT
        schemaname,
        tablename,
        (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_name = tablename AND table_schema = schemaname) as column_count
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY tablename
""")

tables = cur.fetchall()

print("\n" + "="*80)
print("DATABASE STATUS: trading")
print("="*80)
print(f"\nTotal tables: {len(tables)}\n")

for schema, table, col_count in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{table}"')
    row_count = cur.fetchone()[0]

    print(f"  {table:<30} {row_count:>8} rows  ({col_count} columns)")

conn.close()
