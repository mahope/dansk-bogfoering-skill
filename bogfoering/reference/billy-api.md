# Billy API — faldgruber (verificeret oktober 2026)

Base `https://api.billysbilling.com/v2`, header `X-Access-Token`. Klient: `scripts/billy.py`.

- **Betalinger:** `GET /bankPayments?minEntryDate=…` ignorerer filteret og returnerer ALLE betalinger siden 2020. Filtrér på `entryDate` lokalt (verificeret 30/10-2026). `cashSide: debit` på en bankkonto = penge ind. Annullerede betalinger har `isVoided: true`.
- **Fakturaer:** `creditedInvoiceId` på en kreditnota kan pege på fakturaer fra før 2025. Hent hele historikken, før en kreditnota kaldes forældreløs.
- **Vedhæftninger:** `GET /attachments?ownerId=<id>` ignorerer filteret og returnerer ALLE vedhæftninger i organisationen. Brug `?ownerReference=bill:<id>`.
- **Upload:** `POST /files` med rå bytes, `Content-Type` og `X-Filename` → `files[0].id`. Derefter `POST /attachments {"attachment":{"ownerReference":"bill:<id>","fileId":…}}`.
- **Fil-indhold:** `GET /files/<id>` → `downloadUrl` (offentlig, tidsbegrænset). Filer er uforanderlige → caches i `<tilstand_mappe>/cache` (standard `~/.bogfoering/cache`).
- **Linjer:** `GET /billLines` kræver `?billId=` (uden giver HTTP 400). `PUT /billLines/<id>` giver **HTTP 500**. Opdatér konto/moms gennem regningen: `PUT /bills/<id> {"bill":{"lines":[{"id":<linje-id>,"accountId":…,"taxRateId":…,"amount":…,"description":…,"quantity":1}]}}` — linje-id bevares (verificeret på en kladde og nulstillet igen).
- **Godkend:** `PUT /bills/<id> {"bill":{"state":"approved"}}`. Slet kladde: `DELETE /bills/<id>` (kun kladder).
- **Bankkladder** har `origin: api`, `isBare: true`, `contactId: null` og rå banktekst i `lineDescription`. Linjen har `accountId: null`, `taxRateId: null`.
- **Regninger fra bilagsindbakken** (scannet af Billy) har ofte bare "Software" som beskrivelse og UUID-filnavne — leverandøren findes kun i PDF'en.
- **Valuta:** `amount` er i regningens valuta; `exchangeRate` omregner til DKK. Bank trækker typisk 0,3–1,5 % mere end Billys kurs (kortgebyr).
- **Momsangivelse:** `GET /salesTaxReturns` (alle perioder, også korrektioner) og `GET /salesTaxReturns/<id>` → `report` med Billys beregnede rubrikker. Flere returns for samme periode = korrektioner (`correctionNo`).
- **Fakturaer (salg):** `GET /invoices` — `amount` ekskl. moms, `grossAmount` inkl.
