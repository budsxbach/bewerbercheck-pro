import uuid
import stripe
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from .models import db, User, CustomerSettings

auth_bp = Blueprint("auth", __name__)


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


# ─── Registrierung ────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        passwort = request.form.get("passwort", "")
        passwort2 = request.form.get("passwort2", "")

        if not email or not passwort:
            flash("Bitte alle Felder ausfüllen.", "danger")
            return render_template("register.html")

        if passwort != passwort2:
            flash("Passwörter stimmen nicht überein.", "danger")
            return render_template("register.html")

        if len(passwort) < 8:
            flash("Passwort muss mindestens 8 Zeichen lang sein.", "danger")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Diese E-Mail-Adresse ist bereits registriert.", "danger")
            return render_template("register.html")

        user = User(email=email, testphase_aktiv=True)
        user.set_password(passwort)
        db.session.add(user)
        db.session.flush()  # ID erzeugen

        # Eindeutigen E-Mail-Token generieren
        token = uuid.uuid4().hex[:8]
        while CustomerSettings.query.filter_by(email_token=token).first():
            token = uuid.uuid4().hex[:8]

        mailgun_domain = current_app.config.get("MAILGUN_DOMAIN", "bewerbungswandler.de")
        settings = CustomerSettings(
            user_id=user.id,
            email_token=token,
            eigene_email=f"firma-{token}@{mailgun_domain}",
        )
        db.session.add(settings)
        db.session.commit()

        # Mailgun-Route anlegen
        _create_mailgun_route(user.id, settings.eigene_email)

        login_user(user)
        flash("Willkommen! Ihr Konto wurde erstellt. Bitte konfigurieren Sie Ihre Einstellungen.", "success")
        return redirect(url_for("settings_bp.index"))

    return render_template("register.html")


def _create_mailgun_route(user_id: int, email_address: str):
    """Legt Mailgun-Route an, die eingehende E-Mails an unseren Webhook weiterleitet."""
    import requests

    api_key = current_app.config.get("MAILGUN_API_KEY")
    domain = current_app.config.get("MAILGUN_DOMAIN")
    app_url = current_app.config.get("APP_URL", "http://localhost:5000")

    if not api_key:
        current_app.logger.warning("MAILGUN_API_KEY nicht gesetzt – Route nicht angelegt.")
        return

    try:
        requests.post(
            "https://api.mailgun.net/v3/routes",
            auth=("api", api_key),
            data={
                "priority": 1,
                "description": f"BewerberCheck Route für User {user_id}",
                "expression": f"match_recipient('{email_address}')",
                "action": [
                    f"forward('{app_url}/webhook/email')",
                    "stop()",
                ],
            },
            timeout=10,
        )
    except Exception as e:
        current_app.logger.error(f"Mailgun Route Fehler: {e}")


# ─── Login / Logout ───────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        passwort = request.form.get("passwort", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(passwort):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.index"))

        flash("E-Mail oder Passwort falsch.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sie wurden abgemeldet.", "info")
    return redirect(url_for("auth.login"))


# ─── Passwort-Reset ───────────────────────────────────────────────────────────

@auth_bp.route("/passwort-vergessen", methods=["GET", "POST"])
def passwort_vergessen():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            s = _get_serializer()
            token = s.dumps(user.email, salt="pw-reset")
            reset_url = url_for("auth.passwort_reset", token=token, _external=True)
            _send_reset_email(user.email, reset_url)

        # Immer gleiche Meldung (verhindert User-Enumeration)
        flash("Falls diese E-Mail existiert, wurde ein Reset-Link gesendet.", "info")
        return redirect(url_for("auth.login"))

    return render_template("passwort_vergessen.html")


@auth_bp.route("/passwort-reset/<token>", methods=["GET", "POST"])
def passwort_reset(token):
    s = _get_serializer()
    try:
        email = s.loads(token, salt="pw-reset", max_age=3600)
    except (SignatureExpired, BadSignature):
        flash("Reset-Link ungültig oder abgelaufen.", "danger")
        return redirect(url_for("auth.passwort_vergessen"))

    user = User.query.filter_by(email=email).first_or_404()

    if request.method == "POST":
        passwort = request.form.get("passwort", "")
        if len(passwort) < 8:
            flash("Passwort muss mindestens 8 Zeichen lang sein.", "danger")
        else:
            user.set_password(passwort)
            db.session.commit()
            flash("Passwort erfolgreich geändert. Bitte einloggen.", "success")
            return redirect(url_for("auth.login"))

    return render_template("passwort_reset.html", token=token)


def _send_reset_email(to_email: str, reset_url: str):
    from app import mail
    try:
        msg = Message(
            subject="Bewerbercheck-Pro – Passwort zurücksetzen",
            recipients=[to_email],
            body=f"Klicken Sie auf den folgenden Link um Ihr Passwort zurückzusetzen:\n\n{reset_url}\n\nDer Link ist 1 Stunde gültig.",
        )
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f"E-Mail-Versand Fehler: {e}")


# ─── Stripe Checkout ──────────────────────────────────────────────────────────

@auth_bp.route("/abo/checkout")
@login_required
def stripe_checkout():
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    app_url = current_app.config["APP_URL"]

    try:
        # Stripe Customer anlegen oder wiederverwenden
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(email=current_user.email)
            current_user.stripe_customer_id = customer.id
            db.session.commit()

        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": current_app.config["STRIPE_PRICE_ID"], "quantity": 1}],
            mode="subscription",
            subscription_data={"trial_period_days": 14},
            success_url=f"{app_url}/abo/erfolg?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{app_url}/dashboard",
        )
        return redirect(session.url, code=303)
    except Exception as e:
        current_app.logger.error(f"Stripe Checkout Fehler: {e}")
        flash("Fehler beim Starten des Checkouts. Bitte versuchen Sie es später.", "danger")
        return redirect(url_for("dashboard.index"))


@auth_bp.route("/abo/erfolg")
@login_required
def stripe_erfolg():
    flash("Ihr Abonnement wurde aktiviert! Willkommen bei Bewerbercheck-Pro.", "success")
    return redirect(url_for("settings_bp.index"))


@auth_bp.route("/abo/portal")
@login_required
def stripe_portal():
    """Stripe Customer Portal – Kunden können Abo selbst verwalten/kündigen."""
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    app_url = current_app.config["APP_URL"]

    if not current_user.stripe_customer_id:
        flash("Kein aktives Abonnement gefunden.", "warning")
        return redirect(url_for("dashboard.index"))

    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{app_url}/dashboard",
        )
        return redirect(session.url, code=303)
    except Exception as e:
        current_app.logger.error(f"Stripe Portal Fehler: {e}")
        flash("Fehler beim Öffnen des Kundenportals.", "danger")
        return redirect(url_for("dashboard.index"))


# ─── Stripe Webhook ───────────────────────────────────────────────────────────

@auth_bp.route("/webhook/stripe", methods=["POST"])
def stripe_webhook():
    """Stripe sendet Events hierher – Zahlung erfolgreich, Abo gekündigt, etc."""
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")
    webhook_secret = current_app.config["STRIPE_WEBHOOK_SECRET"]
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        current_app.logger.warning(f"Stripe Webhook Signatur ungültig: {e}")
        return "Ungültige Signatur", 400

    event_type = event["type"]

    if event_type == "customer.subscription.created":
        _handle_subscription_created(event["data"]["object"])
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(event["data"]["object"])
    elif event_type in ("customer.subscription.deleted", "customer.subscription.paused"):
        _handle_subscription_ended(event["data"]["object"])
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(event["data"]["object"])

    return "OK", 200


def _handle_subscription_created(subscription):
    user = User.query.filter_by(stripe_customer_id=subscription["customer"]).first()
    if user:
        user.abo_aktiv = True
        user.stripe_subscription_id = subscription["id"]
        db.session.commit()


def _handle_subscription_updated(subscription):
    user = User.query.filter_by(stripe_customer_id=subscription["customer"]).first()
    if user:
        status = subscription.get("status")
        user.abo_aktiv = status in ("active", "trialing")
        user.stripe_subscription_id = subscription["id"]
        db.session.commit()


def _handle_subscription_ended(subscription):
    user = User.query.filter_by(stripe_customer_id=subscription["customer"]).first()
    if user:
        user.abo_aktiv = False
        db.session.commit()


def _handle_payment_failed(invoice):
    user = User.query.filter_by(stripe_customer_id=invoice["customer"]).first()
    if user:
        user.abo_aktiv = False
        db.session.commit()
