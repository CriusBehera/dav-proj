"""Copy a whole MySQL database (tables + data) to another MySQL server, e.g. TiDB Cloud.

Works on Windows, Mac and Linux, no `mysqldump` or `mysql` programs needed:

    pip install mysql-connector-python certifi
    python copy_db.py --src-user dav --src-db student_portal ^
        --dst-host gateway01.ap-southeast-1.prod.aws.tidbcloud.com --dst-user XXXX.root

It asks for both passwords (never typed into a file). Create nothing by hand:
the destination database is created if it is missing. Run it again any time;
existing tables with the same names are replaced.
"""
import argparse
import getpass

import mysql.connector


def connect(host, port, user, password, database=None):
    options = dict(host=host, port=port, user=user, password=password, use_pure=True)
    if database:
        options["database"] = database
    if host not in ("localhost", "127.0.0.1"):  # cloud servers need an encrypted connection
        try:
            import certifi
            options.update(ssl_ca=certifi.where(), ssl_verify_identity=True)
        except ImportError:
            raise SystemExit("Run:  pip install certifi   (needed for the secure connection)")
    return mysql.connector.connect(**options)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--src-host", default="localhost")
    p.add_argument("--src-port", type=int, default=3306)
    p.add_argument("--src-user", required=True)
    p.add_argument("--src-db", required=True, help="database to copy")
    p.add_argument("--dst-host", required=True)
    p.add_argument("--dst-port", type=int, default=4000)
    p.add_argument("--dst-user", required=True)
    p.add_argument("--dst-db", help="name on the destination (default: same as source)")
    p.add_argument("--batch", type=int, default=500, help="rows per INSERT")
    a = p.parse_args()
    dst_db = a.dst_db or a.src_db

    src = connect(a.src_host, a.src_port, a.src_user,
                  getpass.getpass(f"Password for {a.src_user}@{a.src_host}: "), a.src_db)
    dst = connect(a.dst_host, a.dst_port, a.dst_user,
                  getpass.getpass(f"Password for {a.dst_user}@{a.dst_host}: "))
    s, d = src.cursor(), dst.cursor()

    d.execute(f"CREATE DATABASE IF NOT EXISTS `{dst_db}`")
    d.execute(f"USE `{dst_db}`")
    d.execute("SET FOREIGN_KEY_CHECKS = 0")  # tables can be copied in any order

    s.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
    tables = [row[0] for row in s.fetchall()]
    print(f"Copying {len(tables)} tables from {a.src_db} to {dst_db} ...")
    for table in tables:
        s.execute(f"SHOW CREATE TABLE `{table}`")
        create = s.fetchone()[1]
        d.execute(f"DROP TABLE IF EXISTS `{table}`")
        d.execute(create)
        s.execute(f"SELECT * FROM `{table}`")
        columns = ", ".join(f"`{c[0]}`" for c in s.description)
        marks = ", ".join(["%s"] * len(s.description))
        total = 0
        while rows := s.fetchmany(a.batch):
            d.executemany(f"INSERT INTO `{table}` ({columns}) VALUES ({marks})", rows)
            total += len(rows)
        dst.commit()
        print(f"  OK {table:<25} {total} rows")
    d.execute("SET FOREIGN_KEY_CHECKS = 1")
    dst.commit()
    print("Done.")


if __name__ == "__main__":
    main()
