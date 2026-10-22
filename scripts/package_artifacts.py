"""Check qualification and stage only final deliverables (never drawing-base)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def stage(source, destination, aetheris_revision):
    require(not destination.exists(), "Use a fresh output directory; deliverables already exist.")
    cases = {}
    files = ["bracket.firmament", "bracket-drawing.firmament", "Bracket.step",
             "Bracket.glb", "Bracket.pdf", "Bracket.svg", "Bracket.pptx",
             "Bracket.drawing.json", "qualification.json", "validation.json"]
    for name in ("nominal", "variant"):
        directory = source / name
        qualification = read_json(directory / "qualification.json")
        reconstruction = read_json(directory / "pdf-reconstruction/pdf-qualification.json")
        validation = read_json(directory / "validation.json")["firmamentV2Validation"]
        require(validation["status"] == "valid" and validation["validationLevel"] == "Built",
                f"{name}: source was not admitted through a built validation.")
        require(reconstruction["matchingGeometry"] and reconstruction["referenceReadAfterFreeze"],
                f"{name}: PDF reconstruction did not match independently.")
        require(len(reconstruction["negativeCasesRejected"]) == 9,
                f"{name}: incomplete drawing guards missing.")
        for filename, expected in qualification["hashes"].items():
            require(hashlib.sha256((directory / filename).read_bytes()).hexdigest() == expected,
                    f"{name}: artifact changed after qualification: {filename}")
        require(qualification["pmi"]["Success"] and qualification["pmi"]["DatumCount"] == 1
                and qualification["pmi"]["DimensionCount"] == 1, f"{name}: STEP PMI missing.")
        glb = (directory / "Bracket.glb").read_bytes()
        require(glb[:4] == b"glTF" and struct.unpack_from("<II", glb, 4) == (2, len(glb)),
                f"{name}: invalid GLB container.")
        length, kind = struct.unpack_from("<II", glb, 12)
        require(kind == 0x4E4F534A, f"{name}: missing GLB JSON.")
        document = json.loads(glb[20:20 + length])
        pmi = [node["extras"]["pmi"] for node in document["nodes"] if "pmi" in node.get("extras", {})]
        require({item["kind"] for item in pmi} == {"Datum", "Diameter"}
                and all(item["stepFaceEntities"] for item in pmi), f"{name}: GLB semantic association missing.")
        cases[name] = {"dimensions": qualification["dimensions"], "hashes": qualification["hashes"],
                       "parserRoute": validation["parserRoute"], "validationLevel": validation["validationLevel"],
                       "pdfReconstructionMatches": True, "incompleteDrawingsRejected": 9,
                       "stepPmiItems": len(qualification["pmi"]["Items"]), "glbPmiItems": len(pmi),
                       "processCapabilityVerified": qualification["processCapabilityVerified"]}
        target = destination / name
        target.mkdir(parents=True)
        for filename in files:
            shutil.copy2(directory / filename, target / filename)
        shutil.copytree(directory / "pdf-reconstruction", target / "pdf-reconstruction")
    repository = Path(__file__).resolve().parents[1]
    demo_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    result = {"schema": "code-native-design-demo/1", "aetherisRevision": aetheris_revision,
              "demoRevision": demo_revision,
              "demoSourceDirty": bool(subprocess.check_output(
                  ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=repository, text=True).strip()),
              "runUrl": (f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/"
                         f"{os.environ['GITHUB_RUN_ID']}" if "GITHUB_RUN_ID" in os.environ else None),
              "cases": cases}
    (destination / "run.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("## Two qualified parametric parts\n\n"
                          "STEP AP242, GLB, PDF, SVG, PPTX and source are in the bracket artifact.\n\n"
                          "Both PDFs independently reconstructed; 18 incomplete-drawing guards rejected. "
                          "STEP and GLB retain datum/shaft PMI. Checked/approved remain blank.\n\n"
                          f"Aetheris: `{aetheris_revision}`\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--aetheris", required=True)
    args = parser.parse_args()
    try:
        stage(args.input, args.output, args.aetheris)
    except (ValueError, KeyError, OSError) as error:
        sys.exit(str(error))
