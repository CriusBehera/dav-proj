import argparse
import getpass
from pathlib import Path

import mysql.connector

FILES = ["schema.sql"]


def statements(path):
    text = "\n".join(line for line in Path(path).read_text().splitlines()
                     if not line.strip().startswith("--"))
    return [s.strip() for s in text.split(";\n") if s.strip().rstrip(";")]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--port", type=int, default=4000)
    parser.add_argument("--file", help="run only this .sql file")
    args = parser.parse_args()

    options = dict(host=args.host, port=args.port, user=args.user,
                   password=getpass.getpass(f"Password for {args.user}: "), use_pure=True)
    if args.host not in ("localhost", "127.0.0.1"):
        options.update(ssl_ca="/etc/ssl/cert.pem", ssl_verify_identity=True)

    conn = mysql.connector.connect(**options)
    cur = conn.cursor()
    for name in [args.file] if args.file else FILES:
        stmts = statements(name)
        for sql in stmts:
            cur.execute(sql.rstrip(";"))
        conn.commit()
        print(f"✓ {name}: ran {len(stmts)} statements")

    for table in ("users", "products", "warehouses", "stock", "customers", "orders", "order_items", "payments"):
        cur.execute(f"SELECT COUNT(*) FROM dav_db.{table}")
        print(f"  {table:<9} {cur.fetchone()[0]} rows")
    conn.close()


if __name__ == "__main__":
    main()
