# Source documents (docs/)

Primary regulatory texts for the corpus (Topic 8 — AI governance).

| File | Document | Pages | Source | Note |
|------|----------|-------|--------|------|
| `GDPR_2016-679_EN.pdf` | Regulation (EU) 2016/679 (GDPR), full OJ text | 77 | kiowa.tech mirror of OJ L 119, 4.5.2016 | Verified: header reads "REGULATION (EU) 2016/679 … of 27 April 2016". Matches the official Official Journal text. |
| `EU_AI_Act_2024-1689_EN.pdf` | AI Act, **pre-final consolidated** text incl. annexes | 258 | artificialintelligenceact.eu (Future of Life Institute) | ⚠️ Confirmed pre-final: article numbering runs to **Art 85 + lettered articles** (e.g. 28a, 52a). The **final** Regulation 2024/1689 has **113 renumbered** articles. Swap recommended for citation accuracy. |

## Why not EUR-Lex directly?

The official EUR-Lex / europa.eu PDF endpoints were unreachable from the build
environment — every `europa.eu` request returned `HTTP 202 Accepted` with an empty
body (a JavaScript anti-bot challenge that a command-line client cannot pass). The
files above are faithful full-text copies from third-party hosts.

## To get the pristine EUR-Lex OJ PDFs (optional)

Download them in a browser (they work fine interactively):

- AI Act — https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689
- GDPR — https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32016R0679

In this Claude Code session you can also run, e.g.:
`! start "" "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689"`

Then replace the file here, keeping the same name.
