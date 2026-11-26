"""Build an installable Dogbone ZIP from a local release tag."""
import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILES = ("Dogbone.py", "Dogbone.manifest", "config.py", "constants.py",
                 "commands", "lib", "py_packages", "resources", "README.md")


def build(tag):
    if not re.fullmatch(r"v?[0-9]+(?:\.[0-9]+){1,3}", tag):
        raise ValueError("Expected a numeric release tag such as v2.4")
    archive = subprocess.check_output(
        ["git", "archive", "--format=zip", "--prefix=Dogbone/", f"refs/tags/{tag}",
         "--", *PACKAGE_FILES], cwd=ROOT)
    result = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(archive)) as source, zipfile.ZipFile(result, "w") as target:
        for entry in source.infolist():
            data = source.read(entry)
            if entry.filename == "Dogbone/Dogbone.manifest":
                manifest = json.loads(data)
                manifest["version"] = tag.lstrip("v")
                data = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
            target.writestr(entry, data)
    output = ROOT / "dist" / f"Dogbone-{tag}.zip"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(result.getvalue())
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="locally available release tag")
    print(build(parser.parse_args().tag))
