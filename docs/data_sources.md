# Data sources

## StatsBomb Open Data

Everything in this section was checked against the source on 2026-11-15
at upstream commit `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`. It
describes that revision only; re-check before relying on it later.

### Location

| Item | Observed |
|---|---|
| Canonical repository | https://github.com/hudl/open-data |
| Former address | https://github.com/statsbomb/open-data, which now redirects (HTTP 301) to the canonical one |
| Default branch | `master` |
| Repository title in its README | "StatsBomb Open Data" |

The project uses the canonical address in every URL and never relies on
the redirect.

### Layout

Confirmed from the repository README and a listing of the `data/`
directory at the pinned commit.

| Upstream path | Content, as described by the upstream README |
|---|---|
| `data/competitions.json` | Competitions and seasons |
| `data/matches/<competition_id>/<season_id>.json` | Matches of one competition-season |
| `data/lineups/<match_id>.json` | Lineups of one match |
| `data/events/<match_id>.json` | Events of one match |
| `data/three-sixty/<match_id>.json` | StatsBomb 360 data, for selected matches only |
| `doc/` | Format documentation as PDF files |

At this commit `competitions.json` lists 80 competition-seasons.

### Terms of use

This is a summary to work from, not legal advice. The linked documents
are authoritative; read them before publishing anything.

Sources, pinned to the commit that was read:

- README: https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/README.md
- User agreement: https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/LICENSE.pdf
  ("StatsBomb Public Data User Agreement", marked "last updated 8 September 2023")

What they say:

| Topic | Requirement | Where |
|---|---|---|
| Licence type | Not an open-source licence. GitHub reports it as "Other". Use is governed by the user agreement. | LICENSE.pdf |
| Permitted purpose | Analysis and research. | Agreement 1.1 |
| Redistribution | The user may not edit, distort, distribute, reproduce, sell, or provide the data to any third party. | Agreement 1.2.1, 7 |
| Commercial use | The data, and analysis derived from it, may not be commercially exploited. | Agreement 1.2.2 |
| Attribution | Published research, analysis, or insights must name StatsBomb as the data source and carry the StatsBomb logo. The README links a media pack for the logo. | README "Terms & Conditions"; Agreement 1.4 |
| Registration | The agreement asks users to register their name and email, and names `www.statsbomb.com/resource-centre` as the place. That address was not opened or checked by this project. | Agreement preamble, 2.2 |
| Warranty | Provided "as is", with no warranty of accuracy, reliability, or completeness. | Agreement 3.2 to 3.4 |
| Ownership | The data remains StatsBomb's property. | Agreement 7 |

### How this project responds

- Raw files stay in `data/raw/`, which Git ignores. They are not
  committed and must not be published.
- Manifests are committed. They hold URLs, hashes, sizes, timestamps,
  and a few identifying fields of the selected match (IDs, names of the
  competition, season, and teams, and the match date). They hold no
  event or lineup content.
- Raw files are stored byte for byte; nothing edits them.
- No analysis has been published, so no attribution has been needed yet.

### Unresolved

Nothing below has been verified. None of it is settled by this
document, and nothing here is a legal assurance.

- **Registration.** No registration has been made by or for this
  project. The address the agreement names was not checked: whether it
  still works, redirects elsewhere, or offers a registration process at
  all is unknown. Do not treat it as a working registration procedure.
- **Who the agreement is with.** The agreement names StatsBomb Services
  Ltd and the former repository address. The repository now sits under
  the `hudl` organisation. Whether the same agreement still applies
  unchanged was not investigated.
- **Redistribution.** The agreement forbids providing the data to third
  parties. Whether the identifying match fields in a committed manifest
  count as data in that sense is undecided. Decide before this
  repository is shared or made public.
- **Commercial use.** The agreement forbids commercial exploitation of
  the data and of analysis derived from it. What counts as commercial
  for this project's possible future uses has not been assessed.
- **Attribution materials.** The media pack link in the upstream README
  was not opened or checked.
