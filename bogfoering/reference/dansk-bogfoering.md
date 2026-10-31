# Dansk bogføring og moms: arbejdsregler

Kort udgave til brug under bogføringen. Hver regel peger på en primærkilde. Den fulde research med ordrette citater ligger i `dansk-bogfoering-kilder.md` (læst 31/10-2026).

Forkortelser: ML = momsloven (LBK 209/2024), mbek = momsbekendtgørelsen (BEK 1435/2023), BFL = bogføringsloven (lov 700/2022), JV = Den juridiske vejledning (info.skat.dk), LL = ligningsloven.

**"Ikke verificeret"** betyder, at der ikke er fundet en primærkilde. Gæt ikke. Spørg ejeren eller revisor, eller marker det.

## 1. Bilag og fakturakrav

- **Fuld faktura** (mbek § 58) indeholder:
  - dato og fortløbende nummer;
  - sælgers CVR;
  - begge parters navn og adresse;
  - ydelsens art og omfang;
  - momsgrundlag, sats og momsbeløb.
- **Udenlandsk sælger med omvendt betalingspligt** skal desuden have købers momsnummer og teksten "reverse charge" på fakturaen (mbek § 59).
- **Købers CVR kræves ikke** på en dansk faktura efter momsreglerne, kun købers navn og adresse (mbek § 58, stk. 1, nr. 4). BEK 1383 § 1 afgør kun, hvilke købs- og salgsbilag der skal opbevares digitalt (dem med navn, adresse og CVR på begge parter); den gør ikke CVR til et krav på fakturaen.
  - Om virksomheden er omfattet af pligten til digital opbevaring, afhænger af omsætningen, se afsnit 8.
  - **Praksis (ikke lovkrav):** bed gerne om en ny faktura, hvis købers CVR mangler. Mange bogholdere ønsker det, og det gør bilaget robust.
- **Forenklet faktura:** tilladt ved højst 3.000 kr. pr. leverance (mbek § 66). Om beløbet er inkl. eller ekskl. moms, er ikke verificeret. En registreret køber kan altid forlange en fuld faktura.
- **Hvad der ikke er bilag nok:**
  - **Ordrebekræftelse:** ikke en faktura (SKM2013.881.BR).
  - **Kontoudtog:** opfylder ikke kravet alene (SKM2021.692.LSR).
  - **Betalingskvittering:** duer kun, hvis den opfylder kravene til en (forenklet) faktura. Det er udledt, ikke verificeret som selvstændig regel.
- **Bilag efter BFL § 9:** skal vise transaktionsdato og beløb, og registreringen skal henvise til bilaget.

## 2. Kreditnota (salg)

- **Hvornår:** kreditnota skal udstedes ved returvarer og ved prisafslag efter fakturering (ML § 52 a, stk. 5). En faktura annulleres med en kreditnota til kunden, ikke internt (JV A.B.3.3.1.4).
- **Indhold:** samme formkrav som en faktura, plus henvisning til den oprindelige fakturas dato og nummer (JV A.B.3.3.1.2).
  - **I Billy:** opret altid ud fra fakturaen (`creditedInvoiceId`), med samme konto, momskode og valuta.
- **Moms:** salgsmomsen nedsættes kun, hvis kreditnotaen angiver momsen (ML § 27, stk. 4).
- **Udsendelse:** kreditnotaen skal sendes til køber (JV D.A.8.1.1.4). En kreditnota, der kun ligger i Billy, er ikke nok.
- **Periode:** behøver ikke være samme momsperiode som fakturaen (SKM2021.376.SR). Praksis er reguleringen i den periode, kreditnotaen udstedes og bogføres i.
- **Øredifferencer (fx 0,09 kr.):** der er ingen regel om at afskrive små differencer i stedet for en kreditnota. Brug en kreditnota med henvisning, eller lad det være et debitorspørgsmål. Påstå aldrig en bagatelgrænse.

## 3. Køb af ydelser fra udlandet (omvendt betalingspligt)

- **Hvem betaler momsen:** Virksomheden beregner og fradrager selv momsen, når en udenlandsk sælger leverer ydelser. Det gælder både for EU- og ikke-EU-sælgere (ML § 46, stk. 1, nr. 3; JV D.A.13.2.2.3).
- **Hvor det angives:**

  | Sælger etableret i | Billy-kode | Rubrik A-ydelser | Feltet "moms af ydelseskøb i udlandet" |
  |---|---|---|---|
  | Andet EU-land | **KYE** | ja, værdien uden moms (mbek § 79, stk. 3) | ja |
  | Uden for EU | **KYU** | nej, rubrik A er kun for EU (mbek § 79, stk. 1 og 3) | ja (mbek § 76, stk. 6) |

- **Hvad der afgør det:** hvor det udstedende selskab er etableret, dvs. hjemsted eller fast forretningssted. Hverken momsnummeret eller teksten "reverse charge" afgør det (JV D.A.13.2.2.3). En postadresse alene gør det ikke (SKM2024.510.SR). Læs selskabsnavn og adresse øverst på fakturaen.
- **Vurdering 31/10-2026 (ikke afgjort af skat.dk):**
  - OpenAI fakturerer fra "OpenAI OpCo, LLC, San Francisco" med EU OSS-nummer. Anthropic fakturerer fra "Anthropic, PBC, San Francisco" med det irske momsnummer IE4276970QH.
  - Begge er amerikanske selskaber, altså **KYU**.
  - Begge vurderinger er udledt af fakturaens selskabsnavn og adresse plus etableringsreglen. Hvilke selskaber der fakturerer danske kunder, og at et "EU"-præfiks hører til ikke-EU-ordningen (non-Union OSS), er IKKE VERIFICERET mod en primærkilde (se `dansk-bogfoering-kilder.md`, Uafklaret). For Anthropic er et irsk fast forretningssted ikke udelukket.
  - Momsen netto er 0 kr. uanset hvad. Kun rubrik A-ydelser påvirkes.
- **Forskellen fra Google Ads:** Google Ireland Limited er et irsk selskab, altså **KYE**.

## 4. Repræsentation og restaurant

- **Moms:** moms af repræsentation, underholdning og gaver kan ikke fradrages. Men 25 % af momsen af restaurationsydelser kan, når udgiften er strengt erhvervsmæssig (ML § 42, stk. 1, nr. 5 og stk. 2). Billy-kode **KR** (6,25 %).
- **Skat:** repræsentation fradrages med 25 % af udgiften (LL § 8, stk. 4). Den ikke-fradragsberettigede moms indgår også kun med 25 % (JV C.C.2.2.2.14).
- **Bilaget:** skal vise, hvem der deltog, og hvorfor (JV C.C.2.2.2.5.4). Bed ejeren om det, før kladden konteres.

## 5. Momsfrie udgifter (KF)

- **Momsfrie (ML § 13, stk. 1):**
  - bankgebyrer, betalinger og overførsler (nr. 11 c);
  - forsikring (nr. 10);
  - personbefordring, fx DSB og bus i rutekørsel (nr. 15);
  - post omfattet af befordringspligten (nr. 13).
- **Forsikringsafgift:** er en punktafgift, ikke moms (JV E.A.6.1.5).
- **Taxi og Uber:** ikke verificeret.

## 6. Fejl i momsangivelsen

- **Åben periode:** ret bogføringen før angivelsen. En indberetning kan rettes samme dag frem til kl. 16.
- **Afregnet periode:**
  - Ret angivelsen i TastSelv Erhverv. Juridisk er det en anmodning om genoptagelse (JV A.A.8.3.1.3).
  - Fristen er 3 år fra angivelsesfristen (SFL § 31, stk. 2). Der er ikke fundet nogen beløbsgrænse for rettelser.
  - Ret aldrig bare bogføringen i en afregnet periode uden også at rette angivelsen (se SKILL.md, regel 11).
- **Ikke verificeret:** at små fejl må rettes i næste angivelse. Antag rettelse af den berørte periode.

## 7. Betalinger og afstemning

- **Dokumentation:** hver registrering skal kunne dokumenteres ved bilag og have et kontrolspor (BFL §§ 8-9).
- **Afstemning:** registreringer afstemmes med likvidbeholdningerne i det omfang, det er nødvendigt. Det skal senest ske ved fristen for momsangivelsen (BFL § 11, stk. 2).
- **Vores praksis:** se `laerte-regler.md`, regel 1, og `regnskabstjek.py`.
  - En betaling bogføres kun mod en bankpostering, på den konto pengene lander: bankkontoen eller betalingsudbyderens konto.

## 8. Bogføringsloven

- **Opbevaring:** 5 år fra udgangen af regnskabsåret (BFL § 12).
- **Digitalt bogføringssystem:** pligten gælder fra regnskabsåret 2026 for personligt ejede virksomheder med en nettoomsætning over 300.000 kr. i hvert af de to foregående år (BEK 297/2025; BFL § 16). Bilag skal opbevares digitalt i systemet (BEK 1383).
  - Tjek hvert år omsætningen i de to foregående år mod grænsen. Fakturaer minus kreditnotaer ekskl. moms i Billy er et praktisk overslag; den præcise definition af nettoomsætning er ikke undersøgt her.
  - Om Billy er registreret hos Erhvervsstyrelsen som digitalt bogføringssystem, er ikke verificeret.
- **Rettidighed:** transaktioner registreres "snarest muligt" (BFL § 7). Erhvervsstyrelsen skriver, at virksomheder som udgangspunkt bør tilstræbe at registrere inden for løbende måned.

## 9. Straksafskrivning

- **Grænser:** 36.000 kr. i 2026 og 34.400 kr. i 2025, ekskl. fradragsberettiget moms (JV C.C.2.4.2.4.2.5). Stemmer med `momskoder.md`.
- **Samlesæt:** aktiver, der bruges samlet, tæller som ét driftsmiddel.
- **Software:** kan ikke straksafskrives for anskaffelser fra 1/1-2025.
