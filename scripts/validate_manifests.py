"""Validate that every YAML manifest in the repository parses."""
import glob
import sys

import yaml

PATTERNS = ("infra/**/*.yml", "infra/**/*.yaml", ".github/**/*.yml", "services/**/config/*.yaml")


def main() -> int:
    failures = []
    for pattern in PATTERNS:
        for path in sorted(glob.glob(pattern, recursive=True)):
            try:
                list(yaml.safe_load_all(open(path, encoding="utf-8")))
                print(f"ok   {path}")
            except yaml.YAMLError as exc:
                failures.append((path, exc))
                print(f"FAIL {path}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
