import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # SECRET_KEY: in Produktion MUSS diese Env-Variable gesetzt sein
    _secret_key = os.environ.get("SECRET_KEY")
    _is_prod = os.environ.get("APP_URL", "http://localhost:5000").startswith("https://")
    if not _secret_key and _is_prod:
        raise RuntimeError(
            "SECRET_KEY Umgebungsvariable ist nicht gesetzt! "
            "Die Anwendung kann in Produktion nicht ohne sicheren SECRET_KEY starten."
        )
    SECRET_KEY = _secret_key or "dev-only-insecure-key-do-not-use-in-production"

    _db_url = os.environ.get("DATABASE_URL", "postgresql://localhost/bewerbercheck")

    # ── Sichere Cookie-Einstellungen ──────────────────────────────
    _is_production = _is_prod  # Alias (bereits oben definiert)
    SESSION_COOKIE_SECURE = _is_production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = _is_production
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=30)  # Statt Standard 365 Tage
    PREFERRED_URL_SCHEME = "https" if _is_production else "http"

    # ── Request-Größe begrenzen (DoS-Schutz für Datei-Uploads) ───
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB
    # Railway sometimes provides postgres:// (legacy) — SQLAlchemy requires postgresql://
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mailgun
    MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")
    MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN", "systemautomatik.com")
    MAILGUN_API_BASE = os.environ.get("MAILGUN_API_BASE", "https://api.eu.mailgun.net/v3")
    MAILGUN_WEBHOOK_SIGNING_KEY = os.environ.get("MAILGUN_WEBHOOK_SIGNING_KEY")

    # Anthropic
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

    # Stripe
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY")
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
    STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")  # monthly subscription price

    # Google Sheets
    GOOGLE_SERVICE_ACCOUNT_EMAIL = os.environ.get("GOOGLE_SERVICE_ACCOUNT_EMAIL")
    GOOGLE_SERVICE_ACCOUNT_KEY_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY_JSON")

    # Flask-Mail (for password reset)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.mailgun.org")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@systemautomatik.com")

    # App URL (for Stripe redirects)
    APP_URL = os.environ.get("APP_URL", "http://localhost:5000")

    # Admin diagnostic key (protects /admin/mailgun-diagnose)
    ADMIN_DIAGNOSE_KEY = os.environ.get("ADMIN_DIAGNOSE_KEY")

    # Analytics (DSGVO-konform, kein Cookie-Consent nötig)
    PLAUSIBLE_DOMAIN = os.environ.get("PLAUSIBLE_DOMAIN")
