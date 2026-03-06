from flask import Blueprint, render_template, redirect, url_for, abort
from flask_login import login_required, current_user

from .models import Application

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def index():
    if not current_user.hat_zugang:
        return redirect(url_for("auth.stripe_checkout"))

    # Bewerbungen nach Score absteigend sortiert
    applications = (
        Application.query
        .filter_by(user_id=current_user.id, verarbeitet=True)
        .order_by(Application.score.desc().nullslast(), Application.eingegangen_am.desc())
        .all()
    )

    fehler_count = (
        Application.query
        .filter_by(user_id=current_user.id, verarbeitet=False)
        .filter(Application.fehler.isnot(None))
        .count()
    )

    return render_template(
        "dashboard.html",
        applications=applications,
        fehler_count=fehler_count,
    )


@dashboard_bp.route("/bewerbung/<int:application_id>")
@login_required
def detail(application_id):
    application = Application.query.get_or_404(application_id)
    if application.user_id != current_user.id:
        abort(403)
    return render_template("bewerbung_detail.html", application=application)
