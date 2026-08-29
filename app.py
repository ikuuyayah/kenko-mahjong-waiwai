from flask import Flask, request, jsonify, render_template
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
# ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# イベントを登録する（管理者用）
@app.route("/api/events/create", methods=["POST"])
def create_event():
    data = request.get_json(silent=True) or {}

    # admin_password = data.get("admin_password")
    event_date = data.get("event_date")
    event_name = data.get("event_name")
    description = data.get("description", "")
    start_time = data.get("start_time")

    # 管理用パスワードを確認　※一時停止中
    # if not ADMIN_PASSWORD:
    #     return jsonify({
    #         "status": "error",
    #         "message": "管理用パスワードが設定されていません"
    #     }), 500

    # if admin_password != ADMIN_PASSWORD:
    #     return jsonify({
    #         "status": "error",
    #         "message": "管理用パスワードが違います"
    #     }), 403

    # 必須項目を確認
    if not event_date or not event_name or not start_time:
        return jsonify({
            "status": "error",
            "message": "開催日・イベント名・開始時刻を入力してください"
        }), 400

    # 日付と時刻の形式を確認
    try:
        datetime.strptime(event_date, "%Y-%m-%d")
        datetime.strptime(start_time, "%H:%M")
    except ValueError:
        return jsonify({
            "status": "error",
            "message": "開催日または開始時刻の形式が正しくありません"
        }), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 同じ日にイベントが登録されていないか確認
        cursor.execute("""
            SELECT id
            FROM events
            WHERE event_date = %s
        """, (event_date,))

        if cursor.fetchone() is not None:
            return jsonify({
                "status": "error",
                "message": "この開催日にはすでにイベントが登録されています"
            }), 409

        # イベントを登録
        cursor.execute("""
            INSERT INTO events (
                event_date,
                event_name,
                description,
                start_time
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (
            event_date,
            event_name,
            description,
            start_time
        ))

        event_id = cursor.fetchone()[0]
        conn.commit()

        return jsonify({
            "status": "ok",
            "message": "イベントを登録しました",
            "event_id": event_id
        })

    except Exception as error:
        conn.rollback()
        print(error)

        return jsonify({
            "status": "error",
            "message": "イベントの登録中にエラーが発生しました"
        }), 500

    finally:
        cursor.close()
        conn.close()

def get_connection():
    return psycopg2.connect(DATABASE_URL)

# DB初期化
def init_db():
    conn = get_connection()
    c = conn.cursor()

    # 参加申し込み
    c.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id SERIAL PRIMARY KEY,
            date TEXT,
            user_id TEXT,
            name TEXT,
            created TEXT
        )
    ''')

    # イベント情報
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            event_date DATE NOT NULL,
            event_name VARCHAR(100) NOT NULL,
            description TEXT,
            start_time TIME NOT NULL
        )
    ''')

    conn.commit()
    c.close()
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

# イベント管理画面
@app.route("/event-admin")
def event_admin():
    return render_template("event_admin.html")

# 利用者向けイベント情報画面
@app.route("/event-info")
def event_info():
    return render_template("event_info.html")

# イベント情報を取得する
@app.route("/api/events")
def get_events():
    # 例：2026-08
    selected_month = request.args.get("month")

    # 月が指定されていない場合は今月
    if not selected_month:
        selected_month = datetime.now().strftime("%Y-%m")

    # YYYY-MM形式になっているか確認
    try:
        datetime.strptime(selected_month, "%Y-%m")
    except ValueError:
        return jsonify({
            "status": "error",
            "message": "月はYYYY-MM形式で指定してください"
        }), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                e.id,
                e.event_date,
                e.event_name,
                e.description,
                e.start_time,
                COUNT(p.id) AS participant_count
            FROM events e
            LEFT JOIN participants p
                ON p.date = TO_CHAR(e.event_date, 'YYYY-MM-DD')
            WHERE e.event_date >= TO_DATE(%s || '-01', 'YYYY-MM-DD')
            AND e.event_date < TO_DATE(%s || '-01', 'YYYY-MM-DD')
                                + INTERVAL '1 month'
            AND e.event_date >=
                (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Tokyo')::date
            GROUP BY
                e.id,
                e.event_date,
                e.event_name,
                e.description,
                e.start_time
            ORDER BY
                e.event_date,
                e.start_time
        """, (selected_month, selected_month))

        events = []

        for row in cursor.fetchall():
            events.append({
                "id": row[0],
                "event_date": row[1].strftime("%Y-%m-%d"),
                "event_name": row[2],
                "description": row[3] or "",
                "start_time": row[4].strftime("%H:%M"),
                "participant_count": row[5]
            })

        return jsonify({
            "status": "ok",
            "month": selected_month,
            "events": events
        })

    except Exception as error:
        print(error)

        return jsonify({
            "status": "error",
            "message": "イベント情報を取得できませんでした"
        }), 500

    finally:
        cursor.close()
        conn.close()

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
