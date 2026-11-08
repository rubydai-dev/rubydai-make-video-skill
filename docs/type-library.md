# Type library

74 distinctive, licence-clean typefaces and 80 pairings for the TYPE DIRECTION step. The data lives in `references/type-library.json` (read by `deal.py deal type`); this page is the same library for people. Checked 2026-10-16: Fontsource API metadata; Vietnamese coverage, OpenType features and axes read from the font tables (cmap, GSUB, fvar) of the pinned web files (Vietnamese: the Fontsource vietnamese + latin files, weight 400); foundry repositories for local-only fonts; Fontshare licence page for ITF-FFL; full-font features and cap/x-height (OS/2) from the font files; Velvetyne files at pinned GitLab commits; Vietnamese coverage checked 2026-11-05.

How to read it
- **Tiếng Việt**: `verified` = every Vietnamese test letter (Ă Đ Ĩ Ũ Ơ Ư, both cases, and the stacked and dot-below vowels) is in the font's cmap, read from the Fontsource vietnamese + latin web files; `missing` names the absent letters or a missing vietnamese subset (Latin-only lines, or another family for Vietnamese text); `unverified` = a local file not read (render the Vietnamese line on a specimen card first).
- **Features**: OpenType features present in the pinned web files (what will actually render; Fontsource web files keep few). `features_full` in the JSON lists the full font features, available when the full file (`load.full`) is loaded locally. Apply them per role through `features` in the TYPE block (FontFace `featureSettings`).
- **Axes**: variable axes `tag min-max`. `wght` animates through the font weight; any other axis through axis stops (TYPE block `stops`).
- **Load**: `fontsource` = pinned on jsDelivr (`@fontsource/<pkg>@<version>`, variable files from `@fontsource-variable/<pkg>`). `local` = the user downloads the files from the foundry into the project's `fonts/` folder (gitignored); OFL files may travel with the project with their licence file, Fontshare (ITF Free Font License) files are used in the video and never shared, committed or subset.
- Licences: SIL Open Font License 1.1 unless marked ITF-FFL (Fontshare: free for commercial video, no redistribution, no modification). Every font used gets a LICENSES.csv row.
- Sources: independent open foundries (Velvetyne, Collletttivo, The League of Moveable Type, Open Foundry; fonts on the Badass Libre Fonts by Womxn list are marked ♀), quality Google Fonts via Fontsource, and Fontshare where its licence fits.

## Serif: titles, literary, period, luxury

| Font | Foundry / designer | Roles | Character | Axes | Features | Cap / x | Tiếng Việt | Load |
|---|---|---|---|---|---|---|---|---|
| [Fraunces](https://github.com/undercasetype/Fraunces) ♀ | Undercase Type: Undercase Type, Phaedra Charles, Flavia Zimbardi | display, text | serif, old-style, warm, quirky, literary | ital 0-1 opsz 9-144 wght 100-900 SOFT 0-100 WONK 0-1 | liga rvrn | 0.70 / 0.48 | verified | `fraunces@5.3.0` · var `full` |
| [Instrument Serif](https://github.com/Instrument/instrument-serif) | Instrument: Rodrigo Fuenzalida, Jordan Egstad | display | serif, condensed, elegant, editorial, quiet | — | liga | 0.72 / 0.51 | missing (no subset) | `instrument-serif@5.3.0` |
| [DM Serif Display](https://github.com/googlefonts/dm-fonts) | Colophon Foundry: Colophon Foundry | display | serif, high-contrast, luxurious, warm | — | frac liga | 0.66 / 0.48 | missing (no subset) | `dm-serif-display@5.3.0` |
| [Bodoni Moda](https://github.com/indestructible-type/Bodoni) | indestructible type*: Owen Earl | display, text | serif, didone, high-contrast, luxurious, elegant | ital 0-1 opsz 6-96 wght 400-900 | frac liga pnum tnum | 0.75 / 0.46 | missing (no subset) | `bodoni-moda@5.3.0` · var `standard` |
| [Gloock](https://github.com/duartp/gloock) | Duarte Pinto: Duarte Pinto | display | serif, high-contrast, loud, editorial | — | dnom frac liga numr pnum tnum | 0.75 / 0.51 | missing (no subset) | `gloock@5.3.0` |
| [Young Serif](https://github.com/noirblancrouge/YoungSerif) | Bastien Sozeau / noirblancrouge: Bastien Sozeau | display | serif, heavy, warm, friendly, nostalgic | — | calt dnom frac liga lnum numr pnum tnum | 0.75 / 0.50 | missing (no subset) | `young-serif@5.3.0` |
| [Cormorant](https://github.com/CatharsisFonts/Cormorant) | Catharsis Fonts: Christian Thalmann | display | serif, garalde, elegant, romantic, fragile | ital 0-1 wght 300-700 | calt dnom frac liga lnum numr tnum | 0.62 / 0.39 | verified | `cormorant@5.3.0` · var `wght` |
| [Libre Caslon Display](https://github.com/impallari/Libre-Caslon-Display) | Impallari Type: Impallari Type | display | serif, transitional, literary, classic | — | dnom frac liga numr | 0.69 / 0.42 | missing (no subset) | `libre-caslon-display@5.3.0` |
| [Newsreader](https://github.com/productiontype/Newsreader) | Production Type: Production Type | text, display | serif, transitional, editorial, quiet | ital 0-1 opsz 6-72 wght 200-800 | liga pnum tnum | 0.67 / 0.43 | verified | `newsreader@5.3.0` · var `standard` |
| [Imbue](https://github.com/Etcetera-Type-Co/Imbue) | Tyler Finck: Tyler Finck, ETC | display | serif, didone, condensed, fashion, elegant | opsz 10-100 wght 100-900 | dnom frac liga numr | 0.70 / 0.52 | verified | `imbue@5.3.0` · var `standard` |
| [Piazzolla](https://github.com/huertatipografica/piazzolla) | Huerta Tipográfica: Juan Pablo del Peral, HT Fonts | text, display | serif, sturdy, literary, warm | ital 0-1 opsz 8-30 wght 100-900 | calt dnom frac liga numr pnum tnum | 0.64 / 0.48 | verified | `piazzolla@5.3.0` · var `standard` |
| [Sorts Mill Goudy](https://www.theleagueofmoveabletype.com/sorts-mill-goudy) | The League of Moveable Type: Barry Schwartz | text, display | serif, old-style, antique, literary | — | dnom frac liga lnum numr | 0.71 / 0.44 | missing (no subset) | `sorts-mill-goudy@5.3.0` |
| [Redaction](https://www.redaction.us) | Titus Kaphar & Reginald Dwayne Betts project (MCKL): Jeremy Mickel, Forest Young | display, text | serif, degraded, documentary, political, archival | — | frac numr sups | 0.70 / 0.47 | missing (no ƠơƯưẠạẦầẪẫỆệỘộỮữỸỹ) | `redaction@5.3.0` |
| [IBM Plex Serif](https://github.com/IBM/plex) | IBM / Bold Monday: Mike Abbink, Bold Monday | text | serif, slab-ish, technical, neutral | — | dnom frac liga numr | 0.70 / 0.52 | verified | `ibm-plex-serif@5.3.0` |
| [Basteleur](https://gitlab.com/velvetyne/basteleur) | Velvetyne Type Foundry: Keussel | display | serif, blackletter-ish, sinister, folk, handmade | — | case liga ordn ss01 sups | 0.74 / 0.55 | unverified | local |
| [Boska](https://www.fontshare.com/fonts/boska) | Indian Type Foundry (Fontshare): Barbara Bigosińska · [ITF-FFL](https://www.fontshare.com/licenses/itf-ffl) | display, text | editorial, elegant, luxurious, serif | wght 200-900 | case frac liga lnum onum pnum salt smcp tnum | 0.71 / 0.48 | unverified | local |
| [Sentient](https://www.fontshare.com/fonts/sentient) | Indian Type Foundry (Fontshare): Noopur Choksi · [ITF-FFL](https://www.fontshare.com/licenses/itf-ffl) | text, display | editorial, elegant, quiet, serif | wght 200-700 | case dlig frac liga lnum onum salt ss01 ss02 | 0.69 / 0.50 | unverified | local |
| [Chunk Five](https://github.com/theleagueof/chunk) | The League of Moveable Type (Meredith Mandel): The League of Moveable Type (Meredith Mandel) | display | handmade, loud, retro, serif, warm | — | — | 0.70 / 0.50 | missing (no ĨĩŨũƠơƯưẠạẦầẪẫỆệỘộỮữỸỹ) | `chunk-five@5.3.0` |

## Sans and grotesque: text, labels, launches

| Font | Foundry / designer | Roles | Character | Axes | Features | Cap / x | Tiếng Việt | Load |
|---|---|---|---|---|---|---|---|---|
| [Bricolage Grotesque](https://github.com/ateliertriay/bricolage) | Mathieu Triay: Mathieu Triay | display, text | sans, grotesque, quirky, friendly, warm | opsz 12-96 wdth 75-100 wght 200-800 | dnom frac numr pnum tnum | 0.66 / 0.53 | verified | `bricolage-grotesque@5.3.0` · var `standard` |
| [Space Grotesk](https://github.com/floriankarsten/space-grotesk) | Florian Karsten: Florian Karsten | display, text | sans, grotesque, technical, quirky | wght 300-700 | dnom frac liga numr pnum tnum | 0.70 / 0.49 | verified | `space-grotesk@5.3.0` · var `wght` |
| [Syne](https://gitlab.com/bonjour-monde/fonderie/syne-typeface) | Bonjour Monde: Bonjour Monde, Lucas Descroix, George Triantafyllakos | display | sans, wide, artistic, loud, experimental | wght 400-800 | dnom frac liga lnum numr pnum tnum | 0.65 / 0.50 | missing (no subset) | `syne@5.3.0` · var `wght` |
| [Unbounded](https://github.com/googlefonts/unbounded) | NaN: NaN | display | sans, wide, rounded, geometric, futuristic | wght 200-900 | dnom frac liga numr pnum tnum | 0.75 / 0.57 | verified | `unbounded@5.3.0` · var `wght` |
| [Familjen Grotesk](https://github.com/Familjen-Sthlm/Familjen-Grotesk) | Familjen STHLM: Familjen STHLM AB | text, display | sans, grotesque, warm, editorial | ital 0-1 wght 400-700 | calt dnom frac liga numr pnum tnum | 0.65 / 0.50 | verified | `familjen-grotesk@5.3.0` · var `wght` |
| [Schibsted Grotesk](https://github.com/schibsted/schibsted-grotesk) | Bakken & Bæck for Schibsted: Bakken & Bæck, Henrik Kongsvoll | text, label | sans, grotesque, news, neutral | ital 0-1 wght 400-900 | calt dnom frac liga numr pnum tnum | 0.70 / 0.53 | missing (no subset) | `schibsted-grotesk@5.3.0` · var `wght` |
| [Epilogue](https://github.com/Etcetera-Type-Co/Epilogue) | Etcetera Type Co: Tyler Finck, ETC | text, display | sans, grotesque, quirky, editorial | ital 0-1 wght 100-900 | dnom frac liga numr pnum tnum | 0.74 / 0.53 | verified | `epilogue@5.3.0` · var `wght` |
| [Anybody](https://github.com/Etcetera-Type-Co/Anybody) | Etcetera Type Co: Tyler Finck | display | sans, variable-width, kinetic, loud, sporty | ital 0-1 wdth 50-150 wght 100-900 | dnom frac liga numr pnum tnum | 0.68 / 0.59 | verified | `anybody@5.3.0` · var `standard` |
| [Archivo](https://github.com/Omnibus-Type/Archivo) | Omnibus-Type: Omnibus-Type | display, text, label | sans, grotesque, industrial, sporty | ital 0-1 wdth 62-125 wght 100-900 | dnom frac liga numr pnum tnum | 0.69 / 0.53 | verified | `archivo@5.3.0` · var `standard` |
| [League Spartan](https://www.theleagueofmoveabletype.com/league-spartan) ♀ | The League of Moveable Type: Matt Bailey, Tyler Finck | display | sans, geometric, bold, modernist | wght 100-900 | calt frac liga | 0.66 / 0.41 | verified | `league-spartan@5.3.0` · var `wght` |
| [League Gothic](https://www.theleagueofmoveabletype.com/league-gothic) ♀ | The League of Moveable Type: Tyler Finck, Caroline Hadilaksono, Micah Rich | display | sans, condensed, gothic, classic, poster | wdth 75-100 | liga | 0.73 / 0.55 | verified | `league-gothic@5.3.0` · var `standard` |
| [IBM Plex Sans](https://github.com/IBM/plex) | IBM / Bold Monday: Mike Abbink, Bold Monday | text, label | sans, grotesque, technical, neutral | ital 0-1 wdth 75-100 wght 100-700 | dnom frac liga numr | 0.70 / 0.52 | verified | `ibm-plex-sans@5.3.0` · var `standard` |
| [Mona Sans](https://github.com/github/mona-sans) | GitHub: Tobias Bjerrome Ahlin, Github, Degarism Studio, Sebastian Carewe | display, text | sans, grotesque, variable-width, technical | ital 0-1 wdth 75-125 wght 200-900 | dnom frac liga numr pnum tnum | 0.73 / 0.53 | verified | `mona-sans@5.3.0` · var `standard` |
| [Instrument Sans](https://github.com/Instrument/instrument-sans) | Instrument: Rodrigo Fuenzalida, Jordan Egstad | text, label | sans, grotesque, neutral, editorial | ital 0-1 wdth 75-100 wght 400-700 | liga pnum tnum | 0.72 / 0.51 | missing (no subset) | `instrument-sans@5.3.0` · var `standard` |
| [Geist](https://github.com/vercel/geist-font) | Vercel: Andrés Briganti, Mateo Zaragoza, Guillermo Rauch, Evil Rabbit, José Rago, Facundo Santana | text, label | sans, geometric, technical, clean | ital 0-1 wght 100-900 | dnom frac liga numr pnum tnum | 0.71 / 0.53 | verified | `geist@5.3.0` · var `wght` |
| [Host Grotesk](https://fonts.google.com/specimen/Host+Grotesk) | Element Type: Element Type, Doğukan Karapınar, İbrahim Kaçtıoğlu | text, label | sans, grotesque, friendly, clean | ital 0-1 wght 300-800 | calt frac liga | 0.70 / 0.50 | missing (no subset) | `host-grotesk@5.3.0` · var `wght` |
| [Apfel Grotezk](https://www.collletttivo.it/) | Collletttivo: Luigi Gorlero | display | sans, grotesque, quirky, editorial, independent | — | dlig frac ordn sups | 0.65 / 0.50 | missing (no ĨĩŨũƠơƯưẠạẦầẪẫỆệỘộỮữỸỹ) | `apfel-grotezk@5.3.0` |
| [Anton](https://github.com/googlefonts/AntonFont) | Vernon Adams: Vernon Adams | display | sans, condensed, impact, poster, loud | — | dnom frac liga numr | 0.86 / 0.73 | verified | `anton@5.3.0` |
| [Le Murmure](https://gitlab.com/velvetyne/murmure) | Velvetyne Type Foundry: Jérémy Landes (Studio Triple) | display | sans, condensed, editorial, fashion, independent | — | dlig liga lnum onum ordn salt ss01-ss10 titl zero | 0.81 / 0.67 | unverified | local |
| [Clash Display](https://www.fontshare.com/fonts/clash-display) | Indian Type Foundry (Fontshare): Indian Type Foundry · [ITF-FFL](https://www.fontshare.com/licenses/itf-ffl) | display | sans, grotesque, display, bold, contemporary | wght 200-700 | — | 0.67 / 0.49 | unverified | local |
| [Cabinet Grotesk](https://www.fontshare.com/fonts/cabinet-grotesk) | Indian Type Foundry (Fontshare): Indian Type Foundry · [ITF-FFL](https://www.fontshare.com/licenses/itf-ffl) | display, text | editorial, friendly, loud, sans | wght 100-900 | case dlig frac liga salt ss01 ss02 ss03 ss04 ss05 | 0.67 / 0.48 | unverified | local |
| [Ojuju](https://fonts.google.com/specimen/Ojuju) | Ụdị Foundry (Chisaokwu Joboson, Mirko Velimirović): Ụdị Foundry, Chisaokwu Joboson, Mirko Velimirović | display | loud, organic, playful, sans | wght 200-800 | frac pnum tnum | 0.70 / 0.48 | verified | `ojuju@5.3.0` · var `wght` |
| [Recursive](https://fonts.google.com/specimen/Recursive) | Arrow Type (Stephen Nixon): Arrow Type, Stephen Nixon | mono, text, display | cold, handmade, playful, sans, technical | slnt -15-0 wght 300-1000 CASL 0-1 CRSV 0-1 MONO 0-1 | frac pnum | 0.70 / 0.53 | verified | `recursive@5.3.0` · var `full` |
| [Figtree](https://fonts.google.com/specimen/Figtree) | Erik Kennedy: Erik Kennedy | text, label | sans, geometric, friendly, clean | wght 300-900 | dnom frac numr pnum tnum | 0.70 / 0.50 | missing (no subset) | `figtree@5.3.0` · var `wght` |

## Display, script and expressive

| Font | Foundry / designer | Roles | Character | Axes | Features | Cap / x | Tiếng Việt | Load |
|---|---|---|---|---|---|---|---|---|
| [Danfo](https://github.com/Afrotype/danfo) | Afrotype: Afrotype, Seyi Olusanya, Eyiyemi Adegbite, David Udoh, Mirko Velimirović | display | display, signage, loud, playful | ELSH 0-100 | dnom frac numr pnum tnum | 0.72 / 0.50 | verified | `danfo@5.3.0` · var `full` |
| [Climate Crisis](https://kampanjat.hs.fi/climatefont/) | Helsingin Sanomat: Daniel Coull, Eino Korkala | display | display, data-driven, political, documentary | YEAR 1979-2050 | calt dnom frac liga numr | 0.75 / 0.62 | missing (no subset) | `climate-crisis@5.3.0` · var `full` |
| [Bungee](https://github.com/djrrb/Bungee) | David Jonathan Ross: David Jonathan Ross | display | display, signage, urban, loud, vertical | — | vert | 0.72 / 0.50 | verified | `bungee@5.3.0` |
| [Shrikhand](https://github.com/jonpinhorn/shrikhand) | Jonny Pinhorn: Jonny Pinhorn | display | display, script-ish, sweet, playful | — | liga pres | 0.67 / 0.52 | missing (no subset) | `shrikhand@5.3.0` |
| [Tilt Warp](https://github.com/googlefonts/Tilt-Fonts) | Andy Clymer: Andy Clymer | display | display, 3d, rotating, playful | XROT -45-45 YROT -45-45 | — | 0.68 / 0.52 | missing (no đ) | `tilt-warp@5.3.0` · var `full` |
| [Dela Gothic One](https://github.com/syakuzen/DelaGothic) | artakana: artakana | display | display, heavy, gothic, loud | — | dnom frac liga numr pnum tnum | 0.73 / 0.54 | verified | `dela-gothic-one@5.3.0` |
| [Ouroboros](https://gitlab.com/velvetyne/ouroboros) | Velvetyne Type Foundry: Ariel Martín Pérez | display | display, occult, retro, psychedelic, independent | — | calt case dlig liga salt ss01 ss02 ss03 | 0.70 / 0.50 | unverified | local |
| [Trickster](https://gitlab.com/velvetyne/Trickster) | Velvetyne Type Foundry: see the repository | display | display, quirky, fable, handmade, independent | — | calt liga onum ss01-ss06 swsh | 0.76 / 0.58 | unverified | local |
| [Big Shoulders](https://fonts.google.com/specimen/Big+Shoulders) | Patric King (for the City of Chicago): Patric King | display, numerals | brutal, display, industrial, loud | opsz 10-72 wght 100-900 | frac liga | 0.80 / 0.60 | verified | `big-shoulders@5.3.0` · var `standard` |
| [Grenze Gotisch](https://fonts.google.com/specimen/Grenze+Gotisch) | Omnibus-Type (Renata Polastri): Omnibus-Type | display | display, dramatic, occult, retro | wght 100-900 | frac liga lnum pnum tnum | 0.60 / 0.45 | verified | `grenze-gotisch@5.3.0` · var `wght` |
| [Mourier](https://gitlab.com/velvetyne/mourier) | Velvetyne (after Eric Mourier, 1971): Velvetyne (after Eric Mourier, 1971) | display | display, futurist, geometric, retro | — | salt ss01 ss02 ss03 ss04 ss05 | 0.70 / 0.50 | unverified | local |
| [Shantell Sans](https://fonts.google.com/specimen/Shantell+Sans) | Shantell Martin, Arrow Type, Anya Danilova: Shantell Martin, Arrow Type, Anya Danilova | text, display, label | display, friendly, handmade, playful, warm | wght 300-800 BNCE -100-100 INFM 0-100 SPAC 0-100 | frac liga tnum | 0.70 / 0.48 | verified | `shantell-sans@5.3.0` · var `full` |
| [Special Elite](https://fonts.google.com/specimen/Special+Elite) | Astigmatic: Astigmatic · [Apache-2.0](https://cdn.jsdelivr.net/gh/google/fonts@1d0e46c7933245c8180fe83e47917961c913bbdb/apache/specialelite/LICENSE.txt) | label, text | display, nostalgic, raw-print, retro | — | frac liga | 0.35 / 0.26 | missing (no subset) | `special-elite@5.3.0` |
| [Pixelify Sans](https://fonts.google.com/specimen/Pixelify+Sans) | Stefie Justprince: Stefie Justprince | display, label | display, playful, retro | wght 400-700 | frac liga | 0.70 / 0.45 | missing (no subset) | `pixelify-sans@5.3.0` · var `wght` |
| [Monoton](https://fonts.google.com/specimen/Monoton) | Vernon Adams: Vernon Adams | display | display, loud, nostalgic, retro | — | — | 0.81 / 0.70 | missing (no subset) | `monoton@5.3.0` |
| [Caveat Brush](https://fonts.google.com/specimen/Caveat+Brush) | Impallari Type: Impallari Type | accent | script, brush, handmade, warm, energetic | — | dnom frac liga numr | 0.66 / 0.42 | missing (no subset) | `caveat-brush@5.3.0` |
| [Sedgwick Ave Display](https://fonts.google.com/specimen/Sedgwick+Ave+Display) | Pedro Vergani, Kevin Burke: Pedro Vergani, Kevin Burke | accent | script, graffiti, urban, loud, handmade | — | liga | 0.95 / 0.65 | verified | `sedgwick-ave-display@5.3.0` |
| [Yellowtail](https://fonts.google.com/specimen/Yellowtail) | Astigmatic: Astigmatic · [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) | accent | script, retro, signage, americana, warm | — | — | — | missing (no subset) | `yellowtail@5.3.0` |
| [Marck Script](https://fonts.google.com/specimen/Marck+Script) | Denis Masharov: Denis Masharov | accent | script, handwriting, casual, personal | — | — | 0.64 / 0.26 | missing (no subset) | `marck-script@5.3.0` |
| [Kalam](https://fonts.google.com/specimen/Kalam) | Indian Type Foundry: Indian Type Foundry | accent | script, handwriting, marker, friendly | — | liga | 0.74 / 0.53 | missing (no subset) | `kalam@5.3.0` |
| [Mynerve](https://fonts.google.com/specimen/Mynerve) | Carolina Short: Carolina Short | accent | script, handwriting, school, playful | — | calt dnom frac liga numr | 0.67 / 0.42 | verified | `mynerve@5.3.0` |
| [Square Peg](https://fonts.google.com/specimen/Square+Peg) | Robert Leuschke: Robert Leuschke | accent | script, handwriting, fine, elegant, quirky | — | frac liga | 0.60 / 0.26 | verified | `square-peg@5.3.0` |

## Mono: data, code, credits, timestamps

| Font | Foundry / designer | Roles | Character | Axes | Features | Cap / x | Tiếng Việt | Load |
|---|---|---|---|---|---|---|---|---|
| [Major Mono Display](https://github.com/googlefonts/majormono) | Emre Parlak: Emre Parlak | display | mono, display, geometric, futuristic, retro | — | frac liga pnum tnum | 0.70 / 0.70 | verified | `major-mono-display@5.3.0` |
| [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) | JetBrains: JetBrains, Philipp Nurullin, Konstantin Bulenkov | mono | mono, technical, code | ital 0-1 wght 100-800 | calt frac | 0.73 / 0.55 | verified | `jetbrains-mono@5.3.0` · var `wght` |
| [IBM Plex Mono](https://github.com/IBM/plex) | IBM / Bold Monday: Mike Abbink, Bold Monday | mono | mono, technical, neutral | — | dnom frac numr | 0.70 / 0.52 | verified | `ibm-plex-mono@5.3.0` |
| [Space Mono](https://github.com/googlefonts/spacemono) | Colophon Foundry: Colophon Foundry | mono, display | mono, retro, quirky, editorial | — | dnom frac numr | 0.70 / 0.50 | verified | `space-mono@5.3.0` |
| [Martian Mono](https://github.com/evilmartians/mono) | Evil Martians: Roman Shamin, Evil Martians | mono | mono, variable-width, technical | wdth 75-112.5 wght 100-800 | calt dnom frac numr | 0.80 / 0.60 | missing (no subset) | `martian-mono@5.3.0` · var `standard` |
| [Fragment Mono](https://github.com/weiweihuanghuang/fragment-mono) | Wei Huang: Wei Huang, URW Design Studio | mono | mono, grotesque, clean | — | calt frac | 0.70 / 0.52 | missing (no subset) | `fragment-mono@5.3.0` |
| [Commit Mono](https://github.com/eigilnikolajsen/commit-mono) | Eigil Nikolajsen: Eigil Nikolajsen | mono | mono, neutral, technical | — | calt cv01 cv02 cv03 cv04 cv05 cv06 cv07 cv08 cv09 cv10 cv11 ss01 ss02 ss03 ss04 ss05 | 0.70 / 0.54 | missing (no ƠơƯưẠạẦầẪẫỆệỘộỮữỸỹ) | `commit-mono@5.3.0` |
| [League Mono](https://github.com/theleagueof/league-mono) | The League of Moveable Type: Tyler Finck | mono | mono, geometric, editorial | — | case ordn pnum salt ss01 tnum | 0.70 / 0.50 | verified | `league-mono@5.3.0` |
| [Sligoil](https://gitlab.com/velvetyne/sligoil) | Velvetyne (Ariel Martín Pérez): Velvetyne (Ariel Martín Pérez) | mono, display, label | mono, playful, raw-print, retro | — | calt dlig salt ss01 ss02 ss03 ss04 | 0.70 / 0.54 | unverified | local |
| [Geist Mono](https://fonts.google.com/specimen/Geist+Mono) | Vercel: Andrés Briganti, Mateo Zaragoza, Guillermo Rauch, Evil Rabbit, José Rago, Facundo Santana | mono | mono, technical, clean | wght 100-900 | dnom frac numr | 0.71 / 0.53 | verified | `geist-mono@5.3.0` · var `wght` |

## Notes per font

- **Fraunces**: SOFT and WONK axes: the same word goes from crisp to soft; opsz 144 for titles, 9-14 for small lines.
- **Instrument Serif**: a condensed display serif with an italic; large and quiet, one weight.
- **DM Serif Display**: high contrast at large sizes; keep above 48 px at 1080.
- **Bodoni Moda**: opsz 6-96: the didone hairlines stay printable at small sizes.
- **Gloock**: heavy contrast serif for one-word cards.
- **Young Serif**: a sturdy 1970s-flavoured serif; food, craft, children.
- **Cormorant**: very fine at small sizes: titles only, never under 40 px at 1080.
- **Libre Caslon Display**: Caslon for large literary titles.
- **Newsreader**: opsz 6-72: one family from captions to titles.
- **Imbue**: condensed didone with opsz 10-100; tall fashion titles.
- **Piazzolla**: robust text serif with opsz 8-30, good for subtitles on texture.
- **Sorts Mill Goudy**: Goudy revival: intertitles, period letters.
- **Redaction**: sibling packages redaction-10 … -100 are progressively degraded cuts: swap one step per beat for decay or memory.
- **IBM Plex Serif**: with Plex Sans and Plex Mono: one superfamily voice.
- **Danfo**: ELSH axis (element shape) from Lagos bus lettering; animate it on the beat.
- **Bricolage Grotesque**: opsz 12-96 and wdth 75-100: ink traps grow with size.
- **Space Grotesk**: pairs with Space Mono as one voice.
- **Syne**: the weight axis also widens the letters: 800 is a different, wide voice.
- **Unbounded**: wide rounded display for launches.
- **Familjen Grotesk**: calm grotesque with character in a, g and y.
- **Schibsted Grotesk**: newsroom grotesque: labels, lower thirds, legal lines.
- **Epilogue**: squarish grotesque, black weight for posters.
- **Anybody**: wdth 50-150 and wght 100-900: stretch with the music.
- **Archivo**: wdth 62-125: condensed labels and expanded headlines from one file.
- **League Spartan**: geometric display in the Futura tradition.
- **League Gothic**: Alternate Gothic lineage, wdth 75-100: posters, trailers, westerns.
- **IBM Plex Sans**: wdth 75-100 includes the condensed cut.
- **Mona Sans**: wdth 75-125: one family for labels and wide headlines.
- **Instrument Sans**: companion to Instrument Serif; wdth 75-100.
- **Geist**: interface sans for UI hero shots.
- **Host Grotesk**: friendly product grotesque (by Turkish designers Doğukan Karapınar and İbrahim Kaçtıoğlu).
- **Apfel Grotezk**: from the Italian open collective Collletttivo; one latin file carries every glyph.
- **Anton**: trailer caps; track +2-4 % in caps.
- **Climate Crisis**: YEAR axis 1979-2050 melts the letters with Arctic sea-ice data: tie it to a date counter.
- **Bungee**: street signage; has vertical forms (vert).
- **Shrikhand**: Gujarati-lettering-inspired italic display; food, candy, festive.
- **Tilt Warp**: XROT and YROT axes -45..45: turn the letters in fake 3D.
- **Dela Gothic One**: very heavy gothic for impact cards.
- **Major Mono Display**: monospaced geometric display by a Turkish designer; mixed-case forms.
- **JetBrains Mono**: code on screen; tall x-height reads small.
- **IBM Plex Mono**: timestamps, data captions.
- **Space Mono**: retro-futurist mono with character.
- **Martian Mono**: wdth 75-112: monospace that narrows for long data lines.
- **Fragment Mono**: Helvetica-flavoured mono: labels and credits.
- **Commit Mono**: character variants cv01-cv11; one latin file carries every glyph.
- **League Mono**: mono with stylistic set ss01; one latin file carries every glyph.
- **Basteleur**: woodcut-flavoured display for folk tales and horror.
- **Le Murmure**: tall condensed display with ten stylistic sets.
- **Ouroboros**: sinuous 1970s-occult display.
- **Trickster**: mischievous display with swashes.
- **Clash Display**: contemporary display grotesk.
- **Boska**: Sharp contemporary serif with smcp, onum/lnum and tnum. ITF Free Font License: free for video and ads, no redistribution, no modification or subsetting.
- **Cabinet Grotesk**: Grotesk with ss01-ss05. ITF Free Font License (no redistribution, no modification).
- **Sentient**: Calm text serif with onum/lnum. ITF Free Font License (no redistribution, no modification).
- **Big Shoulders**: Condensed industrial sans with opsz 10-72 (display and text cuts in one file); smcp; scoreboards, stencils, signage.
- **Chunk Five**: Ultra-bold slab; one weight; Americana, signage.
- **Grenze Gotisch**: Blackletter hybrid with wght 100-900, readable at title sizes; folk horror and fable titles.
- **Mourier**: Quasi-abstract geometric letters from 1971 with five stylistic sets. Local only.
- **Sligoil**: Mono with huge ink traps in optical cuts (Micro to Big); risograph and zine looks.
- **Ojuju**: Igbo-inspired display grotesk with ink cuts; dtls, tnum.
- **Recursive**: MONO 0-1, CASL 0-1, CRSV, slnt and wght 300-1000: sans to mono and linear to casual in one file; animate MONO or CASL on a beat.
- **Shantell Sans**: Marker handwriting with BNCE (bounce), INFM (informality) and SPAC axes: real hand-made jitter, seeded per glyph through BNCE.
- **Special Elite**: Worn typewriter; dossiers, letters, archival captions. Apache 2.0.
- **Pixelify Sans**: Pixel sans with wght 400-700; game and Y2K looks.
- **Monoton**: Inline neon tube caps; one weight; glow it, never stroke it.
- **Caveat Brush**: a quick brush hand for one or two words over a heavy grotesque.
- **Sedgwick Ave Display**: graffiti hand-style; one word, tucked into a black wide display.
- **Yellowtail**: 1950s sign-painter script; a single word over condensed caps.
- **Marck Script**: a light personal hand; the human note beside an industrial display.
- **Kalam**: felt-marker handwriting (use Bold) for a friendly aside.
- **Mynerve**: a quick school-notebook hand; one word next to a heavy gothic.
- **Square Peg**: a fine, tall casual hand; needs size, never small.
- **Figtree**: clean geometric text face for subtitles and body beside expressive displays.
- **Geist Mono**: the mono for labels and data beside Geist or Bricolage.

## Pairings (dealt by `deal.py deal type`)

Display + text (+ mono); `setup` in the JSON gives tested weights and axis values per role. Each pairing keeps two families at most plus a mono, built on structural contrast with shared proportions (see typography.md §1).

| Pairing | Display | Text | Mono | Purpose | Look families | Why it works |
|---|---|---|---|---|---|---|
| `velvet-noir` | Fraunces | Instrument Sans | IBM Plex Mono | ad, cinematic | glossy-commercial, noir-night, period-classic, realist-cinematic, storybook-handmade | old-style display serif (opsz 144, WONK 1) over a neutral grotesque: contrast of structure, similar x-height |
| `didone-gala` | Bodoni Moda | Schibsted Grotesk | — | ad, cinematic | glossy-commercial, period-classic | hairline didone for the name, a news grotesque for every fact |
| `editorial-whisper` | Instrument Serif | Geist | JetBrains Mono | ad, cinematic | editorial-minimal, glossy-commercial, tech-ui | condensed serif at large size, clean geometric sans small: one quiet voice |
| `chicago-steel` | Big Shoulders | IBM Plex Sans | IBM Plex Mono | cinematic, ad | realist-cinematic, kinetic-bold | civic condensed caps with the Plex system for data and captions |
| `condensed-western` | League Gothic | Newsreader | — | cinematic | period-classic, realist-cinematic | poster gothic caps over a transitional text serif (opsz for small lines) |
| `bricolage-play` | Bricolage Grotesque | Fragment Mono | — | ad | kinetic-bold, glossy-commercial, storybook-handmade | a characterful grotesque (opsz 96) with a plain mono for prices and labels |
| `syne-wide` | Syne | Martian Mono | — | ad, cinematic | retro-futurist, kinetic-bold, editorial-minimal | Syne 800 (wide) against a narrow mono: width contrast |
| `unbounded-launch` | Unbounded | Instrument Sans | — | ad | editorial-minimal, glossy-commercial, kinetic-bold, tech-ui | wide rounded display, neutral narrow grotesque for the details |
| `caslon-quiet` | Libre Caslon Display | Familjen Grotesk | — | cinematic | period-classic, realist-cinematic | Caslon title with a warm grotesque: literary but current |
| `gloock-poster` | Gloock | Space Mono | — | ad, cinematic | editorial-minimal, kinetic-bold | heavy contrast serif with a characterful mono |
| `imbue-tall` | Imbue | Epilogue | — | ad, cinematic | glossy-commercial, editorial-minimal | tall condensed didone, squarish grotesque below |
| `cormorant-elegy` | Cormorant | Mona Sans | — | cinematic | period-classic, realist-cinematic | fragile garalde titles, sturdy grotesque captions |
| `redaction-dossier` | Redaction | Commit Mono | — | cinematic | realist-cinematic, noir-night | degrading serif (swap redaction-10…100 per beat) with a neutral mono for the record |
| `anybody-stretch` | Anybody | JetBrains Mono | — | ad, cinematic | editorial-minimal, kinetic-bold, retro-futurist | wdth 50-150 moving with the beat; mono for scores and numbers |
| `archivo-sport` | Archivo | Martian Mono | — | ad | kinetic-bold, editorial-minimal | expanded headline, condensed labels, mono stats |
| `climate-data` | Climate Crisis | IBM Plex Mono | — | cinematic, ad | realist-cinematic, editorial-minimal | YEAR axis on a date counter, mono for the figures |
| `bungee-street` | Bungee | Space Grotesk | — | ad, cinematic | editorial-minimal, glossy-commercial, kinetic-bold, retro-futurist | signage display with a technical grotesque |
| `shrikhand-sweet` | Shrikhand | Host Grotesk | — | ad | storybook-handmade, glossy-commercial | lettering-like italic display, friendly grotesque for price and CTA |
| `young-folk` | Young Serif | Mona Sans | — | ad, cinematic | storybook-handmade, glossy-commercial | chunky 70s serif, neutral variable grotesque |
| `dela-impact` | Dela Gothic One | Geist | — | ad | kinetic-bold | one heavy word per card, a clean sans for everything else |
| `danfo-signal` | Danfo | Space Mono | — | ad | kinetic-bold | ELSH axis on the beat with a retro mono |
| `tilt-3d` | Tilt Warp | JetBrains Mono | — | ad | retro-futurist, kinetic-bold | fake-3D rotation axes, a quiet mono |
| `major-terminal` | Major Mono Display | Geist | JetBrains Mono | ad, cinematic | editorial-minimal, retro-futurist, tech-ui | geometric mono display, clean sans text, code mono |
| `plex-system` | IBM Plex Serif | IBM Plex Sans | IBM Plex Mono | ad | editorial-minimal, tech-ui | one superfamily: serif, sans and mono share proportions |
| `piazzolla-book` | Piazzolla | Instrument Sans | — | cinematic | storybook-handmade, realist-cinematic | sturdy book serif, neutral grotesque labels |
| `dm-serif-lux` | DM Serif Display | Geist | — | ad | glossy-commercial | high contrast serif name, clean geometric sans details |
| `goudy-intertitle` | Sorts Mill Goudy | League Spartan | — | cinematic | period-classic, storybook-handmade | Goudy intertitles with geometric caps labels (period pairing) |
| `apfel-editorial` | Apfel Grotezk | Newsreader | — | ad, cinematic | editorial-minimal, storybook-handmade | independent grotesque display over a text serif |
| `anton-trailer` | Anton | Newsreader | — | cinematic, ad | realist-cinematic, kinetic-bold | trailer caps over a quiet serif |
| `league-voice` | League Spartan | League Mono | — | ad, cinematic | editorial-minimal, period-classic | one foundry voice: geometric display and its mono |
| `space-voice` | Space Grotesk | Space Mono | — | ad | tech-ui, retro-futurist | grotesque and the mono it grew from |
| `ouroboros-occult` (local files) | Ouroboros | Space Mono | — | cinematic, ad | retro-futurist, noir-night | Velvetyne display (local file) with a retro mono |
| `basteleur-folk` (local files) | Basteleur | Instrument Sans | — | cinematic | noir-night, period-classic, storybook-handmade | woodcut display (local file) with a neutral grotesque |
| `murmure-fashion` (local files) | Le Murmure | Newsreader | — | ad, cinematic | editorial-minimal, glossy-commercial | tall condensed display (local file) with a text serif |
| `trickster-fable` (local files) | Trickster | Piazzolla | — | cinematic | storybook-handmade | swash display (local file) with a book serif |
| `quiet-cinema` | Instrument Serif | Familjen Grotesk | — | cinematic | editorial-minimal, realist-cinematic | A condensed sharp serif for the title, a warm grotesk with ink traps for captions; both narrow, both restrained. |
| `noir-didone` | Bodoni Moda | IBM Plex Sans | — | cinematic, ad | realist-cinematic | Hairline contrast at opsz 96 against a condensed industrial sans (wdth 85): glamour over machinery. |
| `museum-light` | Cormorant | Archivo | — | cinematic | realist-cinematic, storybook-handmade | Garamond-born display capitals with small caps for labels; Archivo semi-condensed keeps captions modern and legible. |
| `documentary-plain` | Newsreader | IBM Plex Sans | IBM Plex Mono | cinematic, ad | editorial-minimal, realist-cinematic | News serif headlines (opsz 72), Plex Sans for names and Plex Mono for dates and data: a newspaper's hierarchy. |
| `picture-book` | Young Serif | Shantell Sans | — | cinematic, ad | storybook-handmade | A round heavy serif title and the narrator's own marker hand for captions (INFM 40, BNCE seeded per glyph). |
| `literary` | Gloock | Newsreader | — | cinematic | realist-cinematic, storybook-handmade | A heavy-contrast serif title over a quiet news serif with optical sizes: a book jacket. |
| `folk-horror` | Grenze Gotisch | Cormorant | — | cinematic | realist-cinematic, storybook-handmade | A blackletter gothic for the title, a fragile garalde for the lines: old print, a cold room. |
| `alchemy` (local files) | Ouroboros | Sorts Mill Goudy | — | cinematic | realist-cinematic, storybook-handmade | Ritual flared capitals (Velvetyne) over a warm Goudy text with small caps. |
| `tarot` (local files) | Basteleur | Newsreader | — | cinematic | storybook-handmade | A woodcut display for the card names, a news serif with optical sizes for the reading. |
| `print-edition` | Redaction | Space Mono | — | cinematic, ad | storybook-handmade | Redaction's eroded grades give real ink loss; Space Mono labels read like a stamp. Swap grades over time for decay. |
| `typewriter-archive` | Special Elite | Newsreader | — | cinematic | realist-cinematic, storybook-handmade | A worn typewriter for dossiers and dates, a news serif for the narration cards. |
| `vhs-memory` | Instrument Serif | Space Mono | — | cinematic | retro-futurist | A quiet condensed serif for memory, a retro mono for the timestamp: a home video label. |
| `neon-arcade` | Monoton | Space Grotesk | JetBrains Mono | ad, cinematic | retro-futurist | Inline tube capitals glow; a geometric grotesk and a code mono keep the information clean. |
| `turning-title` | Tilt Warp | Martian Mono | — | ad, cinematic | editorial-minimal, kinetic-bold, retro-futurist | XROT/YROT turn the letters in 3D on the beat; a width-variable mono answers below. |
| `observatory` | Syne | IBM Plex Mono | — | cinematic | editorial-minimal, realist-cinematic | Syne widens as it gains weight, so the title can open like a horizon; Plex Mono carries coordinates. |
| `nordic-minimal` | Instrument Sans | Newsreader | — | ad, cinematic | editorial-minimal, storybook-handmade | A condensed precise sans for titles (wdth 75), a quiet serif for the lines: generous space, one accent. |
| `premium-product` (local files) | Clash Display | Geist | JetBrains Mono | ad | editorial-minimal, glossy-commercial | A tight neo-grotesk headline, a product-UI sans for claims, tabular figures for prices. |
| `launch-friendly` | Bricolage Grotesque | Geist | — | ad | editorial-minimal, glossy-commercial | Bricolage at opsz 96 and wdth 75 shows its quirks in the headline; Geist keeps the UI and CTA sober. |
| `fashion-editorial` | Imbue | Space Grotesk | — | ad, cinematic | glossy-commercial, realist-cinematic | A tall condensed didone (opsz high) against a geometric grotesk: a magazine cover. |
| `luxe-serif` (local files) | Boska | Cabinet Grotesk | — | ad | glossy-commercial | A sharp serif with real small caps and tabular figures for prices; a grotesk with stylistic sets for claims. |
| `stadium` | Big Shoulders | Space Grotesk | — | ad, cinematic | editorial-minimal, realist-cinematic | Condensed scoreboard capitals (opsz 72) with tabular figures, a geometric grotesk for the rest. |
| `cartoon-bounce` | Shrikhand | Shantell Sans | — | ad, cinematic | kinetic-bold, storybook-handmade | A lettering-like italic display with a bouncing marker text face: Saturday-morning energy. |
| `pixel-game` | Pixelify Sans | Martian Mono | — | ad, cinematic | kinetic-bold, retro-futurist | Pixel titles over a crisp variable mono; set the pixel face on whole pixels. |
| `kitchen-notes` | Fraunces | Shantell Sans | — | ad, cinematic | glossy-commercial, storybook-handmade | A soft wonky serif for the dish, a hand-drawn marker (Shantell Sans) for the notes in the margin. |
| `travel-cover` (local files) | Le Murmure | Instrument Sans | — | ad, cinematic | editorial-minimal, glossy-commercial, realist-cinematic | Tall cut display caps for the place, a neutral sans for distances and names. |
| `melting-data` | Climate Crisis | IBM Plex Sans | IBM Plex Mono | cinematic, ad | editorial-minimal, realist-cinematic | The YEAR axis melts the headline as the data moves; Plex carries the numbers. |
| `one-voice-code` | Recursive | Recursive | — | ad, cinematic | editorial-minimal, glossy-commercial | Recursive alone: Sans Linear for headlines, Mono Casual for code; animate MONO or CASL as the software comes alive. |
| `software-ui` | Geist | Geist | JetBrains Mono | ad | editorial-minimal, glossy-commercial | Geist for interface and copy, JetBrains Mono for code: the product speaks for itself. |
| `summer-anime` | Ojuju | Familjen Grotesk | — | cinematic, ad | kinetic-bold, storybook-handmade | Ojuju's ink cuts give a hand-cut title card; Familjen keeps subtitles friendly. |
| `pop-chrome` | Tilt Warp | Unbounded | — | ad | glossy-commercial, kinetic-bold, retro-futurist | Fake-3D rotating display letters over a wide rounded sans: loud pop packaging. |
| `mosaic-mystic` (local files) | Trickster | Cormorant | — | cinematic | realist-cinematic, storybook-handmade | A mischievous swash display over Garamond-born capitals. |
| `geometric-1971` (local files) | Mourier | Martian Mono | — | cinematic, ad | editorial-minimal, retro-futurist | Abstract 1971 geometric letters for the title, a width-variable mono for all text. |
| `riso-zine` (local files) | Apfel Grotezk | Sligoil | — | cinematic, ad | editorial-minimal, storybook-handmade | Collletttivo's eccentric grotesk with Velvetyne's ink-trap mono: a risograph zine. |
| `americana` | League Gothic | Sorts Mill Goudy | — | cinematic | realist-cinematic, storybook-handmade | Condensed League Gothic caps for the place, a Goudy Oldstyle text: two League classics. |
| `noir-condensed` | Imbue | Geist | — | cinematic, ad | realist-cinematic, retro-futurist | A condensed Didone at opsz 100 for the title, a sober sans for labels. |
| `slab-poster` | Chunk Five | League Spartan | — | ad, cinematic | editorial-minimal, storybook-handmade | An ultra-bold slab over a geometric gothic: a fairground poster. |
| `quiet-product` (local files) | Sentient | Instrument Sans | — | ad | editorial-minimal, glossy-commercial | A calm text serif for the claim, a precise sans for the CTA and legal line. |

## Mixed-style pairings (tag `mixed`: title, chapter, CTA, cover and end cards)

One dominant voice + one script or italic accent (typography.md §12), dealt with `deal.py deal type --mixed`; the subtitle face is the `text` role, the mono label is small and does not count as a family.

| Pairing | Dominant (setup) | Accent | Subtitles | Mono label | Why it works |
|---|---|---|---|---|---|
| `mixed-archivo-brush` | Archivo (wght 900, wdth 125) | Caveat Brush 400 | Archivo | JetBrains Mono | Archivo Expanded Black carries the line; one Caveat Brush word adds the hand; a JetBrains Mono label stays small. |
| `mixed-unbounded-sedgwick` | Unbounded (wght 900) | Sedgwick Ave Display 400 | Unbounded | Space Mono | Unbounded Black, wide and round, with one graffiti word from Sedgwick Ave Display; Space Mono for the tiny label. |
| `mixed-anton-yellowtail` | Anton (wght 400) | Yellowtail 400 | Figtree | — | Anton condensed caps and one Yellowtail sign-painter word: contrast of structure and slope only. |
| `mixed-shoulders-marck` | Big Shoulders (wght 900, opsz 72) | Marck Script 400 | Big Shoulders | IBM Plex Mono | Big Shoulders Display Black, civic and industrial, with a personal Marck Script note; Plex Mono for dates. |
| `mixed-bricolage-instrument` | Bricolage Grotesque (wght 800, wdth 75) | Instrument Serif Italic 400 | Bricolage Grotesque | Geist Mono | Bricolage ExtraBold at wdth 75 with an Instrument Serif Italic word: structure + slope, an editorial cover. |
| `mixed-anybody-kalam` | Anybody (wght 900, wdth 150) | Kalam 700 | Anybody | — | Anybody at wdth 150 Black fills the frame; one Kalam Bold word is the friendly aside. |
| `mixed-dela-mynerve` | Dela Gothic One (wght 400) | Mynerve 400 | Figtree | — | Dela Gothic One, very heavy, with a Mynerve notebook word; Figtree for any subtitles. |
| `mixed-syne-squarepeg` | Syne (wght 800) | Square Peg 400 | Figtree | — | Syne ExtraBold (wide) with a fine Square Peg word; subtitles in Figtree (Inter only as the user's own choice). |

## Look families

Looks and recipes map to these families (`look_map` in the JSON); `deal.py deal type --look <look id>` favours matching pairings.

- **realist-cinematic**: photographic realism, documentary, epic landscapes, chiaroscuro. Looks: archive-lighttable, backrooms, cinematic-realistic, lidar-survey, microscope, satellite-briefing, tilt-shift, white-model.
- **noir-night**: night, rain, neon, fog, horror. Looks: backrooms.
- **period-classic**: silent film, engraving, period drama, pastoral. Looks: archive-lighttable, art-deco, engraving, halftone-dossier, handmade-ink, impasto, midcentury-toon, papercut-red, rubber-hose, shadow-puppet, silent-film, silkscreen-poster, spy-titles, stained-glass, ukiyoe, woodcut.
- **storybook-handmade**: storybook, picture book, papercut, watercolour, ink, clay, puppets. Looks: anime-cel, brick-toy, briefing-board, claymation, crayon-book, handmade-ink, hd-2d, impasto, ink-wash, line-boil, lowpoly-island, one-line, paper-lantern, paper-popup, papercut-collage, papercut-red, pastel-storybook, shadow-puppet, stained-glass, stickman, tilt-shift, ukiyoe, urban-sketch, watercolor, whiteboard, woodcut.
- **retro-futurist**: synthwave, VHS, Y2K, space-age. Looks: ascii-crt, cel-anime-80s, game-show, hd-2d, hologram-hud, microgame, pixel-rpg, retro-synthwave-vhs, scifi-toon.
- **glossy-commercial**: product studio, food, travel, fashion. Looks: art-deco, dark-keynote, glass-product, glossy-commercial, liquid-motion, shape-morph, teardown.
- **editorial-minimal**: Scandinavian minimal, explainers, isometric, magazine layouts. Looks: blueprint, briefing-board, data-physical, dataviz, halftone-dossier, iso-infographic, living-screencast, lowpoly-island, one-line, pictogram-motion, risograph, shape-morph, sticker-explainer, stickman, swiss-motion, urban-sketch, vox-explainer, white-model, whiteboard.
- **kinetic-bold**: kinetic type, music video, sports, comics, cartoons. Looks: anime-cel, brick-toy, cel-anime-80s, game-show, line-boil, liquid-motion, microgame, midcentury-toon, paper-popup, pictogram-motion, pixel-rpg, risograph, rubber-hose, scifi-toon, silkscreen-poster, spy-titles, swiss-motion, variety-captions, vox-explainer.
- **tech-ui**: software UI, data, space observatory, code. Looks: ascii-crt, blueprint, dark-keynote, data-physical, dataviz, glass-product, hologram-hud, iso-infographic, lidar-survey, living-screencast, microscope, satellite-briefing, sticker-explainer, teardown.

## Highlight picks per mood

- **Cinematic, literary**: Fraunces (SOFT/WONK, opsz 144), Libre Caslon Display, Newsreader, Cormorant for fragile titles.
- **Period and western**: League Gothic over Newsreader, Sorts Mill Goudy intertitles, Big Shoulders for civic documentary.
- **Noir, horror, folk**: Basteleur, Ouroboros and Mourier (Velvetyne, local), Grenze Gotisch, Redaction with its degrading siblings, Special Elite for archives.
- **Luxury and fashion ads**: Bodoni Moda (opsz), Imbue, DM Serif Display, Boska and Sentient (Fontshare, local), Le Murmure (Velvetyne, local).
- **Launch, tech, UI**: Unbounded, Geist, Mona Sans (wdth), Cabinet Grotesk and Clash Display (Fontshare, local), Recursive (MONO/CASL axes), Tilt Warp for playful 3D.
- **Kinetic, sports, music**: Anybody (wdth 50-150), Archivo, Syne 800, Danfo (ELSH), Bungee, Dela Gothic One.
- **Warm, food, storybook**: Young Serif, Shrikhand, Shantell Sans (bounce axis), Bricolage Grotesque, Piazzolla, Trickster (Velvetyne, local).
- **Data and documentary**: Climate Crisis (YEAR axis), IBM Plex trio, Redaction, Martian Mono.
- **Retro, games, zines**: Pixelify Sans, Monoton, Major Mono Display, Sligoil (Velvetyne, local), Chunk Five, Ojuju.

## Kept out

- Licence unconfirmed: Lack (Velvetyne): no licence file in its repository when checked.
- Overused defaults, not dealt (the user can still name them as their own answer): Inter, Roboto, Montserrat, Poppins, Bebas Neue, Playfair Display, EB Garamond, Caveat.
