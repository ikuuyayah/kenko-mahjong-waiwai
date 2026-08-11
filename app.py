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

# 参加申し込みをキャンセルする
@app.route("/cancel", methods=["POST"])
def cancel():
    data = request.get_json(silent=True) or {}

    dates = data.get("dates", [])
    user_id = data.get("user_id")

    if not dates:
        return jsonify({
            "status": "error",
            "message": "キャンセルする日付が指定されていません"
        }), 400

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "LINEユーザー情報を取得できませんでした"
        }), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM participants
            WHERE user_id = %s
              AND date = ANY(%s)
        """, (user_id, dates))

        deleted_count = cursor.rowcount
        conn.commit()

        return jsonify({
            "status": "ok",
            "message": "参加申し込みをキャンセルしました",
            "deleted_count": deleted_count
        })

    except Exception as error:
        conn.rollback()
        print(error)

        return jsonify({
            "status": "error",
            "message": "キャンセル中にエラーが発生しました"
        }), 500

    finally:
        cursor.close()
        conn.close()

# 自分が登録している参加日を取得する
@app.route("/my-dates")
def my_dates():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({
            "status": "error",
            "message": "LINEユーザー情報を取得できませんでした"
        }), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT date
            FROM participants
            WHERE user_id = %s
            ORDER BY date
        """, (user_id,))

        dates = [str(row[0]) for row in cursor.fetchall()]
        
        return jsonify({
            "status": "ok",
            "dates": dates
        })

    except Exception as error:
        print(error)

        return jsonify({
            "status": "error",
            "message": "参加日の取得中にエラーが発生しました"
        }), 500

    finally:
        cursor.close()
        conn.close()

# 指定した日の参加人数を取得する
@app.route("/participant-count")
def participant_count():
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
            SELECT COUNT(*)
            FROM participants
            WHERE date = %s
        """, (selected_date,))

        count = cursor.fetchone()[0]

        return jsonify({
            "status": "ok",
            "date": selected_date,
            "count": count,
            "is_full": count >= 32,
            "show_warning": count >= 33
        })

    except Exception as error:
        print(error)

        return jsonify({
            "status": "error",
            "message": "参加人数の取得中にエラーが発生しました"
        }), 500

    finally:
        cursor.close()
        conn.close()

        
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
