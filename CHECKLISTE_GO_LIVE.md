# Schritt-für-Schritt-Anleitung: Die 4 manuellen Aufgaben vor dem Go-Live

## Was ist das?

Nachdem der Code für die App fertig geschrieben wurde, gibt es 4 Dinge, die **Sie selbst** erledigen müssen, weil sie Ihre persönlichen Firmendaten und geheime Schlüssel betreffen. Hier wird jeder Schritt ganz genau erklärt.

---

## Aufgabe 1: Impressum & Datenschutz mit Ihren echten Firmendaten füllen

### Was muss gemacht werden?
In den Dateien `impressum.html` und `datenschutz.html` stehen Platzhalter wie `[Firmenname eintragen]`. Diese müssen durch Ihre echten Daten ersetzt werden. **Das ist Pflicht in Deutschland** – ohne Impressum darf keine Website online sein.

### So geht's Schritt für Schritt:

**Datei 1: `templates/impressum.html`**

1. Öffnen Sie den Ordner `Bewerbungswandler` auf Ihrem Desktop
2. Gehen Sie in den Ordner `templates`
3. Klicken Sie mit der rechten Maustaste auf `impressum.html`
4. Wählen Sie "Öffnen mit" → "Editor" (oder "Notepad" / "VS Code")
5. Suchen Sie diese Stellen und ersetzen Sie die Platzhalter:

| Platzhalter | Was eintragen? | Beispiel |
|---|---|---|
| `[Firmenname eintragen]` | Ihr Firmenname (oder Ihr Name bei Einzelunternehmen) | `Max Mustermann IT-Services` |
| `[Vorname Nachname]` (2x vorkommend) | Ihr vollständiger Name | `Max Mustermann` |
| `[Straße Hausnummer]` | Ihre Geschäftsadresse | `Musterstraße 12` |
| `[PLZ Ort]` | Postleitzahl und Stadt | `80331 München` |
| `[Telefonnummer]` | Ihre Telefonnummer | `+49 89 12345678` |
| `[E-Mail-Adresse]` | Ihre Kontakt-E-Mail (NICHT die App-E-Mail) | `info@meinefirma.de` |
| `[USt-IdNr.]` | Ihre Umsatzsteuer-ID (falls vorhanden) | `DE123456789` |
| `[Adresse]` | Nochmal Ihre Adresse | `Musterstraße 12, 80331 München` |

6. Speichern mit `Strg + S`

**Datei 2: `templates/datenschutz.html`**

1. Gleicher Ordner (`templates`), Datei `datenschutz.html` öffnen
2. Nur 3 Platzhalter zu ersetzen (ganz oben in der Datei):

| Platzhalter | Was eintragen? | Beispiel |
|---|---|---|
| `[Firmenname]` | Ihr Firmenname | `Max Mustermann IT-Services` |
| `[Adresse]` | Ihre Geschäftsadresse | `Musterstraße 12, 80331 München` |
| `[E-Mail-Adresse]` | Ihre Kontakt-E-Mail | `info@meinefirma.de` |

3. Speichern mit `Strg + S`

**Hinweis:** Falls Sie keine USt-IdNr. haben (z.B. als Kleinunternehmer), löschen Sie den ganzen Abschnitt "Umsatzsteuer-ID" aus der `impressum.html` – also diese 4 Zeilen:
```html
    <h2>Umsatzsteuer-ID</h2>
    <p>
        Umsatzsteuer-Identifikationsnummer gemäß § 27a Umsatzsteuergesetz:<br>
        [USt-IdNr.]
    </p>
```

---

## Aufgabe 2: Open-Graph-Bild erstellen (`og-image.png`)

### Was ist das?
Wenn jemand Ihren Link auf Facebook, LinkedIn oder WhatsApp teilt, wird ein Vorschaubild angezeigt. Ohne Bild sieht der geteilte Link langweilig aus. Mit Bild sieht er professionell aus und wird häufiger angeklickt.

### So geht's:

**Option A: Einfach mit Canva (empfohlen, kostenlos)**

1. Gehen Sie auf **canva.com** und erstellen Sie ein kostenloses Konto (falls noch nicht vorhanden)
2. Klicken Sie auf "Design erstellen"
3. Wählen Sie als Größe: **1200 x 630 Pixel** (das ist die Standard-OG-Größe)
   - Oder suchen Sie nach "Social Media" → "Facebook Post" (ähnliche Größe)
4. Gestalten Sie das Bild:
   - Hintergrund: Dunkelblau oder Lila (passend zur App-Farbe #4f46e5)
   - Text groß: "Bewerbercheck-Pro"
   - Text kleiner: "Bewerbungen automatisch per KI auswerten"
   - Optional: Ein kleines Icon/Symbol
5. Klicken Sie auf "Herunterladen" → Format **PNG** auswählen
6. Speichern Sie die Datei als `og-image.png`

**Option B: Noch einfacher – Screenshot nutzen**

1. Öffnen Sie Ihre fertige App im Browser
2. Machen Sie einen schönen Screenshot der Landing Page
3. Öffnen Sie den Screenshot in Paint (Windows: `Win + S` → "Paint" eintippen)
4. Zuschneiden auf ca. 1200 x 630 Pixel
5. Speichern als `og-image.png`

**Wo muss die Datei hin?**

1. Gehen Sie in den Ordner `Bewerbungswandler` auf Ihrem Desktop
2. Öffnen Sie den Ordner `static`
3. Legen Sie die Datei `og-image.png` dort hinein

Der vollständige Pfad muss sein: `Bewerbungswandler/static/og-image.png`

---

## Aufgabe 3: Plausible Analytics einrichten (optional)

### Was ist das?
Plausible ist ein Statistik-Tool, das Ihnen zeigt, wie viele Besucher Ihre Website hat. Es ist DSGVO-konform (braucht keinen Cookie-Consent) und kostet ca. 9€/Monat. **Diese Aufgabe ist optional** – die App funktioniert auch ohne.

### So geht's (nur wenn Sie Plausible nutzen wollen):

**Schritt 1: Plausible-Konto erstellen**

1. Gehen Sie auf **plausible.io**
2. Klicken Sie auf "Start your free trial"
3. Erstellen Sie ein Konto mit Ihrer E-Mail
4. Fügen Sie Ihre Domain hinzu (z.B. `bewerbercheck-pro.de` oder Ihre Railway-URL)

**Schritt 2: Domain in Railway eintragen**

1. Öffnen Sie **railway.app** in Ihrem Browser
2. Loggen Sie sich ein
3. Klicken Sie auf Ihr Projekt (Bewerbungswandler)
4. Klicken Sie auf den Service (den lila Block)
5. Gehen Sie zum Tab **"Variables"** (Variablen)
6. Klicken Sie auf **"+ New Variable"** (Neue Variable)
7. Tragen Sie ein:
   - **Name:** `PLAUSIBLE_DOMAIN`
   - **Value:** Ihre Domain (z.B. `bewerbercheck-pro.de`)
8. Klicken Sie auf "Add" → dann **"Deploy"** drücken (ganz oben)

**Wenn Sie Plausible NICHT nutzen wollen:**
Sie müssen gar nichts tun. Die Variable bleibt einfach leer und das Analytics-Script wird nicht geladen.

---

## Aufgabe 4: Alle API-Schlüssel rotieren (WICHTIG für Sicherheit!)

### Was bedeutet "rotieren"?
API-Schlüssel sind wie Passwörter für Ihre Dienste. "Rotieren" heißt: alte Schlüssel löschen, neue erstellen, die neuen in Railway eintragen. Das sollten Sie tun, falls die alten Schlüssel irgendwo unsicher gespeichert waren (z.B. mal in einer Chat-Nachricht geteilt).

### So geht's für jeden Dienst:

---

#### 4a) SECRET_KEY (Flask-Geheimschlüssel)

Dieser Schlüssel wird zum Verschlüsseln von Session-Cookies und CSRF-Tokens verwendet.

1. Öffnen Sie die **Windows PowerShell** (Startmenü → "PowerShell" eintippen)
2. Tippen Sie folgenden Befehl ein und drücken Sie Enter:
   ```
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
3. Es erscheint eine lange Zeichenkette wie z.B. `a3f8b2c1d4e5f6...`
4. Kopieren Sie diese Zeichenkette
5. Gehen Sie zu **Railway** → Ihr Projekt → Variables
6. Suchen Sie die Variable `SECRET_KEY`
7. Klicken Sie drauf und ersetzen Sie den alten Wert mit dem neuen
8. Speichern

---

#### 4b) Anthropic API-Key (für die KI)

1. Gehen Sie auf **console.anthropic.com**
2. Loggen Sie sich ein
3. Klicken Sie links auf **"API Keys"**
4. Klicken Sie auf **"Create Key"** (Neuen Schlüssel erstellen)
5. Geben Sie einen Namen ein, z.B. "Bewerbercheck-Pro Produktion"
6. Kopieren Sie den neuen Schlüssel (fängt an mit `sk-ant-...`)
   - **WICHTIG:** Den Key sofort kopieren! Er wird nur einmal angezeigt!
7. Gehen Sie zu **Railway** → Variables
8. Ersetzen Sie den Wert von `ANTHROPIC_API_KEY` mit dem neuen Schlüssel
9. Zurück bei Anthropic: Löschen Sie den alten Key (auf "Delete" / Mülleimer-Symbol klicken)

---

#### 4c) Stripe-Schlüssel (für die Zahlungen)

**Wichtig:** Stripe hat 3 Schlüssel. Alle 3 müssen erneuert werden.

1. Gehen Sie auf **dashboard.stripe.com**
2. Loggen Sie sich ein
3. Klicken Sie oben links auf **"Developers"** (Entwickler) → dann **"API keys"**

**Publishable Key + Secret Key:**
4. Klicken Sie auf **"Roll key..."** neben dem Secret Key
5. Bestätigen Sie
6. Kopieren Sie den neuen **Secret Key** (fängt an mit `sk_live_...`)
7. Kopieren Sie den neuen **Publishable Key** (fängt an mit `pk_live_...`)
8. In **Railway** → Variables:
   - `STRIPE_SECRET_KEY` → neuen Secret Key eintragen
   - `STRIPE_PUBLISHABLE_KEY` → neuen Publishable Key eintragen

**Webhook Secret:**
9. Klicken Sie in Stripe auf **"Webhooks"** (im Entwickler-Menü)
10. Klicken Sie auf Ihren Webhook-Endpoint
11. Klicken Sie auf **"Reveal signing secret"** (Signing-Secret anzeigen)
12. Falls Sie einen neuen Webhook erstellen mussten: Kopieren Sie das neue Secret (fängt an mit `whsec_...`)
13. In **Railway** → Variables: `STRIPE_WEBHOOK_SECRET` → neuen Wert eintragen

---

#### 4d) Mailgun-Schlüssel

1. Gehen Sie auf **app.mailgun.com**
2. Loggen Sie sich ein
3. Klicken Sie rechts oben auf Ihr Profil → **"API Security"**
4. Klicken Sie auf **"Create API Key"** oder "Reset" neben dem bestehenden Key
5. Kopieren Sie den neuen Key
6. In **Railway** → Variables: `MAILGUN_API_KEY` → neuen Wert eintragen

**Mailgun Webhook Signing Key:**
7. Gehen Sie zu **"Webhooks"** in der linken Seitenleiste
8. Der Signing Key steht oben auf der Seite
9. In **Railway** → Variables: `MAILGUN_WEBHOOK_SIGNING_KEY` → Wert eintragen/prüfen

---

#### 4e) Google Service Account Key

Dieser ist am aufwendigsten, aber auch nur nötig, wenn Sie glauben, dass der alte Key kompromittiert ist.

1. Gehen Sie auf **console.cloud.google.com**
2. Wählen Sie Ihr Projekt aus (oben in der Leiste)
3. Klicken Sie links auf **"IAM & Admin"** → **"Service Accounts"**
4. Klicken Sie auf Ihren Service Account
5. Tab **"Keys"** (Schlüssel)
6. Klicken Sie auf **"ADD KEY"** → **"Create new key"** → Format **JSON**
7. Eine JSON-Datei wird heruntergeladen
8. Öffnen Sie die Datei mit dem Editor (Notepad)
9. Kopieren Sie den **gesamten Inhalt** (Strg+A, dann Strg+C)
10. In **Railway** → Variables: `GOOGLE_SERVICE_ACCOUNT_KEY_JSON` → den gesamten kopierten Text eintragen
11. Bei Google: Den alten Key löschen (Mülleimer-Symbol neben dem alten Key)

---

### Nach dem Rotieren: Deploy auslösen

Nachdem Sie alle neuen Keys in Railway eingetragen haben:

1. Gehen Sie in Railway zu Ihrem Projekt
2. Klicken Sie auf **"Deploy"** oder es wird automatisch neu deployed
3. Warten Sie ca. 2 Minuten bis die App neu gestartet ist
4. Testen Sie: Loggen Sie sich ein und prüfen Sie, ob alles funktioniert

---

## Checkliste zum Abhaken

- [ ] Impressum: Alle `[Platzhalter]` in `templates/impressum.html` ersetzt
- [ ] Datenschutz: Alle `[Platzhalter]` in `templates/datenschutz.html` ersetzt
- [ ] OG-Bild: `og-image.png` (1200x630px) liegt in `static/og-image.png`
- [ ] (Optional) Plausible: `PLAUSIBLE_DOMAIN` in Railway gesetzt
- [ ] SECRET_KEY in Railway rotiert
- [ ] ANTHROPIC_API_KEY in Railway rotiert
- [ ] STRIPE_SECRET_KEY + STRIPE_PUBLISHABLE_KEY in Railway rotiert
- [ ] STRIPE_WEBHOOK_SECRET in Railway geprüft/rotiert
- [ ] MAILGUN_API_KEY in Railway rotiert
- [ ] MAILGUN_WEBHOOK_SIGNING_KEY in Railway geprüft
- [ ] (Optional) GOOGLE_SERVICE_ACCOUNT_KEY_JSON rotiert
- [ ] App neu deployed und Login funktioniert
