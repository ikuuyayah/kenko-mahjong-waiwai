from flask import Flask, request, jsonify, render_template
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL)

# DB初期化
def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id SERIAL PRIMARY KEY,
            date TEXT,
            user_id TEXT,
            name TEXT,
            created TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 画面表示（LIFF）
@app.route("/")
def index():
    return render_template("index.html")

# 参加者確認用
@app.route("/confirm")
def confirm():
    return render_template("confirm.html")

# 参加する
@app.route("/join", methods=["POST"])
def join():
    data = request.json

    conn = sqlite3.connect('participants.db')
    c = conn.cursor()

    # すでに登録されてたら無視
    c.execute("""
        SELECT * FROM participants
        WHERE date=? AND user_id=?
    """, (data["date"], data["user_id"]))

    if not c.fetchone():
        c.execute("""
            INSERT INTO participants
            (date, user_id, name, created)
            VALUES (?, ?, ?, ?)
        """, (
            data["date"],
            data["user_id"],
            data["name"],
            datetime.now().isoformat()
        ))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# やめる
@app.route("/cancel", methods=["POST"])
def cancel():
    data = request.json

    conn = sqlite3.connect('participants.db')
    c = conn.cursor()

    c.execute("""
        DELETE FROM participants
        WHERE date=? AND user_id=?
    """, (data["date"], data["user_id"]))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# 一覧取得
@app.route("/list")
def list_day():
    date = request.args.get("date")

    conn = sqlite3.connect('participants.db')
    c = conn.cursor()

    c.execute("""
        SELECT name FROM participants
        WHERE date=?
        ORDER BY created
    """, (date,))

    users = [r[0] for r in c.fetchall()]
    conn.close()

    return jsonify(users)

import os
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
