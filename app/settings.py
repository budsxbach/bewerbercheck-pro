import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user

from .models import db, CustomerSettings

settings_bp = Blueprint("settings_bp", __name__)


@settings_bp.route("/einstellungen", methods=["GET", "POST"])
@login_required
def index():
    settings = current_user.settings
    if not settings:
        flash("Einstellungen nicht gefunden. Bitte neu registrieren.", "danger")
        return redirect(url_for("auth.logout"))

    if request.method == "POST":
        sheets_url = request.form.get("sheets_url", "").strip()
        stellenbeschreibung = request.form.get("stellenbeschreibung", "").strip()
        bewertungskriterien = request.form.get("bewertungskriterien", "").strip()

        # Grundlegende URL-Validierung
        if sheets_url and "docs.google.com/spreadsheets" not in sheets_url:
            flash("Bitte geben Sie eine gültige Google Sheets URL ein.", "danger")
            return render_template("settings.html", settings=settings, service_account_email=_get_service_account_email())

        settings.sheets_url = sheets_url or None
        settings.stellenbeschreibung = stellenbeschreibung or None
        settings.bewertungskriterien = bewertungskriterien or None
        db.session.commit()

        flash("Einstellungen gespeichert!", "success")
        return redirect(url_for("settings_bp.index"))

    service_account_email = _get_service_account_email()
    return render_template("settings.html", settings=settings, service_account_email=service_account_email)


def _get_service_account_email() -> str:
    """Gibt die Service-Account-E-Mail zurück, die Kunden als Editor hinzufügen müssen."""
    return os.environ.get("GOOGLE_SERVICE_ACCOUNT_EMAIL", "Nicht konfiguriert")
