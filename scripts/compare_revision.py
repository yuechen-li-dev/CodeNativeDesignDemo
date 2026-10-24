"""A bounded part-review projection of qualified compiler artifacts, not a CAD engine."""
import argparse
from array import array
import hashlib
import html
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont
from qualify_assembly import glb_triangles


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def view_geometry(directory, name):
    document = load(directory / "Bracket.drawing.json")
    view = next(view for page in document["Pages"] for view in page["Views"] if view["Identity"] == name)
    # Undo the page layout, retaining the compiler's actual projected geometry.
    # Camera origin and scale map the same world origin on both revisions.
    camera, scale = view["Camera"], view["Scale"]
    require(scale > 0, "Invalid drawing projection scale.")
    paths = [[((p["X"] - camera["OriginX"]) / scale,
               (p["Y"] - camera["OriginY"]) / scale) for p in primitive["Points"]]
             for primitive in view["Primitives"] if primitive["Kind"] in (0, 1)]
    require(paths and all(math.isfinite(v) for path in paths for point in path for v in point),
            "Drawing has no usable projected geometry.")
    return paths, camera


def bounds(paths):
    points = [point for path in paths for point in path]
    return min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)


def geometry_preview(before, after, output, font, assembly_added=False):
    before_color, after_color = "#596675", "#007f76"
    for name in ("ISO", "TOP"):
        a, ac = view_geometry(before, name)
        b, bc = view_geometry(after, name)
        require(ac["Right"] == bc["Right"] and ac["Up"] == bc["Up"], "Projection axes differ between revisions.")
        low_x, low_y, high_x, high_y = bounds(a + b)
        width, height = (1800, 940) if name == "ISO" else (1800, 1020)
        factor = 2  # Supersampled line art, then downsampled for the review.
        image = Image.new("RGB", (width * factor, height * factor), "#ffffff")
        draw = ImageDraw.Draw(image)

        def text(x, y, value, size=26, color="#182431"):
            draw.text((x * factor, y * factor), value, fill=color,
                      font=ImageFont.truetype(str(font), size * factor))

        text(55, 30, "BRACKET REVISION / GEOMETRY", 38)
        text(55, 86, "Compiler-projected BRep edges. Common origin, camera and scale; display preview only.", 23)
        if name == "ISO":
            panel_width, panel_height, top = 800, 590, 215
            scale = min((panel_width - 70) / (high_x - low_x), (panel_height - 70) / (high_y - low_y))
            for left, label, color, paths in ((55, "BEFORE", before_color, a), (945, "PROPOSED", after_color, b)):
                text(left + 30, 150, label, 30, color)
                draw.rounded_rectangle((left * factor, top * factor, (left + panel_width) * factor,
                                        (top + panel_height) * factor), radius=14 * factor, outline="#d6dfe5", width=2 * factor)
                ox = left + panel_width / 2 - (low_x + high_x) / 2 * scale
                oy = top + panel_height / 2 - (low_y + high_y) / 2 * scale
                for path in paths:
                    if len(path) > 1:
                        draw.line([((ox + x * scale) * factor, (oy + y * scale) * factor) for x, y in path],
                                  fill=color, width=3 * factor, joint="curve")
            text(55, 844, "Bracket preserved; the proposed revision adds a separate, semantically seated fastener." if assembly_added else
                 "The horizontal arm extends; the countersunk through hole follows. Original STEP/GLB supplied.", 24)
            target = output / "geometry-before-after.png"
        else:
            scale = min(1470 / (high_x - low_x), 660 / (high_y - low_y))
            ox, oy = 165 - low_x * scale, 215 - low_y * scale
            text(55, 145, "TOP OVERLAY", 30)
            text(375, 151, "BEFORE (gray)  /  PROPOSED (teal)", 25)
            for paths, color, stroke in ((a, before_color, 5), (b, after_color, 3)):
                for path in paths:
                    if len(path) > 1:
                        draw.line([((ox + x * scale) * factor, (oy + y * scale) * factor) for x, y in path],
                                  fill=color, width=stroke * factor, joint="curve")
            draw.ellipse(((ox - 5) * factor, (oy - 5) * factor, (ox + 5) * factor, (oy + 5) * factor), fill="#182431")
            text(ox - 60, oy + 20, "O (X0, Y0)", 24)
            text(55, 952, "Aligned to the physical origin. The bracket geometry and hole location coincide." if assembly_added else
                 "Aligned to the physical origin. Overlapping edges coincide; both old and new hole positions remain visible.", 23)
            target = output / "top-overlay.png"
        image.resize((width, height), Image.Resampling.LANCZOS).save(target)


def assembly_preview(path, output, font):
    # Presentation only: project actual GLB triangles; qualification reads the same artifact independently.
    components = glb_triangles(path)
    image = Image.new('RGB', (1800, 900), 'white')
    draw = ImageDraw.Draw(image)
    def text(x, y, message, size=24):
        draw.text((x, y), message, fill='#182431', font=ImageFont.truetype(str(font), size))
    text(45, 28, 'CODE → ASSEMBLY / EXPORTED GEOMETRY', 36)
    text(45, 84, 'Actual GLB triangles. Exploded view is display only; the STEP assembly keeps the seated mate.')
    for column, label in enumerate(('SEATED', 'EXPLODED', 'TIP CHAMFER / DETAIL')):
        text(40 + 590 * column, 150, label, 25)
        triangles = []
        for name, faces in components.items():
            if column == 2 and name != 'Fastener':
                continue
            for face in faces:
                points = [(x, y, z + (23 if column == 1 and name == 'Fastener' else 0)) for x, y, z in face]
                if column == 2:
                    # Turn the fastener sideways in this display-only detail to expose the lead-in.
                    points = [(z, y, -x) for x, y, z in points]
                a, b, c = points
                u, v = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
                normal = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
                magnitude = math.sqrt(sum(n*n for n in normal))
                if magnitude < 1e-12 or sum(n*d for n, d in zip(normal, (.519615, -.69282, .5))) <= 0:
                    continue
                projected = [(.8*x + .6*y, .3*x - .4*y - .8660254*z, .519615*x - .69282*y + .5*z) for x, y, z in points]
                light = .55 + .45 * max(0, sum(n*d for n, d in zip(normal, (-.3, -.4, .8660254))) / magnitude)
                rgb = (201, 156, 75) if name == 'Fastener' else (126, 154, 173)
                triangles.append((projected, tuple(round(c*light) for c in rgb)))
        xs = [p[0] for face, _ in triangles for p in face]
        ys = [p[1] for face, _ in triangles for p in face]
        scale = min(510 / (max(xs)-min(xs)), 480 / (max(ys)-min(ys)))
        # Pixel depth prevents a large stock triangle from hiding a seated head,
        # or an occluded shaft showing through it. No geometry is altered.
        depth = array('f', [float('-inf')]) * (520 * 490)
        pixels = image.load()
        for face, color in triangles:
            a, b, c = [((x-min(xs))*scale + 4, (y-min(ys))*scale + 4, z) for x, y, z in face]
            denominator = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
            if abs(denominator) < 1e-9:
                continue
            for y in range(max(0, math.floor(min(a[1], b[1], c[1]))), min(490, math.ceil(max(a[1], b[1], c[1])) + 1)):
                for x in range(max(0, math.floor(min(a[0], b[0], c[0]))), min(520, math.ceil(max(a[0], b[0], c[0])) + 1)):
                    u = ((b[1]-c[1])*(x+.5-c[0]) + (c[0]-b[0])*(y+.5-c[1])) / denominator
                    v = ((c[1]-a[1])*(x+.5-c[0]) + (a[0]-c[0])*(y+.5-c[1])) / denominator
                    if min(u, v, 1-u-v) < -1e-8:
                        continue
                    z = u*a[2] + v*b[2] + (1-u-v)*c[2]
                    offset = y*520 + x
                    if z > depth[offset]:
                        depth[offset] = z
                        pixels[40 + column*590 + x, 220 + y] = color
    text(45, 770, 'Threadless countersunk blank: Ø5.7 shaft · Ø12 head × 90° · length 16 mm · tip 0.5 mm × 45°')
    text(45, 815, 'Nominal 0.3 mm diametral clearance; retention, strength and production approval remain unqualified.', 22)
    image.save(output / 'assembly-preview.png')


def compare(before_root, after_root, output, font):
    require(not output.exists(), "Use a fresh review output directory.")
    before_run, after_run = load(before_root / "run.json"), load(after_root / "run.json")
    require(before_run["aetherisRevision"] == after_run["aetherisRevision"],
            "Compiler pins differ: qualify a compiler upgrade separately before comparing design revisions.")
    for receipt in (before_run, after_run):
        require(all(receipt["cases"][case]["pdfReconstructionMatches"]
                    and receipt["cases"][case]["incompleteDrawingsRejected"] == 9
                    and receipt["cases"][case]["validationLevel"] == "Built"
                    for case in ("nominal", "variant")), "All four built cases require complete qualification receipts.")
    sides = []
    for root in (before_root, after_root):
        directory = root / "nominal"
        q = load(directory / "qualification.json")
        r = load(directory / "pdf-reconstruction/pdf-qualification.json")
        require(r["matchingGeometry"] and r["referenceReadAfterFreeze"] and len(r["negativeCasesRejected"]) == 9,
                "Each drawing must independently reconstruct and reject incomplete definitions.")
        for filename, expected in q["hashes"].items():
            require(digest(directory / filename) == expected, f"Changed qualified artifact: {filename}")
        sides.append(q)
    before, after = sides
    changes = {key: {"before": value, "after": after["dimensions"][key], "delta": after["dimensions"][key] - value}
               for key, value in before["dimensions"].items() if key != "Volume" and value != after["dimensions"][key]}
    assembly_added = 'assembly' not in before_run['cases']['nominal'] and 'assembly' in after_run['cases']['nominal']
    require(changes or assembly_added, "Neither the nominal specification nor the assembly changed.")
    volume_delta = after["exactConstructionVolume"] - before["exactConstructionVolume"]
    mass_delta = after["independentMass"]["AbsoluteVolume"] - before["independentMass"]["AbsoluteVolume"]
    require((digest(before_root / "nominal/Bracket.step") != digest(after_root / "nominal/Bracket.step")) == bool(changes),
            "Changed part intent produced unchanged STEP.")
    require((digest(before_root / "nominal/Bracket.pdf") != digest(after_root / "nominal/Bracket.pdf")) == bool(changes),
            "Changed part intent produced unchanged drawing.")
    controls = {filename: digest(before_root / "variant" / filename) == digest(after_root / "variant" / filename)
                for filename in ("Bracket.step", "Bracket.pdf")}
    require(all(controls.values()), "Unchanged control part geometry/drawing changed.")
    semantic_fields = ("Kind", "Name", "Target", "Value", "TolerancePlus", "ToleranceMinus")
    semantic = lambda q: [tuple(item[field] for field in semantic_fields) for item in q["pmi"]["Items"]]
    require(semantic(before) == semantic(after), "This arm/placement revision must preserve semantic hole/datum requirements.")
    extension_check = None
    if set(changes) == {"Width", "HoleX"}:
        extension_check = changes["Width"]["delta"] * before["dimensions"]["LegHeight"] * before["dimensions"]["Thickness"]
        require(abs(volume_delta - extension_check) < 1e-7, "Arm extension failed the independent volume delta check.")
        require(abs(mass_delta - extension_check) <= max(before["exactConstructionVolume"], after["exactConstructionVolume"]) * 2e-5,
                "Reimported BRep mass delta disagrees with the arm extension.")
    output.mkdir(parents=True)
    shutil.copytree(before_root, output / "before")
    shutil.copytree(after_root, output / "after")
    geometry_preview(before_root / "nominal", after_root / "nominal", output, font, assembly_added)
    if assembly_added:
        require(all(after_run['cases'][case]['assembly']['status'] == 'passed' for case in ('nominal', 'variant')), 'Both assemblies must qualify')
        assembly_preview(after_root / 'nominal/assembly/MountedBracket.glb', output, font)
    for label, root in (("before", before_root), ("after", after_root)):
        subprocess.run(["pdftoppm", "-scale-to", "1800", "-singlefile", "-png", str(root / "nominal/Bracket.pdf"),
                        str(output / (label + "-drawing"))], check=True)
    result = {"schema": "code-native-design-review/1", "beforeRun": before_run, "afterRun": after_run,
              "changedDimensionsMillimetres": changes, "assemblyAdded": assembly_added,
              "exactConstructionVolumeDeltaCubicMillimetres": volume_delta,
              "independentBrepMassDeltaCubicMillimetres": mass_delta,
              "armExtensionVolumeCheckCubicMillimetres": extension_check,
              "unchangedControlByteEqual": controls, "semanticRequirementsPreserved": True,
              "previewSource": "Actual Drawing IR projected edge points, with camera origin and page scale removed.",
              "previewHashes": {p.name: digest(p) for p in output.glob("*.png")}}
    (output / "comparison.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    rows = "".join(f"<tr><td>{html.escape(key)}</td><td>{v['before']:g}</td><td>{v['after']:g}</td><td>{v['delta']:+g}</td></tr>"
                   for key, v in changes.items())
    if assembly_added and not changes:
        rows = '<tr><td colspan="4">Bracket dimensions preserved. Added a separate chamfered fastener, named seating frames and fixed mate.</td></tr>'
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Bracket revision review</title><style>
body{{font:16px/1.5 system-ui,sans-serif;background:#f2f5f6;color:#182431;margin:0}}main{{max-width:1240px;margin:auto;padding:32px}}
h1{{font-size:36px;margin-bottom:8px}}section{{background:white;border:1px solid #d6dfe5;border-radius:12px;padding:24px;margin:24px 0}}
table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #d6dfe5}}img{{width:100%;height:auto}}a{{color:#007f76}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}code{{overflow-wrap:anywhere}}@media(max-width:750px){{.pair{{grid-template-columns:1fr}}}}
</style><main><h1>Review a bracket revision</h1><p>Design source → pull request → qualified engineering artifacts.</p>
<section><h2>What changed</h2><table><tr><th>Dimension / mm</th><th>Before</th><th>Proposed</th><th>Change</th></tr>{rows}</table>
<p>Analytic construction volume change: <strong>{volume_delta:+.1f} mm³</strong>.
Independently evaluated BRep mass-volume change: {mass_delta:+.1f} mm³.</p>
<p>The unchanged control part has byte-identical STEP and PDF. Datum/shaft semantic requirements are preserved.</p></section>
<section><h2>Geometry at the same scale</h2><a href="geometry-before-after.png"><img src="geometry-before-after.png" alt="Before and proposed compiler-projected geometry"></a>
<a href="top-overlay.png"><img src="top-overlay.png" alt="Origin-aligned top-view overlay"></a></section>
{('<section><h2>New assembly</h2><img src="assembly-preview.png" alt="Seated assembly, exploded display and fastener detail"><p><a href="after/nominal/assembly/MountedBracket.step">Assembly STEP AP242</a> · <a href="after/nominal/assembly/MountedBracket.glb">Assembly glTF / GLB</a> · <a href="after/nominal/assembly/mounted-bracket.firmasm">Named-mate source</a> · <a href="after/nominal/assembly/qualification.json">Assembly qualification</a></p><p>Two components, a flush countersunk seat, 0.3 mm nominal diametral clearance and a 0.5 mm × 45° terminal chamfer. STEP roundtrip and GLB world bounds qualify. Part PMI is intentionally not inherited into assembly export.</p></section>') if assembly_added else ''}
<section><h2>The actual drawings</h2><div class="pair">"""
    for label, heading in (("before", "Before"), ("after", "Proposed")):
        page += f"""<div><h3>{heading}</h3><a href="{label}/nominal/Bracket.pdf"><img src="{label}-drawing.png" alt="{heading} dimensioned drawing"></a>
<p><a href="{label}/nominal/Bracket.pdf">Original PDF</a> · <a href="{label}/nominal/Bracket.step">STEP AP242</a> ·
<a href="{label}/nominal/Bracket.glb">GLB</a> · <a href="{label}/nominal/bracket.firmament">Firmament</a></p></div>"""
    page += f"""</div><p>Both PDFs independently reconstruct matching solids. All 36 incomplete-drawing guards across the four built cases reject.</p>
<p>Unsigned engineering-review drawings. Git commits identify these working states; the family's planned release is 1.0.0. Manufacturing approval remains blank.</p></section>
<section><h2>Provenance</h2><p>Base commit: <code>{html.escape(before_run['demoRevision'])}</code><br>
Proposed build commit: <code>{html.escape(after_run['demoRevision'])}</code><br>Compiler: <code>{html.escape(after_run['aetherisRevision'])}</code></p>
<p><a href="comparison.json">Comparison evidence and hashes</a> · <a href="before/run.json">Base build receipt</a> · <a href="after/run.json">Proposed build receipt</a></p>
<p>Projected line previews explain the change; the supplied solids and dimensioned PDFs remain the engineering artifacts.</p></section></main></html>"""
    (output / "index.html").write_text(page, encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in ("beforeRun", "afterRun")}, indent=2))
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("\n## Revision comparison\n\n| Dimension / mm | Before | Proposed | Delta |\n|---|---:|---:|---:|\n")
            for key, v in changes.items():
                summary.write(f"| {key} | {v['before']:g} | {v['after']:g} | {v['delta']:+g} |\n")
            summary.write(f"\nConstruction volume delta: {volume_delta:+.1f} mm³. Unchanged control STEP/PDF match; semantic requirements preserved.\n\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("before", "after", "output", "font"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        compare(args.before, args.after, args.output, args.font)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
