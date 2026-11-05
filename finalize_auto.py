"""Create explicit game-root ZIPs only after the deployment/startup fixtures pass."""
from pathlib import Path
import json
import tempfile
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
    archives, staged = [], []
    def stage(target):
        # Do not truncate a previously usable release when archive creation is
        # interrupted (for example, a full disk). No recursive cleanup is used.
        with tempfile.NamedTemporaryFile(prefix="." + target.name + ".", suffix=".tmp", dir=destination, delete=False) as handle:
            temporary = Path(handle.name)
        staged.append((temporary, target))
        return temporary
    try:
        for package, members in ready:
            archive = destination / package["archive"]
            temporary = stage(archive)
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
                for member in members:
                    file = ROOT / package["package"] / member
                    if member.startswith("/") or ".." in Path(member).parts or file.is_symlink():
                        raise ValueError("Unsafe archive member")
                    entry = zipfile.ZipInfo(member, (2026, 11, 6, 0, 0, 0))
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    entry.external_attr = 0o644 << 16
                    output.writestr(entry, file.read_bytes())
            with zipfile.ZipFile(temporary) as checked:
                if checked.testzip() is not None or sorted(checked.namelist()) != sorted(members):
                    raise ValueError("ZIP membership/CRC failed")
            archives.append({"file": archive.name, "version": package["version"], "bytes": temporary.stat().st_size, "members": len(members)})
        summary = stage(destination / "release-summary.json")
        summary.write_text(json.dumps({"archives": archives,
            "upstreamRelease": "0.4.6", "deployment": "Vortex Enable/Deploy; automatic next startup", "manualApplyRequired": False,
            "fixtureScenarios": len(report["scenarios"]),
            "mixedReleaseScenarios": len(report.get("mixedReleaseCases", [])),
            "totalFixtureScenarios": len(report["scenarios"]) + len(report.get("mixedReleaseCases", [])),
            "publishedToNexus": False, "gameplayVerified": False,
            "archiveWideHashScan": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Every archive is complete and checked before replacing any published
        # file. Each rename is atomic; the summary becomes visible last.
        for temporary, target in staged:
            temporary.replace(target)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    print(json.dumps({"archives": archives, "published": False, "manualApplyRequired": False}))


if __name__ == "__main__":
    main()
