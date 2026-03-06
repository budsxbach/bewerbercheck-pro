import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://localhost/bewerbercheck")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mailgun
    MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")
    MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN", "bewerbungswandler.de")
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
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@bewerbungswandler.de")

    # App URL (for Stripe redirects)
    APP_URL = os.environ.get("APP_URL", "http://localhost:5000")
