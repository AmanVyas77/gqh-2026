# Current research note

**Submit this PDF:** [`research_note_edited.pdf`](research_note_edited.pdf): five main pages plus one
references page (references sit outside the track's five-page limit), 11 pt minimum text, one-inch
margins. Authors, in order: Aman Vyas, Zhicheng Li, Nicolas Slenko.

| File | Role |
|---|---|
| `research_note_edited.pdf` | Current note (SHA-256 recorded in `../submission/artifacts.json`) |
| `research_note_edited.html` | Editable source; `../verify_submission.py` checks its numbers against saved tables |
| `build_note.py` | Reporting-only renderer (HTML + `archived_equity.png` to PDF); imports no project code and reads no market data |
| `archived_equity.png`, `archived_equity_relabeled.png` | Archived equity-curve pixels used by the PDF and HTML |
| `verification.json` | Formatting QA recorded when the PDF was built (pages, fonts, text bounds) |

**Superseded notes, do not submit:** `../note/research_note.pdf` (the 4-page note at the freeze) and the
older uploaded `GQH_Research Note.pdf` (not in this repository). The verifier fails if either is put in
place of the current PDF.

**Erratum.** The H1 development table shows 20.7% maximum drawdown for the supplemental "A + overlay, net"
row. The saved fraction is 0.2064627979599919 (`results/tables/variant_a.csv`, run `overlay`, returns
`net`), which rounds to **20.6%** at one decimal; 20.7% came from rounding twice. No registered test,
decision or headline number uses this row. The PDF was not rebuilt in this pass because ReportLab is not
installed here; the erratum is registered in `../submission/claims.json`, and the verifier reports it as
an advisory item and fails on any other mismatch.

**Rebuilding** needs ReportLab and the macOS Arial fonts the renderer loads (not part of
`../requirements.txt`): `python paper/build_note.py` from `cattle_crush/`. Browser printing of the HTML
is not the verified build path. Relocated prose and the editorial history are in
[`../review/editorial_revision/EDITORIAL_NOTES.md`](../review/editorial_revision/EDITORIAL_NOTES.md).
