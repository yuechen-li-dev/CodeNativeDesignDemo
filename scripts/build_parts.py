"""Build every part in parts/ with the pinned Aetheris CLI.

For each top-level parts/<name>.firmament this writes, under the output directory:
  <name>/<name>.step         exact STEP AP242 from the compiler
  <name>/<name>.stl          triangle mesh for quick viewing
  <name>/drawing/...         PDF/SVG/PPTX drawing (complete, or reference-only when the
                             automatic dimension planner cannot fully define the part)
  <name>/validation.json     the compiler's own admission report
and summary.json / summary.md for the whole run. The exit code is non-zero when any part
fails validation or its STEP build: CI is the reviewer of geometry, not the author.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

# The automatic planner refuses rather than guess; these refusals still allow a labelled
# reference drawing. Anything else is a real failure.
REFERENCE_FALLBACK = {"drawing-definition-incomplete", "drawing-layout-impossible"}


def run(cli, *args):
    result = subprocess.run(["dotnet", str(cli), *map(str, args), "--json"], capture_output=True, text=True)
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"success": False, "diagnostics": [{"code": "cli-output-unreadable", "message": result.stdout[-2000:] + result.stderr[-2000:]}]}
    return result.returncode, payload


def diagnostics(payload):
    items = payload.get("diagnostics") or payload.get("firmamentV2Validation", {}).get("diagnostics") or []
    return [{"code": d.get("code"), "severity": d.get("severity"), "message": d.get("message"), "line": d.get("line")} for d in items]


def build_part(cli, source, root):
    name = source.stem
    out = root / name
    out.mkdir(parents=True, exist_ok=False)
    record = {"part": name, "source": source.as_posix(), "ok": False, "drawing": None}

    code, validation = run(cli, "validate", source)
    (out / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    report = validation.get("firmamentV2Validation", {})
    record["validation"] = {"status": report.get("status"), "level": report.get("validationLevel"), "diagnostics": diagnostics(validation)}
    if code != 0 or report.get("status") != "valid":
        return record

    step = out / f"{name}.step"
    code, build = run(cli, "build", source, "--output", step)
    record["build"] = {"success": build.get("success"), "featureCount": build.get("featureCount"), "diagnostics": diagnostics(build)}
    if code != 0 or not build.get("success") or not step.exists():
        return record
    record["stepSha256"] = hashlib.sha256(step.read_bytes()).hexdigest()

    code, mesh = run(cli, "mesh", source, "--format", "stl", "--output", out / f"{name}.stl")
    record["mesh"] = {"success": mesh.get("success"), "watertight": mesh.get("watertight"), "triangles": mesh.get("triangleCount")}

    code, drawing = run(cli, "drawing", "generate", source, "--out-dir", out / "drawing")
    if drawing.get("success"):
        record["drawing"] = "complete"
    else:
        refused = {d.get("code") for d in diagnostics(drawing)}
        record["drawingRefusal"] = diagnostics(drawing)
        if refused and refused <= REFERENCE_FALLBACK:
            code, drawing = run(cli, "drawing", "generate", source, "--out-dir", out / "drawing-reference", "--reference-only")
            record["drawing"] = "reference-only" if drawing.get("success") else "failed"
        else:
            record["drawing"] = "failed"
    record["ok"] = True
    return record


def markdown(records, revision):
    lines = [f"### Parts built with Aetheris `{revision[:12]}`", "",
             "| Part | Valid | STEP | Features | Drawing | Notes |", "|---|---|---|---|---|---|"]
    for r in records:
        valid = r.get("validation", {}).get("status") == "valid"
        build = r.get("build", {})
        notes = []
        for stage in ("validation", "build"):
            for d in r.get(stage, {}).get("diagnostics", []):
                if d.get("severity") in ("fatal", "error"):
                    where = f" (line {d['line']})" if d.get("line") else ""
                    notes.append(f"`{d.get('code')}`{where}: {str(d.get('message', ''))[:160]}")
        if r.get("drawing") == "reference-only":
            notes.append("reference drawing: the automatic planner could not fully dimension this part")
        lines.append(f"| `{r['part']}` | {'✅' if valid else '❌'} | {'✅' if build.get('success') else '❌'} | "
                     f"{build.get('featureCount', '')} | {r.get('drawing') or ''} | {'<br>'.join(notes).replace('|', '/')} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cli", required=True, type=Path, help="Path to the pinned aetheris.dll")
    parser.add_argument("--parts", default=Path("parts"), type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--revision", default="unknown")
    args = parser.parse_args()
    if args.output.exists():
        sys.exit("Use a fresh output directory.")
    args.output.mkdir(parents=True)
    sources = sorted(args.parts.glob("*.firmament"))
    if not sources:
        sys.exit("No parts/*.firmament files found.")
    records = [build_part(args.cli, source, args.output) for source in sources]
    (args.output / "summary.json").write_text(json.dumps({"aetheris": args.revision, "parts": records}, indent=2), encoding="utf-8")
    (args.output / "summary.md").write_text(markdown(records, args.revision), encoding="utf-8")
    print(markdown(records, args.revision))
    failed = [r["part"] for r in records if not r["ok"]]
    if failed:
        sys.exit(f"Parts that did not build: {', '.join(failed)}")


if __name__ == "__main__":
    main()
