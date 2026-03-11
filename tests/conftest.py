"""
Test-Konfiguration für Bewerbercheck-Pro.
Env-Variablen werden VOR dem ersten Flask-Import gesetzt,
damit config.py die SQLite-URL verwendet.
"""
import os
import pytest

# ─── Testumgebung VOR Flask-Import konfigurieren ────────────────────────────
# Absoluter Pfad notwendig – SQLite schlägt mit relativem Pfad fehl
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_TESTS_DIR, "test_bewerber.db").replace("\\", "/")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_DB_PATH}")
os.environ.setdefault("APP_URL", "http://localhost:5000")
os.environ.setdefault("SECRET_KEY", "test-secret-nur-fuer-tests-niemals-produktion")
os.environ.setdefault("ADMIN_DIAGNOSE_KEY", "test-admin-key-123")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-fake-anthropic-key")
# Leerer Webhook-Key → localhost-Bypass in _verify_mailgun_signature aktiv
os.environ["MAILGUN_WEBHOOK_SIGNING_KEY"] = ""


@pytest.fixture(scope="session")
def app():
    """Flask-App mit SQLite-Testdatenbank (session-scoped, einmalig erstellt)."""
    from app import create_app

    test_app = create_app()
    test_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "KI_LIMIT_TESTPHASE": 0,
    })

    # Rate Limiting deaktivieren: limiter.enabled wird bei init_app() einmalig
    # gesetzt; config-Update allein reicht nicht – Instanz direkt patchen
    from app import limiter
    limiter.enabled = False
    yield test_app

    # Testdatenbank aufräumen (Engine vorher freigeben, sonst Windows-Lock)
    from app.models import db
    with test_app.app_context():
        db.engine.dispose()
    try:
        if os.path.exists(_DB_PATH):
            os.remove(_DB_PATH)
    except PermissionError:
        pass  # Windows-Lock: DB-Datei bleibt, stört nicht


@pytest.fixture()
def client(app):
    """Flask-Testclient."""
    return app.test_client()


@pytest.fixture()
def test_user_id(app):
    """
    Erstellt einen Test-User + CustomerSettings, liefert die user.id.
    Räumt nach dem Test alle zugehörigen Daten auf.
    """
    from app.models import db, User, CustomerSettings, Application
    from datetime import timedelta
    from app.models import _utcnow

    with app.app_context():
        # Vorherigen Test-User bereinigen (falls vorhanden)
        old = User.query.filter_by(email="webhook-test@example.com").first()
        if old:
            Application.query.filter_by(user_id=old.id).delete()
            CustomerSettings.query.filter_by(user_id=old.id).delete()
            db.session.delete(old)
            db.session.commit()

        user = User(
            email="webhook-test@example.com",
            testphase_aktiv=True,
            testphase_enddatum=_utcnow() + timedelta(days=7),
            abo_aktiv=False,
        )
        user.set_password("test123")
        db.session.add(user)
        db.session.flush()

        settings = CustomerSettings(
            user_id=user.id,
            eigene_email="firma-testtoken@systemautomatik.com",
            email_benachrichtigung=False,  # Keine echten E-Mails
        )
        db.session.add(settings)
        db.session.commit()
        uid = user.id

    yield uid

    # Teardown: alles löschen
    with app.app_context():
        Application.query.filter_by(user_id=uid).delete()
        CustomerSettings.query.filter_by(user_id=uid).delete()
        User.query.filter_by(id=uid).delete()
        db.session.commit()
