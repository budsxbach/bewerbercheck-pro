"""
Integrationstest: Vollständiger Neukunden-Flow
Registrierung → Stripe-Zahlung → Mailgun-Webhook → Dashboard

Testet alle 5 Schritte so, wie ein echter Neukunde sie durchläuft:
1. Registrierung (/register) – User + CustomerSettings + Mailgun-Route
2. Stripe Checkout + /abo/erfolg – abo_aktiv wird sofort gesetzt
3. Mailgun-Webhook /webhook/email – KI verarbeitet Bewerbung
4. Dashboard /dashboard – Bewerbung erscheint in der Tabelle
5. Tabelle /tabelle – CSV-Export enthält den Bewerber
"""
import json
import time
import pytest
from unittest.mock import patch, MagicMock


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _ki_ergebnis(**overrides):
    base = {
        "name": "Anna Neukunde",
        "email": "anna@beispiel.de",
        "telefon": "+49 40 123456",
        "skills": "Python, Flask, SQL",
        "berufserfahrung_jahre": 4.0,
        "ausbildung": "Bachelor Informatik, TU Hamburg",
        "sprachen": "Deutsch (Muttersprache), Englisch (B2)",
        "uebersetzter_text": "Anna bewirbt sich als Python-Entwicklerin mit 4 Jahren Erfahrung.",
        "score": 8,
        "score_begruendung": "Sehr gute Python-Kenntnisse, erfüllt alle Anforderungen.",
    }
    base.update(overrides)
    return base


def _fake_stripe_checkout_session(payment_status="paid", subscription_id="sub_test123"):
    """Simuliert ein Stripe Checkout Session Objekt."""
    session = MagicMock()
    session.payment_status = payment_status
    session.subscription = subscription_id
    return session


# ═════════════════════════════════════════════════════════════════════════════
# SCHRITT 1 – Registrierung
# ═════════════════════════════════════════════════════════════════════════════

class TestSchritt1Registrierung:

    def test_registrierung_erstellt_user_und_settings(self, app, client):
        """POST /register → User + CustomerSettings in DB, Weiterleitung zu /einstellungen."""
        from app.models import User, CustomerSettings

        with patch("app.auth._send_willkommen_email"), \
             patch("app.auth._create_mailgun_route", return_value={"ok": True}):

            resp = client.post("/register", data={
                "email": "neukunde-flow@example.com",
                "passwort": "TestPasswort123",
                "passwort2": "TestPasswort123",
            }, follow_redirects=False)

        # Weiterleitung zu /einstellungen
        assert resp.status_code in (302, 303), \
            f"Erwartet Redirect nach Registrierung, Status: {resp.status_code}"
        assert "/einstellungen" in resp.headers.get("Location", "") or \
               "settings" in resp.headers.get("Location", ""), \
            f"Redirect-Ziel falsch: {resp.headers.get('Location')}"

        with app.app_context():
            user = User.query.filter_by(email="neukunde-flow@example.com").first()
            assert user is not None, "User wurde nicht in DB angelegt"

            settings = CustomerSettings.query.filter_by(user_id=user.id).first()
            assert settings is not None, "CustomerSettings wurden nicht angelegt"
            assert settings.eigene_email is not None, "Eigene E-Mail-Adresse fehlt"
            assert settings.eigene_email.startswith("firma-"), \
                f"E-Mail-Format falsch: {settings.eigene_email}"
            assert "@" in settings.eigene_email, "Kein @ in eigener E-Mail"

            # Aufräumen
            from app.models import db, Application
            Application.query.filter_by(user_id=user.id).delete()
            CustomerSettings.query.filter_by(user_id=user.id).delete()
            db.session.delete(user)
            db.session.commit()

    def test_duplikat_email_wird_abgelehnt(self, app, client):
        """Zweite Registrierung mit gleicher E-Mail → Fehlermeldung."""
        from app.models import db, User, CustomerSettings, Application

        # Ersten User anlegen
        with patch("app.auth._send_willkommen_email"), \
             patch("app.auth._create_mailgun_route", return_value={"ok": True}):
            client.post("/register", data={
                "email": "duplikat@example.com",
                "passwort": "TestPasswort123",
                "passwort2": "TestPasswort123",
            })

        # Ausloggen, damit die zweite Registrierung nicht als eingeloggter User gewertet wird
        client.get("/logout")

        # Zweite Registrierung mit gleicher E-Mail (kein follow_redirects → vermeidet Stripe-Redirect)
        with patch("app.auth._send_willkommen_email"), \
             patch("app.auth._create_mailgun_route", return_value={"ok": True}):
            resp = client.post("/register", data={
                "email": "duplikat@example.com",
                "passwort": "AnderesPW123",
                "passwort2": "AnderesPW123",
            }, follow_redirects=False)

        # Kein Redirect → Fehlerseite direkt zurückgegeben (200 mit Flash-Meldung)
        assert resp.status_code == 200
        assert b"bereits registriert" in resp.data

        # Aufräumen
        with app.app_context():
            user = User.query.filter_by(email="duplikat@example.com").first()
            if user:
                Application.query.filter_by(user_id=user.id).delete()
                CustomerSettings.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
                db.session.commit()

    def test_willkommens_email_wird_gesendet(self, app, client):
        """Nach Registrierung → _send_willkommen_email aufgerufen."""
        from app.models import db, User, CustomerSettings, Application

        with patch("app.auth._send_willkommen_email") as mock_mail, \
             patch("app.auth._create_mailgun_route", return_value={"ok": True}):

            client.post("/register", data={
                "email": "willkommen-test@example.com",
                "passwort": "TestPasswort123",
                "passwort2": "TestPasswort123",
            })

        mock_mail.assert_called_once()
        args = mock_mail.call_args
        assert "willkommen-test@example.com" in str(args)

        # Aufräumen
        with app.app_context():
            user = User.query.filter_by(email="willkommen-test@example.com").first()
            if user:
                Application.query.filter_by(user_id=user.id).delete()
                CustomerSettings.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
                db.session.commit()

    def test_catchall_route_wird_geprueft(self, app, client):
        """Bei Registrierung wird _catchall_route_exists aufgerufen."""
        from app.models import db, User, CustomerSettings, Application

        with patch("app.auth._send_willkommen_email"), \
             patch("app.auth._catchall_route_exists", return_value=True) as mock_catchall, \
             patch("app.auth._ensure_catchall_route"):

            client.post("/register", data={
                "email": "catchall-test@example.com",
                "passwort": "TestPasswort123",
                "passwort2": "TestPasswort123",
            })

        mock_catchall.assert_called()

        # Aufräumen
        with app.app_context():
            user = User.query.filter_by(email="catchall-test@example.com").first()
            if user:
                Application.query.filter_by(user_id=user.id).delete()
                CustomerSettings.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
                db.session.commit()


# ═════════════════════════════════════════════════════════════════════════════
# SCHRITT 2 – Stripe Zahlung → /abo/erfolg sofort abo_aktiv setzen
# ═════════════════════════════════════════════════════════════════════════════

class TestSchritt2StripeBug1Fix:

    def _erstelle_user_mit_abo(self, app):
        """Hilfsmethode: Neuen User ohne Abo anlegen, einloggen."""
        from app.models import db, User, CustomerSettings
        with app.app_context():
            user = User(email="stripe-test@example.com", abo_aktiv=False, testphase_aktiv=False)
            user.set_password("Passw0rt!")
            db.session.add(user)
            db.session.flush()
            settings = CustomerSettings(
                user_id=user.id,
                eigene_email="firma-stripetest@systemautomatik.com",
            )
            db.session.add(settings)
            db.session.commit()
            return user.id

    def _loesche_user(self, app, user_id):
        from app.models import db, User, CustomerSettings, Application
        with app.app_context():
            Application.query.filter_by(user_id=user_id).delete()
            CustomerSettings.query.filter_by(user_id=user_id).delete()
            User.query.filter_by(id=user_id).delete()
            db.session.commit()

    def test_erfolg_setzt_abo_aktiv_sofort(self, app):
        """GET /abo/erfolg?session_id=... → abo_aktiv=True sofort gesetzt, kein Webhook nötig."""
        from app.models import db, User

        user_id = self._erstelle_user_mit_abo(app)

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        fake_session = _fake_stripe_checkout_session(payment_status="paid")

        with patch("app.auth.stripe") as mock_stripe:
            mock_stripe.checkout.Session.retrieve.return_value = fake_session
            resp = client.get("/abo/erfolg?session_id=cs_test_123", follow_redirects=False)

        assert resp.status_code in (302, 303)

        with app.app_context():
            user = User.query.get(user_id)
            assert user.abo_aktiv is True, \
                f"abo_aktiv sollte True sein nach /abo/erfolg, ist: {user.abo_aktiv}"
            assert user.abo_start_datum is not None, \
                "abo_start_datum sollte gesetzt sein"
            assert user.stripe_subscription_id == "sub_test123", \
                f"stripe_subscription_id falsch: {user.stripe_subscription_id}"

        self._loesche_user(app, user_id)

    def test_erfolg_ohne_session_id_zeigt_flash(self, app):
        """GET /abo/erfolg ohne session_id → kein Fehler, Flash-Meldung erscheint."""
        from app.models import db, User

        user_id = self._erstelle_user_mit_abo(app)

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        resp = client.get("/abo/erfolg", follow_redirects=True)
        assert resp.status_code == 200

        self._loesche_user(app, user_id)

    def test_erfolg_bei_unpaid_setzt_abo_nicht(self, app):
        """/abo/erfolg mit payment_status != 'paid' → abo_aktiv bleibt False."""
        from app.models import db, User

        user_id = self._erstelle_user_mit_abo(app)

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        fake_session = _fake_stripe_checkout_session(payment_status="unpaid")

        with patch("app.auth.stripe") as mock_stripe:
            mock_stripe.checkout.Session.retrieve.return_value = fake_session
            client.get("/abo/erfolg?session_id=cs_unpaid_123", follow_redirects=False)

        with app.app_context():
            user = User.query.get(user_id)
            assert user.abo_aktiv is False, \
                f"abo_aktiv sollte False bleiben bei unpaid, ist: {user.abo_aktiv}"

        self._loesche_user(app, user_id)

    def test_erfolg_stripe_fehler_wird_abgefangen(self, app):
        """/abo/erfolg mit Stripe-API-Fehler → kein 500, nur Warning geloggt."""
        from app.models import db, User

        user_id = self._erstelle_user_mit_abo(app)

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        with patch("app.auth.stripe") as mock_stripe:
            mock_stripe.checkout.Session.retrieve.side_effect = Exception("Stripe Timeout")
            resp = client.get("/abo/erfolg?session_id=cs_broken_123", follow_redirects=False)

        assert resp.status_code in (302, 303), \
            f"Stripe-Fehler darf keine 500 verursachen, Status: {resp.status_code}"

        self._loesche_user(app, user_id)

    def test_bereits_aktives_abo_wird_nicht_doppelt_gesetzt(self, app):
        """Wenn abo_aktiv bereits True → kein doppeltes commit."""
        from app.models import db, User

        user_id = self._erstelle_user_mit_abo(app)

        # Abo vorab setzen
        with app.app_context():
            user = User.query.get(user_id)
            user.abo_aktiv = True
            db.session.commit()

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        fake_session = _fake_stripe_checkout_session(payment_status="paid")

        with patch("app.auth.stripe") as mock_stripe, \
             patch("app.models.db.session.commit") as mock_commit:
            mock_stripe.checkout.Session.retrieve.return_value = fake_session
            client.get("/abo/erfolg?session_id=cs_dup_123", follow_redirects=False)

        # commit sollte NICHT aufgerufen worden sein (da bereits aktiv)
        mock_commit.assert_not_called(), \
            "DB-Commit sollte nicht erfolgen wenn abo_aktiv bereits True"

        self._loesche_user(app, user_id)


# ═════════════════════════════════════════════════════════════════════════════
# SCHRITT 3 – Mailgun Webhook → KI verarbeitet Bewerbung
# ═════════════════════════════════════════════════════════════════════════════

class TestSchritt3MailgunWebhook:

    def _erstelle_user_mit_aktivem_abo(self, app):
        from app.models import db, User, CustomerSettings
        from app.models import _utcnow
        with app.app_context():
            user = User(email="webhook-neukunde@example.com", abo_aktiv=True, testphase_aktiv=False)
            user.set_password("Passw0rt!")
            db.session.add(user)
            db.session.flush()
            settings = CustomerSettings(
                user_id=user.id,
                eigene_email="firma-neukundetest@systemautomatik.com",
                email_benachrichtigung=False,
                stellenbeschreibung="Python-Entwickler gesucht",
                bewertungskriterien="Mind. 3 Jahre Python, Deutsch Pflicht",
            )
            db.session.add(settings)
            db.session.commit()
            return user.id

    def _loesche_user(self, app, user_id):
        from app.models import db, User, CustomerSettings, Application
        with app.app_context():
            Application.query.filter_by(user_id=user_id).delete()
            CustomerSettings.query.filter_by(user_id=user_id).delete()
            User.query.filter_by(id=user_id).delete()
            db.session.commit()

    def _webhook_post(self, client, recipient, **extra):
        data = {
            "recipient": recipient,
            "sender": "anna@beispiel.de",
            "subject": "Bewerbung als Python-Entwicklerin",
            "body-plain": (
                "Sehr geehrte Damen und Herren,\n\n"
                "ich bewerbe mich als Python-Entwicklerin. "
                "Ich bringe 4 Jahre Erfahrung in Python, Flask und PostgreSQL mit.\n\n"
                "Mit freundlichen Grüßen\nAnna Neukunde\nTel: +49 40 123456"
            ),
            "timestamp": str(int(time.time())),
            "token": "testtoken_neukunde",
            "signature": "fakesig",
        }
        data.update(extra)
        return client.post("/webhook/email", data=data)

    def test_webhook_verarbeitet_bewerbung_und_speichert_in_db(self, app):
        """Mailgun-Webhook → KI wird aufgerufen → Bewerbung in DB gespeichert."""
        from app.models import Application

        user_id = self._erstelle_user_mit_aktivem_abo(app)
        client = app.test_client()

        with patch("app.email_webhook.verarbeite_bewerbung", return_value=_ki_ergebnis()) as mock_ki, \
             patch("app.email_webhook.schreibe_in_sheet"), \
             patch("app.email_webhook._sende_bewerbungsbenachrichtigung"):

            resp = self._webhook_post(client, "firma-neukundetest@systemautomatik.com")

        assert resp.status_code == 200
        mock_ki.assert_called_once()

        with app.app_context():
            application = Application.query.filter_by(user_id=user_id).first()
            assert application is not None, "Bewerbung nicht in DB gespeichert"
            assert application.verarbeitet is True, "Bewerbung als nicht verarbeitet markiert"
            assert application.bewerber_name == "Anna Neukunde"
            assert application.score == 8
            assert application.bewerber_email == "anna@beispiel.de"

        self._loesche_user(app, user_id)

    def test_webhook_ohne_abo_ignoriert_email(self, app):
        """User ohne aktives Abo → Webhook gibt 200 zurück, aber keine Bewerbung gespeichert."""
        from app.models import db, User, CustomerSettings, Application

        with app.app_context():
            user = User(email="kein-abo@example.com", abo_aktiv=False, testphase_aktiv=False)
            user.set_password("Passw0rt!")
            db.session.add(user)
            db.session.flush()
            settings = CustomerSettings(
                user_id=user.id,
                eigene_email="firma-keinabo@systemautomatik.com",
            )
            db.session.add(settings)
            db.session.commit()
            user_id = user.id

        client = app.test_client()

        with patch("app.email_webhook.verarbeite_bewerbung") as mock_ki:
            resp = self._webhook_post(client, "firma-keinabo@systemautomatik.com")

        assert resp.status_code == 200
        mock_ki.assert_not_called(), "KI sollte nicht aufgerufen werden ohne aktives Abo"

        with app.app_context():
            count = Application.query.filter_by(user_id=user_id).count()
            assert count == 0, f"Es sollten keine Bewerbungen gespeichert sein, sind: {count}"

        with app.app_context():
            Application.query.filter_by(user_id=user_id).delete()
            CustomerSettings.query.filter_by(user_id=user_id).delete()
            User.query.filter_by(id=user_id).delete()
            db.session.commit()

    def test_unbekannter_empfaenger_wird_ignoriert(self, app):
        """E-Mail an unbekannte Adresse → 200 zurück, kein DB-Eintrag."""
        from app.models import Application

        count_before = 0
        with app.app_context():
            count_before = Application.query.count()

        client = app.test_client()
        resp = self._webhook_post(client, "unbekannt-xyz@systemautomatik.com")

        assert resp.status_code == 200
        with app.app_context():
            count_after = Application.query.count()
        assert count_after == count_before, "Für unbekannte Adresse darf nichts gespeichert werden"

    def test_ki_fehler_speichert_fehler_in_db(self, app):
        """KI wirft Exception → Bewerbung mit fehler-Feld in DB gespeichert."""
        from app.models import Application

        user_id = self._erstelle_user_mit_aktivem_abo(app)
        client = app.test_client()

        with patch("app.email_webhook.verarbeite_bewerbung",
                   side_effect=Exception("Claude API Timeout")), \
             patch("app.email_webhook.schreibe_in_sheet"), \
             patch("app.email_webhook._sende_bewerbungsbenachrichtigung"):

            resp = self._webhook_post(
                client,
                "firma-neukundetest@systemautomatik.com",
                **{"Message-Id": "unique-fehler-id@mailgun"}
            )

        assert resp.status_code == 200  # Webhook immer 200

        with app.app_context():
            application = Application.query.filter_by(user_id=user_id).order_by(
                Application.id.desc()
            ).first()
            assert application is not None
            assert application.verarbeitet is False, "Fehlgeschlagene Bewerbung darf nicht als verarbeitet gelten"
            assert application.fehler is not None, "Fehler-Text sollte gesetzt sein"
            assert "Claude API Timeout" in application.fehler

        self._loesche_user(app, user_id)

    def test_deduplizierung_verhindert_doppelte_eintraege(self, app):
        """Gleiche Message-Id zweimal → nur ein DB-Eintrag."""
        from app.models import Application

        user_id = self._erstelle_user_mit_aktivem_abo(app)
        client = app.test_client()
        msg_id = "dedup-test-123@mailgun.org"

        with patch("app.email_webhook.verarbeite_bewerbung", return_value=_ki_ergebnis()), \
             patch("app.email_webhook.schreibe_in_sheet"), \
             patch("app.email_webhook._sende_bewerbungsbenachrichtigung"):

            # Erste Sendung
            self._webhook_post(
                client,
                "firma-neukundetest@systemautomatik.com",
                **{"Message-Id": msg_id}
            )
            # Zweite Sendung (Duplikat)
            self._webhook_post(
                client,
                "firma-neukundetest@systemautomatik.com",
                **{"Message-Id": msg_id}
            )

        with app.app_context():
            count = Application.query.filter_by(
                user_id=user_id, mailgun_message_id=msg_id
            ).count()
            assert count == 1, f"Duplikat nicht verhindert, Einträge: {count}"

        self._loesche_user(app, user_id)


# ═════════════════════════════════════════════════════════════════════════════
# SCHRITT 4 – Dashboard zeigt verarbeitete Bewerbungen
# ═════════════════════════════════════════════════════════════════════════════

class TestSchritt4Dashboard:

    def _erstelle_user_mit_bewerbung(self, app):
        from app.models import db, User, CustomerSettings, Application
        from app.models import _utcnow
        with app.app_context():
            user = User(email="dashboard-test@example.com", abo_aktiv=True, testphase_aktiv=False)
            user.set_password("Passw0rt!")
            db.session.add(user)
            db.session.flush()

            settings = CustomerSettings(
                user_id=user.id,
                eigene_email="firma-dashboardtest@systemautomatik.com",
            )
            db.session.add(settings)

            # Bewerbung direkt anlegen (wie nach Webhook-Verarbeitung)
            application = Application(
                user_id=user.id,
                bewerber_name="Anna Neukunde",
                bewerber_email="anna@beispiel.de",
                telefon="+49 40 123456",
                skills="Python, Flask, SQL",
                berufserfahrung_jahre=4.0,
                ausbildung="Bachelor Informatik, TU Hamburg",
                sprachen="Deutsch (Muttersprache), Englisch (B2)",
                score=8,
                score_begruendung="Sehr gute Python-Kenntnisse.",
                original_email_text="Test-Bewerbungstext",
                uebersetzter_text="Anna bewirbt sich als Python-Entwicklerin.",
                verarbeitet=True,
                eingegangen_am=_utcnow(),
            )
            db.session.add(application)
            db.session.commit()
            return user.id

    def _loesche_user(self, app, user_id):
        from app.models import db, User, CustomerSettings, Application
        with app.app_context():
            Application.query.filter_by(user_id=user_id).delete()
            CustomerSettings.query.filter_by(user_id=user_id).delete()
            User.query.filter_by(id=user_id).delete()
            db.session.commit()

    def test_dashboard_zeigt_bewerbung(self, app):
        """GET /dashboard → Bewerbung mit Name und Score sichtbar."""
        user_id = self._erstelle_user_mit_bewerbung(app)
        client = app.test_client()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert b"Anna Neukunde" in resp.data, \
            "Bewerber-Name nicht im Dashboard sichtbar"
        assert b"8" in resp.data, \
            "Score nicht im Dashboard sichtbar"

        self._loesche_user(app, user_id)

    def test_dashboard_ohne_abo_leitet_zu_checkout(self, app):
        """User ohne Abo → /dashboard leitet zu /abo/checkout weiter."""
        from app.models import db, User, CustomerSettings
        with app.app_context():
            user = User(email="kein-abo-dash@example.com", abo_aktiv=False, testphase_aktiv=False)
            user.set_password("Passw0rt!")
            db.session.add(user)
            db.session.flush()
            settings = CustomerSettings(user_id=user.id)
            db.session.add(settings)
            db.session.commit()
            user_id = user.id

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        resp = client.get("/dashboard", follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert "checkout" in resp.headers.get("Location", ""), \
            f"Ohne Abo sollte zu Checkout weitergeleitet werden: {resp.headers.get('Location')}"

        with app.app_context():
            from app.models import Application
            Application.query.filter_by(user_id=user_id).delete()
            CustomerSettings.query.filter_by(user_id=user_id).delete()
            User.query.filter_by(id=user_id).delete()
            db.session.commit()

    def test_tabelle_zeigt_alle_bewerbungen(self, app):
        """GET /tabelle → Bewerbung Anna Neukunde ist sichtbar."""
        user_id = self._erstelle_user_mit_bewerbung(app)
        client = app.test_client()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        resp = client.get("/tabelle")
        assert resp.status_code == 200
        assert b"Anna Neukunde" in resp.data

        self._loesche_user(app, user_id)

    def test_csv_export_enthaelt_bewerber(self, app):
        """GET /tabelle/export.csv → CSV-Datei enthält Anna Neukunde mit Score 8."""
        user_id = self._erstelle_user_mit_bewerbung(app)
        client = app.test_client()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        resp = client.get("/tabelle/export.csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("Content-Type", "")

        csv_text = resp.data.decode("utf-8-sig")
        assert "Anna Neukunde" in csv_text, "Bewerber-Name nicht im CSV"
        assert "8" in csv_text, "Score nicht im CSV"
        assert "anna@beispiel.de" in csv_text, "Bewerber-E-Mail nicht im CSV"

        self._loesche_user(app, user_id)


# ═════════════════════════════════════════════════════════════════════════════
# SCHRITT 5 – Kompletter End-to-End Flow (alle Schritte zusammen)
# ═════════════════════════════════════════════════════════════════════════════

class TestSchritt5KompletterFlow:

    def test_vollstaendiger_neukunden_flow(self, app):
        """
        Kompletter Flow:
        1. Registrierung → User + Settings angelegt
        2. /abo/erfolg → abo_aktiv=True sofort gesetzt
        3. Mailgun-Webhook → Bewerbung verarbeitet
        4. /dashboard → Bewerbung sichtbar
        5. /tabelle/export.csv → CSV enthält Bewerbung
        """
        from app.models import db, User, CustomerSettings, Application

        client = app.test_client()
        TEST_EMAIL = "e2e-flow@example.com"

        # ── SCHRITT 1: Registrierung ───────────────────────────────────────
        with patch("app.auth._send_willkommen_email"), \
             patch("app.auth._create_mailgun_route", return_value={"ok": True}):
            resp = client.post("/register", data={
                "email": TEST_EMAIL,
                "passwort": "TestPasswort123!",
                "passwort2": "TestPasswort123!",
            }, follow_redirects=False)

        assert resp.status_code in (302, 303), f"Registrierung fehlgeschlagen: {resp.status_code}"

        with app.app_context():
            user = User.query.filter_by(email=TEST_EMAIL).first()
            assert user is not None, "User nach Registrierung nicht gefunden"
            assert user.abo_aktiv is False, "Abo sollte nach Registrierung noch inaktiv sein"
            settings = CustomerSettings.query.filter_by(user_id=user.id).first()
            assert settings is not None, "CustomerSettings fehlen nach Registrierung"
            eigene_email = settings.eigene_email
            user_id = user.id

        # ── SCHRITT 2: Stripe /abo/erfolg → abo_aktiv sofort True ─────────
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        fake_session = _fake_stripe_checkout_session(payment_status="paid", subscription_id="sub_e2e_123")

        with patch("app.auth.stripe") as mock_stripe:
            mock_stripe.checkout.Session.retrieve.return_value = fake_session
            resp = client.get("/abo/erfolg?session_id=cs_e2e_test", follow_redirects=False)

        assert resp.status_code in (302, 303), f"abo/erfolg fehlgeschlagen: {resp.status_code}"

        with app.app_context():
            user = User.query.get(user_id)
            assert user.abo_aktiv is True, \
                "KRITISCHER BUG: abo_aktiv ist nach /abo/erfolg immer noch False!"
            assert user.abo_start_datum is not None, "abo_start_datum fehlt"

        # ── SCHRITT 3: Mailgun-Webhook → Bewerbung verarbeiten ────────────
        with patch("app.email_webhook.verarbeite_bewerbung", return_value=_ki_ergebnis()) as mock_ki, \
             patch("app.email_webhook.schreibe_in_sheet"), \
             patch("app.email_webhook._sende_bewerbungsbenachrichtigung"):

            resp = client.post("/webhook/email", data={
                "recipient": eigene_email,
                "sender": "anna@beispiel.de",
                "subject": "Bewerbung als Python-Entwicklerin",
                "body-plain": (
                    "Sehr geehrte Damen und Herren,\n"
                    "ich bewerbe mich. 4 Jahre Python-Erfahrung.\n"
                    "Anna Neukunde, Tel: +49 40 123456"
                ),
                "timestamp": str(int(time.time())),
                "token": "e2e_token",
                "signature": "e2e_sig",
                "Message-Id": "e2e-unique-id@mailgun.org",
            })

        assert resp.status_code == 200, f"Webhook-Fehler: {resp.status_code}"
        mock_ki.assert_called_once(), "KI wurde nicht aufgerufen"

        with app.app_context():
            application = Application.query.filter_by(user_id=user_id).first()
            assert application is not None, "Bewerbung nicht in DB gespeichert"
            assert application.verarbeitet is True, "Bewerbung nicht als verarbeitet markiert"
            assert application.score == 8, f"Score falsch: {application.score}"
            assert application.bewerber_name == "Anna Neukunde", \
                f"Bewerber-Name falsch: {application.bewerber_name}"

        # ── SCHRITT 4: Dashboard → Bewerbung sichtbar ─────────────────────
        resp = client.get("/dashboard")
        assert resp.status_code == 200, f"Dashboard-Fehler: {resp.status_code}"
        assert b"Anna Neukunde" in resp.data, \
            "Bewerber-Name nicht im Dashboard sichtbar – Flow gescheitert!"

        # ── SCHRITT 5: CSV-Export → Bewerbung enthalten ───────────────────
        resp = client.get("/tabelle/export.csv")
        assert resp.status_code == 200
        csv_text = resp.data.decode("utf-8-sig")
        assert "Anna Neukunde" in csv_text, "Bewerber nicht im CSV-Export"

        # ── AUFRÄUMEN ─────────────────────────────────────────────────────
        with app.app_context():
            Application.query.filter_by(user_id=user_id).delete()
            CustomerSettings.query.filter_by(user_id=user_id).delete()
            User.query.filter_by(id=user_id).delete()
            db.session.commit()
