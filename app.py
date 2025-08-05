from flask import Flask, render_template, g, request, redirect, url_for, session    
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # 用于加密 session


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'database', 'crdatabase.db'))
        db.row_factory = sqlite3.Row  # 结果可以访问
    return db


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/cards')
def all_cards():
    db = get_db()
    cursor = db.execute('SELECT * FROM cards')
    cards = cursor.fetchall()

    # Convert to list of dicts with just the image filename
    card_list = []
    for card in cards:
        card_dict = {
            'id': card[0],
            'name': card[1],
            'type': card[2],
            'elixir_cost': card[3],
            'arena_unlocked': card[4],
            'rarity': card[5],
            'image': os.path.basename(card[6])  # <-- just the filename!
        }
        card_list.append(card_dict)

    return render_template('all_cards.html', cards=card_list)


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/cards/<int:card_id>')
def get_card_details(card_id):
    """
    显示指定卡牌的详细信息页面。
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
    card = cursor.fetchone()

    if card is None:
        return "Card not found", 404

    # 将数据库结果转成字典格式，方便 HTML 模板使用
    card_data = {
        'id': card[0],
        'name': card[1],
        'type': card[2],
        'elixir_cost': card[3],
        'arena_unlocked': card[4],
        'rarity': card[5],
        'image': os.path.basename(card[6])
    }

    return render_template('card_details.html', card=card_data)

@app.route('/compare')
def compare_cards():
    """
    比较两张卡牌的属性，并显示差异。
    示例链接: /compare?card1=1&card2=4
    """
    card1_id = request.args.get('card1')
    card2_id = request.args.get('card2')

    if not card1_id or not card2_id:
        return "请提供两个卡牌ID，例如 /compare?card1=1&card2=4", 400

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM cards WHERE id = ?", (card1_id,))
    card1 = cursor.fetchone()

    cursor.execute("SELECT * FROM cards WHERE id = ?", (card2_id,))
    card2 = cursor.fetchone()

    if not card1 or not card2:
        return "某个卡牌不存在", 404

    # 转换为字典
    def to_dict(card):
        return {
            'id': card[0],
            'name': card[1],
            'type': card[2],
            'elixir_cost': card[3],
            'arena_unlocked': card[4],
            'rarity': card[5],
            'image': os.path.basename(card[6])
        }

    return render_template('compare.html', card1=to_dict(card1), card2=to_dict(card2))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier']  # username or email
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM users 
            WHERE (username = ? OR email = ?) AND password = ?
        """, (identifier, identifier, password))

        user = cursor.fetchone()
        if user:
            session['user'] = user[1]  # Save username in session
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Invalid login.")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, password)
            )
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error="Username or email already exists.")

    return render_template('register.html')


# 启动
if __name__ == '__main__':
    app.run(debug=True)
