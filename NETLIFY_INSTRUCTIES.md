# accountRADAR v2.0.0 op Netlify zetten (met login)

**Belangrijk verschil met eerdere versies:** tot en met v1.6.0 kon je gewoon een
map naar Netlify slepen ("Deploy manually"). Dat werkt vanaf v2.0.0 niet meer,
omdat de site nu ook server-functies (Netlify Functions) bevat die eerst
"gebouwd" moeten worden (o.a. het bcrypt-pakket voor veilige wachtwoorden
installeren). Daarvoor moet Netlify gekoppeld worden aan een plek waar de
bestanden staan — meestal GitHub. Dat klinkt technischer dan het is: hieronder
staat elke stap, en je hebt geen terminal of programmeerkennis nodig.

---

## Stap 1 — GitHub-account en repository

1. Ga naar https://github.com en maak een gratis account (als je die nog niet hebt).
2. Klik rechtsboven op "+" → "New repository".
3. Geef een naam, bijvoorbeeld `accountradar`. Kies "Private" (niet verplicht,
   maar verstandig — dan kan niemand anders de broncode zien). Klik "Create repository".
4. Je komt op een lege repository-pagina. Klik op de link **"uploading an existing file"**
   (staat op die pagina).
5. Sleep **alle bestanden en mappen uit deze `netlify_package_v2`-map** naar het
   upload-vlak: `index.html`, `manifest.json`, `service-worker.js`, `icon-192.png`,
   `icon-512.png`, `package.json`, `netlify.toml`, en de hele map `netlify` (met
   de map `functions` erin). GitHub ondersteunt het slepen van hele mappen.
6. Onderaan de pagina: klik "Commit changes" (de standaardtekst mag blijven staan).

Je hebt nu een GitHub-repository met de volledige site erin.

## Stap 2 — Netlify koppelen aan deze repository

Als je al een bestaande Netlify-site hebt (van v1.6.0, via drag-and-drop):
1. Ga naar die site in het Netlify-dashboard → "Site configuration" → "Build & deploy"
   → "Link repository" (of "Link site to Git" — de exacte tekst kan iets verschillen).
2. Kies GitHub, log in/geef toestemming, en selecteer je `accountradar`-repository.
3. Netlify herkent automatisch de instellingen uit `netlify.toml` (build-commando
   `npm install`, functions-map, etc.) — je hoeft daar niets voor in te vullen.

Heb je nog geen Netlify-site: ga naar https://app.netlify.com → "Add new site" →
"Import an existing project" → GitHub → selecteer de repository. Netlify herkent
de instellingen automatisch.

Netlify start nu een eerste "deploy" (dat duurt typisch 1-2 minuten). Zodra die
groen/klaar is, is je site live op hetzelfde `.netlify.app`-adres als voorheen
(of een nieuw adres, als dit een nieuwe site is).

## Stap 3 — Environment variables instellen (de "geheimen")

Ga naar je site in Netlify → "Site configuration" → "Environment variables" →
"Add a variable". Zet deze drie erin:

| Naam | Waarde |
|---|---|
| `SESSION_SECRET` | Een lange, willekeurige tekst — bijvoorbeeld gegenereerd via https://1password.com/password-generator/ (kies 40+ tekens, mag alles bevatten). Gebruik deze **nergens anders**. |
| `GOOGLE_PLACES_API_KEY` | Je bestaande Google Places API-sleutel (dezelfde die eerder in `CONFIG.GOOGLE_PLACES_API_KEY` in de HTML stond). |
| `SETUP_SECRET` | Nog een lange, willekeurige tekst, alleen voor eenmalig gebruik in Stap 4 hieronder. |

Na het toevoegen van variabelen: ga naar "Deploys" → klik "Trigger deploy" →
"Deploy site" om de site opnieuw te bouwen met deze instellingen.

## Stap 4 — Testgebruikers aanmaken (eenmalig)

Open in je browser, **één keer**, de volgende link (vervang de twee onderdelen
tussen `<...>`):

```
https://JOUW-SITE.netlify.app/.netlify/functions/setup-users?secret=<JOUW_SETUP_SECRET>
```

Bij succes zie je iets als `{"ok":true,"created":["testgebruiker1","testgebruiker2","testgebruiker3"]}`.

De drie testaccounts zijn:

| Gebruikersnaam | Wachtwoord |
|---|---|
| `testgebruiker1` | `Radar4721!` |
| `testgebruiker2` | `Kompas3098#` |
| `testgebruiker3` | `Anker6650@` |

Deze staan hardcoded in `netlify/functions/setup-users.js` — pas dat bestand aan
(en roep de link opnieuw aan) als je andere namen/wachtwoorden wilt, of vervang
ze zodra de echte klantaccounts er zijn (dat komt in een latere fase, met een
beheerpagina). Bewaar deze wachtwoorden op een veilige plek (wachtwoordmanager) —
ze staan verder nergens leesbaar opgeslagen.

## Stap 5 — Testen

Ga naar je site-URL. Je zou nu eerst een inlogscherm moeten zien. Log in met een
van de testaccounts hierboven. Test ook "Nieuwe bedrijven vinden" — dat moet nu
via de server werken zonder dat je ergens een sleutel hoeft in te vullen.

---

## Daarna: updates doorvoeren

**Specifiek voor de update naar v4.1.0:** geen nieuwe environment variables.
Upload de bijgewerkte `index.html` en `beheer.html`, en de nieuwe
`netlify/functions/admin-delete-user.js` (plus de aangepaste `_auth.js`,
`login.js` en enkele andere Functions), en trigger een nieuwe deploy. Geen
nieuwe setup-link nodig.

**Specifiek voor de update naar v4.0.0 (beheerpagina):** de bestaande
environment variables blijven allemaal ongewijzigd — geen nieuwe nodig. Wel:
1. Upload alle bestanden (inclusief het nieuwe `beheer.html` en de nieuwe
   bestanden in `netlify/functions/`) naar je GitHub-repository.
2. Trigger een nieuwe deploy.
3. Open **eenmalig** de volgende link om het beheeraccount aan te maken:
   `https://JOUW-SITE.netlify.app/.netlify/functions/setup-admin?secret=JOUW_SETUP_SECRET`
   (zelfde SETUP_SECRET als bij de testgebruikers). Dit maakt het account
   `basiser` aan met het wachtwoord dat in dit gesprek is afgesproken.
4. Ga naar `https://JOUW-SITE.netlify.app/beheer` en log in met dat account.
5. **Verstandig om direct te doen:** wijzig via "Wachtwoord resetten" bij je
   eigen account meteen het wachtwoord naar iets dat alleen jij kent — het
   wachtwoord dat nu in dit gesprek is afgesproken, heeft in de chatgeschiedenis
   gestaan en is dus niet meer als geheim te beschouwen.

**Specifiek voor de update naar v3.2.0:** ook dit is een pure HTML-update
(geen nieuwe Functions, geen nieuwe environment variables, geen nieuwe
setup-link nodig). Alleen `index.html` uploaden en opnieuw deployen.

**Specifiek voor de update naar v3.1.0:** dit is een pure HTML/tekst-update
(geen nieuwe Functions, geen nieuwe environment variables). Upload alleen het
nieuwe `index.html` naar je GitHub-repository (overschrijft het bestaande
bestand) en trigger een nieuwe deploy. Geen setup-link nodig, saldi blijven
ongewijzigd.

**Specifiek voor de update naar v3.0.0 (tokensysteem):** de environment
variables van Fase 1 (`SESSION_SECRET`, `GOOGLE_PLACES_API_KEY`,
`SETUP_SECRET`, `BLOBS_SITE_ID`, `BLOBS_TOKEN`) blijven ongewijzigd — die
hoef je niet opnieuw in te stellen. Wel nodig:
1. Upload alle bestanden uit deze nieuwe `netlify_package_v3`-map naar je
   GitHub-repository (overschrijft de bestaande bestanden, inclusief de
   nieuwe map `netlify/functions/token-*.js` en `_tokens.js`).
2. Trigger een nieuwe deploy (Deploys → Trigger deploy → Deploy site).
3. Open opnieuw de setup-users-link
   (`.../.netlify/functions/setup-users?secret=...`). Dit zet de drie
   testgebruikers terug naar hun startwaarden: testgebruiker1 onbeperkt,
   testgebruiker2 en testgebruiker3 met 250 tokens. **Let op:** als je al met
   deze accounts had getest, wordt hun eventueel gewijzigde/verbruikte saldo
   hierdoor teruggezet naar 250.
4. Log in en controleer bovenaan de zijbalk of het saldo zichtbaar is
   (oneindig-teken bij testgebruiker1, "250 tokens" bij de andere twee).

Voor toekomstige aanpassingen (nieuwe versie van `index.html`, of wijzigingen
aan de Functions): vervang de bestanden in je GitHub-repository (via dezelfde
"upload files"-knop, of door het bestaande bestand te openen en te bewerken via
het potloodje-icoon op GitHub). Netlify bouwt dan automatisch een nieuwe versie.
Een map slepen naar Netlify werkt dus niet meer als update-methode.

## Eigen domeinnaam (optioneel, ongewijzigd)

Ga in het Netlify-dashboard naar je site → "Domain settings" → "Add a domain" en
volg de stappen om je eigen domeinnaam te koppelen.
