from flask import Flask, redirect, url_for, jsonify
from flask_login import LoginManager
from flask_mail import Mail

from .models import db, User

mail = Mail()
login_manager = LoginManager()


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

    # Extensions
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
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

    # Startseite
    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("landing"))

    @app.route("/start")
    def landing():
        from flask import render_template
        return render_template("landing.html")

    # Health-Check
    @app.route("/health")
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            return jsonify({"status": "error", "detail": str(e)}), 500

    # Datenbankinitialisierung
    with app.app_context():
        db.create_all()

        # Neue Spalten zu bestehenden Tabellen hinzufügen (db.create_all() macht das nicht)
        _add_column_if_missing(db, "users", "testphase_enddatum", "TIMESTAMP")
        _add_column_if_missing(db, "applications", "sheets_geschrieben", "BOOLEAN DEFAULT FALSE")

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
