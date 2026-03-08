import hashlib
import hmac
import io
import logging
from flask import Blueprint, request, current_app
from flask_mail import Message

from .models import db, CustomerSettings, Application
from .ai_processor import verarbeite_bewerbung
from .sheets_writer import schreibe_in_sheet

email_bp = Blueprint("email", __name__)
logger = logging.getLogger(__name__)


@email_bp.route("/webhook/email", methods=["POST"])
def email_webhook():
    """Mailgun sendet neue eingehende E-Mails als POST hierher."""

    # Mailgun-Signatur prüfen
    if not _verify_mailgun_signature(request):
        logger.warning("Mailgun Webhook: Ungültige Signatur – Anfrage abgelehnt.")
        return "Unauthorized", 401

    # Deduplizierung: Mailgun Message-ID prüfen
    message_id = request.form.get("Message-Id", "").strip()
    if message_id:
        existing = Application.query.filter_by(mailgun_message_id=message_id).first()
        if existing:
            logger.info(f"Duplikat ignoriert: Message-ID {message_id}")
            return "OK", 200

    empfaenger = request.form.get("recipient", "").lower().strip()
    absender = request.form.get("sender", "").strip()
    betreff = request.form.get("subject", "")
    body_plain = request.form.get("body-plain", "")
    body_html = request.form.get("body-html", "")

    # Kunden anhand der Empfänger-Adresse identifizieren
    customer_settings = CustomerSettings.query.filter_by(eigene_email=empfaenger).first()
    if not customer_settings:
        logger.warning(f"Kein Kunde für Empfänger {empfaenger!r} gefunden.")
        return "OK", 200  # Trotzdem 200 zurück, damit Mailgun nicht wiederholt

    user = customer_settings.user
    if not user.hat_zugang:
        logger.info(f"User {user.id} hat kein aktives Abo – E-Mail ignoriert.")
        return "OK", 200

    # PDF-Anhänge extrahieren
    anhang_texte = _extrahiere_anhaenge(request)

    # Bewerbung in Datenbank speichern (zuerst als unverarbeitet)
    application = Application(
        user_id=user.id,
        original_email_text=body_plain or _html_zu_text(body_html),
        verarbeitet=False,
        mailgun_message_id=message_id or None,
    )
    db.session.add(application)
    db.session.commit()

    # KI-Verarbeitung
    try:
        ergebnis = verarbeite_bewerbung(
            email_text=application.original_email_text,
            anhang_texte=anhang_texte,
            stellenbeschreibung=customer_settings.stellenbeschreibung or "",
            bewertungskriterien=customer_settings.bewertungskriterien or "",
        )

        # Ergebnis in Datenbank speichern
        application.bewerber_name = ergebnis.get("name")
        application.bewerber_email = ergebnis.get("email", absender)
        application.telefon = ergebnis.get("telefon")
        application.skills = ergebnis.get("skills")
        application.berufserfahrung_jahre = ergebnis.get("berufserfahrung_jahre")
        application.ausbildung = ergebnis.get("ausbildung")
        application.sprachen = ergebnis.get("sprachen")
        application.score = ergebnis.get("score")
        application.score_begruendung = ergebnis.get("score_begruendung")
        application.uebersetzter_text = ergebnis.get("uebersetzter_text")
        application.verarbeitet = True
        db.session.commit()

        # In Google Sheet schreiben (falls konfiguriert)
        if customer_settings.sheets_url:
            try:
                schreibe_in_sheet(customer_settings.sheets_url, application)
                application.sheets_geschrieben = True
                db.session.commit()
            except Exception as e:
                logger.error(f"Google Sheets Fehler für User {user.id}: {e}")
                application.sheets_geschrieben = False
                db.session.commit()

        # Benachrichtigung per E-Mail (falls aktiviert)
        if customer_settings.email_benachrichtigung:
            _sende_bewerbungsbenachrichtigung(user, application)

    except Exception as e:
        logger.error(f"KI-Verarbeitung Fehler für Application {application.id}: {e}")
        application.fehler = str(e)
        db.session.commit()

    return "OK", 200


def _sende_bewerbungsbenachrichtigung(user, application):
    """Sendet eine E-Mail-Benachrichtigung über eine neue Bewerbung."""
    try:
        from app import mail
        name = application.bewerber_name or "Unbekannt"
        score = application.score or "–"
        msg = Message(
            subject=f"Neue Bewerbung: {name} (Score: {score}/10)",
            recipients=[user.email],
            body=(
                f"Eine neue Bewerbung wurde verarbeitet:\n\n"
                f"Name: {name}\n"
                f"Score: {score}/10\n"
                f"E-Mail: {application.bewerber_email or '–'}\n\n"
                f"Details finden Sie in Ihrem Dashboard.\n\n"
                f"– Bewerbercheck-Pro\n\n"
                f"Tipp: Sie können diese Benachrichtigungen in den Einstellungen deaktivieren."
            ),
        )
        mail.send(msg)
    except Exception as e:
        logger.error(f"Benachrichtigungs-E-Mail Fehler für User {user.id}: {e}")


def _verify_mailgun_signature(req) -> bool:
    """Prüft die HMAC-Signatur von Mailgun."""
    signing_key = current_app.config.get("MAILGUN_WEBHOOK_SIGNING_KEY")
    if not signing_key:
        app_url = current_app.config.get("APP_URL", "")
        if "localhost" in app_url or "127.0.0.1" in app_url:
            logger.warning("MAILGUN_WEBHOOK_SIGNING_KEY nicht gesetzt – Entwicklungsmodus, durchgelassen.")
            return True
        logger.error("MAILGUN_WEBHOOK_SIGNING_KEY fehlt in Produktion – Anfrage abgelehnt!")
        return False

    timestamp = req.form.get("timestamp", "")
    token = req.form.get("token", "")
    signature = req.form.get("signature", "")

    value = f"{timestamp}{token}".encode("utf-8")
    expected = hmac.new(signing_key.encode("utf-8"), value, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _extrahiere_anhaenge(req) -> list[str]:
    """Extrahiert Text aus PDF-Anhängen der E-Mail."""
    texte = []
    # Mailgun sendet Anhänge als attachment-1, attachment-2, ...
    i = 1
    while True:
        datei = req.files.get(f"attachment-{i}")
        if not datei:
            break
        i += 1

        dateiname = datei.filename or ""
        if dateiname.lower().endswith(".pdf"):
            try:
                pdf_text = _pdf_zu_text(datei.read())
                if pdf_text.strip():
                    texte.append(pdf_text)
            except Exception as e:
                logger.warning(f"PDF-Extraktion fehlgeschlagen für {dateiname}: {e}")
        elif dateiname.lower().endswith((".doc", ".docx", ".txt")):
            try:
                text = datei.read().decode("utf-8", errors="ignore")
                if text.strip():
                    texte.append(text)
            except Exception as e:
                logger.warning(f"Text-Extraktion fehlgeschlagen für {dateiname}: {e}")

    return texte


def _pdf_zu_text(pdf_bytes: bytes) -> str:
    """Extrahiert Text aus einem PDF-Dokument."""
    try:
        # Erst PyPDF2 versuchen (schnell)
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        texte = []
        for seite in reader.pages:
            text = seite.extract_text()
            if text:
                texte.append(text)
        ergebnis = "\n".join(texte)
        if ergebnis.strip():
            return ergebnis
    except Exception:
        pass

    try:
        # Fallback: pdfminer (gründlicher, langsamer)
        from pdfminer.high_level import extract_text as pdfminer_extract
        return pdfminer_extract(io.BytesIO(pdf_bytes))
    except Exception as e:
        raise RuntimeError(f"PDF konnte nicht gelesen werden: {e}") from e


def _html_zu_text(html: str) -> str:
    """Entfernt HTML-Tags für reinen Text."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
