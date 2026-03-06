import json
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Application

logger = logging.getLogger(__name__)

# Reihenfolge der Spalten im Google Sheet
# Score zuerst → HR sieht sofort die Bewertung ohne scrollen
SPALTEN_REIHENFOLGE = [
    "Eingegangen am",
    "Score (1-10)",
    "Bewertung",
    "Name",
    "E-Mail",
    "Telefon",
    "Skills",
    "Erfahrung (Jahre)",
    "Ausbildung",
    "Sprachen",
    "Zusammenfassung",
]


def schreibe_in_sheet(sheets_url: str, application: "Application") -> None:
    """
    Schreibt eine Bewerbung als neue Zeile in das Google Sheet des Kunden.

    Bei der ersten Bewerbung werden automatisch Spaltenköpfe angelegt.
    Der Kunde muss den Service-Account einmalig als Editor hinzufügen.
    """
    import os
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    spreadsheet_id = _extrahiere_sheet_id(sheets_url)
    if not spreadsheet_id:
        raise ValueError(f"Ungültige Google Sheets URL: {sheets_url!r}")

    credentials = _lade_credentials()
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    sheet = service.spreadsheets()

    # Prüfen ob Sheet leer ist (Header noch nicht gesetzt)
    try:
        result = sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range="A1:A1",
        ).execute()
        hat_header = bool(result.get("values"))
    except HttpError as e:
        logger.error(f"Sheets API Fehler beim Lesen: {e}")
        raise

    zeilen = []
    if not hat_header:
        zeilen.append(SPALTEN_REIHENFOLGE)

    # Datenwerte in gleicher Reihenfolge wie SPALTEN_REIHENFOLGE
    datumzeit = application.eingegangen_am.strftime("%d.%m.%Y %H:%M") if application.eingegangen_am else ""
    zeilen.append([
        datumzeit,
        application.score or "",
        application.score_begruendung or "",
        application.bewerber_name or "",
        application.bewerber_email or "",
        application.telefon or "",
        application.skills or "",
        application.berufserfahrung_jahre if application.berufserfahrung_jahre is not None else "",
        application.ausbildung or "",
        application.sprachen or "",
        (application.uebersetzter_text or "")[:500],  # Zusammenfassung kürzen
    ])

    try:
        sheet.values().append(
            spreadsheetId=spreadsheet_id,
            range="A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": zeilen},
        ).execute()
        logger.info(f"Bewerbung {application.id} erfolgreich in Sheet {spreadsheet_id} geschrieben.")
    except HttpError as e:
        logger.error(f"Sheets API Fehler beim Schreiben: {e}")
        raise


def _extrahiere_sheet_id(url: str) -> str | None:
    """Extrahiert die Spreadsheet-ID aus einer Google Sheets URL."""
    # Format: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None


def _lade_credentials():
    """Lädt Google Service Account Credentials aus Umgebungsvariable."""
    import os
    from google.oauth2.service_account import Credentials

    key_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY_JSON")
    if not key_json:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_KEY_JSON nicht gesetzt")

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]

    try:
        key_data = json.loads(key_json)
        return Credentials.from_service_account_info(key_data, scopes=scopes)
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(f"GOOGLE_SERVICE_ACCOUNT_KEY_JSON ungültig: {e}") from e
