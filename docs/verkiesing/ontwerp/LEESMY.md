# Wyk-soeker — goedgekeurde ontwerp (Piet, 2026-09-15)

Hierdie `.dc.html`-lêers is die mockups wat Piet goedgekeur het ("Love it"). Hulle is statiese HTML met inlyn-style: gebruik hulle as die visuele bron vir die werklike komponente (spasiëring, groottes, rye, volgorde), nie as kode om te kopieer nie. Die werf gebruik Tailwind-tokens uit `app/globals.css`.

| Lêer | Skerm |
|---|---|
| `Main.dc.html` | Tuisblad, rekenaar: soek oop met "Brooklyn"-resultate |
| `SoekFoon.dc.html` | Tuisblad, foon: soek oop |
| `SoekToestande.dc.html` | Soekboks: rustig, ligging besig, ligging geweier, geen resultate, buite 'n wyk, een plek met baie wyke |
| `Wyk.dc.html` | `/wyk/[wykId]`, rekenaar |
| `WykFoon.dc.html` | `/wyk/[wykId]`, foon |
| `Munisipaliteit.dc.html` | `/munisipaliteit/[kode]` |
| `Deelkaart.dc.html` | Open Graph-kaart (1200×630), geen partyname |

Kandidaatname in die mockups is plekhouers (VOORBEELD / PARTY A–F). Die Afrikaanse kopie in die mockups is 'n konsep — Gemini skryf die finale kopie.

## Regstellings op die mockups (2026-09-16)

- **Knoppies is 44 px hoog, nie 32 nie.** Die `.knop`-styl in hierdie lêers is `padding: 8px 16px; font-size: 12px`, wat ~32 px hoog uitkom. Dis te klein vir 'n vinger: die werklike komponente gebruik `min-h-11` (44 px), soos `ovk-aksies.tsx` reeds doen. Die res van die styl bly dieselfde.
- **Die resultate-lys skuif.** Die soek-RPC gee tot 20 rye terug; die mockups wys net 5. Die werklike lys kry 'n maksimum hoogte en skuif binne-in.
- **Koördinate gaan in 'n POST-liggaam**, nie in 'n URL nie, sodat hulle nie in 'n bedienerlog beland nie.
