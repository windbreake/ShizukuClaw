#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""PostgreSQL 建库建表：与 create_database.py 相同，从 CONFIG（data/database.json）读连接信息。"""

import os
import sys

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from psycopg2 import Error as PgError
except ImportError:
    print("Missing dependency: pip install psycopg2-binary")
    sys.exit(1)

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.config import CONFIG


def _normalize_host(host: str) -> str:
    """避免 localhost 解析为 ::1 而 pg_hba 只放行 127.0.0.1 导致认证异常。"""
    if (host or '').strip().lower() in ('localhost', '::1'):
        return '127.0.0.1'
    return host


def _pg_cfg():
    d = CONFIG.get('database', {})
    port = d.get('port')
    port = 5432 if port is None or port == '' else int(port)
    return {
        'host': _normalize_host(d.get('host', '127.0.0.1')),
        'port': port,
        'user': d.get('user', 'postgres'),
        'password': d.get('password', ''),
        'database': d.get('database', 'catgirl_db'),
        'maintenance_db': 'postgres',
    }


def ensure_database(cfg):
    maintenance = cfg.get('maintenance_db', 'postgres')
    dbname = cfg['database']
    conn = None
    try:
        conn = psycopg2.connect(
            host=cfg['host'],
            port=cfg['port'],
            user=cfg['user'],
            password=cfg['password'],
            dbname=maintenance,
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute('SELECT 1 FROM pg_database WHERE datname = %s', (dbname,))
        if cur.fetchone() is None:
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(dbname)))
            print(f'Created database: {dbname}')
        else:
            print(f'Database already exists: {dbname}')
        cur.close()
    finally:
        if conn is not None:
            conn.close()


def execute_sql_file(sql_file_path, cfg):
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(
            host=cfg['host'],
            port=cfg['port'],
            user=cfg['user'],
            password=cfg['password'],
            dbname=cfg['database'],
        )
        cur = conn.cursor()
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            script = f.read()
        for statement in script.split(';'):
            stmt = statement.strip()
            if not stmt:
                continue
            try:
                cur.execute(stmt)
            except PgError as e:
                err = str(e)
                print(f'Statement error (may be non-fatal): {err}')
                if 'already exists' in err.lower() or 'duplicate key' in err.lower():
                    print('  (ignored)')
                else:
                    raise
        conn.commit()
        print(f'Successfully ran SQL file: {sql_file_path}')
    except PgError as e:
        print(f'SQL file failed: {e}')
        if conn is not None:
            conn.rollback()
        return False
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if conn is not None:
            conn.close()
    return True


def main():
    print('PostgreSQL: creating database and tables...')
    print('(using data/database.json via CONFIG — same as app / MySQL script)')
    cfg = _pg_cfg()
    try:
        ensure_database(cfg)
    except PgError as e:
        print(f'Could not ensure database: {e}')
        print('Check data/database.json: user, password, port, and host (try 127.0.0.1).')
        return

    sql_path = os.path.join(PROJECT_ROOT, 'data', 'init_postgresql.sql')
    if not execute_sql_file(sql_path, cfg):
        print('SQL execution failed')
        return

    print('PostgreSQL init done.')


if __name__ == '__main__':
    main()
