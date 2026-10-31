# Momskoder og konti i Billy

Koderne er Billys standard-momskoder (hentet fra `/taxRates`). Kontonumrene nedenfor er et eksempel fra en Billy-konto, så tjek jeres egen kontoplan (`/accounts`). Kontonumre, som skillet selv bruger, kan sættes i `config.json` under `billy_konti`.

## Købsmoms (bruges på regninger)

| Kode | Billy-navn | Bruges når | Typiske eksempler |
|---|---|---|---|
| **K** | 25 % | Dansk leverandør med dansk moms på fakturaen | Domæner hos danske registrarer, dagligvarer til erhverv |
| **KR** | 6,25 % Repræsentation | Restaurant/forplejning med forretningsforbindelser: kun 25 % af momsen fradrages | Forretningsmiddage |
| **KYE** | 0 % Ydelser EU | Ydelse købt fra virksomhed i et andet EU-land med omvendt betalingspligt. Billy beregner erhvervelsesmoms og fradrag (netto 0) og fylder rubrik A-ydelser | Google Ads (Google Ireland) |
| **KYU** | 0 % Ydelser udland | Ydelse købt uden for EU (fx USA) med omvendt betalingspligt | OpenAI, GitHub, Cursor |
| **KVE** | 0 % Varer EU | Varer fra EU-land (rubrik A-varer) | |
| **KVU** | 0 % Varer udland | Varer/abonnementer uden for EU | Nogle software-abonnementer behandles som varer, tjek med revisor |
| **KOB** | 0 % Omvendt betalingspligt | Indenlandsk omvendt betalingspligt (fx mobiltelefoner/byggeydelser) | Sjælden |
| **KF** | 0 % Momsfri | Momsfri køb: gebyrer, forsikring, offentlig personbefordring | Bankgebyrer, forsikring, tog |

Salgskoder (S, SYE, SYU, SVE, SVU, SOB, SF) bruges på fakturaer, ikke regninger.

**Tommelfingerregel for momskode:** se på *sælgers* momsnummer på fakturaen, ikke jeres eget, som står på alle udenlandske fakturaer til jer.
- Dansk CVR + 25 % moms: K
- Sælger er etableret i et andet EU-land, fx "Google Ireland Limited", og der står "reverse charge": KYE (ydelser) / KVE (varer)
- Sælger er etableret uden for EU (USA osv.): KYU / KVU. Det gælder også, selvom fakturaen viser et IE- eller EU OSS-momsnummer (fx Anthropic, PBC; OpenAI OpCo, LLC).

**Vurdering 31/10-2026, med forbehold:** Anthropic og OpenAI viser et EU-momsnummer på fakturaen (IE… og EU OSS), men det er stadig KYU.
- Sikkerheden er ikke ens for de to:
  - **OpenAI:** stærkest. EU OSS-nummeret hører til ikke-EU-ordningen, og den er kun for virksomheder uden etablering i EU.
  - **Anthropic:** udledt. IE4276970QH er et almindeligt irsk momsnummer, så et fast forretningssted i Irland er ikke udelukket.
- Momsen netto er 0 kr. i begge tilfælde. Kun rubrik A-ydelser påvirkes.
- Afgørende er, hvor det udstedende selskab er etableret. Her er det "Anthropic, PBC" og "OpenAI OpCo, LLC", begge i San Francisco. Momsnummeret afgør det ikke.
- Rubrik A-ydelser gælder kun sælgere etableret i EU, fx Google Ireland Limited, som får KYE.
- Kilderne står i `dansk-bogfoering.md`, afsnit 3.
- `analyse.foreslaa` flager "MOMSLAND … AFVIGER" på IE-numre. Behandl det som et tjek af selskabsnavn og adresse, ikke som en fejl.

## Typiske udgiftskonti

| Nr. | Konto | Typisk indhold |
|---|---|---|
| 1815 | Subscriptions | SaaS/AI-abonnementer |
| 1820 | Website | Domæner, hosting |
| 1250 | Purchase of Services - Other Countries | Udenlandske tjenesteydelser (uden for abonnement) |
| 1630 | Advertising and Marketing | Annoncering |
| 1270 | Other Direct Costs | Viderefaktureret konsulentydelse |
| 1860 | Consultants and Freelancers | Underleverandører |
| 1620 | Transport and Travel | Tog, rejser |
| 1660 | Restaurant | Repræsentation (standardmomskode KR) |
| 1840 | Small Acquisitions | Småanskaffelser under straksafskrivningsgrænsen (2026: 36.000 kr. ekskl. moms; 2025: 34.400 kr. Kilde: dinero.dk/ordbog/straksafskrivning, tjek SKAT ved tvivl) |
| 1880 | Equipment | Udstyr over småaktivgrænsen (afskrives ved årsafslutning) |
| 2320 | Fees | Gebyrer |
| 1430 | Employee Benefits | Personalegoder |
| 1825 | Accounting Software | Regnskabsprogram |
| 1210 | Purchase of Goods | Varekøb |
| 5715 | Momskonto | Momsbetalinger (balance), bruges kun til momsafregning |

`regler.json` (bygget af `laer.py`) er sandheden for, hvilken konto en given leverandør får. Tabellen her er til forståelse.
