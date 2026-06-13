import sqlite3

def save_row(db_path, row):
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO t VALUES (?)", row)
    conn.commit()
