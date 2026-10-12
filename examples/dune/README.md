# DUNE Bags example (user: alice)

The real folder `~/Downloads/DUNE Bags` is embedded once and reused for every store shape:

| Store | How it is made | Contents |
|---|---|---|
| `dune-bags` | `kb ingest` (one upload, real EmbeddingGemma 2 embeddings) | 3 Word info sheets, 12 studio renders, 360 turntable frames, 3 turntable videos (`.py/.stl/.blend` ignored, not supported) |
| `dune-sirocco`, `dune-mirage`, `dune-sahara` | `kb stores split dune-bags --field bag` | one **live view** per sub-folder |
| `dune-sirocco-mirage` | `kb stores merge dune-sirocco dune-mirage --into …` | two bags combined, duplicates removed, no re-embedding |
| `dune-info-sheets` | `kb stores derive … --mode snapshot --filter kind=info` | the three sheets, frozen |
| `dune-sahara-renders` | `kb stores derive dune-sahara … --mode view --filter kind=render` | a view **over a view** |

## Run
```bash
# services running (see repo README): API :3000, inference, worker; Ollama with gemma4:12b-nvfp4 for answers
export KB_CONFIG_DIR=$PWD/examples/dune/.kb          # alice's CLI profile (dev IdP)
node cli/kb.ts ingest dune-bags "$HOME/Downloads/DUNE Bags" --yes --wait
examples/dune/setup.sh                               # tag, split, merge, snapshot, nested view, export, app key
python3 examples/dune/rag.py --selftest              # end-to-end checks with the real answer model
python3 examples/dune/rag.py --store dune-mirage "How deep are the ribs?"
python3 examples/dune/rag.py --image "$HOME/Downloads/DUNE Bags/Sahara - quilted charm bag/Sahara_02_front.png" "Which bag is this and what is its surface pattern?"
```

`rag.py` uses only the Python standard library. Retrieval goes through the store search API with an application key (`.kb/app.key`, scopes `search` and `source:read`). Generation uses your own model (local Ollama). Retrieved images are shown to the answer model as pictures, and every answer cites `[n]` sources with file path and location.
