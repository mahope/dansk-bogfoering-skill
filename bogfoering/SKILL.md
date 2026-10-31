---
name: bogfoering
description: Use when doing Danish bookkeeping in Billy (billy.dk) - månedsluk, kontering af kladder, dubletoprydning, manglende bilag, momstjek/momsangivelse, skyggedrift mod en bogholder, eller forberedelse af årsafslutning. Triggers - "bogfør", "konter", "månedsluk", "kladder i Billy", "dubletter i Billy", "moms", "momsangivelse", "manglende bilag", "bogholder", "afstem", "årsafslutning".
---

# Bogføring i Billy

Målet er, at den løbende bogføring kan laves her i stedet for hos en ekstern bogholder. Først i **skyggedrift** (skillet foreslår, bogholderen bogfører, forslagene måles), derefter selvstændigt, når træfsikkerheden er dokumenteret. Årsafslutning og selvangivelse er en separat opgave (se `reference/aarsafslutning.md`).

Skillet er et hjælpeværktøj og ikke bogførings-, skatte- eller revisorrådgivning. Reglerne i `reference/` er læst fra primærkilder, men skal altid kunne verificeres af en fagperson.

Sprog: dansk. Alle scripts ligger i `scripts/` og køres med `python <script>.py` fra den mappe. Al tilstand (regler, skyggelog, cache, backups, ændringslog) ligger i `tilstand_mappe` fra config (standard `~/.bogfoering/`). Billy-token læses fra miljøvariablen `BILLY_API_TOKEN` eller fra `billy_token_fil` og printes aldrig. Config ligger i `~/.bogfoering/config.json` (flyttes med `BOGFOERING_CONFIG`); se `config.example.json`.

## Hårde regler

1. **Skyggedrift er spærret i koden.** Så længe markørfilen (`skyggedrift_markoer`, standard `<tilstand_mappe>/SKYGGEDRIFT`) findes, nægter `konter.py --apply`, `--godkend` og `ret_moms.py --udfoer` at skrive. Skyggedrift spærrer altså kontering, godkendelse og momsrettelser. Oprydning af dubletter (`dubletter.py --apply`) og upload af bilag (`billy.upload_file` + `billy.attach`) er bevidst tilladt i skyggedrift, fordi de ikke ændrer bogførte tal, og fordi dubletoprydning altid tager backup og flytter bilag først (regel 4). Markøren slettes først, når kriteriet nedenfor er nået OG ejeren har sagt go. (`--tving` findes, men må kun bruges efter ejerens udtrykkelige go.)
2. **Godkend aldrig i bulk.** Godkendelse = bogføring. `--godkend` kræver `--id`, og hver kladde skal være kladde, ikke være en ikke-regning, have mindst én linje, konto+momskode på alle linjer og mindst ét bilag.
3. **Bulk-kontering tager kun rene forslag.** `--apply --sikkerhed høj` springer alt over, der har advarselsflag (mulig dublet, mangler bilag, valuta-gæt, afvigende momsland, privat/erhverv, repræsentation). Flaggede kladder konteres kun med eksplicit `--id`.
4. **Slet aldrig uden backup og bilagsflyt.** Dubletter fjernes kun via `dubletter.py --apply` → `dublet.flyt_bilag_og_slet`: bilag sammenlignes på INDHOLD (sha256), kopieres, verificeres, filerne kopieres til `backup/bilag_<id>/`, og først derefter slettes kladden. Kun kladder slettes, aldrig bogførte poster.
5. **"Sikker" dublet** (slås sammen automatisk) = DKK-bankkladde mod bogført EUR/USD-regning med samme genkendte leverandør og ≤ 1,5 % kursafvigelse, eller samme fakturanummer på begge sider. Par i samme valuta med samme beløb er altid "tjek" (kan være to ens køb, fx to togbilletter). Togbilletter, MobilePay, dagligvarer og restauranter er aldrig "sikre".
6. **Disse kladder er ikke regninger** og må hverken konteres som udgift, godkendes eller slettes som dublet. De står i `leverandoer.IKKE_REGNING` og skal tilpasses jeres bank:
   - `Income sorter` = bankens automatiske fordeling af kundeindbetalinger til en moms- og skattekonto (eksempel).
   - `Udtræk …` = privat hævning.
   - `SKATTEKONTOEN`, `SKAT …`, `Gældsstyrelsen` = betalinger til skattekontoen.
   - `STRIPE XXXXXX` = udbetaling (indtægt).
   **`Transfer` er bevidst IKKE med**: en bankoverførsel kan være en udgift (fx en bogholders faktura). Bogholderens opgave er at afstemme ikke-regningerne som overførsler. Spørg bogholderen, før sådanne kladder slettes.
7. **Valuta:** Regninger fra en bilagsindbakke bogføres i EUR/USD med kurs. De er *ikke* "euro læst som kroner". Bankkladden i DKK for samme køb er dubletten.
8. **Moms indberettes aldrig herfra.** Skillet tjekker; ejeren indberetter i TastSelv eller via Billy.
9. **Usikkerhed → spørg, ikke gæt.** Bankkladder i DKK fra en ukendt leverandør får intet forslag (valutaen siger intet om landet). Repræsentation, privat/erhverv, udstyr over småaktivgrænsen og ukendte leverandører markeres og forelægges ejeren.
10. **Bilag skal være selve fakturaen/kvitteringen.** Skærmbilleder, ordrebekræftelser, print af portalsider ("Faktura betalt"-siden), betalingsnotitser ("We charged $10") og mail-gengivelser tæller ikke. Hent PDF'en med sælger, køber (jeres navn og CVR), varebeskrivelse og moms. En betalingskvittering uden varebeskrivelse ("Payment to X") duer kun, hvis leverandøren ikke har en faktura. Læg den rigtige faktura på posteringen, og fjern kun det svage bilag efter backup (`backup/bilag_<id>/`).
11. **Rettelser af bogførte poster kræver ejerens udtrykkelige go, og alt dokumenteres.** Det gælder tydelige fejl med bevis (fx en momskode, der strider mod fakturaen og mod de fleste tilsvarende linjer). Hver rettelse har backup før, en kommentar bagpå linjens beskrivelse i Billy og en post i `<tilstand_mappe>/aendringer/<dato>.jsonl`. Rettelser af momskode på bogførte regninger går kun gennem `scripts/ret_moms.py` (prøvekørsel først, `--udfoer` skriver og kontrollerer bagefter, `--tving` kræves, så længe skyggedrift er aktiv), og aldrig i en afregnet momsperiode (så kræves en korrektion af momsangivelsen). Bogføring (godkendelse) af kladder og deling af en faktura mellem flere linjer/konti kræver stadig, at tvivl forelægges ejeren (regel 9).

## Arbejdsgang: månedsluk (ca. den 5. i måneden)

```
python status.py --maaned 2026-09        # overblik: kladder, manglende bilag, dubletter, momsfrist
python dubletter.py --fra 2026-09-01     # vis dubletkandidater
python dubletter.py --fra 2026-09-01 --apply   # slå de sikre sammen (samme leverandør begge sider)
python konter.py --maaned 2026-09        # konteringsforslag (logges til skyggeloggen)
python regnskabstjek.py --fra 2026-09-01 # det en bogholder ville gøre indsigelse imod (kun læsning)
```
Manglende bilag hentes fra leverandørernes fakturaportaler. Upload med `billy.upload_file` + `billy.attach`.

Rapportér til ejeren: antal kladder pr. kategori, hvad der blev ryddet, hvad der mangler bilag, og konteringer med flag.

## Sådan gøres det rigtigt

Målet er at bogføre lige så rigtigt som en erfaren dansk bogholder. Fagreglerne med kilder står i `reference/dansk-bogfoering.md`. Det, der er lært af rettelser, står i `reference/laerte-regler.md`.

- **Betalinger** bogføres kun mod en bankpostering. Beløb og retning skal være de samme, og datoen højst 3 dage fra.
  - Betalingen bogføres på den konto, pengene lander på: kort via en betalingsudbyder på udbyderens konto og bankoverførsel på bankkontoen.
  - Udbetalinger fra betalingsudbyderen er overførsler. Gebyret går på en gebyrkonto.
- **Kreditnotaer** laves altid ud fra den oprindelige faktura.
  - Samme konto, momskode og valuta.
  - Højst fakturaens beløb, og dateret efter den.
  - Begrundelsen står i teksten, og den logges.
  - Kreditnotaen sendes til kunden.
- **Bilag** er sælgers faktura med jeres navn og CVR (se regel 10). Bilaget skal passe til netop den bankpostering, på dato og beløb.
- **Når nogen retter jer:** hver rettelse fra bogholder, revisor eller SKAT bliver én post i `laerte-regler.md` og ét tjek. Tjekket lægges i `regnskabstjek.py` eller i en test, og `python -m unittest discover -p "test_*.py"` (fra `scripts/`) skal være grøn.

## Skyggedrift mod en bogholder

1. Opret markørfilen (`touch ~/.bogfoering/SKYGGEDRIFT`), så skillet ikke kan kontere, godkende eller rette moms i Billy fra første dag.
2. Kør `konter.py` efter hver månedsluk. Forslagene gemmes i `skygge.jsonl` (første forslag pr. kladde tæller).
3. Når bogholderen har bogført, kør `python skygge.py`: træfsikkerhed og liste over afvigelser.
4. Ved afvigelser: kør `python laer.py` (lærer af de nye bogføringer). Systematiske afvigelser rettes som særregel i `analyse.foreslaa`.
5. **Kriterium for at overtage:** ≥ 95 % helt rigtige (konto OG momskode) over mindst to måneders bogføringer, og ingen afvigelser på momskode for EU/udland. Først derefter må `konter.py --apply` bruges på egne bogføringer, og kun efter ejerens go.

Mål træfsikkerheden uden at vente: `python laer.py --godkendt-foer <dato> --ud regler_backtest.json && python backtest.py --godkendt-fra <dato>`. Reglerne læres kun af regninger før datoen og afprøves på dem, der blev godkendt efter. Backtesten skelner mellem "helt rigtig" og "skattemæssigt korrekt" (samme momsbeløb og fradragstype, men anden konto eller rubrik).

## Kontering: hvad reglerne bygger på

`laer.py` læser alle bogholderens bogførte regninger, finder leverandøren via (1) træningspar fra dubletoprydning, (2) beskrivelsen, (3) teksten i bilagets PDF (kræver den valgfri pakke PyMuPDF), og gemmer mest brugte konto+momskode pr. leverandør i `regler.json` med sikkerhed høj/middel/lav. Ukendte leverandører får en fallback ud fra fakturaens momsland. Se `reference/momskoder.md` for koderne og hvornår de bruges.

Nye leverandører: tilføj en linje i `scripts/leverandoer.py` (banktekst-regex, navn, fakturatekst-regex) og kør `laer.py`. Listen i filen er kun et startpunkt.

## Moms

`python moms.py` viser Billys egen momsangivelse for indeværende/forrige periode (salgsmoms, købsmoms, moms af køb i udlandet, rubrik A/B) og advarer om:
- udgiftskladder i perioden (tæller ikke med i momsen, før de er bogført),
- bogførte regninger uden bilag,
- afregnede perioder, der ikke er markeret betalt.

Frister ved halvårlig afregning: H1 → 1. september, H2 → 1. marts. Tjek altid din egen frist på skat.dk.

## Bankdata (valgfrit, kun læsning)

`regnskabstjek.py` kan sammenligne betalinger i Billy med bankposteringer. Bankdata ligger som JSON-filer i `bank.data_mappe` (Enable Banking/PSD2-format, se README), og koblingen fra Billy-kontonummer til bankkontoens slutcifre står i `bank.konti`. Skillet henter ikke selv bankdata og har ingen betalingsfunktion.

## Filer

| Fil | Formål |
|---|---|
| `config.example.json` | Eksempel på config (virksomhed, tilstandsmappe, token-fil, bankkonti) |
| `scripts/config.py` | Indlæsning af config og token |
| `scripts/billy.py` | API-klient, cache, backup, upload |
| `scripts/leverandoer.py` | Leverandørgenkendelse, ikke-regninger, momsland |
| `scripts/laer.py` | Bygger `regler.json` fra bogholderens bogføringer |
| `scripts/analyse.py` | Konteringsforslag og sammenligning (rigtig / skattemæssigt ens / forkert) |
| `scripts/dublet.py` | Dubletfinder og sikker sammenlægning |
| `scripts/status.py` / `dubletter.py` / `konter.py` / `skygge.py` / `moms.py` / `backtest.py` / `ret_moms.py` | Kommandoer (se ovenfor) |
| `scripts/regnskabstjek.py` + `test_regnskabstjek.py` | Bogholder-tjek: betalinger uden bankpostering, kreditnotaer (også ikke sendt), fakturanumre, regninger uden bilag; `--bilagsindhold` (CVR og beløb på bilaget) og `--straks` (straksafskrivning) |
| `scripts/test_config.py` | Tests af config-indlæsning |
| `reference/dansk-bogfoering.md` | Danske regler (bogføringsloven, fakturakrav, kreditnota, omvendt betalingspligt, repræsentation, fejlrettelse) med kilder |
| `reference/dansk-bogfoering-kilder.md` | Den fulde research bag reglerne: ordrette citater og "ikke verificeret"-liste (læst 31/10-2026) |
| `reference/laerte-regler.md` | Skabelon og generelle lærdomme, hver med et tjek |
| `reference/momskoder.md` | Billys momskoder og typiske konti |
| `reference/billy-api.md` | API-faldgruber |
| `reference/aarsafslutning.md` | Plan for årsafslutnings-agent |
