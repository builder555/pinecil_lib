import subprocess
import os
import uuid


class ReleaseNotes:
    def __init__(self):
        self.breaking = []
        self.features = []
        self.fixes = []
        self.other = []

    def add_breaking(self, commit):
        self.breaking.append(commit.removeprefix("fix!").removeprefix("feat!"))

    def add_features(self, commit):
        self.features.append(commit.removeprefix("feat:"))

    def add_fixes(self, commit):
        self.fixes.append(commit.removeprefix("fix:"))

    def add_other(self, commit):
        self.other.append(commit.removeprefix("chore:"))

    def __repr__(self):
        text = ""
        if self.breaking:
            text += "## Breaking Changes\n* " + "\n* ".join(self.breaking) + "\n\n"
        if self.features:
            text += "## Features\n* " + "\n* ".join(self.features) + "\n\n"
        if self.fixes:
            text += "## Fixes\n* " + "\n* ".join(self.fixes) + "\n\n"
        if self.other:
            text += "## Other\n* " + "\n* ".join(self.other) + "\n\n"
        return text


def get_last_tag() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "describe", "--tags", "--abbrev=0"], stderr=subprocess.PIPE
            )
            .strip()
            .decode()
        )
    except subprocess.CalledProcessError:
        return ""


def get_commit_messages(since_tag: str):
    command = ["git", "log", "--pretty=format:%s (%h)"]
    if since_tag:
        command.append(f"{since_tag}..HEAD")
    return subprocess.check_output(command).strip().decode().split("\n")


def parse_commits(commits: list[str]) -> tuple[ReleaseNotes, dict[str, int]]:
    notes = ReleaseNotes()
    version_bump = {"major": 0, "minor": 0, "patch": 0}

    for commit in commits:
        if commit.startswith("fix!") or commit.startswith("feat!"):
            version_bump["major"] += 1
            version_bump["minor"] = 0
            version_bump["patch"] = 0
            notes.add_breaking(commit)
        elif commit.startswith("fix:"):
            version_bump["patch"] += 1
            notes.add_fixes(commit)
        elif commit.startswith("feat:"):
            version_bump["minor"] += 1
            version_bump["patch"] = 0
            notes.add_features(commit)
        else:
            notes.add_other(commit)

    return notes, version_bump


def increment_version(last_version: str, version_bump: dict[str, int]):
    if not last_version:
        last_version = "0.0.0"
    major, minor, patch = [int(v.strip()) for v in last_version.strip("v").split(".")]
    major += version_bump["major"]
    minor += version_bump["minor"]
    patch += version_bump["patch"]
    return f"{major}.{minor}.{patch}"


def main():
    last_tag = get_last_tag()
    commits = get_commit_messages(last_tag)
    release_notes, version_bump = parse_commits(commits)
    if not (version_bump["major"] or version_bump["minor"] or version_bump["patch"]):
        print("No new release")
        return
    new_version = increment_version(last_tag, version_bump)
    set_output("tag", f"v{new_version}")
    set_output("version", new_version)
    set_output("release_notes", release_notes)
    print(f"Release {new_version} created with notes: \n{release_notes}")


def set_output(name, value):
    with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
        delimiter = uuid.uuid1()
        print(f"{name}<<{delimiter}", file=fh)
        print(value, file=fh)
        print(delimiter, file=fh)


if __name__ == "__main__":
    main()
