from flask import Flask, request, render_template, redirect, url_for
import sqlite3
from datetime import datetime
import pytz  # JSTのためのライブラリ

app = Flask(__name__)

# データベースの初期化
def init_db():
    with sqlite3.connect('progress.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            twitter_id TEXT NOT NULL,
            nickname TEXT NOT NULL,
            field TEXT NOT NULL,
            date DATE NOT NULL,
            page_count INTEGER NOT NULL,
            UNIQUE(twitter_id, nickname, date)  -- 同じtwitter_id, nickname, dateの組み合わせで重複を防ぐ
        )''')
        conn.commit()

# フォーム表示
@app.route('/')
def index():
    return render_template('index.html')

# フォームデータの保存とリダイレクト
@app.route('/submit', methods=['POST'])
def submit():
    twitter_id = request.form['twitter']
    nickname = request.form['nickname']
    field = request.form['field']
    date = request.form['date']
    page_count = int(request.form['page_count'])

    with sqlite3.connect('progress.db') as conn:
        cursor = conn.cursor()

        # 既存データを更新するか、新しいデータを挿入する
        cursor.execute('''SELECT id FROM progress WHERE twitter_id = ? AND nickname = ? AND date = ?''', 
                       (twitter_id, nickname, date))
        existing_entry = cursor.fetchone()

        if existing_entry:
            # 存在すれば更新
            cursor.execute('''UPDATE progress SET page_count = ? WHERE id = ?''',
                           (page_count, existing_entry[0]))
        else:
            # 存在しなければ挿入
            cursor.execute('''INSERT INTO progress (twitter_id, nickname, field, date, page_count)
                              VALUES (?, ?, ?, ?, ?)''',
                           (twitter_id, nickname, field, date, page_count))
        conn.commit()

    # 現在の日付 (JST) を取得
    jst = pytz.timezone('Asia/Tokyo')
    today = datetime.now(jst).strftime('%Y-%m-%d')  # 今日の日付をJSTで取得

    # その日付に対するランキングの取得（0ページは除外）
    with sqlite3.connect('progress.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT twitter_id, nickname, SUM(page_count) AS total_pages 
                          FROM progress
                          WHERE date = ? AND page_count > 0  -- 0ページは除外
                          GROUP BY twitter_id
                          ORDER BY total_pages DESC
                          LIMIT 10''', (today,))

        top_users = cursor.fetchall()

    # 上位10名に満たない場合、"Unknown"を補填
    if len(top_users) < 10:
        for _ in range(10 - len(top_users)):
            top_users.append(('unknown', 'Unknown', 0))  # 0ページの"Unknown"ユーザーを追加

    # グラフデータ作成
    # グラフデータ作成
    graph_data = []
    user_labels = []
    
    # 0ページを含まないすべてのデータを取得
    with sqlite3.connect('progress.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT date, twitter_id, nickname, SUM(page_count) AS total_pages
                          FROM progress 
                          WHERE page_count > 0  -- 0ページは除外
                          GROUP BY date, twitter_id, nickname
                          ORDER BY date, total_pages DESC''')
        data = cursor.fetchall()
    
    # グラフデータ作成
    # 過去の日付のみで入力したユーザーも表示するため、top_usersとは独立してすべてのユーザーを扱う
    for user in set((row[1], row[2]) for row in data):  # ユーザーごとのセットを取得
        user_data = {
            "twitter_id": user[0],
            "nickname": user[1],
            "data": []
        }
    
        # ユーザーごとのデータを追加
        for date in sorted(set(row[0] for row in data)):  # すべての日付に対して
            user_progress = next((row[3] for row in data if row[0] == date and row[1] == user[0] and row[2] == user[1]), 0)
            user_data["data"].append({
                "date": date,
                "total_pages": user_progress
            })
    
        graph_data.append(user_data)
        user_labels.append(user[1])
    
    # すべての日付を取得 (graph.htmlで使うため)
    all_dates = sorted(set(row[0] for row in data))  # すべての日付を取得
    
    return render_template('graph.html', graph_data=graph_data, top_users=top_users, user_labels=user_labels, all_dates=all_dates)


# メインエントリーポイント
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
