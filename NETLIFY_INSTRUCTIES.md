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

Voor toekomstige aanpassingen (nieuwe versie van `index.html`, of wijzigingen
aan de Functions): vervang de bestanden in je GitHub-repository (via dezelfde
"upload files"-knop, of door het bestaande bestand te openen en te bewerken via
het potloodje-icoon op GitHub). Netlify bouwt dan automatisch een nieuwe versie.
Een map slepen naar Netlify werkt dus niet meer als update-methode.

## Eigen domeinnaam (optioneel, ongewijzigd)

Ga in het Netlify-dashboard naar je site → "Domain settings" → "Add a domain" en
volg de stappen om je eigen domeinnaam te koppelen.
