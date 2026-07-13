# OSF registration hand-off

Registration actions that require the account holder's approval are not
automated. Local preparation continues without blocking on these steps.

## Project record

Use this exact title:

> Eye of Poirot – Sanction-exposure metrics for FIFA World Cup disciplinary
> records, 2014–2026

## Public registration

Create a private OSF project, then upload only:

- `docs/METHODOLOGY.md`;
- `output/pdf/METHODOLOGY-v0.2.pdf`;
- `data/MANIFEST-sha256-2026-07-13.txt`.

Create an **Open-Ended Registration** from those files, make the registration
public, and self-approve the pending registration if OSF asks. Record the DOI
in `CITATION.cff` and both README files after it resolves.

## Embargoed reproducibility snapshot

In a separate component, upload the complete derived-data snapshot, draft
figures, and current pipeline. Do **not** upload `data/raw/`, downloaded working
XLSX files, browser exports, or private correspondence.

Create a registration of that component with a four-year embargo and
self-approve it if required. Record its DOI after it resolves. During review or
outreach, share only an OSF view-only link; test the link in a signed-out
browser before sending it.

## Manual checklist

- [ ] Confirm the account name and contributor order.
- [ ] Confirm that the public registration contains only the three frozen files.
- [ ] Confirm that no raw snapshot or personal email appears in either upload.
- [ ] Approve the public registration and copy its DOI.
- [ ] Approve the four-year embargoed registration and copy its DOI.
- [ ] Test the view-only link while signed out.
- [ ] Add both DOIs to `CITATION.cff`, `README.md`, and `README.zh-CN.md`.
