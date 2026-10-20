"""Explicit one-package inactive import; no app startup, watcher or model work."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--allow-test-profiles", action="store_true")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "packages/jse_intelligence_core/src"))
    from application.release_inbox import ReleaseInbox, StorageError, Rejection, load_profiles
    from application.release_inbox.protocol import plain_path
    try:
        package, store, profiles = map(plain_path, (args.package, args.store, args.profiles))
        if (store == package or package in store.parents or store in package.parents
                or package == profiles or package in profiles.parents):
            raise Rejection("UNSAFE_PATH")
        importer = ReleaseInbox(store, load_profiles(profiles), allow_test_profiles=args.allow_test_profiles)
        ack = importer.process(package)
    except (Rejection, StorageError, OSError, ValueError):
        print(json.dumps({"error": "LOCAL_INBOX_CONFIGURATION_OR_STORAGE_ERROR"}))
        return 4
    print(json.dumps(ack, sort_keys=True))
    return 0 if ack["outcome"] in ("IMPORTED_INACTIVE", "ALREADY_IMPORTED") else 2 if ack["outcome"] == "PENDING" else 3


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
