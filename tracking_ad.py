from flask import Blueprint, render_template, redirect, url_for, current_app, abort, session, Response, request
from urllib.parse import quote, urlparse
import io, csv, hmac, hashlib
from datetime import datetime
from models import db, Post, User

tracking_ad_bp = Blueprint("tracking_ad", __name__, template_folder="templates")

# --- 計測テーブル ---
class MapClick(db.Model):
    __tablename__ = "map_clicks"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class CouponEvent(db.Model):
    __tablename__ = "coupon_events"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    code = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

# --- 権限ヘルパ ---
def is_admin() -> bool:
    return bool(session.get("is_admin"))

def current_user_id():
    return session.get("user_id")

def is_advertiser_account() -> bool:
    return current_user_id() == current_app.config.get("ADVERTISER_USER_ID", 1)

def has_export_rights() -> bool:
    # CSVは 管理者 or 広告アカウント(ID=1)
    return is_admin() or is_advertiser_account()

def is_ad_post(post: "Post") -> bool:
    # 広告投稿: 投稿者ID=1 または MapsURLあり
    adv_id = current_app.config.get("ADVERTISER_USER_ID", 1)
    return (post.user_id == adv_id) or bool(post.google_maps_url)

# --- 補助 ---
def _coupon_code(post: "Post") -> str:
    secret = (current_app.config.get("COUPON_SECRET") or "dev-secret").encode()
    msg = f"{post.store_name}|{post.id}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()[:8].upper()

def _maps_url(post: "Post") -> str:
    # 許可ドメインのMapsURLを優先、無ければ検索URL
    if post.google_maps_url:
        u = urlparse(post.google_maps_url)
        print(f"DEBUG: Parsed URL - scheme: {u.scheme}, netloc: {u.netloc}")
        # より緩い許可ドメインチェック
        allowed_domains = {
            "www.google.com", "google.com", "maps.google.com", 
            "maps.app.goo.gl", "goo.gl"
        }
        if u.scheme in {"http", "https"} and u.netloc in allowed_domains:
            print(f"DEBUG: Using custom Maps URL: {post.google_maps_url}")
            return post.google_maps_url
        else:
            print(f"DEBUG: Domain {u.netloc} not in allowed list, falling back to search")
    
    q = f"{post.store_name} {post.area or ''}".strip()
    search_url = f"https://www.google.com/maps/search/?api=1&query={quote(q)}"
    print(f"DEBUG: Using search URL: {search_url}")
    return search_url

def admin_required():
    if not has_export_rights():
        abort(403)

# --- ルート（広告投稿のみ計測） ---
@tracking_ad_bp.route("/go/<int:post_id>")
def go(post_id: int):
    post = Post.query.get_or_404(post_id)
    print(f"DEBUG: Processing post ID {post_id}, store: {post.store_name}, area: {post.area}")
    print(f"DEBUG: google_maps_url: {post.google_maps_url}")
    print(f"DEBUG: is_ad_post: {is_ad_post(post)}")
    
    if is_ad_post(post):
        try:
            db.session.add(MapClick(post_id=post.id))
            db.session.commit()
            print("DEBUG: MapClick recorded successfully")
        except Exception as e:
            # テーブルが存在しない場合もリダイレクトは継続
            print(f"MapClick tracking error: {e}")
            db.session.rollback()
    
    target_url = _maps_url(post)
    print(f"DEBUG: Redirecting to: {target_url}")
    return redirect(target_url, code=302)

@tracking_ad_bp.route("/coupon/<int:post_id>")
def coupon(post_id: int):
    post = Post.query.get_or_404(post_id)
    if not is_ad_post(post):
        abort(404)
    code = _coupon_code(post)
    try:
        db.session.add(CouponEvent(post_id=post.id, code=code))
        db.session.commit()
    except Exception as e:
        # テーブルが存在しない場合もクーポンは表示
        print(f"CouponEvent tracking error: {e}")
        db.session.rollback()
    return render_template("coupon.html", post=post, code=code)

# --- 管理：投稿編集（全投稿編集可） ---
@tracking_ad_bp.route("/admin/posts")
def admin_posts():
    admin_required()
    posts = Post.query.order_by(Post.created_at.desc()).limit(200).all()
    return render_template("admin_posts.html", posts=posts)

@tracking_ad_bp.route("/admin/posts/<int:post_id>/edit", methods=["GET","POST"])
def admin_edit_post(post_id: int):
    admin_required()
    post = Post.query.get_or_404(post_id)
    if request.method == "POST":
        for field in ["store_name","area","caption","price_range","school"]:
            if field in request.form:
                setattr(post, field, request.form[field])
        gmaps = (request.form.get("google_maps_url") or "").strip() or None
        if gmaps:
            u = urlparse(gmaps)
            if u.scheme in {"http","https"} and u.netloc in {"www.google.com","google.com","maps.app.goo.gl","maps.google.com"}:
                post.google_maps_url = gmaps[:300]
        else:
            post.google_maps_url = None
        db.session.commit()
        return redirect(url_for("tracking_ad.admin_posts"))
    return render_template("admin_edit_post.html", post=post)

# --- 管理：CSV（管理者 or 広告ID=1） ---
@tracking_ad_bp.route("/admin/export/map_clicks.csv")
def export_map_clicks():
    admin_required()
    q = (
        db.session.query(MapClick.id, MapClick.created_at, MapClick.post_id, Post.store_name, Post.area)
        .join(Post, Post.id==MapClick.post_id)
        .order_by(MapClick.created_at.desc())
    ).all()
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["id","created_at","post_id","store_name","area"])
    for r in q:
        w.writerow([r.id, r.created_at.isoformat(), r.post_id, r.store_name, r.area or ""])
    return Response(buf.getvalue().encode("utf-8-sig"),
                    mimetype="text/csv",
                    headers={"Content-Disposition":'attachment; filename="map_clicks.csv"'})

@tracking_ad_bp.route("/admin/export/coupon_events.csv")
def export_coupon_events():
    admin_required()
    q = (
        db.session.query(CouponEvent.id, CouponEvent.created_at, CouponEvent.post_id, CouponEvent.code, Post.store_name, Post.area)
        .join(Post, Post.id==CouponEvent.post_id)
        .order_by(CouponEvent.created_at.desc())
    ).all()
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["id","created_at","post_id","code","store_name","area"])
    for r in q:
        w.writerow([r.id, r.created_at.isoformat(), r.post_id, r.code, r.store_name, r.area or ""])
    return Response(buf.getvalue().encode("utf-8-sig"),
                    mimetype="text/csv",
                    headers={"Content-Disposition":'attachment; filename="coupon_events.csv"'})

# テーブル作成は手動またはマイグレーションで行ってください