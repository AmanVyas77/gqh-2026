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

**Reporting update, 4 October 2026.** The supplemental A + overlay development drawdown is now corrected to **20.6%**, directly rounded from saved fraction 0.2064627979599919. Section 4 adds an explicitly prospective, post-evaluation governance assessment; the full four-scenario matrix is in [`../review/risk_methodology_assessment.md`](../review/risk_methodology_assessment.md). Reference [14] now points to the packaged artifact verifier. No strategy results or decisions changed. The PDF was rebuilt with the existing bundled ReportLab runtime and visually checked.

**Rebuilding** needs ReportLab and the macOS Arial fonts the renderer loads (not part of
`../requirements.txt`): `python paper/build_note.py` from `cattle_crush/`. Browser printing of the HTML
is not the verified build path. Relocated prose and the editorial history are in
[`../review/editorial_revision/EDITORIAL_NOTES.md`](../review/editorial_revision/EDITORIAL_NOTES.md).

**Funding sensitivity addition:** Section 4 now includes a joint A/B finding explicitly labeled exploratory and post-hoc. Its qualitative direction is independently supported by the packaged minimum NAV/margin ratios; no dated private scratch data, strategy changes or claims of control effectiveness were added. The holdout-access qualification moved to Section 1 and remains intact.
