# Parts

Every `*.firmament` file in this folder is built by the [Build parts](../.github/workflows/parts.yml)
workflow into:

| File | What it is |
|---|---|
| `<name>/<name>.step` | Exact STEP AP242 from the Aetheris compiler |
| `<name>/<name>.stl` | Triangle mesh for a quick look |
| `<name>/drawing/*.pdf` | A fully dimensioned drawing, when the automatic planner can define the part |
| `<name>/drawing-reference/*.pdf` | Otherwise, labelled geometry views marked *not for manufacture* |
| `<name>/validation.json` | The compiler's admission report |
| `summary.md` | The table shown in the run summary |

## Make your own part

1. Fork this repository, open the fork's **Actions** tab and enable workflows
   (forks start with Actions disabled).
2. In the fork on GitHub, open `parts/starter-plate.firmament`, copy its contents, and
   create `parts/<your-name>.firmament` with **Add file → Create new file**. Change the
   numbers. Commit.
3. Open **Actions → Build parts → your run**. The summary says whether the part is valid,
   and the `parts-<commit>` artifact holds the STEP, STL and PDF drawing.

If the part does not compile, the run fails and the summary shows the compiler's
diagnostic with its line number. Fix that line and commit again.

## Build locally

With a built Aetheris CLI at the pinned revision (see `../README.md`, *Reproduce locally*):

```bash
python scripts/build_parts.py --cli <aetheris>/Aetheris.CLI/bin/Release/net10.0/aetheris.dll \
  --output artifacts/local/parts --revision "$(cat aetheris-revision.txt)"
```
