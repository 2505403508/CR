from flask import (
    Flask,
    render_template,
    g,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)  # Flask core imports / Flask核心导入
# For password hashing / 密码加密用
from werkzeug.security import generate_password_hash, check_password_hash
# For fuzzy search / 模糊搜索用
from difflib import SequenceMatcher
import sqlite3  # Database / 数据库
import os  # File path / 路径
import uuid  # Generate unique id / 生成唯一id
import random  # Random deck / 随机卡组

app = Flask(__name__)
# Session encryption / session加密
app.secret_key = 'your-secret-key'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        # Connect to db / 连接数据库
        db_path = os.path.join(
            os.path.dirname(__file__),
            'database',
            'crdatabase.db',
        )
        db = g._database = sqlite3.connect(db_path)
        # Use dict-like rows / 行可以用字段名访问
        db.row_factory = sqlite3.Row
    return db


@app.route('/')
def home():
    # Get language / 获取语言
    lang = request.args.get('lang', 'en')
    # Render homepage / 渲染主页
    return render_template('home.html', lang=lang)


@app.route('/cards')
def all_cards():
    db = get_db()
    cursor = db.cursor()

    # Get search query / 获取搜索内容
    q = request.args.get('q', '').strip()
    # Flag for long search / 标记搜索过长
    search_too_long = False

    if len(q) > 30:
        # Show message / 提示用户
        flash(
            "Your search is too long. Please enter 30 characters or less. "
            "没有超过30字符的卡牌名。",
            "error",
        )
        search_too_long = True
        q = ''

    if q and not search_too_long:
        import re
        # Clean input / 清理输入
        search_key = ''.join(re.findall(r'[a-zA-Z]', q)).lower()

        cursor.execute("SELECT id, name FROM cards")
        for card in cursor.fetchall():
            # Clean db name / 清理卡牌名
            db_key = ''.join([c for c in card['name'] if c.isalpha()]).lower()
            if search_key == db_key and card['id']:
                try:
                    # Ensure id is int / 确保id是整数
                    card_id = int(card['id'])
                    # Jump to card / 跳转到卡牌详情
                    return redirect(
                        url_for('get_card_details', card_id=card_id)
                    )
                except (ValueError, TypeError):
                    pass
        # If not found, show all cards / 没找到就显示全部

    cursor.execute("SELECT * FROM cards")
    cards = cursor.fetchall()
    card_list = []
    for card in cards:
        card_dict = {
            'id': card['id'],
            'name': card['name'],
            'type': card['type'],
            'elixir_cost': card['elixir_cost'],
            'arena_unlocked': card['arena_unlocked'],
            'rarity': card['rarity'],
            'image': os.path.basename(card['image']),
        }
        card_list.append(card_dict)

    # Show all cards / 展示所有卡牌
    return render_template('all_cards.html', cards=card_list)


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        # Close db / 关闭数据库
        db.close()


@app.route('/card/<int:card_id>', methods=['GET', 'POST'])
def get_card_details(card_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
    card = cursor.fetchone()

    if not card:
        # Card not exist / 卡牌不存在
        flash("Card not found.", "error")
        return redirect(url_for('all_cards'))

    is_fav = False
    if 'user_id' in session:
        cursor.execute(
            "SELECT 1 FROM favourite WHERE user_id = ? AND card_id = ?",
            (session['user_id'], card_id),
        )
        # Check if favourite / 检查是否收藏
        is_fav = cursor.fetchone() is not None

    if request.method == 'POST':
        if 'user_id' not in session:
            # Not logged in / 没登录跳转
            return redirect(url_for('login'))
        if is_fav:
            cursor.execute(
                "DELETE FROM favourite WHERE user_id = ? AND card_id = ?",
                (session['user_id'], card_id),
            )
            db.commit()
            # Remove favourite / 取消收藏
            flash('Removed from favourites!', 'info')
        else:
            cursor.execute(
                "INSERT INTO favourite (user_id, card_id) VALUES (?, ?)",
                (session['user_id'], card_id),
            )
            db.commit()
            # Add favourite / 添加收藏
            flash('Added to favourites!', 'success')

        return redirect(url_for('get_card_details', card_id=card_id))

    card_data = {
        'id': card['id'],
        'name': card['name'],
        'type': card['type'],
        'elixir_cost': card['elixir_cost'],
        'arena_unlocked': card['arena_unlocked'],
        'rarity': card['rarity'],
        'image': os.path.basename(card['image']),
    }
    # Show card detail / 展示卡牌详情
    return render_template('card_details.html', card=card_data, is_fav=is_fav)


@app.route('/compare')
def compare_cards():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM cards")
    all_cards = cursor.fetchall()

    all_cards_list = []
    for card in all_cards:
        all_cards_list.append({
            'id': card['id'],
            'name': card['name'],
            'type': card['type'],
            'elixir_cost': card['elixir_cost'],
            'arena_unlocked': card['arena_unlocked'],
            'rarity': card['rarity'],
            'image': os.path.basename(card['image']),
        })

    card1_id = request.args.get('card1')
    card2_id = request.args.get('card2')
    card1 = card2 = None

    def to_dict(card):
        return {
            'id': card['id'],
            'name': card['name'],
            'type': card['type'],
            'elixir_cost': card['elixir_cost'],
            'arena_unlocked': card['arena_unlocked'],
            'rarity': card['rarity'],
            'image': os.path.basename(card['image']),
        }

    if card1_id and card2_id:
        try:
            card1_id = int(card1_id)
            card2_id = int(card2_id)
        except ValueError:
            card1_id = card2_id = None

        if card1_id and card2_id:
            cursor.execute("SELECT * FROM cards WHERE id = ?", (card1_id,))
            c1 = cursor.fetchone()
            cursor.execute("SELECT * FROM cards WHERE id = ?", (card2_id,))
            c2 = cursor.fetchone()
            if c1 and c2:
                card1 = to_dict(c1)
                card2 = to_dict(c2)

    # Compare cards / 卡牌对比
    return render_template(
        'compare.html',
        all_cards=all_cards_list,
        card1=card1,
        card2=card2,
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        identifier = request.form['identifier'].strip()
        password = request.form['password']
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (identifier, identifier),
        )
        user = cursor.fetchone()
        if user:
            db_password = user['password']
            # Support plain or hashed / 支持明文或加密
            if (
                db_password == password
                or check_password_hash(db_password, password)
            ):

                session['user'] = user['username']
                session['user_id'] = user['id']
                # Login success / 登录成功
                flash('Login successful!', 'success')
                return redirect(url_for('home'))
        # Login fail / 登录失败
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

        cursor.execute(
            "SELECT 1 FROM users WHERE username = ? OR email = ?",
            (username, email),
        )
        if cursor.fetchone():
            # User exists / 用户已存在
            error = "Username or email already exists."
            return render_template('register.html', error=error)

        if len(email) > 100 or '@' not in email or '.' not in email:
            # 邮箱不合法
            error = "Invalid email address."
            return render_template('register.html', error=error)

        if len(username) > 20 or not username.isalnum():
            # 用户名不合法
            error = "Username must be up to 20 letters or numbers."
            return render_template('register.html', error=error)

        if len(password) < 6 or len(password) > 32:
            # 密码长度不合法
            error = "Password must be 6-32 characters."
            return render_template('register.html', error=error)

        user_id = uuid.uuid4().hex
        # Encrypt password / 加密密码
        hashed_pw = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (id, username, email, password) "
            "VALUES (?, ?, ?, ?)",
            (user_id, username, email, hashed_pw),
        )
        db.commit()

        session['user'] = username
        session['user_id'] = user_id
        # Register success / 注册成功
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
    error = None

    if request.method == 'POST':
        if len(all_cards) < 8:
            # 卡牌数量不足8张
            error = (
                "Sorry, there are not enough cards in the game "
                "to make a deck of 8."
            )
        else:
            # 检查是否有重复（random.sample不会重复；但筛选后可能不足8张）
            selected = random.sample(all_cards, 8)
            card_names = [card['name'] for card in selected]
            if len(set(card_names)) < 8:
                # 有重复
                error = (
                    "Sorry, there are not enough unique cards "
                    "to make a deck of 8."
                )
            else:
                deck = [{
                    'id': card['id'],
                    'name': card['name'],
                    'type': card['type'],
                    'elixir_cost': card['elixir_cost'],
                    'arena_unlocked': card['arena_unlocked'],
                    'rarity': card['rarity'],
                    'image': os.path.basename(card['image']),
                } for card in selected]

    # Show random deck / 展示随机卡组
    return render_template('random_deck.html', deck=deck, error=error)


@app.route('/random_deck_pro', methods=['GET', 'POST'])
def random_deck_pro():
    db = get_db()
    cursor = db.cursor()

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
        elif (
            troop_count > len(troops)
            or spell_count > len(spells)
            or building_count > len(buildings)
        ):
            error = "Not enough cards of the selected type."
        else:
            # 保证每种类型内部不重复（按名字唯一）
            def unique_sample(card_list, count):
                seen = set()
                unique_cards = []
                for card in card_list:
                    if card['name'] not in seen:
                        seen.add(card['name'])
                        unique_cards.append(card)
                if len(unique_cards) < count:
                    # 不够唯一卡牌
                    return None
                return random.sample(unique_cards, count)

            deck = []
            if troop_count > 0:
                troop_sample = unique_sample(troops, troop_count)
                if troop_sample is None:
                    error = "Sorry, not enough unique Troop cards."
                else:
                    deck += troop_sample

            if spell_count > 0 and not error:
                spell_sample = unique_sample(spells, spell_count)
                if spell_sample is None:
                    error = "Sorry, not enough unique Spell cards."
                else:
                    deck += spell_sample

            if building_count > 0 and not error:
                building_sample = unique_sample(buildings, building_count)
                if building_sample is None:
                    error = "Sorry, not enough unique Building cards."
                else:
                    deck += building_sample

            # 最终再检查整体唯一
            if not error:
                card_names = [card['name'] for card in deck]
                if len(set(card_names)) < 8:
                    error = (
                        "Sorry, there are not enough unique cards "
                        "to make a deck of 8."
                    )
                else:
                    deck = [{
                        'id': card['id'],
                        'name': card['name'],
                        'type': card['type'],
                        'elixir_cost': card['elixir_cost'],
                        'arena_unlocked': card['arena_unlocked'],
                        'rarity': card['rarity'],
                        'image': os.path.basename(card['image']),
                    } for card in deck]

    # Show pro deck / 展示高级随机卡组
    return render_template('random_deck_pro.html', deck=deck, error=error)


@app.route('/favourite/<int:card_id>', methods=['POST'])
def favourite_card(card_id):
    if 'user_id' not in session:
        # Not logged in / 没登录
        return redirect(url_for('login'))

    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT 1 FROM favourite WHERE user_id = ? AND card_id = ?",
        (user_id, card_id),
    )
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO favourite (user_id, card_id) VALUES (?, ?)",
            (user_id, card_id),
        )
        db.commit()
        # Add favourite / 添加收藏
        flash("Card added to favourites!", "success")
    else:
        # Already favourite / 已收藏
        flash("Already in favourites!", "info")

    referer = request.referrer or url_for('all_cards')
    return redirect(referer)


@app.route('/favourite')
def favourite_page():
    if 'user_id' not in session:
        # Not logged in / 没登录
        return redirect(url_for('login'))

    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT cards.id, cards.name, cards.image
        FROM favourite
        JOIN cards ON favourite.card_id = cards.id
        WHERE favourite.user_id = ?
        """,
        (user_id,),
    )
    fav_cards = cursor.fetchall()

    card_list = []
    for card in fav_cards:
        card_list.append({
            'id': card['id'],
            'name': card['name'],
            'image': os.path.basename(card['image']),
        })

    # Show favourites / 展示收藏夹
    return render_template('favourite.html', cards=card_list)


@app.route('/logout')
def logout():
    session.clear()
    # Logout / 退出登录
    flash('Logged out successfully!', 'info')
    return redirect(url_for('home'))


@app.route('/autocomplete')
def autocomplete():
    # Get search input / 获取搜索内容
    q = request.args.get('q', '').strip().lower()
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, name FROM cards")

    results = []
    for card in cursor.fetchall():
        name = card['name'].lower()
        # Fuzzy match / 模糊匹配
        ratio = SequenceMatcher(None, q, name).ratio()
        if ratio >= 0.6:
            results.append({'id': card['id'], 'name': card['name']})

    # Return json / 返回json
    return jsonify(results=results)


@app.errorhandler(404)
def page_not_found(e):
    # 404
    return render_template('404.html'), 404


if __name__ == '__main__':
    # Start server / 启动服务
    app.run(debug=True)

# CREATE TABLE users (
#     id TEXT PRIMARY KEY,
#     username TEXT UNIQUE NOT NULL,
#     email TEXT UNIQUE NOT NULL,
#     password TEXT NOT NULL
