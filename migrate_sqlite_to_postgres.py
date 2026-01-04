# migrate_sqlite_to_postgres.py
# Usage on Render:
# 1) Ensure DATABASE_URL env var is set in Render (Settings → Environment → DATABASE_URL)
# 2) Deploy so the script is present on the container
# 3) Open the service Shell in Render and run:
#    python migrate_sqlite_to_postgres.py /path/to/orders.db
#
import sys
import os
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker

if len(sys.argv) < 2:
    print("Usage: python migrate_sqlite_to_postgres.py /path/to/orders.db")
    sys.exit(1)

sqlite_path = os.path.abspath(sys.argv[1])
if not os.path.exists(sqlite_path):
    print("Fichier sqlite introuvable:", sqlite_path)
    sys.exit(1)

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("Exportez d'abord DATABASE_URL en tant que variable d'environnement (Render Settings).")
    sys.exit(1)

sqlite_url = f"sqlite:///{sqlite_path}"
print("Source (sqlite):", sqlite_url)
print("Cible (postgres):", DATABASE_URL)

eng_src = create_engine(sqlite_url, connect_args={"check_same_thread": False})
eng_dst = create_engine(DATABASE_URL)

meta_src = MetaData()
meta_dst = MetaData()

tables_to_copy = ['services', 'plans', 'users', 'orders', 'cumulative_stats', 'order_messages']
meta_src.reflect(bind=eng_src, only=tables_to_copy)
meta_dst.reflect(bind=eng_dst)

SessionDst = sessionmaker(bind=eng_dst)
dst_session = SessionDst()

try:
    for tbl_name in tables_to_copy:
        if tbl_name not in meta_src.tables:
            print(f"Table source manquante: {tbl_name}, skip")
            continue
        src_table = Table(tbl_name, meta_src, autoload_with=eng_src)
        if tbl_name not in meta_dst.tables:
            print(f"Table {tbl_name} absente en destination -> creation automatique")
            src_table.metadata = meta_dst
            src_table.create(bind=eng_dst)
            meta_dst.reflect(bind=eng_dst)
        dst_table = Table(tbl_name, meta_dst, autoload_with=eng_dst)
        with eng_src.connect() as conn_src:
            rows = conn_src.execute(src_table.select()).fetchall()
        if not rows:
            print(f"Aucune ligne pour {tbl_name}")
            continue
        print(f"Copie {len(rows)} lignes vers {tbl_name} ...")
        batch = []
        for r in rows:
            rowdict = dict(r)
            # remove keys not present in destination table (in case schema differs)
            rowdict = {k: v for k, v in rowdict.items() if k in dst_table.c}
            batch.append(rowdict)
            if len(batch) >= 200:
                dst_session.execute(dst_table.insert(), batch)
                dst_session.commit()
                batch = []
        if batch:
            dst_session.execute(dst_table.insert(), batch)
            dst_session.commit()
    print("Migration terminée.")
except Exception as e:
    print("Erreur migration:", e)
    dst_session.rollback()
finally:
    dst_session.close()
