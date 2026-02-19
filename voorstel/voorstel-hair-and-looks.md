# Voorstel: Salonhub → Klaviyo Integratie voor Hair & Looks

## Probleemstelling

Hair & Looks is overgestapt op de Salonhub afspraken-widget. Daardoor is de automatische klantinstroom naar Klaviyo gestopt. Nieuwe klanten die via de widget een afspraak maken of een intentie tonen, komen niet meer in Klaviyo terecht — waardoor e-mailmarketing en opvolgflows stil liggen.

In 2023 bouwde Sven Bakker (Hogans) een vergelijkbare Pilarrr → Klaviyo koppeling (kosten: €2.090). We bouwen nu een eigen, toekomstbestendige oplossing die direct op de Salonhub webhooks aansluit.

---

## Twee Smaken

### Smaak 1: Simpel (Profiel + Lijst)

**Wat het doet:**
- Ontvangt Salonhub webhooks bij nieuwe afspraken/intenties
- Maakt automatisch een Klaviyo profiel aan (email + naam)
- Voegt het profiel toe aan een Klaviyo lijst
- Dagelijkse verwerking om middernacht

**Klaviyo scopes nodig:** `profiles:write`, `lists:write`

**Geschikt voor:** Direct starten met e-mailmarketing, flows triggeren op basis van lijstlidmaatschap.

---

### Smaak 2: Uitgebreid (Profiel + Properties + Events)

**Alles van Smaak 1, plus:**
- Custom profiel-properties in Klaviyo:
  - `salon_naam`, `salon_id` — voor per-vestiging segmentatie
  - `kapper_naam`, `stylist_id` — voor per-kapper personalisatie
  - `is_nieuwe_klant` — om nieuwe vs. terugkerende klanten te onderscheiden
  - `laatste_behandeling` — voor behandeling-specifieke opvolging
  - `campagne_bron` — voor UTM/campagne tracking
- Custom events:
  - `appointmentMade` — klant heeft daadwerkelijk een afspraak gemaakt
  - `appointmentIntention` — klant heeft interesse getoond maar geen afspraak afgerond
- Slimme aggregatie: meerdere intenties + afspraak per dag → 1 profiel-update

**Klaviyo scopes nodig:** `profiles:read/write`, `lists:read/write`, `events:write`

**Geschikt voor:** Geavanceerde segmentatie, abandoned booking flows, per-kapper flows, nieuwe klant welkomstflows.

---

## Hoe Het Werkt (Technisch)

```
Salonhub Widget
    ↓ webhook
FastAPI Middleware (onze server)
    ↓ opslaan
SQLite Buffer
    ↓ dagelijks om middernacht
Processor (filter + merge)
    ↓
Klaviyo V3 API
```

1. Klant maakt een afspraak of toont intentie via de Salonhub widget
2. Salonhub stuurt een webhook naar onze middleware
3. De middleware valideert de webhook (HMAC signature) en slaat de data op
4. Elke nacht om middernacht worden de intenties van de vorige dag verwerkt:
   - Meerdere intenties van dezelfde klant worden samengevoegd
   - Als er een afspraak bij zit → `appointmentMade`
   - Alleen intenties → `appointmentIntention`
5. Het resultaat wordt naar Klaviyo gestuurd

---

## Taakverdeling

| Wie | Taak |
|-----|------|
| **Salonhub** | Webhook configureren + webhook documentatie delen |
| **Kickso** | Klaviyo account setup, lijst aanmaken, API key genereren, flows bouwen |
| **Developer** | Middleware bouwen, deployen, aansluiten op Salonhub + Klaviyo |

---

## Stap 2: Roadmap (Voorbereiding al Ingebouwd)

De middleware is al voorbereid op de volgende uitbreidingen:

- **Per-kapper personalisatie**: Flows in Klaviyo die triggeren op basis van welke kapper de afspraak heeft (bijv. "Jouw kapper Laura heeft een tip voor je")
- **Nieuwe-klant tracking**: Automatisch detecteren of iemand een nieuwe of terugkerende klant is
- **Per-vestiging segmentatie**: Verschillende communicatie per salon-locatie
- **Campagne tracking**: Bijhouden via welk kanaal (Instagram, Google, etc.) klanten binnenkomen

---

## Referentie

De Pilarrr → Klaviyo koppeling die Sven Bakker (Hogans) in 2023 bouwde kostte €2.090. Onze oplossing biedt vergelijkbare functionaliteit met meer flexibiliteit en voorbereiding op toekomstige uitbreidingen.

---

## Volgende Stappen

1. Salonhub deelt webhook documentatie en configureert de webhook URL
2. Kickso levert Klaviyo API key en lijst ID aan
3. Wij passen de middleware aan op het exacte webhook formaat
4. Testen met een paar test-afspraken
5. Live!
