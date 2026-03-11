import csv
import io
import logging
from flask import Blueprint, render_template, redirect, url_for, abort, flash, request, make_response
from flask_login import login_required, current_user

from .models import db, Application, CustomerSettings
from .ai_processor import verarbeite_bewerbung
from .sheets_writer import schreibe_in_sheet

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def index():
    if not current_user.hat_zugang:
        return redirect(url_for("auth.stripe_checkout"))

    page = request.args.get("page", 1, type=int)

    # Bewerbungen nach Score absteigend sortiert (paginiert)
    pagination = (
        Application.query
        .filter_by(user_id=current_user.id, verarbeitet=True)
        .order_by(Application.score.desc().nullslast(), Application.eingegangen_am.desc())
        .paginate(page=page, per_page=25, error_out=False)
    )

    fehlerhafte = (
        Application.query
        .filter_by(user_id=current_user.id, verarbeitet=False)
        .filter(Application.fehler.isnot(None))
        .order_by(Application.eingegangen_am.desc())
        .all()
    )

    return render_template(
        "dashboard.html",
        applications=pagination.items,
        pagination=pagination,
        fehlerhafte=fehlerhafte,
    )


@dashboard_bp.route("/tabelle")
@login_required
def tabelle():
    if not current_user.hat_zugang:
        return redirect(url_for("auth.stripe_checkout"))
    applications = Application.query.filter_by(
        user_id=current_user.id, verarbeitet=True
    ).order_by(Application.score.desc().nullslast(), Application.eingegangen_am.desc()).all()
    return render_template("tabelle.html", applications=applications)


@dashboard_bp.route("/tabelle/export.csv")
@login_required
def tabelle_export():
    if not current_user.hat_zugang:
        return redirect(url_for("auth.stripe_checkout"))
    applications = Application.query.filter_by(
        user_id=current_user.id, verarbeitet=True
    ).order_by(Application.score.desc().nullslast(), Application.eingegangen_am.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Eingegangen am", "Score (1-10)", "Bewertung", "Name", "E-Mail",
        "Telefon", "Skills", "Erfahrung (Jahre)", "Ausbildung", "Sprachen", "Zusammenfassung",
    ])
    for app in applications:
        writer.writerow([
            app.eingegangen_am.strftime("%d.%m.%Y %H:%M") if app.eingegangen_am else "",
            app.score or "",
            app.score_begruendung or "",
            app.bewerber_name or "",
            app.bewerber_email or "",
            app.telefon or "",
            app.skills or "",
            app.berufserfahrung_jahre if app.berufserfahrung_jahre is not None else "",
            app.ausbildung or "",
            app.sprachen or "",
            (app.uebersetzter_text or "")[:150],
        ])

    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=bewerbungen.csv"
    return response


@dashboard_bp.route("/bewerbung/<int:application_id>")
@login_required
def detail(application_id):
    application = Application.query.get_or_404(application_id)
    if application.user_id != current_user.id:
        abort(403)
    return render_template("bewerbung_detail.html", application=application)


@dashboard_bp.route("/bewerbung/<int:application_id>/retry", methods=["POST"])
@login_required
def retry(application_id):
    application = Application.query.get_or_404(application_id)
    if application.user_id != current_user.id:
        abort(403)

    if application.verarbeitet:
        flash("Diese Bewerbung wurde bereits verarbeitet.", "info")
        return redirect(url_for("dashboard.index"))

    settings = CustomerSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        flash("Bitte zuerst Einstellungen konfigurieren.", "warning")
        return redirect(url_for("dashboard.index"))

    try:
        ergebnis = verarbeite_bewerbung(
            email_text=application.original_email_text or "",
            anhang_texte=[],
            stellenbeschreibung=settings.stellenbeschreibung or "",
            bewertungskriterien=settings.bewertungskriterien or "",
        )

        email_aus_ki = ergebnis.get("email")
        if email_aus_ki and "@" not in str(email_aus_ki):
            logger.warning(f"Retry: KI-E-Mail {email_aus_ki!r} enthält kein '@' – wird verworfen.")
            email_aus_ki = None

        application.bewerber_name = ergebnis.get("name")
        application.bewerber_email = email_aus_ki
        application.telefon = ergebnis.get("telefon")
        application.skills = ergebnis.get("skills")
        application.berufserfahrung_jahre = ergebnis.get("berufserfahrung_jahre")
        application.ausbildung = ergebnis.get("ausbildung")
        application.sprachen = ergebnis.get("sprachen")
        application.score = ergebnis.get("score")
        application.score_begruendung = ergebnis.get("score_begruendung")
        application.uebersetzter_text = ergebnis.get("uebersetzter_text")
        application.verarbeitet = True
        application.fehler = None
        db.session.commit()

        # Sheets nachholen
        if settings.sheets_url:
            try:
                schreibe_in_sheet(settings.sheets_url, application)
                application.sheets_geschrieben = True
                db.session.commit()
            except Exception as e:
                logger.error(f"Sheets Retry Fehler: {e}")

        flash(f"Bewerbung von {application.bewerber_name or 'Unbekannt'} erfolgreich verarbeitet!", "success")
    except Exception as e:
        application.fehler = str(e)
        db.session.commit()
        flash("Erneute Verarbeitung fehlgeschlagen. Bitte prüfen Sie die Server-Logs.", "danger")

    return redirect(url_for("dashboard.index"))
