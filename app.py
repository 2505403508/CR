from flask import Flask, render_template, g, request, redirect, url_for, session, flash
import sqlite3
import os
import uuid
import random

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
    cursor = db.cursor()
    q = request.args.get('q', '').strip()
    if q:
        # 只保留字母，转小写
        import re
        search_key = ''.join(re.findall(r'[a-zA-Z]', q)).lower()
        # 查询所有卡牌
        cursor.execute("SELECT id, name FROM cards")
        for card_id, name in cursor.fetchall():
            db_key = ''.join([c for c in name if c.isalpha()]).lower()
            if search_key == db_key:
                return redirect(url_for('get_card_details', card_id=card_id))
    cursor.execute("SELECT * FROM cards")
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
    db = get_db()
    cursor = db.cursor()
    # 获取所有卡牌用于下拉选择
    cursor.execute("SELECT * FROM cards")
    all_cards = cursor.fetchall()
    all_cards_list = []
    for card in all_cards:
        all_cards_list.append({
            'id': card[0],
            'name': card[1],
            'type': card[2],
            'elixir_cost': card[3],
            'arena_unlocked': card[4],
            'rarity': card[5],
            'image': os.path.basename(card[6])
        })

    card1_id = request.args.get('card1')
    card2_id = request.args.get('card2')
    card1 = card2 = None

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

    if card1_id and card2_id:
        cursor.execute("SELECT * FROM cards WHERE id = ?", (card1_id,))
        c1 = cursor.fetchone()
        cursor.execute("SELECT * FROM cards WHERE id = ?", (card2_id,))
        c2 = cursor.fetchone()
        if c1 and c2:
            card1 = to_dict(c1)
            card2 = to_dict(c2)

    return render_template('compare.html', all_cards=all_cards_list, card1=card1, card2=card2)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        identifier = request.form['identifier'].strip()
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE (username = ? OR email = ?) AND password = ?",
            (identifier, identifier, password)
        )
        user = cursor.fetchone()
        if user:
            session['user'] = user['username']
            session['user_id'] = user['id']
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            error = "Invalid username/email or password."
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()

        # Check for existing username or email
        cursor.execute("SELECT 1 FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            error = "Username or email already exists."
            return render_template('register.html', error=error)

        user_id = uuid.uuid4().hex  # Generate a unique hash ID

        cursor.execute(
            "INSERT INTO users (id, username, email, password) VALUES (?, ?, ?, ?)",
            (user_id, username, email, password)
        )
        db.commit()
        session['user'] = username
        session['user_id'] = user_id
        flash('Register successful!', 'success')
        return redirect(url_for('home'))
    return render_template('register.html', error=error)

@app.route('/random_deck', methods=['GET', 'POST'])
def random_deck():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM cards")
    all_cards = cursor.fetchall()

    deck = []
    if request.method == 'POST':
        # 随机选8张不重复的卡牌
        selected = random.sample(all_cards, 8)
        # 转成字典方便模板渲染
        deck = [{
            'id': card[0],
            'name': card[1],
            'type': card[2],
            'elixir_cost': card[3],
            'arena_unlocked': card[4],
            'rarity': card[5],
            'image': card[6]
        } for card in selected]

    return render_template('random_deck.html', deck=deck)

@app.route('/random_deck_pro', methods=['GET', 'POST'])
def random_deck_pro():
    db = get_db()
    cursor = db.cursor()
    # 获取所有类型的卡牌
    cursor.execute("SELECT * FROM cards WHERE type = 'Troop'")
    troops = cursor.fetchall()
    cursor.execute("SELECT * FROM cards WHERE type = 'Spell'")
    spells = cursor.fetchall()
    cursor.execute("SELECT * FROM cards WHERE type = 'Building'")
    buildings = cursor.fetchall()

    deck = []
    error = None

    if request.method == 'POST':
        try:
            troop_count = int(request.form.get('troop', 0))
            spell_count = int(request.form.get('spell', 0))
            building_count = int(request.form.get('building', 0))
        except ValueError:
            troop_count = spell_count = building_count = 0

        total = troop_count + spell_count + building_count
        if total != 8:
            error = "The total number of cards must be exactly 8."
        elif troop_count > len(troops) or spell_count > len(spells) or building_count > len(buildings):
            error = "Not enough cards of the selected type."
        else:
            import random
            deck = []
            if troop_count > 0:
                deck += random.sample(troops, troop_count)
            if spell_count > 0:
                deck += random.sample(spells, spell_count)
            if building_count > 0:
                deck += random.sample(buildings, building_count)
            # 转为字典方便模板渲染
            deck = [{
                'id': card[0],
                'name': card[1],
                'type': card[2],
                'elixir_cost': card[3],
                'arena_unlocked': card[4],
                'rarity': card[5],
                'image': card[6]
            } for card in deck]

    return render_template('random_deck_pro.html', deck=deck, error=error)

@app.route('/favourite/<int:card_id>', methods=['POST'])
def favourite_card(card_id):
    # 检查是否登录
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    # 检查是否已收藏
    cursor.execute("SELECT 1 FROM favourite WHERE user_id = ? AND card_id = ?", (user_id, card_id))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO favourite (user_id, card_id) VALUES (?, ?)", (user_id, card_id))
        db.commit()
        flash("Card added to favourites!", "success")
    else:
        flash("Already in favourites!", "info")
    # 返回上一页
    referer = request.referrer or url_for('all_cards')
    return redirect(referer)

@app.route('/favourite')
def favourite_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT cards.id, cards.name, cards.image
        FROM favourite
        JOIN cards ON favourite.card_id = cards.id
        WHERE favourite.user_id = ?
    """, (user_id,))
    fav_cards = cursor.fetchall()
    card_list = []
    for card in fav_cards:
        card_list.append({
            'id': card[0],
            'name': card[1],
            'image': os.path.basename(card[2])
        })
    return render_template('favourite.html', cards=card_list)

# staart the Flask app
if __name__ == '__main__':
    app.run(debug=True)

# CREATE TABLE users (
#     id TEXT PRIMARY KEY,
#     username TEXT UNIQUE NOT NULL,
#     email TEXT UNIQUE NOT NULL,
#     password TEXT NOT NULL
# );
