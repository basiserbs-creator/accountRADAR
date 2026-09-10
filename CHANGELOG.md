# accountRADAR — changelog

## v4.2.0 — 09-09-2026
- **Bugfix:** op het postcodeveld deed de Enter-toets niets (alleen wegklikken uit het veld werkte, via het `change`-event). Enter zoekt nu direct — dit was een echte code-omissie, geen browser- of geolocatie-probleem.
- **Belgische postcodes ondersteund**, via een apart NL/BE-keuzevakje naast het postcodeveld. Nederlandse en Belgische postcodes kunnen namelijk overlappen (bijv. "2100" bestaat in beide landen), dus in plaats van blind te gokken/terugvallen wordt bij "BE" gericht en uitsluitend binnen België gezocht (via Nominatim/OpenStreetMap), en bij "NL" ongewijzigd via PDOK.
- `autocomplete="off"` toegevoegd aan het zoekveld en de vrije-tekst-zoekterm bij prospecting, tegen ongewenste automatisch ingevulde tekst van de browser (bijv. Edge dat een eerder ingelogde gebruikersnaam liet verschijnen in het zoekveld).
- **Beheerpagina:**
  - Nieuw overzicht "Totaal verbruik per gebruiker" boven het activiteitenlog, gebaseerd op het altijd-correcte bijgehouden totaal per gebruiker (niet beperkt tot de laatste 500 logregels).
  - Kolommen in de gebruikerstabel zijn nu ook klikbaar sorteerbaar (zelfde manier als het activiteitenlog al had).
  - Het klantveld bij "Nieuwe gebruiker aanmaken" toont nu suggesties uit bestaande klanten tijdens het typen (een nieuwe klantnaam intypen blijft gewoon mogelijk).

## v4.1.1 — 09-09-2026
- Het zoekvak staat nu bovenaan het blok met de tabs (Account/Merk/Expiratie), waar het inhoudelijk bij hoort, in plaats van in het locatieblok.
- "Zoeken & locatie" heet nu "Locatie-instellingen"; het geneste sub-blokje daarin heet "Geavanceerd" (was ook "Locatie-instellingen", dat gaf dubbele namen).
- Het oogje bij wachtwoordvelden (geïntroduceerd in v4.1.0) is weer verwijderd na voortschrijdend inzicht — veiliger om wachtwoorden nooit zichtbaar te kunnen maken op een gedeeld scherm. Betreft zowel de hoofdtool als de beheerpagina.

## v4.1.0 — 09-09-2026
- **Bugfix:** de cache van eerdere zoekopdrachten naar nieuwe bedrijven (en de negeerlijst) werd gedeeld tussen alle gebruikers op hetzelfde apparaat/browser — dus als gebruiker A zocht, zag gebruiker B op hetzelfde apparaat dezelfde "eerder gevonden"-melding. Beide zijn nu strikt per ingelogde gebruiker gescheiden.
- **1 actieve sessie per account:** een nieuwe login op een ander apparaat/browser maakt een eerdere sessie van datzelfde account direct ongeldig (geverifieerd met een lokale end-to-end test: login A → login B elders → sessie A direct 401).
- **Automatisch uitloggen na 15 minuten inactiviteit** in de pagina zelf (schakel je naar een andere app of tabblad, dan telt de klok gewoon door), met een waarschuwing 1 minuut van tevoren. Bij uitloggen wordt ook meteen de in het geheugen geladen klantdata gewist.
- Oogje toegevoegd aan het wachtwoordveld bij het inloggen (tonen/verbergen), zowel in de hoofdtool als op de beheerpagina.
- **Beheerpagina:**
  - Gebruikers/klanten kunnen nu verwijderd worden (nieuwe Function `admin-delete-user`, met bevestigingsvraag; een beheerder kan zichzelf niet verwijderen).
  - Kopieerknop bij elk getoond gegenereerd wachtwoord.
  - Activiteitenlog: kolommen zijn nu klikbaar sorteerbaar.
  - Datums overal in DD-MM-JJJJ in plaats van de ruwe YYYY-MM-DD-vorm.
  - Uitlijning van de invoervelden in het aanmaakformulier rechtgetrokken (labels van verschillende lengte lieten voorheen de velden verspringen).
- **Technische kanttekening:** "1 sessie per account" vereist dat sessies voortaan bij élke actie live tegen de opgeslagen gebruikersgegevens gecontroleerd worden (1 extra Blobs-leesactie per verzoek) — dit is dus een uitzondering op de eerder afgesproken "optie A" (geen live-controle) voor wachtwoordreset, die zelf ongewijzigd blijft: een reset maakt bestaande sessies nog steeds niet direct ongeldig.

## v4.0.0 — 09-09-2026 (Fase 3 van het beveiligingsplan: beheerpagina)
- **Beheerpagina toegevoegd** op `/beheer`: klanten/gebruikers aanmaken, saldo en billing_mode aanpassen, gebruikers blokkeren/deblokkeren, wachtwoorden resetten, en een activiteitenlog bekijken.
- **Activiteitenlog**: registreert voortaan bij elke afgeschreven actie wie, welke actie, wanneer en hoeveel credits — uitsluitend metadata, nooit de inhoud van Excel-bestanden, zoekresultaten of exports.
- **Accounteinddatum**: een account kan nu een optionele einddatum krijgen. Na die datum (actief tot en met 23:59:59, tijdzone Europe/Amsterdam) kan er niet meer worden ingelogd. Geen einddatum ingesteld = het account blijft actief.
- **Blokkeren**: de beheerder kan een account blokkeren; een geblokkeerd account kan niet meer inloggen totdat het gedeblokkeerd wordt.
- **Bewuste keuze — wachtwoordreset en sessies:** in overleg gekozen voor de eenvoudige variant. Een wachtwoordreset zorgt dat het *nieuwe* wachtwoord nodig is om opnieuw in te loggen, maar een sessie die al actief was (bv. nog ingelogd op een ander apparaat) loopt gewoon door tot die vanzelf verloopt of de gebruiker zelf uitlogt. Bij een sterk vermoeden van misbruik: ook het account blokkeren voor een directer effect.
- Nieuwe Netlify Functions: `admin-list-users`, `admin-create-user`, `admin-update-user`, `admin-reset-password`, `admin-activity-log`, `setup-admin`, en gedeelde helpers `_admin.js`, `_activity.js`, `_accountdate.js`.
- Nieuw bestand `beheer.html`, bereikbaar via de nette URL `/beheer` (via een redirect in `netlify.toml`).
- Fase 3 hiermee afgerond — alle drie de fases uit het oorspronkelijke beveiligingsplan zijn nu gebouwd.

## v3.2.2 — 09-09-2026
- Bugfix: als je op het Merk- of Expiratie-tabblad stond en op "Zoek bedrijven in deze regio" klikte, werden er wel resultaten gevonden maar was je niet op het tabblad waar prospects zichtbaar zijn (Account). De tool schakelt nu automatisch naar Account zodra je een zoekopdracht start.

## v3.2.1 — 09-09-2026
- De kostenmelding bij "Nieuwe bedrijven vinden" vereenvoudigd naar "Dit kost 10 credits plus 2 credits per resultaat." De eerder berekende "maximaal X credits"/"je kunt maximaal Y resultaten ophalen" klopten niet meer zodra caching meespeelde en zijn verwijderd.
- Het veld "Maximaal aantal resultaten" laat nu nooit meer invullen dan je huidige saldo daadwerkelijk toelaat (bijv. bij 100 credits kan er niet meer dan 45 ingevuld worden). Bij onbeperkt saldo blijft de algemene grens van 60 gelden.

## v3.2.0 — 09-09-2026
- Verlopende contracten bekijken kost nu 1 credit per pin die je daadwerkelijk aanklikt op het Expiratie-tabblad (maximaal 1x per contract per sessie), in plaats van in één keer voor alle zichtbare contracten bij het wisselen naar dat tabblad.
- **Bugfix:** postcode invullen had geen effect op de actieradius/prospecting-locatie. De postcode-zoekopdracht gebruikt nu het juiste locatietype (`type:postcode`), met een terugvalzoekopdracht als die niets vindt.
- **Bugfix:** als een identieke zoekopdracht binnen 36 uur uit cache kwam maar je zette het maximum aantal resultaten hoger, werd er niets bijgezocht. Nu wordt alleen het verschil bijgezocht, en ook alleen daarvoor credits gerekend (2 per extra resultaat, geen dubbele basisprijs van 10). Exporteren blijft, zoals altijd, gewoon 1 credit per resultaat kosten, ongeacht of de onderliggende zoekopdracht gratis (cache) of betaald was.
- **Bugfix:** het bestandsveld kon na een herlaad van de pagina nog een oude bestandsnaam tonen, terwijl de data zelf (bewust, om AVG-redenen) niet bewaard blijft. Het veld wordt nu bij elke herlaad leeggemaakt.
- Titels "Bestand" en "Zoeken & locatie" zijn nu net zo vet weergegeven als de andere bloktitels.

## v3.1.0 — 09-09-2026
- Het tegoed heet nu overal "credits" in plaats van "tokens" (in de tool zelf; de Netlify Functions heten intern nog steeds `token-*`, dat ziet de gebruiker niet).
- Een identieke zoekopdracht naar nieuwe bedrijven (zelfde regio + zelfde zoektermen) binnen 36 uur wordt gratis uit cache getoond, zonder opnieuw credits te kosten.
- Overbodige uitleg bij "Nieuwe bedrijven vinden" verwijderd (stond al in het invoerveld zelf).
- "Ingelogd als …" en de uitlogknop netter gestyled (stonden er rommelig/te krap bij).
- De melding "Geen bestand geladen" bovenaan de zijbalk verdwijnt nu totdat er echt een bestand is ingeladen (stond dubbelop met de status onder "Bestand").
- Hint-tekst bij bestand uploaden verkort naar "Werkt ook met bestanden op een netwerkschijf of in de cloud."
- Het "Zoeken"-blok (zoekveld, actieradius, postcode) staat nu onder de tabbladen in plaats van erboven, en is standaard dichtgeklapt.
- Tabvolgorde aangepast naar Account, Merk, Expiratie.

## v3.0.0 — 09-09-2026 (Fase 2 van het beveiligingsplan: tokensysteem)
- **Tokensysteem toegevoegd.** Elke gebruiker heeft een saldo (zichtbaar bovenaan de zijbalk), of `billing_mode: onbeperkt` voor gebruikers zonder saldolimiet.
- Kosten per actie: Excel-bestand koppelen 10 tokens (vast), zoekopdracht naar nieuwe bedrijven 10 + 2 tokens per resultaat (met een instelbaar maximum aantal resultaten en een kostenindicatie vooraf), aanvullingen exporteren 1 token per resultaat, verlopende contracten bekijken (Expiratie-tabblad) 1 token per getoond contract.
- Reserveren-dan-afschrijven: tokens worden vooraf gereserveerd, pas na een succesvolle actie definitief afgeschreven. Bij een fout (bijv. een onleesbaar Excel-bestand of een verlopen sessie tijdens het zoeken) wordt de reservering teruggegeven — geen kosten.
- Niet-afgeronde reserveringen (bijv. door een gesloten browser) worden na 10 minuten automatisch vrijgegeven.
- Bij onvoldoende saldo wordt een actie geblokkeerd met een duidelijke melding. Uitzondering: het bekijken van al lokaal geladen gegevens (het Expiratie-tabblad) wordt nooit geblokkeerd — dat wordt alleen niet als verbruik geregistreerd bij te weinig saldo.
- Nieuwe Netlify Functions: `token-balance`, `token-reserve`, `token-confirm`, `token-release`, en een gedeelde `_tokens.js`-helper.
- **Belangrijke kanttekening (bewust, passend bij deze schaal):** saldo-updates gebeuren als eenvoudige lees-pas aan-schrijf terug, niet met een echte databasetransactie. Bij een paar bekende gebruikers is de kans op een botsing verwaarloosbaar; bij een grotere, drukkere gebruikersgroep zou dit met een "echte" database herzien moeten worden.
- Export en "verlopende contracten getoond" blijven — zoals in het oorspronkelijke plan al benoemd — op vertrouwen geregistreerd: deze gebeuren volledig lokaal in de browser en kunnen door de server niet geverifieerd worden.
- `setup-users.js` uitgebreid: testgebruiker1 = onbeperkt, testgebruiker2 en testgebruiker3 = normaal met een startsaldo van 250 tokens. Bestaande testgebruikers moeten opnieuw via de setup-link aangemaakt worden (dit overschrijft hun saldo en verbruik naar de startwaarden).

## v2.0.0 — 09-09-2026 (Fase 1 van het beveiligingsplan)
- **Login toegevoegd.** De tool is vanaf nu pas bruikbaar na inloggen met een gebruikersnaam en wachtwoord. Wachtwoorden worden veilig gehasht (bcrypt, cost 12) opgeslagen — nooit leesbaar, ook niet voor de beheerder.
- Na 3 mislukte inlogpogingen volgt een blokkade van 10 minuten op dat account.
- **Google API-sleutel niet meer zichtbaar in de browser.** "Nieuwe bedrijven vinden" loopt voortaan via een eigen server-functie (Netlify Function) die eerst controleert of er een geldige sessie is, en pas daarna de sleutel gebruikt — die alleen op de server bekend is via een environment variable.
- Het handmatige API-sleutelveld in de zijbalk is hiermee overbodig en verwijderd.
- Uitlogknop toegevoegd bovenin de zijbalk, met vermelding van de ingelogde gebruiker.
- Dit is Fase 1 van 3 uit het beveiligingsplan. Tokensysteem (Fase 2) en een beheerpagina (Fase 3) volgen later — zie de losse technische opzet hieronder.
- **Belangrijk voor het deployen:** vanaf deze versie moet de site via GitHub aan Netlify gekoppeld worden (niet meer alleen een map slepen) — zie NETLIFY_INSTRUCTIES.md.

## v1.6.0 — 01-09-2026
- "Nieuwe bedrijven vinden" heeft nu een invulveld voor het soort bedrijf. Leeg = de 6 standaard grafische termen; vul je een van die 6 (of een gelijkende term) in, dan wordt alsnog de hele grafische markt gezocht; vul je iets anders in, dan wordt alleen op die term gezocht. Meerdere, komma-gescheiden termen mogen.
- Nieuw postcode-veld (4 cijfers) als alternatief voor de automatische locatiebepaling. Ingevuld: actieradius en prospecting gebruiken die postcode. Leeg: automatische locatie zoals voorheen.
- Volgorde van de tabbladen in de "Jouw aanvullingen"-download omgedraaid: "Nieuwe bedrijven" is nu tabblad 1, "Nieuwe machines" tabblad 2 — handig om de download direct als nieuw bronbestand te hergebruiken.

## v1.5.2 — 01-09-2026
- Scrollen binnen het menu losgekoppeld van het vastgezette menu-paneel zelf (dezelfde soort Safari-eigenaardigheid als eerder, nu ook op deze plek verholpen). Verhelpt: tikken die op de verkeerde knop terechtkwamen, en het niet kunnen dichtklappen van "Locatie-instellingen", op iPhone in liggende stand.

## v1.5.1 — 01-09-2026
- Gedeelde Google API-sleutel centraal ingesteld.
- Het handmatige API-sleutelveld verbergt zichzelf nu automatisch zodra er al een centrale sleutel is ingesteld.

## v1.5.0 — 01-09-2026
- Donker overlay-scherm bij een openstaand mobiel menu verwijderd: de kaart blijft nu altijd volledig bedienbaar (klikken, inzoomen, slepen), ook terwijl het menu openstaat. Sluiten kan via het kruisje of het menu-knopje.
- Menu-knopje op iPhone/iPad in liggende stand hersteld: gebruikt nu een betrouwbaardere schermhoogte-techniek (dvh), zodat de zichtbare positie en de werkelijke klikbare plek weer overeenkomen.

## v1.4.0 — 01-09-2026
- PWA-ondersteuning toegevoegd: via Netlify is de tool nu installeerbaar op telefoon/tablet/laptop met een eigen app-icoon en schermvullende weergave, en blijft gewoon als normale webpagina werken in elke browser.
- Menu-knopje op mobiel/tablet verplaatst, zodat het niet meer over de zoomknoppen van de kaart valt.
- Menu-knopje en de donkere overlay steviger aan het scherm vastgezet, zodat ze niet meer kunnen "verdwijnen" tijdens het pannen/scrollen op de kaart (bekende iOS Safari-eigenaardigheid).
- "Leeslink"-veld verwijderd: Google Drive, SharePoint/OneDrive en Dropbox blokkeren dit soort directe koppelingen technisch (CORS), waardoor het veld in de praktijk nooit werkte. Bestanden van deze diensten kun je gewoon via de normale upload-knop kiezen (werkt ook op iPhone/iPad via de cloud-koppeling in de bestandenkiezer).

## v1.3.1 — 28-08-2026
- Glimworm-effect (pulserende gloed bij contracten die snel aflopen) werkt nu ook betrouwbaar op mobiele Safari/Chrome; gebruikt een robuustere animatietechniek.
- Privacy-balk bovenin de kaart verschoven, zodat deze niet meer over de zoomknoppen van de kaart valt, met een vaste minimumafstand tot het logo.

## v1.3.0 — 28-08-2026
- Uitschuifmenu op smallere schermen (< 1280px breed: telefoons en iPads in beide standen): het menu staat standaard dicht en opent als paneel over de kaart via een knop linksboven.
- Een open pop-up van een account blijft nu staan wanneer je van tabblad wisselt (Account/Expiratie/Merk), in plaats van steeds te sluiten.

## v1.2.1 — 28-08-2026
- AVG/GDPR-tekst verplaatst van de zijbalk naar een doorlopende balk bovenin de kaart, over de volle breedte, met het logo aan de rechterkant.

## v1.2.0 — 28-08-2026
- Logo rechtsboven op de kaart flink vergroot (± 2,5 cm) en verplaatst naar rechts van de tekst, in de hoek.
- "Bestand"-titel verkleind/soberder gestijld, gear-icoontje verwijderd.
- Google API-sleutelblok en Versiegeschiedenis verplaatst naar onderaan de zijbalk, beide klein/onopvallend en standaard dichtgevouwen.
- "Nieuwe bedrijven vinden" staat nu standaard dichtgevouwen bij het opstarten.
- Adres in de pop-up is nu zelf de link naar Apple Kaarten, met kleine iconlinks naar Google Maps en Waze ernaast.

## v1.1.0 — 28-08-2026
- Logo verplaatst naar rechtsboven op de kaart; zijbalk-header is nu een dunne statusregel.
- Google API-sleutelveld verplaatst naar een eigen, standaard dichtgevouwen blokje bovenaan.
- Zoekfunctie ("Zoeken") doorzoekt nu alle klant- en machinegegevens, niet alleen de klantnaam.
- Locatiemarkers verkleind naar het formaat van de prospecting-stipjes.
- Handmatige startlocatie vervangen door automatische geolocatie, gebruikt voor zowel de actieradius als prospecting.
- Prospecting-resultaten worden lokaal gecached per regio (~5 km), zodat eerdere zoekopdrachten ook zonder API-sleutel te bekijken zijn.
- Prospect-popups met compacte iconknoppen (toevoegen / niet meer tonen) en een negeerlijst.
- "Machine toevoegen"-knop nu zichtbaar bij alle accounttypes behalve Customer, alleen op het Merk-tabblad.
- Prospect-resultaten (Google) alleen zichtbaar op het Account-tabblad.

## v1.0.1 — 28-08-2026
- Logo-correctie: kruisdraad-lijnen en de twee "gevonden accounts"-stipjes exact volgens het goedgekeurde ontwerp.

## v1.0.0 — 28-08-2026
- Eerste build.
