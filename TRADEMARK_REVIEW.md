# Name and logo review

Review date 2026-11-04. The screening covers Germany and the EU, with
additional market-use leads. The current products are a cryptography library,
a downloadable password manager and a Firefox extension.

## Names

| Finding | Evidence and relevance |
| --- | --- |
| **CryptoCore**, EU word mark **017604976** | DPMAregister showed the mark as registered on 2026-11-04, held by secunet Security Networks AG, with expiry recorded as 2027-12-15. It covers Nice classes 9, 38, 42 and 45. The goods and services include downloadable software, authentication software, information security and data encryption. The initial C/K spelling difference offers little phonetic separation from KryptoCore, and the software overlap is concrete. [DPMA record](https://register.dpma.de/DPMAregister/marke/registerHABM?AKZ=017604976&CURSOR=1) · [EUIPO record](https://euipo.europa.eu/eSearch/#details/trademarks/017604976) · [secunet product use](https://www.secunet.com/fileadmin/user_upload/01_Seitencontent/Produkt-_und_Serviceseiten/Industry/Downloads/secunet_edge_extended_Datenblatt_V2.pdf) |
| **CRYPTOCORE**, EU mark **000436675** | DPMAregister reported the registration as expired. The live secunet registration is the more immediate issue. [DPMA record](https://register.dpma.de/DPMAregister/marke/registerHABM?AKZ=000436675&CURSOR=0) |
| **Tuxera CryptoCore** | Tuxera markets a cryptography library under this name. NIST independently identifies the product and vendor. This is a commercial-use lead in the same field. The sources cited here do not establish its territorial registration status. [Tuxera product material](https://www.tuxera.com/app/uploads/2025/05/Tuxera_TCPIP_overview_datasheet_public_20250519.pdf) · [NIST product entry](https://csrc.nist.gov/projects/cryptographic-algorithm-validation-program/details?product=18594) |
| **KryptoCoreLabs** and **KryptoCore Vault** | Both retain KryptoCore as the recognizable leading element. Treat both as affected by the CryptoCore result. |
| **Vault** | IBM/HashiCorp uses Vault for secrets-management software and identifies Vault and its stylized triangle in its trademark policy. DPMA searches with the owner terms `HashiCorp` and `IBM` and classes 9/42 returned no hits for those exact filters. That narrow result does not settle protection elsewhere or under other owner names. [HashiCorp trademark policy](https://www.hashicorp.com/en/trademark-policy) |

DPMAregister searches used `?ryptocore?` and `?rypto?core?` in the mark
field, with German, EU and international records selected. Both returned
the two EU records above. DPMA describes this as a database search and
directs users to EUIPO and WIPO for broader coverage and current status.
[DPMA search guidance](https://www.dpma.de/marken/markenrecherche/index.html)

## Artwork

The reviewed Core emblem uses a stylized K over an orange orb with orbital
paths and a hexagonal frame. The Labs version adds a flask, and the Vault
version adds a lock and safe-door elements. The toolbar SVG uses a cyan
lock inside a polygon. These compositions look different from HashiCorp's
Vault triangle in its published branding. The lock, shield, polygon and
orbit motifs are common elements. Visual inspection of these examples
does not establish figurative-mark clearance. The word mark issue persists
when the name appears as part of a graphic. [HashiCorp product branding](https://www.hashicorp.com/en/brand/hcp-brand-logos)

Two additional DPMAregister searches restricted results to active filings
or registrations in Nice classes 9 or 42. The Vienna combination
`14.05 26.05` returned Alchemy Manager (IR 1596893), a yellow cloud and
control-dial logo for learning software. The combination
`01.05 26.05 27.05` returned IR 1641352, IR 1819361 and IR 1868129.
Visual comparison found the closest motif in **COMSPOC** (IR 1868129).
It combines a globe, a broken orbit and a hexagon. Its black-and-white
design and word element differ from the K emblems, and its German
class 42 protection concerns satellite and space-object software.
These were targeted classification searches. [Vienna Classification](https://nivilo.wipo.int/pdf/eng/vienna/vie10eng.pdf) · [Alchemy Manager](https://register.dpma.de/DPMAregister/marke/registerir?AKZ=1596893) · [IR 1641352](https://register.dpma.de/DPMAregister/marke/registerIR?AKZ=1641352&CURSOR=0) · [IR 1819361](https://register.dpma.de/DPMAregister/marke/registerIR?AKZ=1819361&CURSOR=1) · [COMSPOC](https://register.dpma.de/DPMAregister/marke/registerIR?AKZ=1868129&CURSOR=2)

| Reviewed file | SHA-256 |
| --- | --- |
| Core emblem, including the copy in the public Core checkout | `52d1d0e866da390b83d7066d799b0a81914bd0285b8f8b235df295946b7338b5` |
| Labs emblem | `642a2a87d0078d353470e4adbc0924011d337f89f0654c2ce0da42e12386dd1e` |
| Vault emblem | `4379f4d62986c9ad233351067825160239a9ea2a2f77272040684474f8e46100` |
| Vault Firefox toolbar SVG | `65c95ca05cac2b57bb23bd3b541ed4175079dd2de6f12779c7c2abb5ceb11a4c` |

The three emblem images were provided by the project owner. The toolbar SVG
was authored for the add-on. Retain the original artwork, creation records
and any applicable rights grants before treating the assets as cleared.
Image-similarity clearance across TMview and WIPO, and a review of relevant
unregistered uses, are still open. Start image searches with Nice classes
9 and 42 and the Vienna categories for celestial objects, locks, polygons
and stylized letters. [EUIPO image search](https://www.euipo.europa.eu/en/news/ai-at-euipo-in-house-image-search-in-tmview-extended-to-all-tm5-offices) · [WIPO Global Brand Database](https://www.wipo.int/en/web/global-brand-database)

## Release decision

Hold new public releases under the current branding pending a review of
EU mark 017604976 or clearance of a different name. Include the existing
GitHub and AMO listings in that review. Preserve local development and
review packages while the naming decision is open.
