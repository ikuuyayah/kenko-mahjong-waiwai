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
# 参加日を登録する
@app.route("/join", methods=["POST"])
def join():
    data = request.get_json()

    dates = data.get("dates", [])
    user_id = data.get("user_id")
    name = data.get("name")

    if not dates:
        return jsonify({
            "status": "error",
            "message": "参加日が選択されていません"
        }), 400

    if not user_id or not name:
        return jsonify({
            "status": "error",
            "message": "LINEユーザー情報を取得できませんでした"
        }), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        for selected_date in dates:
            # 同じ人・同じ日付が登録済みか確認
            cursor.execute("""
                SELECT id
                FROM participants
                WHERE date = %s AND user_id = %s
            """, (selected_date, user_id))

            # 未登録の場合だけ追加
            if cursor.fetchone() is None:
                cursor.execute("""
                    INSERT INTO participants
                        (date, user_id, name, created)
                    VALUES
                        (%s, %s, %s, %s)
                """, (
                    selected_date,
                    user_id,
                    name,
                    datetime.now().isoformat()
                ))

        conn.commit()

        return jsonify({
            "status": "ok",
            "message": "参加日を登録しました"
        })

    except Exception as error:
        conn.rollback()
        print(error)

        return jsonify({
            "status": "error",
            "message": "登録中にエラーが発生しました"
        }), 500

    finally:
        cursor.close()
        conn.close()

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


# 指定した日の参加者一覧を取得する
@app.route("/list")
def list_day():
    selected_date = request.args.get("date")

    if not selected_date:
        return jsonify({
            "status": "error",
            "message": "日付が指定されていません"
        }), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT name
            FROM participants
            WHERE date = %s
            ORDER BY created
        """, (selected_date,))

        users = [row[0] for row in cursor.fetchall()]

        return jsonify(users)

    except Exception as error:
        print(error)

        return jsonify({
            "status": "error",
            "message": "参加者情報を取得できませんでした"
        }), 500

    finally:
        cursor.close()
        conn.close()

import os
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
