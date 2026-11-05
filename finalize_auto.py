"""Create explicit game-root ZIPs only after the deployment/startup fixtures pass."""
from pathlib import Path
import json
import zipfile

ROOT = Path(__file__).resolve().parent


def read(file):
    return json.loads(file.read_text(encoding="utf-8-sig"))


def relative(value):
    return isinstance(value, str) and value and not value.startswith("/") and "\\" not in value and ":" not in value and all(part not in {"", ".", ".."} for part in value.split("/"))


def main():
    report = read(ROOT / "build/functional-report.json")
    build = read(ROOT / "build/build-summary.json")
    if report.get("allPassed") is not True or report.get("buildId") != build.get("buildId"):
        raise ValueError("A successful current functional report is required")
    ready = []
    for package in read(ROOT / "build/package-roots.json"):
        if package.get("feature") not in {"codex", "japanese"} or package.get("package") != "build/packages/" + package["feature"]:
            raise ValueError("Package root must be this build's relative feature folder")
        if not relative(package.get("archive")) or "/" in package["archive"]:
            raise ValueError("Archive must be a plain release filename")
        package_root = ROOT / package["package"]
        if package_root.is_symlink() or not package_root.resolve().is_relative_to((ROOT / "build/packages").resolve()):
            raise ValueError("Unsafe package root")
        members = read(ROOT / "build" / (package["feature"] + "-members.json"))
        if len(members) != len(set(members)):
            raise ValueError("Duplicate package membership")
        for member in members:
            file = package_root / member
            if not relative(member) or file.is_symlink() or not file.resolve().is_relative_to(package_root.resolve()):
                raise ValueError("Unsafe archive member")
        current = {member: [(package_root / member).stat().st_size, (package_root / member).stat().st_mtime_ns] for member in members}
        if current != report.get("checkedPackageState", {}).get(package["feature"]):
            raise ValueError("Package files changed after functional checks; run the tests again before creating ZIPs")
        for member in members:
            if member.startswith("/") or ".." in Path(member).parts or (ROOT / package["package"] / member).is_symlink():
                raise ValueError("Unsafe archive member")
        ready.append((package, members))
    destination = ROOT / "releases"
    destination.mkdir(exist_ok=True)
    archives = []
    for package, members in ready:
        archive = destination / package["archive"]
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            for member in members:
                file = ROOT / package["package"] / member
                if member.startswith("/") or ".." in Path(member).parts or file.is_symlink():
                    raise ValueError("Unsafe archive member")
                entry = zipfile.ZipInfo(member, (2026, 11, 6, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o644 << 16
                output.writestr(entry, file.read_bytes())
        with zipfile.ZipFile(archive) as checked:
            if checked.testzip() is not None or sorted(checked.namelist()) != sorted(members):
                raise ValueError("ZIP membership/CRC failed")
        archives.append({"file": archive.name, "version": package["version"], "bytes": archive.stat().st_size, "members": len(members)})
    (destination / "release-summary.json").write_text(json.dumps({"archives": archives,
        "upstreamRelease": "0.4.6", "deployment": "Vortex Enable/Deploy; automatic next startup", "manualApplyRequired": False,
        "fixtureScenarios": len(report["scenarios"]),
        "mixedReleaseScenarios": len(report.get("mixedReleaseCases", [])),
        "totalFixtureScenarios": len(report["scenarios"]) + len(report.get("mixedReleaseCases", [])),
        "publishedToNexus": False, "gameplayVerified": False,
        "archiveWideHashScan": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"archives": archives, "published": False, "manualApplyRequired": False}))


if __name__ == "__main__":
    main()
