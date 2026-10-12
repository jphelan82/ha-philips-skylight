"""Bundle canonical integration and firmware sources into the add-on build context."""

import argparse
import shutil
from pathlib import Path

from dashboard_card import generated_files

ROOT = Path(__file__).resolve().parents[1]
PAIRS = (
    (ROOT / "custom_components/philips_skylight", ROOT / "philips_skylight/companion"),
    (ROOT / "esphome", ROOT / "philips_skylight/firmware"),
)


def sources(path):
    return {
        file.relative_to(path): file
        for file in path.rglob("*")
        if file.is_file()
        and "__pycache__" not in file.parts
        and ".esphome" not in file.parts
        and file.name != "secrets.yaml"
        and file.suffix != ".pyc"
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, content in generated_files().items():
        if args.check:
            if path.read_text() != content:
                raise SystemExit(f"Dashboard card differs from its generator: {path.name}")
        else:
            path.write_text(content)
    for source, destination in PAIRS:
        files = sources(source)
        if args.check:
            bundled = sources(destination)
            if files.keys() != bundled.keys() or any(
                file.read_bytes() != bundled[name].read_bytes() for name, file in files.items()
            ):
                raise SystemExit(f"Bundle differs from canonical source: {destination}")
        else:
            if destination.exists():
                shutil.rmtree(destination)
            for name, file in files.items():
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, target)


if __name__ == "__main__":
    main()
