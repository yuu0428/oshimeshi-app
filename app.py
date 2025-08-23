# app.py

import os
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect, generate_csrf
from PIL import Image
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from logging.handlers import RotatingFileHandler
from functools import wraps
import shutil
from flask_talisman import Talisman
import html
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, desc, or_, text
from models import db, User, Post, Like
from supabase import create_client, Client
import base64
from urllib.parse import urlparse
from tracking_ad import tracking_ad_bp, MapClick, CouponEvent


load_dotenv()

# Flask アプリケーションの設定
app = Flask(__name__)

# データベース設定
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL（PostgreSQL URL）が.envファイルに設定されていません。")

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_URLとSUPABASE_ANON_KEYが.envファイルに設定されていません。")

# Supabaseクライアント初期化
supabase = None

def get_supabase_client():
    global supabase
    if supabase is None:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return supabase

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_timeout': 60,  # モバイル回線を考慮して60秒に延長
    'pool_recycle': 1800,  # 30分に短縮してコネクション更新を頻繁に
    'pool_pre_ping': True,  # 接続前にpingで確認
    'pool_size': 10,  # 接続プールサイズを明示的に設定
    'max_overflow': 20,  # 最大オーバーフロー接続数
    'connect_args': {
        'client_encoding': 'utf8',
        'connect_timeout': 30,  # 接続タイムアウトを30秒に設定
        'options': '-c statement_timeout=30000'  # クエリタイムアウトを30秒に設定
    }
}



# その他の設定
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER_PATH', 'static/uploads')
SECRET_KEY = os.environ.get('SECRET_KEY')

if not SECRET_KEY:
    raise ValueError("SECRET_KEYが.envファイルに設定されていません。")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# 高校リスト
SCHOOLS = [
    "北杜高等学校",
    "韮崎高等学校",
    "甲府第一高等学校",
    "甲府西高等学校",
    "甲府南高等学校",
    "甲府東高等学校",
    "甲府工業高等学校",
    "甲府城西高等学校",
    "甲府昭和高等学校",
    "農林高等学校",
    "巨摩高等学校",
    "白根高等学校",
    "青洲高等学校",
    "身延高等学校",
    "笛吹高等学校",
    "日川高等学校",
    "山梨高等学校",
    "塩山高等学校",
    "都留高等学校",
    "中央高等学校",
    "甲府商業高等学校",
    "甲陵高等学校",
    "甲斐清和高等学校",
    "駿台甲府高等学校",
    "山梨学院高等学校",
    "東海大学付属甲府高等学校",
    "日本航空高等学校"
]

GENDERS = ["男性", "女性", "その他"]


app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB制限
app.secret_key = SECRET_KEY
app.config.setdefault("COUPON_SECRET", "change-me-in-env")
app.config.setdefault("ADVERTISER_USER_ID", 1)

#データベース初期化
db.init_app(app)
# CSRFProtect設定
csrf = CSRFProtect(app)

# Blueprint registration
app.register_blueprint(tracking_ad_bp)

# CSRFトークンをテンプレートで利用可能にする
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

@app.context_processor
def inject_coupon_functions():
    from tracking_ad import has_used_coupon, current_user_id
    return dict(has_used_coupon=has_used_coupon, current_user_id=current_user_id)

# CSRFエラーのハンドリング
@app.errorhandler(400)
def handle_csrf_error(e):
    if 'CSRF' in str(e):
        flash('セキュリティトークンが無効です。ページを更新してもう一度お試しください。', 'error')
        return redirect(request.referrer or url_for('index'))
    return e

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"]
)
limiter.init_app(app)

if not app.debug:
    file_handler = RotatingFileHandler('app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

# --- Supabase Storage関連関数 ---

def upload_image_to_supabase(file, filename):
    """Supabase Storageに画像をアップロード"""
    try:
        client = get_supabase_client()
        print(f"Supabase client created: {client}")
        
        # ファイルの内容を読み取り
        file.seek(0)
        file_content = file.read()
        print(f"File content length: {len(file_content)}")
        
        # Supabase Storageにアップロード
        result = client.storage.from_("uploads").upload(
            path=filename,
            file=file_content,
            file_options={"content-type": file.content_type}
        )
        
        print(f"Upload result: {result}")
        
        if hasattr(result, 'status_code') and result.status_code == 200:
            # 公開URLを取得
            public_url = client.storage.from_("uploads").get_public_url(filename)
            print(f"Public URL: {public_url}")
            return public_url, None
        else:
            print(f"Upload failed: {result}")
            return None, f"アップロードエラー: {result}"
            
    except Exception as e:
        print(f"Supabase upload error: {e}")
        return None, "ファイルのアップロードに失敗しました。"

def delete_image_from_supabase(image_path):
    """Supabase Storageから画像を削除（改良版）"""
    if not image_path:
        print("Warning: image_path is empty or None")
        return False
        
    try:
        client = get_supabase_client()
        print(f"Attempting to delete image: {image_path}")
        
        # URLからファイル名を抽出（改良版）
        filename = None
        
        # URLパースしてクエリパラメータを除去
        parsed_url = urlparse(image_path)
        clean_url = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
        
        # 1. Supabase公開URLの場合
        if "supabase.co" in clean_url and "/object/public/uploads/" in clean_url:
            # 例: https://xxx.supabase.co/storage/v1/object/public/uploads/filename.jpg
            parts = clean_url.split("/object/public/uploads/")
            if len(parts) > 1:
                filename = parts[1]
        # 2. /uploads/が含まれる場合（従来の方法）
        elif "/uploads/" in clean_url:
            filename = clean_url.split("/uploads/")[-1]
        # 3. 単純なファイル名の場合
        else:
            # パス部分からファイル名を抽出
            path_parts = parsed_url.path.split('/')
            if path_parts:
                filename = path_parts[-1]
        
        # ファイル名のクリーンアップ（追加の安全対策）
        if filename:
            # URLデコード（日本語ファイル名対応）
            from urllib.parse import unquote
            filename = unquote(filename)
            # 不要な文字を除去
            filename = filename.strip('?&')
        
        if not filename:
            print(f"Error: Could not extract filename from path: {image_path}")
            return False
        
        print(f"Extracted clean filename: {filename}")
        
        # Supabase Storageから削除
        result = client.storage.from_("uploads").remove([filename])
        print(f"Supabase delete result: {result}")
        
        # 削除結果の確認
        if isinstance(result, list):
            if len(result) == 0:
                # 空のリストはファイルが見つからなかった可能性
                print(f"File not found or already deleted: {filename}")
                return True  # 既に削除済みと判断
            else:
                deleted_file = result[0]
                if isinstance(deleted_file, dict):
                    if 'name' in deleted_file and deleted_file['name'] == filename:
                        print(f"Successfully deleted file: {filename}")
                        return True
                    elif deleted_file.get('error'):
                        print(f"Supabase delete error: {deleted_file['error']}")
                        return False
                print(f"File deletion completed: {deleted_file}")
                return True
        elif isinstance(result, dict):
            if result.get('error'):
                print(f"Supabase delete error: {result['error']}")
                return False
            else:
                print(f"Successfully deleted file: {filename}")
                return True
        else:
            print(f"Unknown result format: {result}")
            return True
            
    except Exception as e:
        print(f"Exception during Supabase delete: {str(e)}")
        print(f"Exception type: {type(e).__name__}")
        return False

def process_uploaded_image(file):
    """アップロード画像の処理（Supabase Storage版）"""
    try:
        # 基本検証
        if not file or not file.filename:
            return None, "ファイルが選択されていません。"
        
        # サイズチェック
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            return None, "ファイルサイズは10MB以下にしてください。"
        
        # 画像として開けるかチェック
        img = Image.open(file)
        file.seek(0)
        
        # 形式チェック
        if img.format.lower() not in ['jpeg', 'jpg', 'png']:
            return None, "JPEG、PNG形式の画像のみ対応しています。"
        
        return file, None
        
    except Exception as e:
        print(f"Image processing error: {e}")
        return None, "画像ファイルの処理中にエラーが発生しました。"

# --- データベース関連 ---

def init_db():
    """データベースとテーブルを初期化"""
    with app.app_context():
        try:
            # テーブル作成
            db.create_all()
            print("Database tables created successfully.")
            
            # 広告アカウント（ID=1）の作成
            ad_account = User.query.get(1)
            if not ad_account:
                ad_account = User(
                    id=1,
                    username="【広告】",
                    is_admin=True,
                    is_advertiser=True,
                    gender=None
                )
                db.session.add(ad_account)
                db.session.commit()
                print("Advertisement account created successfully.")
            
        except SQLAlchemyError as e:
            print(f"Database initialization error: {e}")
            raise


@app.cli.command('init-db')
def init_db_command():
    """Clear existing data and create new tables."""
    init_db()
    print('Initialized the database.')

@app.cli.command('reset-db')
def reset_db_command():
    """Drop all tables and recreate them."""
    db.drop_all()
    db.create_all()
    print('Database reset complete.')

# --- ユーザー関連 ---
FOREIGN_FIRST_NAMES = [
    "Alex", "Ben", "Chris", "Dana", "Eli", "Finn", "Gaby", "Hael", "Ira", "Jean",
    "Kim", "Lee", "Max", "Nat", "Oli", "Pat", "Quin", "Ramy", "Sam", "Teo",
    "Uli", "Val", "Wes", "Xei", "Yael", "Ziv",
    "Ace", "Ash", "Blue", "Cole", "Dean", "Eden", "Gray", "Hope", "Ivy", "Jay",
    "Kai", "Luna", "Mika", "Nova"
]

FOREIGN_LAST_NAMES = [
    "Smith", "Jones", "Williams", "Brown", "Davis", "Miller", "Wilson", "Moore", 
    "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", 
    "Thompson", "Garcia", "Martinez", "Robinson", "Clark",
    "Lewis", "Lee", "Walker", "Hall", "Allen", "Young", "King", "Wright", 
    "Lopez", "Hill", "Scott", "Green", "Adams", "Baker", "Gonzalez", "Nelson", 
    "Carter", "Mitchell", "Perez", "Roberts"
]

def generate_random_username():
    return f"{random.choice(FOREIGN_FIRST_NAMES)} {random.choice(FOREIGN_LAST_NAMES)}"

def get_used_schools():
    """使用されたことのある高校を取得し、頻度順でソート"""
    try:
        used_schools = db.session.query(
            Post.school, 
            func.count(Post.id).label('usage_count')
        ).filter(
            Post.school.isnot(None),
            Post.school != ''
        ).group_by(Post.school).order_by(desc('usage_count')).all()
        
        return [school[0] for school in used_schools]
    except SQLAlchemyError as e:
        print(f"Error getting used schools: {e}")
        return []

def get_sorted_schools():
    """使用頻度順に並べた高校リストを返す"""
    used_schools = get_used_schools()
    remaining_schools = [school for school in SCHOOLS if school not in used_schools]
    return used_schools + remaining_schools

def is_uptimerobot_request():
    """UptimeRobotからのアクセスかを判定"""
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # UptimeRobotのユーザーエージェントパターン
    if 'uptimerobot' in user_agent or 'uptime robot' in user_agent:
        return True
    
    # ヘルスチェック用のパスの場合
    if request.path in ['/health', '/ping', '/uptimerobot']:
        return True
    
    return False

def is_mobile_device():
    """モバイルデバイスかどうかを判定"""
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_agents = ['mobile', 'android', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone']
    return any(agent in user_agent for agent in mobile_agents)

def log_request_details():
    """リクエストの詳細をログに記録（モバイル問題調査用）"""
    if is_mobile_device():
        app.logger.info(f"Mobile Request: {request.method} {request.path}")
        app.logger.info(f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}")
        app.logger.info(f"Remote Addr: {request.remote_addr}")
        app.logger.info(f"Headers: {dict(request.headers)}")
        if request.args:
            app.logger.info(f"Args: {dict(request.args)}")
        if request.form:
            app.logger.info(f"Form: {dict(request.form)}")
        return True
    return False

@app.before_request
def load_logged_in_user():
    from flask import g
    import time
    
    # UptimeRobotからのアクセスの場合、ユーザーを作成しない
    if is_uptimerobot_request():
        g.user = None
        return
    
    # モバイルアクセス時の詳細ログ
    if is_mobile_device():
        app.logger.info(f"Mobile before_request: {request.method} {request.path}")
        app.logger.info(f"Session data: {dict(session)}")
    
    user_id = session.get('user_id')

    if user_id is not None:
        try:
            user = User.query.get(user_id)
            if user:
                g.user = user
                session['username'] = user.username
                return
            else:
                session.clear()
                user_id = None
        except SQLAlchemyError as e:
            app.logger.error(f"Error loading user {user_id}: {e}")
            session.clear()
            user_id = None

    if user_id is None:
        # モバイルデバイスの場合、より慎重にユーザー作成
        max_retries = 3 if is_mobile_device() else 1
        
        for attempt in range(max_retries):
            try:
                # 一意なユーザー名を生成（より確実な方法）
                base_username = generate_random_username()
                timestamp = int(time.time() * 1000) % 10000
                username = f"{base_username} {timestamp}"
                
                # より厳密な重複チェック
                retry_count = 0
                while User.query.filter_by(username=username).first() and retry_count < 5:
                    timestamp = int(time.time() * 1000) % 10000
                    username = f"{base_username} {timestamp}"
                    retry_count += 1
                
                new_user = User(
                    username=username,
                    gender=None
                )
                db.session.add(new_user)
                db.session.commit()
                
                session['user_id'] = new_user.id
                session['username'] = username
                g.user = new_user
                
                app.logger.info(f"New user created: {new_user.id} ({username}) - Attempt {attempt + 1}")
                return
                
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.warning(f"User creation attempt {attempt + 1} failed: {e}")
                
                if attempt == max_retries - 1:
                    # 最後の試行でも失敗した場合
                    app.logger.error(f"Failed to create user after {max_retries} attempts: {e}")
                    g.user = None
                    if not is_mobile_device():  # モバイルではフラッシュメッセージを控えめに
                        flash('ユーザー情報の作成に失敗しました。ページを更新してお試しください。', 'error')
                else:
                    # 短時間待機してリトライ
                    time.sleep(0.1 * (attempt + 1))


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



def validate_text_length(text, max_length, field_name):
    """テキストの長さを検証する"""
    if len(text) > max_length:
        return f"{field_name}は{max_length}文字以内で入力してください。"
    return None


def validate_required_fields(**kwargs):
    """必須フィールドの検証"""
    missing_fields = []
    for field_name, value in kwargs.items():
        if not value or (isinstance(value, str) and not value.strip()):
            missing_fields.append(field_name)
    
    if missing_fields:
        return f"以下の項目は必須です: {', '.join(missing_fields)}"
    return None

# --- ルーティング ---
@app.route('/')
def index():
    # モバイルデバッグ用ログ
    log_request_details()
    
    current_user_id = session.get('user_id')

    try:
        posts_query = db.session.query(
            Post.id,
            Post.user_id,
            User.username,
            Post.image_path,
            Post.caption,
            Post.price_range,
            Post.area,
            Post.store_name,
            Post.school,
            Post.created_at,
            func.count(Like.id).label('like_count')
        ).join(User, Post.user_id == User.id) \
         .outerjoin(Like, Post.id == Like.post_id) \
         .group_by(Post.id, User.username) \
         .order_by(desc(Post.created_at)) \
         .all()

        liked_posts_ids = set()
        if current_user_id:
            likes_by_current_user = Like.query.filter_by(user_id=current_user_id).all()
            liked_posts_ids = {like.post_id for like in likes_by_current_user}

        return render_template('index.html', posts=posts_query, liked_posts=liked_posts_ids)
    except SQLAlchemyError as e:
        app.logger.error(f"Database error in index: {e} - User Agent: {request.headers.get('User-Agent', 'Unknown')}")
        error_message = 'データの取得中にエラーが発生しました。'
        if is_mobile_device():
            error_message = 'データの読み込みに失敗しました。ネットワーク接続を確認して再読み込みしてください。'
        flash(error_message, 'error')
        return render_template('index.html', posts=[], liked_posts=set())





@app.route('/post', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def post():
    if not g.user:
        flash('ユーザー情報が取得できません。ページを更新してお試しください。', 'error')
        return redirect(url_for('index'))
    
    user_id = g.user.id
    username = g.user.username
    price_options = ["〜500円", "〜1000円", "〜2000円", "5000円以上"]
    school_options = get_sorted_schools()

    if request.method == 'POST':
        image = request.files.get('image')
        caption = html.escape(request.form.get('caption', '').strip())
        price_range = request.form.get('price_range')
        area = html.escape(request.form.get('area', '').strip())
        store_name = html.escape(request.form.get('store_name', '').strip())
        school = request.form.get('school', '').strip()

        # バリデーション（必須フィールド）
        validation_error = validate_required_fields(
            画像=image and image.filename,
            価格帯=price_range,
            地域=area,
            店名=store_name
        )
        
        if validation_error:
            flash(validation_error, 'error')
            return render_template('post.html', price_options=price_options, school_options=school_options, username=username,
                                 store_name=store_name, area=area, caption=caption, price_range_selected=price_range, 
                                 school_selected=school)

        # 文字数制限チェック
        store_name_error = validate_text_length(store_name, 50, '店名')
        caption_error = validate_text_length(caption, 500, '紹介文')
        
        if store_name_error:
            flash(store_name_error, 'error')
        if caption_error:
            flash(caption_error, 'error')
            
        if store_name_error or caption_error:
            return render_template('post.html', price_options=price_options, school_options=school_options, username=username,
                                 store_name=store_name, area=area, caption=caption, price_range_selected=price_range,
                                 school_selected=school)

        # ファイル形式チェック
        if not allowed_file(image.filename):
            flash('許可されていないファイル形式です。JPEG、PNG形式の画像をアップロードしてください。', 'error')
            return render_template('post.html', price_options=price_options, school_options=school_options, username=username,
                                 store_name=store_name, area=area, caption=caption, price_range_selected=price_range,
                                 school_selected=school)

        # Supabase Storageにファイルアップロード
        safe_filename = secure_filename(image.filename)
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{safe_filename}"
        
        # 画像をSupabaseにアップロード
        public_url, upload_error = upload_image_to_supabase(image, filename)
        
        if upload_error:
            flash(upload_error, 'error')
            return render_template('post.html', price_options=price_options, school_options=school_options, username=username,
                                 store_name=store_name, area=area, caption=caption, price_range_selected=price_range,
                                 school_selected=school)
        
        try:
            new_post = Post(
                user_id=user_id,
                image_path=public_url,  # Supabaseの公開URLを保存
                caption=caption,
                price_range=price_range,
                area=area,
                store_name=store_name,
                school=school if school else None
            )
            
            db.session.add(new_post)
            db.session.commit()
            
            flash('投稿が完了しました！', 'success')
            return redirect(url_for('index'))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            # アップロード済みの画像を削除（修正版）
            if public_url:
                delete_success = delete_image_from_supabase(public_url)
                if delete_success:
                    print(f"Successfully cleaned up uploaded image after database error: {public_url}")
                else:
                    print(f"Failed to clean up uploaded image after database error: {public_url}")
            print(f"Database error in post: {e}")
            flash('データベースエラーが発生しました。もう一度お試しください。', 'error')
        except Exception as e:
            db.session.rollback()
            # アップロード済みの画像を削除（修正版）
            if public_url:
                delete_success = delete_image_from_supabase(public_url)
                if delete_success:
                    print(f"Successfully cleaned up uploaded image after unexpected error: {public_url}")
                else:
                    print(f"Failed to clean up uploaded image after unexpected error: {public_url}")
            print(f"Unexpected error in post: {e}")
            flash('投稿の保存中にエラーが発生しました。もう一度お試しください。', 'error')

    return render_template('post.html', price_options=price_options, school_options=school_options, username=username,
                           store_name="", area="", caption="", price_range_selected="", school_selected="")

@app.route('/search', methods=['GET', 'POST'])
def search():
    user_id = session.get('user_id')
    results = []
    search_criteria = {}
    price_options = ["", "〜500円", "〜1000円", "〜2000円", "5000円以上"]
    school_options = [""] + get_sorted_schools()
    
    if request.method == 'POST':
        area_query = request.form.get('area', '').strip()
        store_name_query = request.form.get('store_name', '').strip()
        price_range_query = request.form.get('price_range', '')
        school_query = request.form.get('school', '')

        search_criteria = {
            'area': area_query,
            'store_name': store_name_query,
            'price_range': price_range_query,
            'school': school_query
        }

        try:
            query = db.session.query(
                Post.id,
                Post.user_id,
                User.username,
                Post.image_path,
                Post.caption,
                Post.price_range,
                Post.area,
                Post.store_name,
                Post.school,
                Post.created_at,
                func.count(Like.id).label('like_count')
            ).join(User, Post.user_id == User.id) \
             .outerjoin(Like, Post.id == Like.post_id)

            if area_query:
                query = query.filter(Post.area.like(f"%{area_query}%"))
            if store_name_query:
                query = query.filter(Post.store_name.like(f"%{store_name_query}%"))
            if price_range_query:
                query = query.filter(Post.price_range == price_range_query)
            if school_query:
                query = query.filter(Post.school == school_query)

            results = query.group_by(Post.id, User.username).order_by(desc(Post.created_at)).all()
            
        except SQLAlchemyError as e:
            app.logger.error(f"Database error in search: {e} - User Agent: {request.headers.get('User-Agent', 'Unknown')}")
            error_message = '検索中にエラーが発生しました。'
            if is_mobile_device():
                error_message = '検索に失敗しました。ネットワーク接続を確認して再試行してください。'
            flash(error_message, 'error')

    liked_posts_ids = set()
    if user_id and results:
        likes_by_current_user = Like.query.filter_by(user_id=user_id).all()
        liked_posts_ids = {like.post_id for like in likes_by_current_user}

    return render_template('search.html', results=results, price_options=price_options, 
                         school_options=school_options, search_criteria=search_criteria, 
                         user_id=user_id, liked_posts=liked_posts_ids)


@app.route('/account')
def account():
    user_id = session.get('user_id')
    username = session.get('username')
    if not user_id:
        flash('ユーザー情報の取得に失敗しました。', 'error')
        return redirect(url_for('index'))
        
    is_admin = session.get('is_admin', False)
    
    try:
        posts_query = db.session.query(
            Post.id,
            Post.user_id,
            User.username.label('username'),
            Post.image_path,
            Post.caption,
            Post.price_range,
            Post.area,
            Post.store_name,
            Post.school,
            Post.created_at,
            func.count(Like.id).label('like_count')
        ).join(User, Post.user_id == User.id) \
         .outerjoin(Like, Post.id == Like.post_id) \
         .filter(Post.user_id == user_id) \
         .group_by(Post.id, User.username) \
         .order_by(desc(Post.created_at)) \
         .all()
        
        return render_template('account.html', posts=posts_query, username=username, is_admin=is_admin)
    except SQLAlchemyError as e:
        app.logger.error(f"Database error in account: {e} - User Agent: {request.headers.get('User-Agent', 'Unknown')}")
        error_message = 'アカウント情報の取得中にエラーが発生しました。'
        if is_mobile_device():
            error_message = 'アカウント情報の読み込みに失敗しました。ネットワーク接続を確認してください。'
        flash(error_message, 'error')
        return render_template('account.html', posts=[], username=username, is_admin=is_admin)

@app.route('/admin_login', methods=['POST'])
def admin_login():
    password = request.form.get('admin_password', '').strip()
    
    if not password:
        flash('パスワードを入力してください。', 'error')
        return redirect(url_for('account'))
    
    # 環境変数から管理者パスワードを取得
    admin_password_hash = os.environ.get('ADMIN_PASSWORD_HASH')
    ad_password_hash = os.environ.get('AD_PASSWORD_HASH')
    
    # パスワード検証
    is_admin_password = check_password_hash(admin_password_hash, password) if admin_password_hash else False
    is_ad_password = check_password_hash(ad_password_hash, password) if ad_password_hash else False
    
    if is_admin_password or is_ad_password:
        try:
            current_user_id = session.get('user_id')
            
            if is_ad_password:
                # 広告パスワードでログイン：固有の広告アカウント（ID=1）にログイン
                if current_user_id != 1:
                    # 前のアカウント情報を保存
                    session['previous_user_id'] = current_user_id
                    session['previous_username'] = session.get('username')
                    session['previous_is_admin'] = session.get('is_admin', False)
                    session['previous_is_advertiser'] = session.get('is_advertiser', False)
                
                # 広告アカウント（ID=1）にログイン
                ad_account = User.query.get(1)
                if ad_account:
                    session['user_id'] = 1
                    session['username'] = ad_account.username
                    session['is_admin'] = True
                    session['is_advertiser'] = True
                    g.user = ad_account
                    flash('広告アカウントにログインしました。', 'success')
                else:
                    flash('広告アカウントが見つかりません。', 'error')
            else:
                # 管理者パスワードでログイン：現在のアカウントに管理者権限のみ付与
                user = User.query.get(current_user_id)
                if user:
                    user.is_admin = True
                    user.is_advertiser = False
                    db.session.commit()
                    session['is_admin'] = True
                    session['is_advertiser'] = False
                    flash('管理者権限が付与されました。', 'success')
            
        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"Error in admin login: {e}")
            flash('ログイン処理中にエラーが発生しました。', 'error')
    else:
        flash('パスワードが間違っています。', 'error')
    
    return redirect(url_for('account'))

@app.route('/update_admin_username', methods=['POST'])
def update_admin_username():
    if not session.get('is_admin'):
        flash('管理者権限が必要です。', 'error')
        return redirect(url_for('account'))
    
    new_username = html.escape(request.form.get('new_username', '').strip())
    
    # バリデーション
    if not new_username:
        flash('ユーザー名を入力してください。', 'error')
        return redirect(url_for('account'))
    
    username_error = validate_text_length(new_username, 50, 'ユーザー名')
    if username_error:
        flash(username_error, 'error')
        return redirect(url_for('account'))
    
    try:
        user_id = session.get('user_id')
        
        # 既存の同じユーザー名がないかチェック（自分以外で）
        existing_user = User.query.filter(User.username == new_username, User.id != user_id).first()
        if existing_user:
            flash('そのユーザー名は既に使用されています。', 'error')
            return redirect(url_for('account'))
        
        user = User.query.get(user_id)
        if user:
            user.username = new_username
            db.session.commit()
            session['username'] = new_username
            flash('ユーザー名を更新しました。', 'success')
        else:
            flash('ユーザーが見つかりません。', 'error')
            
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Error updating username: {e}")
        flash('ユーザー名の更新に失敗しました。', 'error')
    
    return redirect(url_for('account'))

@app.route('/privileged_logout', methods=['POST'])
def privileged_logout():
    """管理者・広告アカウントからのログアウト"""
    if not session.get('is_admin'):
        flash('管理者権限が必要です。', 'error')
        return redirect(url_for('account'))
    
    try:
        current_user_id = session.get('user_id')
        
        if current_user_id == 1 and session.get('is_advertiser'):
            # 広告アカウントからのログアウト：前のアカウントに戻る
            previous_user_id = session.get('previous_user_id')
            if previous_user_id:
                # 前のアカウント情報を復元
                previous_user = User.query.get(previous_user_id)
                if previous_user:
                    session['user_id'] = previous_user_id
                    session['username'] = previous_user.username
                    session['is_admin'] = session.get('previous_is_admin', False)
                    session['is_advertiser'] = session.get('previous_is_advertiser', False)
                    g.user = previous_user
                    
                    # 前のアカウント情報をクリア
                    session.pop('previous_user_id', None)
                    session.pop('previous_username', None)
                    session.pop('previous_is_admin', None)
                    session.pop('previous_is_advertiser', None)
                    
                    flash('前のアカウントに戻りました。', 'success')
                else:
                    flash('前のアカウント情報が見つかりません。', 'error')
            else:
                flash('前のアカウント情報がありません。', 'error')
        else:
            # 通常の管理者権限からのログアウト
            user = User.query.get(current_user_id)
            if user:
                user.is_admin = False
                user.is_advertiser = False
                db.session.commit()
            
            session['is_admin'] = False
            session['is_advertiser'] = False
            
            flash('管理者権限からログアウトしました。', 'success')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Error in privileged_logout: {e}")
        flash('ログアウト処理中にエラーが発生しました。', 'error')
    
    return redirect(url_for('account'))
    
    return redirect(url_for('account'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('管理者権限が必要です。', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin_delete_post/<int:post_id>', methods=['POST'])
def admin_delete_post(post_id):
    if not session.get('is_admin'):
        flash('管理者権限が必要です。', 'error')
        return redirect(request.referrer or url_for('index'))

    try:
        post = Post.query.get(post_id)
        if post:
            # 画像パスを保存（削除前に）
            image_path = post.image_path
            
            # 関連するいいねを削除
            Like.query.filter_by(post_id=post_id).delete()
            # 投稿を削除
            db.session.delete(post)
            db.session.commit()
            
            # 画像ファイルも削除（修正版）
            if image_path:
                delete_success = delete_image_from_supabase(image_path)
                if delete_success:
                    print(f"Successfully deleted image file: {image_path}")
                else:
                    print(f"Failed to delete image file: {image_path}")
                    # 画像削除失敗はログに記録するが、ユーザーエラーにはしない
                    # （投稿データの削除は成功しているため）
            
            flash('投稿を削除しました。', 'success')
        else:
            flash('投稿が存在しません。', 'error')
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Error deleting post: {e}")
        flash('投稿の削除中にエラーが発生しました。', 'error')
    
    return redirect(request.referrer or url_for('index'))

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    user_id = session.get('user_id')
    if not user_id:
        flash('ユーザー情報の取得に失敗しました。', 'error')
        return redirect(url_for('account'))
    
    try:
        post = Post.query.filter_by(id=post_id, user_id=user_id).first()
        if not post:
            flash('削除権限がないか、投稿が存在しません。', 'error')
            return redirect(url_for('account'))
        
        # 画像パスを保存（削除前に）
        image_path = post.image_path
        
        # 関連するいいねを削除
        Like.query.filter_by(post_id=post_id).delete()
        
        # 投稿を削除
        db.session.delete(post)
        db.session.commit()
        
        # 画像ファイルの削除（修正版）
        if image_path:
            delete_success = delete_image_from_supabase(image_path)
            if delete_success:
                print(f"Successfully deleted image file: {image_path}")
            else:
                print(f"Failed to delete image file: {image_path}")
                # 画像削除失敗はログに記録するが、ユーザーエラーにはしない
                # （投稿データの削除は成功しているため）
        
        flash('投稿を削除しました。', 'success')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Database error in delete_post: {e}")
        flash('投稿の削除中にデータベースエラーが発生しました。', 'error')
    
    return redirect(url_for('account'))
    

@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'ユーザー情報がありません。ページを更新してください。'}), 401
        flash('ユーザー情報がありません。', 'error')
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    
    try:
        post = Post.query.get(post_id)
        if not post:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': '投稿が存在しません。'}), 404
            flash('投稿が存在しません。', 'error')
            return redirect(request.referrer or url_for('index'))
        
        existing_like = Like.query.filter_by(post_id=post_id, user_id=user_id).first()

        if existing_like:
            db.session.delete(existing_like)
            message_for_flash = 'いいねを取り消しました。'
            is_now_liked = False
        else:
            new_like = Like(post_id=post_id, user_id=user_id)
            db.session.add(new_like)
            message_for_flash = 'いいねしました！'
            is_now_liked = True

        db.session.commit()
        
        like_count = Like.query.filter_by(post_id=post_id).count()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'ok',
                'message': message_for_flash,
                'like_count': like_count,
                'is_liked': is_now_liked
            })
        else:
            flash(message_for_flash, 'success' if is_now_liked else 'info')

    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Error in like_post: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': '処理中にエラーが発生しました。'}), 500
        flash('エラーが発生しました。もう一度お試しください。', 'error')

    return redirect(request.referrer or url_for('index'))

@app.route('/ranking')
def ranking():
    ranking_type = request.args.get('type', 'overall')  # 'overall' or 'school'
    selected_school = request.args.get('school', '')
    is_admin = session.get('is_admin', False)
    user_id = session.get('user_id')
    
    try:
        # 高校リストを取得（投稿があるもののみ）
        schools_with_posts = db.session.query(
            Post.school,
            func.count(Post.id).label('post_count')
        ).filter(
            Post.school.isnot(None),
            Post.school != ''
        ).group_by(Post.school) \
         .order_by(desc('post_count')) \
         .all()

        if ranking_type == 'school' and selected_school:
            posts = db.session.query(
                Post.id,
                Post.user_id,
                User.username,
                Post.image_path,
                Post.caption,
                Post.price_range,
                Post.area,
                Post.store_name,
                Post.school,
                Post.created_at,
                func.count(Like.id).label('like_count')
            ).join(User, Post.user_id == User.id) \
             .outerjoin(Like, Post.id == Like.post_id) \
             .filter(Post.school == selected_school) \
             .group_by(Post.id, User.username) \
             .order_by(desc('like_count'), desc(Post.created_at)) \
             .limit(20).all()
            page_title = f"🏆 {selected_school} ランキング"
        else:
            posts = db.session.query(
                Post.id,
                Post.user_id,
                User.username,
                Post.image_path,
                Post.caption,
                Post.price_range,
                Post.area,
                Post.store_name,
                Post.school,
                Post.created_at,
                func.count(Like.id).label('like_count')
            ).join(User, Post.user_id == User.id) \
             .outerjoin(Like, Post.id == Like.post_id) \
             .group_by(Post.id, User.username) \
             .order_by(desc('like_count'), desc(Post.created_at)) \
             .limit(20).all()
            page_title = "🏆 総合ランキング"
        
        # いいねした投稿のIDを取得
        liked_posts_ids = set()
        if user_id:
            likes_by_current_user = Like.query.filter_by(user_id=user_id).all()
            liked_posts_ids = {like.post_id for like in likes_by_current_user}

        return render_template('ranking.html', 
                             posts=posts, 
                             liked_posts=liked_posts_ids, 
                             is_admin=is_admin,
                             ranking_type=ranking_type,
                             selected_school=selected_school,
                             schools_with_posts=schools_with_posts,
                             page_title=page_title)
    except SQLAlchemyError as e:
        app.logger.error(f"Database error in ranking: {e} - User Agent: {request.headers.get('User-Agent', 'Unknown')}")
        error_message = 'ランキングの取得中にエラーが発生しました。'
        if is_mobile_device():
            error_message = 'ランキング情報の読み込みに失敗しました。ネットワーク接続を確認してください。'
        flash(error_message, 'error')
        return render_template('ranking.html', 
                             posts=[], 
                             liked_posts=set(), 
                             is_admin=is_admin,
                             ranking_type=ranking_type,
                             selected_school=selected_school,
                             schools_with_posts=[],
                             page_title="🏆 ランキング")


@app.route('/advertisements')
def advertisements():
    is_admin = session.get('is_admin', False)
    user_id = session.get('user_id')
    
    try:
        posts = db.session.query(
            Post.id,
            Post.user_id,
            User.username,
            Post.image_path,
            Post.caption,
            Post.price_range,
            Post.area,
            Post.store_name,
            Post.school,
            Post.created_at,
            func.count(Like.id).label('like_count')
        ).join(User, Post.user_id == User.id) \
         .outerjoin(Like, Post.id == Like.post_id) \
         .filter(Post.user_id == 1) \
         .group_by(Post.id, User.username) \
         .order_by(desc(Post.created_at)) \
         .all()
        
        # いいねした投稿のIDを取得
        liked_posts_ids = set()
        if user_id:
            likes_by_current_user = Like.query.filter_by(user_id=user_id).all()
            liked_posts_ids = {like.post_id for like in likes_by_current_user}

        return render_template('advertisements.html', 
                             posts=posts, 
                             liked_posts=liked_posts_ids, 
                             is_admin=is_admin)
    except SQLAlchemyError as e:
        app.logger.error(f"Database error in advertisements: {e} - User Agent: {request.headers.get('User-Agent', 'Unknown')}")
        error_message = '広告一覧の取得中にエラーが発生しました。'
        if is_mobile_device():
            error_message = '広告情報の読み込みに失敗しました。ネットワーク接続を確認してください。'
        flash(error_message, 'error')
        return render_template('advertisements.html', 
                             posts=[], 
                             liked_posts=set(), 
                             is_admin=is_admin)


def sanitize_input(text, max_length=None):
    """入力値のサニタイズ"""
    if not isinstance(text, str):
        return ""
    
    # HTMLタグの除去
    import html
    text = html.escape(text.strip())
    
    if max_length:
        text = text[:max_length]
    
    return text

def backup_database():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"database_backup_{timestamp}.db"
    shutil.copy2(DATABASE, f"backups/{backup_name}")

if not app.debug and os.environ.get('FLASK_ENV') == 'production':
    csp = {
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline'",
        'style-src': "'self' 'unsafe-inline' fonts.googleapis.com",
        'font-src': "'self' fonts.gstatic.com",
        'img-src': "'self' data: *.supabase.co",
    }
    Talisman(app, force_https=True, content_security_policy=csp)


# 環境に応じたセッション設定
if app.debug or os.environ.get('FLASK_ENV') != 'production':
    # 開発環境
    app.config['SESSION_COOKIE_SECURE'] = False  # HTTPでも動作
else:
    # 本番環境
    app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS必須


app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# セッションクッキーの有効期限を延長（ブラウザが削除されるまで保持）
app.config['SESSION_COOKIE_MAX_AGE'] = None  # ブラウザセッション終了まで保持
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)  # セッション有効期限を10年に延長

# セッションを永続化する設定
@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/robots.txt')
def robots():
    return app.send_static_file('robots.txt')

@app.route('/uptimerobot')
def uptimerobot_check():
    """UptimeRobot専用の軽量チェック"""
    try:
        db.session.execute(text('SELECT 1'))
        return 'OK', 200
    except Exception:
        return 'ERROR', 500

@app.route('/health')
def health_check():
    """ヘルスチェック用"""
    try:
        db.session.execute(text('SELECT 1'))
        return 'OK', 200
    except Exception:
        return 'ERROR', 500

@app.route('/mobile-debug')
def mobile_debug():
    """モバイル接続問題調査用エンドポイント"""
    user_agent = request.headers.get('User-Agent', 'Unknown')
    is_mobile = is_mobile_device()
    
    debug_info = {
        'user_agent': user_agent,
        'is_mobile': is_mobile,
        'headers': dict(request.headers),
        'session_id': session.get('user_id', 'None'),
        'csrf_token': generate_csrf(),
        'request_method': request.method,
        'remote_addr': request.remote_addr,
        'path': request.path
    }
    
    app.logger.info(f"Mobile Debug Request: {debug_info}")
    return jsonify(debug_info)

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)