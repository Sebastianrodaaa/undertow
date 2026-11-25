# Third-party notices

undertow is MIT-licensed. This file records required third-party credit and license terms. No affiliation with these projects, OpenStreetMap, PyTorch, Hugging Face, or the cited authors is claimed.

## Data

- **OpenStreetMap data**: `(c) OpenStreetMap contributors`, licensed under the [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/). The cached extracts and derived raster grids in `data/osm/` and runtime outputs are produced from OSM data and carry the same ODbL attribution requirement. Source: https://www.openstreetmap.org and, where used, the Overpass API. This repository records the actual API source inside each cached extract.

## Software and models

- **PyTorch**: BSD-3-Clause license. https://github.com/pytorch/pytorch
- **llama.cpp**: MIT license. https://github.com/ggml-org/llama.cpp
- **Qwen2.5-Coder-7B-Instruct**: Apache-2.0 license. https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct
- **whisper.cpp**: MIT license. https://github.com/ggml-org/whisper.cpp
- **Piper**: MIT license; individual voice models carry their own permissive licenses and must be checked before redistribution. https://github.com/rhasspy/piper
- **LoopedWSP**: MIT license, used only as reference/inspiration. https://github.com/mbzuai-oryx/LoopedWSP
- **Playwright**: Apache-2.0 license. https://github.com/microsoft/playwright
- **aiohttp**: Apache-2.0 license. https://github.com/aio-libs/aiohttp
- **NumPy**: BSD-3-Clause license. https://github.com/numpy/numpy
- **Matplotlib**: PSF/BSD-style license. https://matplotlib.org/stable/users/project/license.html
- **Pillow**: HPND license. https://python-pillow.org/

## Fonts

- **Geist and Geist Mono**: SIL Open Font License 1.1. https://github.com/vercel/geist-font
- **UnifrakturMaguntia**: SIL Open Font License 1.1, copyright j. 'mach' wust and Peter Wiegel. https://github.com/google/fonts/tree/main/ofl/unifrakturmaguntia

## Art

- **Gustave Dore, *The Deluge***, wood engraving in *La sainte Bible*, vol. 1, Alfred Mame et Fils, 1866; engraver Adolphe Francois Pannemaker. Public domain. Verified source: https://www.oldbookillustrations.com/illustrations/deluge/ (source images from the Internet Archive); related Wikimedia record: https://commons.wikimedia.org/wiki/File:Gustave_Dor%C3%A9_-_The_Holy_Bible_-_Plate_I,_The_Deluge.jpg
- **Anonymous, *Le Pont Neuf***, lithograph, c. April 1844, Musee Carnavalet / Paris Musees. CC0. Verified source: https://www.parismuseescollections.paris.fr/fr/musee-carnavalet/oeuvres/le-pont-neuf-17

## Security note

No secrets, `.env` files, private keys, or paid API credentials are required or committed.
