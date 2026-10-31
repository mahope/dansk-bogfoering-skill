# Årsafslutning: plan for en senere skill/agent

Status: **plan, ikke bygget.** Byg den, når skyggedriften har vist ≥ 95 % træfsikkerhed på løbende kontering (se SKILL.md). Første år bør resultatet gennemgås af en revisor før indberetning.

## Typiske rammer (enkeltmandsvirksomhed, tjek jeres egne)

- Enkeltmandsvirksomhed beskattes efter **de almindelige regler** (overskud = personlig indkomst, AM-bidrag). Der er ingen pligt til at indsende årsrapport til Erhvervsstyrelsen, men et skattemæssigt regnskab skal kunne dokumenteres, og tallene indberettes på **den udvidede selvangivelse** (oplysningsskemaet). Fristen er normalt 1. juli (ikke verificeret her; tjek skat.dk).
- Moms halvårlig: H2 indberettes senest 1. marts.
- Nogle banker kan automatisk overføre en andel af indbetalinger til en separat momskonto. Overførslerne skal gå i nul mellem kontiene i bogføringen.
- Kørselsgodtgørelse samles typisk og bogføres i december.

## Tjekliste, som agenten skal gennemføre (read-only analyse, mappe til ejer/revisor)

1. **Løbende bogføring ajour** pr. 31/12: `status.py` uden udgiftskladder, alle bilag på plads, `dubletter.py` tom.
2. **Bankafstemning** pr. 31/12 for hver bankkonto: saldo i Billy = saldo i banken.
3. **Moms H2** afstemt (`moms.py`) og momskontoens saldo = skyldig moms.
4. **Debitorer:** ubetalte salgsfakturaer pr. 31/12 (indtægt tæller i faktureringsåret).
5. **Kreditorer/periodisering:** årsabonnementer betalt i året for næste år. Små beløb periodiseres normalt ikke, revisor afgør grænsen.
6. **Anlægsaktiver:** køb over straksafskrivningsgrænsen (2026: 36.000 kr. ekskl. moms) på saldoen, afskriv op til 25 % (ikke verificeret her; tjek afskrivningsloven og jeres revisor). Under grænsen = straksafskrivning (konto 1840).
7. **Kørselsgodtgørelse:** bogfør årets kørselsregnskab (km × årets sats) som udgift/godtgørelse.
8. **Repræsentation:** kun 25 % fradrag (skat) og 25 % af momsen (KR).
9. **Private andele:** telefon, internet, computer, hjemmekontor. Fastsæt privat andel eller bekræft, at der ikke er nogen.
10. **Skattemæssigt resultat** → felterne i oplysningsskemaet (omsætning, vareforbrug, øvrige omkostninger, afskrivninger, resultat).
11. **Overvej virksomhedsordning/kapitalafkastordning** ved et større overskud. Det er et revisorspørgsmål, ikke agentens beslutning.

## Byggesten der mangler

- Saldobalance fra Billy-API'et (undersøg `/accounts` + balance-endpoints eller Billys rapport-eksport).
- Bankudtog som CSV eller JSON for alle konti.
- En skabelon for "årsafslutningsmappe": saldobalance, afstemninger, noteliste, forslag til oplysningsskema.
