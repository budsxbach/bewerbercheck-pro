import logging
from flask import Flask, redirect, url_for, jsonify, render_template, request, make_response
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from .models import db, User

mail = Mail()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[], storage_uri="memory://")

logger = logging.getLogger(__name__)


def _add_column_if_missing(db, table, column, col_type):
    """Fügt eine Spalte hinzu, falls sie noch nicht existiert (ALTER TABLE)."""
    try:
        db.session.execute(db.text(
            f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()  # Spalte existiert bereits


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object("config.Config")

    # ProxyFix: Railway sitzt hinter einem Reverse-Proxy → X-Forwarded-Proto vertrauen
    # Ohne das würde request.scheme immer "http" liefern, auch bei HTTPS-Anfragen
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Extensions
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Bitte einloggen um fortzufahren."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints registrieren
    from .auth import auth_bp
    from .dashboard import dashboard_bp
    from .settings import settings_bp
    from .email_webhook import email_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(email_bp)

    # Webhooks von CSRF exemieren (externe Dienste senden keinen Token)
    csrf.exempt(email_bp)

    # Stripe Webhook einzeln exemieren
    from .auth import stripe_webhook as _sw
    csrf.exempt(_sw)

    # Rate Limiting auf kritische Auth-Endpunkte (via shared_limit)
    _auth_limits = {
        "auth.login": "5 per minute",
        "auth.register": "3 per minute",
        "auth.passwort_vergessen": "3 per minute",
    }

    # Dekoriere die View-Funktionen mit Rate Limits
    for endpoint_name, limit_string in _auth_limits.items():
        view_func = app.view_functions.get(endpoint_name)
        if view_func:
            app.view_functions[endpoint_name] = limiter.limit(limit_string)(view_func)

    # ─── HTTPS erzwingen (nur in Produktion) ─────────────────────
    @app.before_request
    def erzwinge_https():
        is_production = app.config.get("APP_URL", "").startswith("https://")
        if is_production and request.headers.get("X-Forwarded-Proto") == "http":
            # GET/HEAD: 301 Permanent Redirect
            # POST/PUT/etc.: 308 Permanent Redirect (Methode + Body bleiben erhalten)
            code = 301 if request.method in ("GET", "HEAD") else 308
            return redirect(request.url.replace("http://", "https://", 1), code=code)

    # ─── Security Headers ────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        is_production = app.config.get("APP_URL", "").startswith("https://")

        # HSTS: Browser merken sich, dass diese Domain nur HTTPS nutzt (1 Jahr)
        if is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Content Security Policy: kontrolliert, was der Browser laden darf
        # unsafe-inline nötig für die Inline-<script>-Blöcke in den Templates
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://plausible.io; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self' https://plausible.io; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

        # Deaktiviert Browser-Features, die die App nicht braucht
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), "
            "usb=(), interest-cohort=()"
        )

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        return response

    # ─── Startseite ──────────────────────────────────────────────
    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("landing"))

    @app.route("/start")
    def landing():
        return render_template("landing.html")

    # ─── Rechtliches ─────────────────────────────────────────────
    @app.route("/impressum")
    def impressum():
        return render_template("impressum.html")

    @app.route("/datenschutz")
    def datenschutz():
        return render_template("datenschutz.html")

    @app.route("/rueckgaberecht")
    def rueckgaberecht():
        return render_template("rueckgaberecht.html")

    # ─── Health-Check (keine Details nach außen) ─────────────────
    @app.route("/health")
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            logger.error(f"Health-Check fehlgeschlagen: {e}")
            return jsonify({"status": "error"}), 500

    # ─── SEO: robots.txt & sitemap.xml ───────────────────────────
    @app.route("/robots.txt")
    def robots_txt():
        content = """User-agent: *
Allow: /
Disallow: /dashboard
Disallow: /einstellungen
Disallow: /webhook/
Disallow: /admin/
Disallow: /abo/

Sitemap: {base}/sitemap.xml
""".format(base=app.config.get("APP_URL", "https://bewerbercheck-pro.systemautomatik.com"))
        response = make_response(content)
        response.headers["Content-Type"] = "text/plain"
        return response

    @app.route("/sitemap.xml")
    def sitemap_xml():
        base = app.config.get("APP_URL", "https://bewerbercheck-pro.systemautomatik.com")
        urls = [
            (f"{base}/start", "weekly", "1.0"),
            (f"{base}/impressum", "monthly", "0.3"),
            (f"{base}/datenschutz", "monthly", "0.3"),
            (f"{base}/rueckgaberecht", "monthly", "0.3"),
            (f"{base}/login", "monthly", "0.5"),
            (f"{base}/register", "monthly", "0.5"),
        ]
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        for loc, freq, prio in urls:
            xml += f"  <url><loc>{loc}</loc><changefreq>{freq}</changefreq><priority>{prio}</priority></url>\n"
        xml += "</urlset>"
        response = make_response(xml)
        response.headers["Content-Type"] = "application/xml"
        return response

    # ─── Custom Error Pages ──────────────────────────────────────
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template("500.html"), 500

    # ─── Datenbankinitialisierung ────────────────────────────────
    with app.app_context():
        db.create_all()

        # Neue Spalten zu bestehenden Tabellen hinzufügen (db.create_all() macht das nicht)
        _add_column_if_missing(db, "users", "testphase_enddatum", "TIMESTAMP")
        _add_column_if_missing(db, "users", "abo_start_datum", "TIMESTAMP")
        _add_column_if_missing(db, "applications", "sheets_geschrieben", "BOOLEAN DEFAULT FALSE")
        _add_column_if_missing(db, "applications", "mailgun_message_id", "VARCHAR(255) UNIQUE")
        _add_column_if_missing(db, "customer_settings", "email_benachrichtigung", "BOOLEAN DEFAULT TRUE")

        # Einmalig: Bestehende User ohne testphase_enddatum bekommen 14 Tage ab erstellt_am
        from datetime import timedelta
        from .models import TESTPHASE_TAGE
        users_ohne_enddatum = User.query.filter(
            User.testphase_aktiv == True,
            User.testphase_enddatum.is_(None),
        ).all()
        for u in users_ohne_enddatum:
            u.testphase_enddatum = u.erstellt_am + timedelta(days=TESTPHASE_TAGE)
        if users_ohne_enddatum:
            db.session.commit()
            app.logger.info(f"Testphase-Enddatum für {len(users_ohne_enddatum)} bestehende User gesetzt.")

    return app
