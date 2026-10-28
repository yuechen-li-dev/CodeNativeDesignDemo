# Code Native Design

[![Build engineering artifacts](https://github.com/yuechen-li-dev/CodeNativeDesignDemo/actions/workflows/build-part.yml/badge.svg)](https://github.com/yuechen-li-dev/CodeNativeDesignDemo/actions/workflows/build-part.yml)

This repo demonstrates software pipeline style workflow for mechanical design using the Aetheris geometry kernel headlessly. 

It is primarily to demonstrate:
1. Editing the part specification with a text editor or via LLMs. 
2. Review the dimensional diff for the part in code, exactly as you would for any software. 
3. Using CI/CD produce the part model and drawing as any other software artifact.

This example builds a **parametric machined L bracket with a
countersunk through hole** using Aetheris/Firmament. Two rectangular guides define
a six-edge traced profile, which is extruded and drilled. It is a single part,
not a bent sheet. Each bracket is also assembled with a separate **chamfered,
threadless countersunk fastener**. The CI job builds nominal and resized examples.

## Design your own part (no install)

Fork the repo, enable **Actions** on your fork, add a file to [parts/](parts/) and commit.
CI compiles it with the pinned Aetheris and hands back STEP AP242, an STL and a PDF drawing:

1. Copy [parts/starter-plate.firmament](parts/starter-plate.firmament) to
   `parts/<your-part>.firmament` and change the numbers.
2. Commit, then open **Actions → Build parts**. The run summary says whether the part is
   valid, with the compiler's diagnostic and line number if it is not.
3. Download the `parts-<commit>` artifact.

Multi-agent CAD here is just Git: one part per file, one agent per branch, pull requests as
proposals and CI as the reviewer of geometry. [AGENTS.md](AGENTS.md) is the protocol;
[parts/claude-mounting-plate.firmament](parts/claude-mounting-plate.firmament) was
contributed that way by an agent.

## Pull the lever

1. Open [Build engineering artifacts](https://github.com/yuechen-li-dev/CodeNativeDesignDemo/actions/workflows/build-part.yml).
2. Select **Run workflow**, choose `main`, then **Run workflow**.
3. Open the finished run and download its `bracket-<commit>` artifact.
4. Open `nominal/Bracket.pdf`, or import `nominal/assembly/MountedBracket.step`
   and `MountedBracket.glb`. `variant/` contains the resized family member.

Pushes to `main` and pull requests run the same checks. For a design revision, edit
the named millimetre dimensions in [src/Program.cs](src/Program.cs). Each call to
`MakeBracket` produces a part, drawing and qualification evidence. The same
dimensions generate a typed Record used by the assembly's Firmament Templates.

| Dimension (mm) | Nominal | Variant |
| --- | ---: | ---: |
| Width / height / thickness | 96 / 60 / 12 | 100 / 75 / 15 |
| Vertical / horizontal leg width | 20 / 20 | 25 / 24 |
| Hole X / Y from lower-left O | 76 / 10 | 70 / 12 |
| Through / countersink entry diameter | 6 / 12 | 8 / 14 |

Both countersinks have a 90-degree included angle. The drawing defines linear
limits of ±0.1 mm and angular limits of ±0.5 degrees, material 6061-T6 aluminium,
the origin, hole axis and top entry face. Checked/approved boxes stay blank.

The fastener composes a Cylinder and Frustum, then chamfers the shaft's bottom
edge by **0.5 mm × 45°**. Its shaft is 0.3 mm smaller than the bore, its head
matches the countersink's entry diameter, and its length is bracket thickness
plus 4 mm. The nominal fastener is Ø5.7 / Ø12 × 16 mm; the variant is
Ø7.7 / Ø14 × 19 mm. These are threadless blanks without drive recesses, not
released screws. Retention, strength and supplier process capability are unqualified.

[The assembly](src/firmament/mounted-bracket.firmasm) anchors the bracket and
joins exposed `FastenerSeat` / `HeadSeat` DatumFrames through `Mate InstallFastener`.
There is no hand-authored placement matrix. A qualification guard moves the hole
1 mm and proves the fastener follows without changing its definition.

## Review a design revision

Pull requests rebuild and qualify **both the exact PR base and the proposed
revision**, using the same pinned compiler. The additional `review-pr<number>-<commit>`
artifact contains both sets of deliverables and an offline `index.html` showing
the parameter/volume changes, geometry at a common projection and scale, an
origin-aligned top-view overlay, and full before/after drawing previews. Extract
the ZIP before opening it. The original PDFs and STEP/GLB files are linked beside
the previews; each side has its own qualification and PDF reconstruction evidence.

The first revision extended the nominal horizontal leg by 16 mm and moved
H1 outward by 16 mm, preserving its 20 mm distance from the right edge. Thickness,
leg widths, hole diameters and angle remain unchanged. The resized control part
must retain byte-identical STEP and PDF. Git revisions identify the compared
working states; the unsigned drawing family's planned release remains 1.0.0.
See the [illustrated revision walkthrough](docs/public/bracket-revision.md) for
the actual before/after geometry, drawings and producing-run evidence.

The assembly revision preserves both bracket definitions and drawings. Its review
pack adds seated, exploded and chamfer-detail previews from the actual exported
GLB triangles. The exploded view is presentation only; STEP retains the seated mate.

Comparisons use the same compiler on both sides. When upgrading the pin, CI also
builds the exact historical source with its original compiler, then requires
byte-identical bracket STEP, GLB, PDF and SVG against the new-compiler control.
`compiler-control.json` records that separate gate. A changed artifact fails the
upgrade rather than silently substituting a compiler for historical source.

## What you get

Each case has final STEP AP242, GLB, PDF, SVG, PPTX, instantiated Firmament source,
Drawing IR, `qualification.json`, `validation.json`, and a PDF-only reconstruction.
The `assembly/` folder adds the modular Firmament source, `MountedBracket.step`,
`MountedBracket.glb`, standalone `Fastener.step` and `Bracket.step`, plus CLI evidence.
CI checks two definitions/occurrences/bodies, mate residuals, STEP reimport/export
transforms and bounds, actual GLB world bounds, terminal chamfer radius and
independent analytic-versus-evaluated fastener volume. The same PDF independently
reconstructs the assembly's bracket component as well as the standalone part.
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

**Part PMI stays part-owned.** Assembly export intentionally does not inherit the
bracket's PMI. Declare PMI explicitly in an assembly when it belongs to that assembly.
The supplied PDF describes the bracket; this demo does not claim a manufacturing
drawing or tolerance-stack approval for the fastener assembly.

These are **unsigned engineering-review artifacts**. The bounded tolerance screen
checks breakout and remaining shaft on ideal orthogonal stock, not supplier process
capability, stock form, inspection approval or a certified manufacturing release.

## Reproduce locally

Install the exact .NET SDK from `global.json`, PowerShell 7, Git, Python 3.12 and
Node.js 24 with npm (for Aetheris's pinned PDF.js resource restoration).
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
composed-hole, bracket and assembly regressions. Aetheris owns its full kernel regression
suite; this repository owns the downstream part/artifact integration checks.

## Source ownership

The short C# consumer and modular assembly Templates live here under
[src/firmament](src/firmament). The standalone bracket helper, drawing layout,
compiler and exporters come from the source-pinned Aetheris project. Read the
[MakeBracket implementation](https://github.com/yuechen-li-dev/Aetheris/blob/b05cca40ec3efd7540c647398892953299d2c136/demos/Aetheris.CodeNativeBracket/Program.cs).
Changing the pin is an explicit compiler upgrade. Published Preview 3 predates
composed-profile countersinks, so this example builds the reviewed source graph.

GitHub artifacts expire after 30 days; rerun the workflow or retain your own copy.
See [LICENSE](LICENSE) and the pinned dependencies' licenses before redistribution.
