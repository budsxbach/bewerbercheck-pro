from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_mail import Mail

from .models import db, User

mail = Mail()
login_manager = LoginManager()


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

    # Datenbankinitialisierung
    with app.app_context():
        db.create_all()

    return app
