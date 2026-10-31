# Lærte regler

Hver gang en bogholder, revisor eller SKAT retter noget, eller I selv finder en fejl, bliver det en regel her. Reglen får en test eller et tjek, så fejlen fanges næste gang. Formålet er, at skillet bogfører lige så rigtigt som en erfaren bogholder. Rettelser er træningsdata, ikke et argument for at stoppe.

Filen indeholder først en skabelon og derefter de generelle lærdomme, som skillet er bygget på. Tilføj jeres egne poster nederst.

## Skabelon

Kopiér blokken, giv den et løbenummer og udfyld den.

```
## N. Kort titel på reglen

- **Dato og kilde:** hvornår, og hvem der påpegede fejlen (bogholder, revisor, SKAT, jer selv).
- **Hvad gik galt:** konkret, med bilags-, faktura- eller betalings-id'er (ikke personoplysninger).
- **Reglen:** hvordan det gøres rigtigt.
- **Tjek:** hvilken test eller hvilket script i `scripts/`, der fanger fejlen.
- **Status:** åben, rettet fremover eller rettet bagud.
```

Når en bogholder eller revisor sender en liste med rettelser, bliver hvert punkt én post plus ét tjek (i `regnskabstjek.py` eller som en test i `test_regnskabstjek.py`).

---

## 1. Kortbetalinger bogføres på betalingsudbyderens konto, ikke banken

- **Hvad gik galt:** Et fakturasystem bogførte alle indbetalinger på bankkontoen. Kortbetalinger går via en betalingsudbyder (fx Stripe), så der kom aldrig en tilsvarende postering i banken. Bogholderen annullerede betalingerne én for én.
- **Reglen:** En betaling bogføres på den konto, pengene faktisk lander på. Kort via betalingsudbyderen går på udbetalingskontoen hos udbyderen. Udbetalingen til banken er en overførsel mellem de to konti, og udbyderens gebyr bogføres på en gebyrkonto. Bankoverførsler går på bankkontoen.
- **Tjek:** `regnskabstjek.py`, "betaling uden bankpostering". Med `--med-annullerede` fanger det også gamle, annullerede betalinger, og det beviser, at tjekket virker.
- **Status:** Rettes ved kilden i det system, der opretter betalingerne (kortbetalinger skal pege på betalingsudbyderens konto). Betalinger fra før rettelsen flyttes manuelt.

## 2. Et bilag er selve fakturaen med køberen på

- **Hvad gik galt:** Leverandørens fakturaer havde køberens navn og adresse, men intet CVR. Tidligere var skærmbilleder, kvitteringer og ordrebekræftelser blevet lagt som bilag.
- **Reglen:** Bilaget skal være fakturaen fra sælger. Den skal have køber (navn; på udenlandske fakturaer også momsnummer, mbek § 59), dato, fakturanummer, varebeskrivelse og moms eller "reverse charge". CVR på danske fakturaer er praksis, ikke lovkrav. Mangler det, bed leverandøren om at genudstede fakturaen. Se `dansk-bogfoering.md`, fakturakrav.
- **Tjek:** `regnskabstjek.py --bilagsindhold` (momsnummer på udenlandske, navn på danske over 3.000 kr., og beløbet). Bogførte regninger helt uden bilag fanges altid.
- **Status:** Løbende. Bed leverandører med automatisk fakturaudsendelse om at bruge det rigtige CVR.

## 3. Find den faktura, der passer til netop den bankpostering

- **Hvad gik galt:** To abonnementer hos samme leverandør kostede det samme og blev fornyet med få dages mellemrum. Fakturaen fra den seneste fornyelse lignede den rigtige til den tidligere bankpostering, men hørte til den næste.
- **Reglen:** Match på fakturadato (±1-2 dage) og beløb, og tjek, hvilken konto eller hvilken mailadresse fakturaen hører til. Ens beløb er ikke nok, når der findes to abonnementer.
- **Tjek:** Manuelt ved upload. Automatisk bilagshentning skal matche på dato og ikke kun på beløb.
- **Status:** Løbende.

## 4. `/bankPayments` ignorerer datofilter

- **Hvad gik galt:** En analyse brugte `minEntryDate` på `/bankPayments` og fik alle betalinger tilbage.
- **Reglen:** Hent alle betalinger og filtrér på `entryDate` lokalt. Samme fælde som `?ownerId=` på `/attachments`. Står også i `billy-api.md`.
- **Tjek:** `regnskabstjek.py` filtrerer lokalt.
- **Status:** Rettet.

## 5. Momskode for udenlandske ydelser afgøres af sælgers etablering

- **Hvad gik galt:** Et irsk (IE) eller EU OSS-momsnummer på en faktura blev behandlet som tegn på et EU-køb (KYE). Men et amerikansk selskab med et EU-momsnummer er stadig et selskab etableret uden for EU, og så er det KYU.
- **Reglen:** Læs det udstedende selskabs navn og adresse øverst på fakturaen. Er selskabet etableret i et andet EU-land, bruges KYE med rubrik A-ydelser. Er det etableret uden for EU, bruges KYU. Momsnummeret afgør det ikke. Se `momskoder.md` og `dansk-bogfoering.md`, afsnit 3.
- **Tjek:** Manuelt ved kontering. `analyse.foreslaa` flager afvigende momsland, men flaget skal læses som et tjek, ikke som en fejl.
- **Status:** Dokumenteret.

## 6. Kreditnotaer skal pege på den faktura, de krediterer, og sendes til kunden

- **Hvad gik galt:** Kreditnotaer var oprettet uden henvisning til den oprindelige faktura og lå kun i Billy.
- **Reglen:** En kreditnota oprettes altid fra den oprindelige faktura (`creditedInvoiceId`). Den har samme konto, samme momskode og samme valuta, er højst på fakturaens beløb og er dateret efter den. Begrundelsen står i teksten, og den logges i ændringsloggen. Kreditnotaen skal også sendes til kunden (JV D.A.8.1.1.4). En kreditnota, der kun ligger i Billy, er ikke nok. Se `dansk-bogfoering.md`, kreditnota.
- **Tjek:** `regnskabstjek.py`, "kreditnota …". Undtagelse: fakturasystemer, der selv sender PDF'er til kunden, står altid som "unsent" i Billy, så tjekket kræver kun afsendelse, når den oprindelige faktura er sendt fra Billy.
- **Status:** Åben, indtil fundene er sendt eller afvist af en person.
