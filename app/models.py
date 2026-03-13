from datetime import datetime, timedelta, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

TESTPHASE_TAGE = 0

db = SQLAlchemy()


def _utcnow():
    """UTC-Zeitstempel ohne Deprecation-Warning (Python 3.12+), naive Datetime für DB-Kompatibilität."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    passwort_hash = db.Column(db.String(255), nullable=False)
    stripe_customer_id = db.Column(db.String(100), unique=True)
    stripe_subscription_id = db.Column(db.String(100), unique=True)
    abo_aktiv = db.Column(db.Boolean, default=False, nullable=False)
    testphase_aktiv = db.Column(db.Boolean, default=True, nullable=False)
    testphase_enddatum = db.Column(db.DateTime)
    erstellt_am = db.Column(db.DateTime, default=_utcnow)
    reset_token = db.Column(db.String(255))
    reset_token_ablauf = db.Column(db.DateTime)
    abo_start_datum = db.Column(db.DateTime, nullable=True)

    settings = db.relationship("CustomerSettings", backref="user", uselist=False, cascade="all, delete-orphan")
    applications = db.relationship("Application", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, passwort):
        self.passwort_hash = generate_password_hash(passwort)

    def check_password(self, passwort):
        return check_password_hash(self.passwort_hash, passwort)

    @property
    def hat_zugang(self):
        """Prüft ob Nutzer aktiven Zugang hat (Abo oder gültige Testphase)."""
        if self.abo_aktiv:
            return True
        if self.testphase_aktiv and self.testphase_enddatum:
            return _utcnow() < self.testphase_enddatum
        return False

    @property
    def geld_zurueck_berechtigt(self):
        """True wenn erste Zahlung < 7 Tage her und Abo aktiv."""
        if not self.abo_aktiv or not self.abo_start_datum:
            return False
        delta = _utcnow() - self.abo_start_datum
        return delta.days < 7

    @property
    def testphase_tage_uebrig(self):
        """Verbleibende Tage der Testphase (0 wenn abgelaufen)."""
        if not self.testphase_enddatum:
            return 0
        delta = self.testphase_enddatum - _utcnow()
        return max(0, delta.days)


class CustomerSettings(db.Model):
    __tablename__ = "customer_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    eigene_email = db.Column(db.String(255), unique=True)  # firma-abc123@systemautomatik.com
    email_token = db.Column(db.String(20), unique=True)    # abc123 Teil der E-Mail
    sheets_url = db.Column(db.Text)
    stellenbeschreibung = db.Column(db.Text)
    bewertungskriterien = db.Column(db.Text)
    email_benachrichtigung = db.Column(db.Boolean, default=True, nullable=False)
    aktualisiert_am = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    bewerber_name = db.Column(db.String(255))
    bewerber_email = db.Column(db.String(255))
    telefon = db.Column(db.String(50))
    skills = db.Column(db.Text)               # Komma-getrennte Skills
    berufserfahrung_jahre = db.Column(db.Float)
    ausbildung = db.Column(db.Text)
    sprachen = db.Column(db.Text)
    score = db.Column(db.Integer)             # 1–10
    score_begruendung = db.Column(db.Text)
    original_email_text = db.Column(db.Text)
    uebersetzter_text = db.Column(db.Text)    # Ins Deutsche übersetzter Volltext
    eingegangen_am = db.Column(db.DateTime, default=_utcnow, index=True)
    verarbeitet = db.Column(db.Boolean, default=False)
    sheets_geschrieben = db.Column(db.Boolean, default=False)
    fehler = db.Column(db.Text)               # Falls KI-Verarbeitung fehlschlug
    mailgun_message_id = db.Column(db.String(255), unique=True, index=True)  # Deduplizierung
