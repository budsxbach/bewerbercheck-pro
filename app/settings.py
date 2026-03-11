import os
from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user

from .models import db, CustomerSettings, User

settings_bp = Blueprint("settings_bp", __name__)


@settings_bp.route("/einstellungen", methods=["GET", "POST"])
@login_required
def index():
    settings = current_user.settings
    if not settings:
        flash("Einstellungen nicht gefunden. Bitte neu registrieren.", "danger")
        return redirect(url_for("auth.logout"))

    if request.method == "POST":
        stellenbeschreibung = request.form.get("stellenbeschreibung", "").strip()
        bewertungskriterien = request.form.get("bewertungskriterien", "").strip()
        settings.stellenbeschreibung = stellenbeschreibung or None
        settings.bewertungskriterien = bewertungskriterien or None
        db.session.commit()

        flash("KI-Einstellungen gespeichert!", "success")
        return redirect(url_for("settings_bp.index"))

    service_account_email = _get_service_account_email()
    return render_template("settings.html", settings=settings, service_account_email=service_account_email)


@settings_bp.route("/einstellungen/sheets", methods=["POST"])
@login_required
def sheets_speichern():
    """Speichert nur die Google Sheets URL – unabhängig von KI-Einstellungen."""
    settings = current_user.settings
    sheets_url = request.form.get("sheets_url", "").strip()
    parsed = urlparse(sheets_url) if sheets_url else None
    if sheets_url and (parsed.netloc != "docs.google.com" or "/spreadsheets" not in parsed.path):
        flash("Bitte eine gültige Google Sheets URL einfügen.", "danger")
        return redirect(url_for("settings_bp.index"))
    settings.sheets_url = sheets_url or None
    db.session.commit()
    flash("Google Sheets gespeichert!", "success")
    return redirect(url_for("settings_bp.index"))


@settings_bp.route("/einstellungen/konto-loeschen", methods=["POST"])
@login_required
def konto_loeschen():
    """DSGVO Art. 17 – Recht auf Löschung. Löscht User + alle Daten (Cascade)."""
    user = User.query.get(current_user.id)
    if not user:
        flash("Benutzer nicht gefunden.", "danger")
        return redirect(url_for("settings_bp.index"))

    from flask_login import logout_user
    user_email = user.email
    logout_user()

    db.session.delete(user)
    db.session.commit()

    current_app.logger.info(f"Konto gelöscht: {user_email}")
    flash("Ihr Konto und alle Daten wurden unwiderruflich gelöscht.", "info")
    return redirect(url_for("landing"))


@settings_bp.route("/einstellungen/route-reparieren", methods=["POST"])
@login_required
def route_reparieren():
    """Löscht alte Mailgun-Route und legt eine neue mit der aktuellen APP_URL an."""
    settings = current_user.settings
    if not settings or not settings.eigene_email:
        flash("Keine E-Mail-Adresse gefunden.", "danger")
        return redirect(url_for("settings_bp.index"))

    from .auth import repariere_mailgun_route
    success = repariere_mailgun_route(current_user.id, settings.eigene_email)

    if success.get("ok"):
        flash("Mailgun-Route wurde erfolgreich neu erstellt. E-Mail-Empfang sollte jetzt funktionieren.", "success")
    else:
        fehler = success.get("error", "Unbekannter Fehler")
        flash(f"Route konnte nicht repariert werden: {fehler}", "danger")

    return redirect(url_for("settings_bp.index"))


@settings_bp.route("/admin/mailgun-diagnose")
@login_required
def admin_mailgun_diagnose():
    """Admin-Diagnose: Zeigt alle Mailgun-Routen und ob sie zur aktuellen APP_URL passen.
    Erfordert Header X-Admin-Key: ADMIN_DIAGNOSE_KEY (nicht mehr als ?key= Query-Param)."""
    import requests

    expected_key = current_app.config.get("ADMIN_DIAGNOSE_KEY") or os.environ.get("ADMIN_DIAGNOSE_KEY")
    if not expected_key or request.headers.get("X-Admin-Key") != expected_key:
        return jsonify({"error": "Unauthorized – Header X-Admin-Key erforderlich"}), 401

    api_key = current_app.config.get("MAILGUN_API_KEY")
    api_base = current_app.config.get("MAILGUN_API_BASE", "https://api.eu.mailgun.net/v3")
    app_url = current_app.config.get("APP_URL", "")
    domain = current_app.config.get("MAILGUN_DOMAIN", "systemautomatik.com")

    result = {
        "app_url": app_url,
        "mailgun_domain": domain,
        "api_base": api_base,
        "webhook_target": f"{app_url}/webhook/email",
        "api_key_set": bool(api_key),
        "api_key_prefix": (api_key[:8] + "...") if api_key else None,
        "routes": [],
        "users_without_route": [],
    }

    # Mailgun-Routen laden
    if api_key:
        try:
            resp = requests.get(
                f"{api_base}/routes",
                auth=("api", api_key),
                params={"limit": 100},
                timeout=10,
            )
            resp.raise_for_status()
            routes = resp.json().get("items", [])
            webhook_url = f"{app_url}/webhook/email"

            for route in routes:
                actions = route.get("actions", [])
                forward_ok = any(webhook_url in a for a in actions)
                result["routes"].append({
                    "id": route["id"],
                    "expression": route.get("expression"),
                    "actions": actions,
                    "webhook_ok": forward_ok,
                })
        except Exception as e:
            result["routes_error"] = str(e)

    # Kunden ohne funktionierende Route prüfen
    all_settings = CustomerSettings.query.all()
    route_expressions = " ".join(r.get("expression", "") for r in result.get("routes", []))
    for s in all_settings:
        if s.eigene_email and s.eigene_email not in route_expressions:
            result["users_without_route"].append({
                "user_id": s.user_id,
                "email": s.eigene_email,
            })

    return jsonify(result)


@settings_bp.route("/admin/fix-routes")
@login_required
def admin_fix_routes():
    """Erstellt eine Catch-All-Route für alle E-Mails an @domain.
    Erfordert Header X-Admin-Key: ADMIN_DIAGNOSE_KEY."""
    expected_key = current_app.config.get("ADMIN_DIAGNOSE_KEY") or os.environ.get("ADMIN_DIAGNOSE_KEY")
    if not expected_key or request.headers.get("X-Admin-Key") != expected_key:
        return jsonify({"error": "Unauthorized – Header X-Admin-Key erforderlich"}), 401

    from .auth import _ensure_catchall_route
    result = _ensure_catchall_route()
    domain = current_app.config.get("MAILGUN_DOMAIN", "systemautomatik.com")

    return jsonify({
        "strategy": "catch-all",
        "domain": domain,
        "result": result,
        "info": f"Eine Route für *@{domain} – alle User werden über den Webhook identifiziert.",
    })


@settings_bp.route("/admin/domain-migration")
@login_required
def admin_domain_migration():
    """Migriert alle CustomerSettings von einem alten Domain auf den aktuell konfigurierten MAILGUN_DOMAIN.
    Erfordert Header X-Admin-Key: ADMIN_DIAGNOSE_KEY sowie Query-Param old_domain=alter-domain.com."""
    from .auth import repariere_mailgun_route

    expected_key = current_app.config.get("ADMIN_DIAGNOSE_KEY") or os.environ.get("ADMIN_DIAGNOSE_KEY")
    if not expected_key or request.headers.get("X-Admin-Key") != expected_key:
        return jsonify({"error": "Unauthorized – Header X-Admin-Key erforderlich"}), 401

    old_domain = request.args.get("old_domain", "systemautomatik.com")
    new_domain = current_app.config.get("MAILGUN_DOMAIN", "systemautomatik.com")

    migrated = []
    skipped = []
    errors = []

    all_settings = CustomerSettings.query.all()
    for s in all_settings:
        if not s.eigene_email or old_domain not in s.eigene_email:
            skipped.append({"user_id": s.user_id, "email": s.eigene_email, "reason": "kein alter Domain"})
            continue

        old_email = s.eigene_email
        new_email = old_email.replace(f"@{old_domain}", f"@{new_domain}")
        s.eigene_email = new_email
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            errors.append({"user_id": s.user_id, "old_email": old_email, "error": str(e)})
            continue

        success = repariere_mailgun_route(s.user_id, new_email)
        migrated.append({
            "user_id": s.user_id,
            "old_email": old_email,
            "new_email": new_email,
            "route_ok": success,
        })

    return jsonify({
        "new_domain": new_domain,
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
        "summary": f"{len(migrated)} migriert, {len(skipped)} übersprungen, {len(errors)} Fehler",
    })


def _get_service_account_email() -> str:
    """Gibt die Service-Account-E-Mail zurück, die Kunden als Editor hinzufügen müssen."""
    return os.environ.get("GOOGLE_SERVICE_ACCOUNT_EMAIL", "Nicht konfiguriert")
