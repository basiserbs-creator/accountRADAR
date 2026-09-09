# accountRADAR — changelog

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
