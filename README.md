# dansk-bogfoering-skill

A [Claude Code](https://claude.com/claude-code) skill for Danish bookkeeping in [Billy](https://www.billy.dk) (Billy API v2). It helps a small Danish business (typically a sole proprietorship or ApS) do the monthly close, learn how its accountant books invoices, and catch the things an accountant would object to.

The skill and its prompts are written in Danish, because the bookkeeping rules, VAT codes and Billy's UI are Danish. The scripts are plain Python.

## What it does

- **Posting proposals (`konter.py`, `laer.py`, `analyse.py`).** Learns the account and VAT code per vendor from the bills your accountant has already approved, then proposes postings for new drafts, with a confidence level (high, medium, low) and warning flags.
- **Shadow mode (`skygge.py`, `backtest.py`).** Logs every proposal, compares it with what the accountant actually booked, and reports accuracy. A back-test mode learns from older bills and tests on newer ones.
- **Duplicate finder (`dublet.py`, `dubletter.py`).** Finds bank drafts that are the same purchase as an approved bill (for example a DKK bank draft against a EUR bill), and merges them safely: attachments are compared by content hash, copied, verified and backed up before the draft is deleted.
- **VAT check (`moms.py`, `ret_moms.py`).** Shows Billy's own VAT return, warns about drafts and missing receipts that would make it wrong, and can correct a VAT code on a single approved bill with backup, a comment and a change log (dry run by default).
- **Accountant-style audit (`regnskabstjek.py`, read-only).** Payments with no matching bank posting, credit notes that do not reference or exceed their invoice or were never sent to the customer, gaps and duplicates in invoice numbers, and approved bills without a receipt. With `--bilagsindhold` it reads the PDFs and flags foreign receipts without the buyer's VAT number, Danish receipts over 3.000 kr without the buyer's name, or with an amount that does not match the bill. With `--straks` it checks small-asset write-off limits (straksafskrivning) per year.
- **Sourced Danish rules (`bogfoering/reference/`).** Invoice requirements, credit notes, reverse charge (KYE/KYU), representation, VAT-exempt costs, VAT return corrections, the bookkeeping act, write-offs. Every rule points at a primary source (retsinformation.dk, info.skat.dk, Erhvervsstyrelsen), and unverified points are marked as such.

## Requirements

- Python 3.10 or newer. The scripts use the standard library only.
- A Billy API token (created in your Billy organisation settings).
- Optional: [PyMuPDF](https://pymupdf.readthedocs.io/) (`pip install pymupdf`) to read the text of PDF attachments. Without it the skill still works, but vendor recognition from invoice PDFs is skipped, and `regnskabstjek.py --bilagsindhold` refuses to run.
- Optional: bank data as JSON files (see "Bank data format") for the payment check in `regnskabstjek.py`.

## Installation

Copy or symlink the `bogfoering/` folder into your Claude Code skills folder.

```
# macOS / Linux
ln -s "$(pwd)/bogfoering" ~/.claude/skills/bogfoering

# Windows (PowerShell, may need developer mode or an elevated shell)
New-Item -ItemType SymbolicLink -Path "$HOME\.claude\skills\bogfoering" -Target "$PWD\bogfoering"
```

Then restart Claude Code. The skill triggers on phrases such as "bogfør", "konter", "månedsluk", "dubletter i Billy" and "momsangivelse". The scripts can also be run directly from `bogfoering/scripts/`.

## Configuration

1. Create the state folder and the shadow-mode marker (see "Safety model"):

   ```
   mkdir -p ~/.bogfoering
   touch ~/.bogfoering/SKYGGEDRIFT
   ```

2. Provide the token, either as an environment variable or in an env file that only you can read:

   ```
   export BILLY_API_TOKEN=<your-token>
   ```

   or put the line `BILLY_API_TOKEN=<your-token>` in a file and point `billy_token_fil` at it. The environment variable takes precedence. The token is never printed.

3. Copy `bogfoering/config.example.json` to `~/.bogfoering/config.json` and edit it. A different location can be set with the environment variable `BOGFOERING_CONFIG`. A missing config file means defaults; a missing token is an error.

| Field | Meaning | Default |
|---|---|---|
| `virksomhed.navn`, `virksomhed.cvr` | Your company. The CVR is ignored when guessing a seller's VAT country, and `--bilagsindhold` looks for the CVR (as VAT number) on foreign invoices and the name on Danish invoices. | empty |
| `tilstand_mappe` | State folder: learned rules, shadow log, cache, backups, change log. | `~/.bogfoering` |
| `billy_token_fil` | Optional env file containing `BILLY_API_TOKEN=`. | none |
| `bank.data_mappe` | Folder with bank JSON files. | `<tilstand_mappe>/bank` |
| `bank.konti` | Maps a Billy account number to the last digits of the bank account, for example `{"5710": "0001"}`. | `{}` |
| `billy_konti` | Account numbers in your chart: `momskonto` (VAT account), `udstyr` (equipment, depreciated), `restaurant` (representation), `smaaanskaffelser` (small assets, written off at once; used by `--straks`). | 5715, 1880, 1660, 1840 |
| `skyggedrift_markoer` | Marker file; while it exists, posting (`konter.py --apply`), approval (`--godkend`) and VAT-code corrections (`ret_moms.py`) refuse to write. | `<tilstand_mappe>/SKYGGEDRIFT` |

Check the vendor list in `bogfoering/scripts/leverandoer.py` (`VENDORS`, `IKKE_REGNING`, `ALIASER`). It is a starting point with common vendors and examples; add your own vendors and adapt the "not an invoice" patterns to your bank's transaction texts.

## Typical use

Run from `bogfoering/scripts/`:

```
python laer.py                       # learn rules from approved bills
python status.py --maaned 2026-09    # overview: drafts, missing receipts, duplicates, VAT deadline
python dubletter.py --fra 2026-09-01 # list duplicate candidates (add --apply for the safe ones)
python konter.py --maaned 2026-09    # posting proposals, logged to the shadow log
python skygge.py                     # accuracy against what the accountant booked
python regnskabstjek.py              # accountant-style audit, read-only
python regnskabstjek.py --bilagsindhold --straks  # also read receipt PDFs and check write-off limits
python moms.py                       # VAT return check
```

## Bank data format

`regnskabstjek.py` can compare Billy payments with bank postings. It reads every `*.json` file in `bank.data_mappe`, in the Enable Banking / PSD2 JSON format. Each file is one account:

```json
{
  "konto": "Example account ...0001",
  "tx": [
    {
      "booking_date": "2026-07-14",
      "credit_debit_indicator": "CRDT",
      "transaction_amount": { "amount": "15000.00", "currency": "DKK" },
      "status": "BOOK"
    }
  ]
}
```

- `konto`: a display name that contains the account's suffix (the value used in `bank.konti`). A file whose `konto` contains none of the configured suffixes is ignored.
- `tx`: a list of PSD2 transactions. `booking_date` (falls back to `value_date`), `credit_debit_indicator` (`CRDT` = money in, `DBIT` = money out), `transaction_amount.amount` and `status` are used. Transactions with status `PDNG` (pending) are skipped.

The skill does not fetch bank data and has no payment functionality. Without `bank.konti`, the payment check is skipped; the credit note and receipt checks still run.

## Safety model

- **Shadow mode first.** While the marker file exists, `konter.py --apply`, `--godkend` and `ret_moms.py --udfoer` refuse to write (`--tving` overrides, only with the owner's explicit go). Housekeeping writes stay allowed: merging duplicate drafts (`dubletter.py --apply`, always with backup and verified attachment copy) and uploading receipts, because they do not change booked figures. The skill proposes, your accountant books, and `skygge.py` measures the difference. Delete the marker only when the accuracy criterion in `SKILL.md` is reached and the business owner agrees.
- **Never bulk-approve.** Approving a draft is bookkeeping. `--godkend` requires explicit ids, and every draft must have lines, an account and VAT code on every line, and an attachment. Bulk `--apply` only touches clean proposals without warning flags.
- **Backups and change log.** Before any write the affected bill and lines are saved to `<tilstand_mappe>/backup/`. Duplicates are removed only after attachments are copied and verified by content hash, and the files are backed up. Corrections to approved bills (`ret_moms.py`) are dry runs by default, leave a comment on the line, are verified afterwards, and are logged to `<tilstand_mappe>/aendringer/`. They are never made in a period whose VAT return is settled.
- **VAT is never filed from here.** The skill checks; you file in TastSelv or through Billy.
- **When unsure, ask.** Unknown vendors, representation, private versus business use and equipment above the write-off limit are flagged and left to a human.

## Tests

```
python -m unittest discover -s bogfoering/scripts -p "test_*.py"
```

The tests need no network and no Billy account.

## Disclaimer

This is not professional accounting, tax or legal advice. The rules in `reference/` were researched from public sources at the time of writing and may be outdated or wrong for your situation; points that could not be verified are marked "ikke verificeret". The posting proposals are statistical guesses based on your accountant's history. Review everything, keep your own backups, and consult your accountant or auditor. You use the software at your own risk (see `LICENSE`). This project is not affiliated with Billy or any of the vendors named in the examples.

## Acknowledgements

Several checks (bilag content against the bill, invoice-number gaps, year-keyed straksafskrivning limits) were inspired by [Rentemester](https://github.com/mikkelkrogsholm/rentemester) by Mikkel Krogsholm (MIT). No code was copied; the ideas were reimplemented in Python for Billy.

## License

MIT, see `LICENSE`.

---

# Dansk

Et Claude Code-skill til dansk bogføring i Billy. Det kan:

- foreslå kontering af kladder ud fra den måde, jeres bogholder tidligere har bogført de samme leverandører (`laer.py`, `konter.py`),
- køre i **skyggedrift**, hvor forslagene logges og sammenlignes med bogholderens faktiske bogføring (`skygge.py`, `backtest.py`),
- finde og rydde dubletter sikkert, med bilagsflyt, kontrol og backup (`dubletter.py`),
- tjekke moms (`moms.py`) og rette en momskode på en bogført regning med backup og ændringslog (`ret_moms.py`),
- lave et bogholder-tjek (`regnskabstjek.py`, kun læsning): betalinger uden bankpostering, kreditnotaer uden henvisning eller ikke sendt, huller i fakturanumre, regninger uden bilag og (med `--bilagsindhold`) udenlandske bilag uden købers momsnummer, danske bilag over 3.000 kr. uden købers navn og bilag med forkert beløb,
- slå op i danske regler med primærkilder (`bogfoering/reference/`).

**Kom i gang:** kopiér eller symlink `bogfoering/` til `~/.claude/skills/`, sæt `BILLY_API_TOKEN` (eller `billy_token_fil` i config), kopiér `config.example.json` til `~/.bogfoering/config.json`, og opret markørfilen `~/.bogfoering/SKYGGEDRIFT`, så skillet ikke kan kontere, godkende eller rette moms i Billy, før I har målt, at forslagene er til at stole på.

**Sikkerhed:** skyggedrift først, aldrig godkendelse i bulk, backup før alle ændringer, ændringslog, og moms indberettes aldrig herfra.

**Bankdata:** valgfrie JSON-filer i Enable Banking/PSD2-format, ét objekt pr. konto med `konto` (visningsnavn med kontoens slutcifre) og `tx` (liste af transaktioner med `booking_date`, `credit_debit_indicator`, `transaction_amount.amount` og `status`). Koblingen fra Billy-kontonummer til slutcifre sættes i `bank.konti`.

**Ansvarsfraskrivelse:** dette er ikke professionel regnskabs-, skatte- eller juridisk rådgivning. Reglerne kan være forældede, og konteringsforslagene er statistiske gæt. Gennemgå alt, og tal med jeres bogholder eller revisor.
