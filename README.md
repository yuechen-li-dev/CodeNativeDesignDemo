# Code Native Design

[![Build engineering artifacts](https://github.com/yuechen-li-dev/CodeNativeDesignDemo/actions/workflows/build-part.yml/badge.svg)](https://github.com/yuechen-li-dev/CodeNativeDesignDemo/actions/workflows/build-part.yml)

Edit a part specification. Review the diff. Let CI produce the part and drawing.

This first example builds a **single parametric machined L bracket with a
countersunk through hole** using Aetheris/Firmament. Two rectangular guides define
a six-edge traced profile, which is extruded and drilled. It is a single part,
not a bent sheet or assembly. The CI job builds a nominal and a resized example.

## Pull the lever

1. Open [Build engineering artifacts](https://github.com/yuechen-li-dev/CodeNativeDesignDemo/actions/workflows/build-part.yml).
2. Select **Run workflow**, choose `main`, then **Run workflow**.
3. Open the finished run and download its `bracket-<commit>` artifact.
4. Open `nominal/Bracket.pdf` and `variant/Bracket.pdf`, or import their STEP/GLB files.

Pushes to `main` and pull requests run the same checks. For a design revision, edit
the named millimetre dimensions in [src/Program.cs](src/Program.cs). Each call to
`MakeBracket` produces a part, drawing and qualification evidence.

| Dimension (mm) | Nominal | Variant |
| --- | ---: | ---: |
| Width / height / thickness | 80 / 60 / 12 | 100 / 75 / 15 |
| Vertical / horizontal leg width | 20 / 20 | 25 / 24 |
| Hole X / Y from lower-left O | 60 / 10 | 70 / 12 |
| Through / countersink entry diameter | 6 / 12 | 8 / 14 |

Both countersinks have a 90-degree included angle. The drawing defines linear
limits of ±0.1 mm and angular limits of ±0.5 degrees, material 6061-T6 aluminium,
the origin, hole axis and top entry face. Checked/approved boxes stay blank.

## What you get

Each case has final STEP AP242, GLB, PDF, SVG, PPTX, instantiated Firmament source,
Drawing IR, `qualification.json`, `validation.json`, and a PDF-only reconstruction.
`run.json` records the demo/compiler revisions and hosted run URL. Artifact hashes
are checked before uploading. Intermediate undimensioned projections are excluded.

The PDF is the nominal manufacturing definition: outline, thickness, hole size,
location, axis, extent and countersink entry/angle. An independent reader consumes
only its printed dimensions and tables, freezes a different Path-based model,
then compares STEP bounds, topology, vertices, cylinder/cone supports and evaluated
volume. Nine deliberately incomplete drawing variants must fail for each part.
This is a bounded witness for this drawing convention, not a general PDF reader.

STEP and GLB carry supported **datum and shaft-diameter semantic PMI**. Additional
outline and countersink limits are on the drawing; this demo does not claim all
PDF requirements have AP242 PMI equivalents. Numerical mass is reported separately
from analytic construction volume and is not described as exact.

These are **unsigned engineering-review artifacts**. The bounded tolerance screen
checks breakout and remaining shaft on ideal orthogonal stock, not supplier process
capability, stock form, inspection approval or a certified manufacturing release.

## Reproduce locally

Install the exact .NET SDK from `global.json`, PowerShell 7, Git, and Python 3.12.
From this repository:

```powershell
git clone https://github.com/yuechen-li-dev/Aetheris.git dependencies/aetheris
git -C dependencies/aetheris checkout (Get-Content aetheris-revision.txt -Raw).Trim()
git clone https://github.com/yuechen-li-dev/Copeland.git dependencies/copeland
git -C dependencies/copeland checkout (Get-Content dependencies/aetheris/scripts/managed-wgsl-commit-pin.txt -Raw).Trim()
./dependencies/aetheris/scripts/prepare-managed-wgsl.ps1 -CopelandRoot "$PWD/dependencies/copeland"
python -m pip install -r requirements.txt
./scripts/Qualify.ps1 -OutputDirectory "$PWD/artifacts/local/first-run"
```

Use a fresh output directory for each qualification. The Aetheris checkout must
match `aetheris-revision.txt` and have clean tracked source. CI also runs the
composed-hole and bracket regressions. Aetheris owns its full kernel regression
suite; this repository owns the downstream part/artifact integration checks.

## Source ownership

The short consumer lives here; the reusable bracket Template, drawing layout,
compiler and exporters come from the source-pinned Aetheris project. Read the
[Firmament family](https://github.com/yuechen-li-dev/Aetheris/blob/81918d9c14a624f1168cd3919c2df4cc0c8b27ba/fixtures/Regression/ComposeHoleFamilies/bracket-library.firmament)
and [MakeBracket implementation](https://github.com/yuechen-li-dev/Aetheris/blob/81918d9c14a624f1168cd3919c2df4cc0c8b27ba/demos/Aetheris.CodeNativeBracket/Program.cs).
Changing the pin is an explicit compiler upgrade. Published Preview 3 predates
composed-profile countersinks, so this example builds the reviewed source graph.

GitHub artifacts expire after 30 days; rerun the workflow or retain your own copy.
See [LICENSE](LICENSE) and the pinned dependencies' licenses before redistribution.
