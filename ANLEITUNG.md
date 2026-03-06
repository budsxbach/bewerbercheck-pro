# Bewerbercheck-Pro – Schritt-für-Schritt-Deployment

Diese Anleitung führt Sie ohne technische Vorkenntnisse durch das komplette Setup.
Geschätzte Zeit: ca. 90 Minuten beim ersten Mal.

---

## Teil 1: Externe Dienste einrichten

### 1.1 Mailgun (E-Mail-Empfang)

1. Gehen Sie zu **mailgun.com** → „Sign Up Free"
2. E-Mail bestätigen, dann im Dashboard:
   - „Add a Domain" → Ihren eigenen Domain-Namen eingeben (z.B. `bewerbungswandler.de`)
   - Alternativ: Mailgun-Sandbox-Domain für Tests verwenden
3. Im Domain-Dashboard:
   - Kopieren Sie den **API Key** (beginnt mit `key-`)
   - Kopieren Sie den **Webhook Signing Key**
4. DNS-Einträge bei Ihrem Domain-Anbieter (Hostinger) eintragen:
   - Mailgun zeigt Ihnen die genauen Einträge an
   - MX, TXT und CNAME-Einträge hinzufügen

### 1.2 Anthropic Claude API

1. Gehen Sie zu **console.anthropic.com** → Konto erstellen
2. „API Keys" → „Create Key"
3. Schlüssel kopieren (beginnt mit `sk-ant-`)
4. Zahlungsmethode hinterlegen (Kreditkarte)

### 1.3 Google Cloud Service Account

1. Gehen Sie zu **console.cloud.google.com**
2. Neues Projekt erstellen (z.B. „bewerbercheck-pro")
3. Linkes Menü → „APIs & Dienste" → „Bibliothek"
4. „Google Sheets API" suchen → Aktivieren
5. Linkes Menü → „APIs & Dienste" → „Anmeldedaten"
6. „Anmeldedaten erstellen" → „Dienstkonto"
   - Name: `bewerbercheck`
   - Fertig (keine weiteren Berechtigungen nötig)
7. Auf das erstellte Dienstkonto klicken → Reiter „Schlüssel"
8. „Schlüssel hinzufügen" → „Neuen Schlüssel erstellen" → JSON → Herunterladen
9. Die JSON-Datei öffnen → den gesamten Inhalt kopieren (für `GOOGLE_SERVICE_ACCOUNT_KEY_JSON`)
10. Die E-Mail-Adresse des Dienstkontos kopieren (für `GOOGLE_SERVICE_ACCOUNT_EMAIL`)
    - Format: `bewerbercheck@ihr-projekt.iam.gserviceaccount.com`

### 1.4 Stripe (Zahlungen)

1. Gehen Sie zu **dashboard.stripe.com** → Konto erstellen
2. Dashboard → „Entwickler" → „API-Schlüssel"
   - Publishable key (`pk_live_...`) kopieren
   - Secret key (`sk_live_...`) kopieren
3. Produkt erstellen:
   - Linkes Menü → „Produktkatalog" → „Produkt hinzufügen"
   - Name: „Bewerbercheck-Pro Monatsabo"
   - Preis: 29€, wiederkehrend, monatlich
   - Price ID kopieren (`price_...`)
4. Webhook einrichten (nach dem Deployment, in Teil 3)

---

## Teil 2: GitHub einrichten

1. Gehen Sie zu **github.com** → Kostenloses Konto erstellen
2. „New repository" → Name: `bewerbercheck-pro` → „Create repository"
3. Laden Sie alle Projektdateien hoch:
   - Auf Ihrem Computer: Git installieren (git-scm.com)
   - Im Projektordner (PowerShell/Terminal):
     ```
     git init
     git add .
     git commit -m "Initial commit"
     git remote add origin https://github.com/IHR-NAME/bewerbercheck-pro.git
     git push -u origin main
     ```

---

## Teil 3: Railway.app Deployment

1. Gehen Sie zu **railway.app** → „Login with GitHub"
2. „New Project" → „Deploy from GitHub repo"
3. Repository `bewerbercheck-pro` auswählen → Deployment startet automatisch

### Datenbank hinzufügen:
4. Im Railway-Projekt: „New" → „Database" → „Add PostgreSQL"
5. Auf die PostgreSQL-Karte klicken → „Connect" → `DATABASE_URL` kopieren

### Umgebungsvariablen eintragen:
6. Auf die Web-App Karte klicken → Reiter „Variables"
7. Folgende Variablen eintragen (aus Teil 1 gesammelt):

| Variable | Wert |
|---|---|
| `DATABASE_URL` | Von Railway PostgreSQL kopiert |
| `SECRET_KEY` | Zufälliger langer String (z.B. 40 Zeichen) |
| `MAILGUN_API_KEY` | Von Mailgun |
| `MAILGUN_DOMAIN` | Ihre Domain (z.B. bewerbungswandler.de) |
| `MAILGUN_WEBHOOK_SIGNING_KEY` | Von Mailgun |
| `ANTHROPIC_API_KEY` | Von Anthropic |
| `STRIPE_PUBLISHABLE_KEY` | Von Stripe |
| `STRIPE_SECRET_KEY` | Von Stripe |
| `STRIPE_PRICE_ID` | Von Stripe Produkt |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL` | Von Google Cloud |
| `GOOGLE_SERVICE_ACCOUNT_KEY_JSON` | JSON-Inhalt (in einer Zeile) |
| `MAIL_USERNAME` | Ihre Mailgun SMTP E-Mail |
| `MAIL_PASSWORD` | Mailgun SMTP-Passwort |
| `APP_URL` | https://ihre-domain.de |

### Domain verknüpfen:
8. Railway → Ihre App → „Settings" → „Domains" → „Add Custom Domain"
9. Ihre Domain eingeben (z.B. `app.bewerbungswandler.de`)
10. Den angezeigten CNAME-Eintrag bei Hostinger eintragen:
    - Hostinger → Domains → DNS-Einstellungen
    - CNAME: `app` → Wert von Railway

### Stripe Webhook eintragen:
11. Railway zeigt Ihre App-URL → kopieren
12. Stripe Dashboard → „Entwickler" → „Webhooks" → „Endpoint hinzufügen"
13. URL: `https://ihre-domain.de/webhook/stripe`
14. Events: `customer.subscription.created`, `.updated`, `.deleted`, `invoice.payment_failed`
15. Webhook-Signing-Secret kopieren → als `STRIPE_WEBHOOK_SECRET` in Railway eintragen

### Mailgun Webhook:
16. Mailgun → „Sending" → „Webhooks" (nicht nötig – Routen werden automatisch angelegt)

---

## Teil 4: Testen

### Lokaler Test (optional):
```bash
# .env Datei aus .env.example kopieren und ausfüllen
cp .env.example .env

# Docker starten
docker-compose up
```
App erreichbar unter: http://localhost

### Funktionstest:
1. **Registrierung**: http://ihre-domain.de → Registrieren → Einstellungsseite erscheint
2. **E-Mail-Adresse**: Wird auf Einstellungsseite angezeigt (z.B. `firma-abc123@bewerbungswandler.de`)
3. **Google Sheet**: Neues Sheet erstellen → Service-Account-E-Mail als Editor hinzufügen → URL eintragen
4. **Testbewerbung senden**:
   - E-Mail mit PDF-Anhang an die angezeigte Bewerbungsadresse schicken
   - Nach 30 Sekunden: Dashboard prüfen → Bewerbung erscheint mit Score
   - Google Sheet prüfen → neue Zeile erscheint
5. **Stripe-Test**:
   - Checkout starten → Testkarte `4242 4242 4242 4242` (beliebiges Datum/CVC)
   - Abo-Status in Einstellungen: „aktiv"

---

## Kosten pro Monat

| Dienst | Kosten |
|---|---|
| Railway.app (Starter) | ca. 5–10€ |
| Mailgun (bis 1.000 E-Mails) | kostenlos |
| Anthropic Claude | ca. 0,003€ pro Bewerbung |
| Google Sheets API | kostenlos |
| Stripe | 1,4% + 0,25€ pro Zahlung |

**Fazit**: Bei 10 Kunden à 29€ = 290€ Umsatz, ca. 15–20€ Kosten.

---

## Häufige Probleme

**App startet nicht**: Railway → Logs prüfen → meist fehlende Umgebungsvariable

**Google Sheets schreibt nicht**: Service-Account-E-Mail als Editor im Sheet hinzugefügt?

**Keine E-Mails ankommen**: Mailgun-Domain verifiziert? MX-Einträge gesetzt?

**Score erscheint nicht**: Anthropic API Key korrekt? Guthaben vorhanden?
