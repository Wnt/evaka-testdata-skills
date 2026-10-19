#!/usr/bin/env python3
"""Make the eVaka backend source of one commit available locally, fast (~3 s).

Fetches ONLY that commit (depth 1) and ONLY the files this skill reads (Kotlin backend and the
DB schema) into a cache directory, with a sparse partial checkout. Do NOT use a full or
blobless clone instead: `git grep` in a blobless clone downloads files one by one and can take
minutes.

  python3 evaka_source.py <appCommit>      # prints the repo path to use as --repo

Cache: $EVAKA_SRC_CACHE or ~/.cache/evaka-src. Upstream: $EVAKA_UPSTREAM or
https://github.com/espoon-voltti/evaka.
"""
import os
import subprocess
import sys

UPSTREAM = os.environ.get("EVAKA_UPSTREAM", "https://github.com/espoon-voltti/evaka")
CACHE = os.environ.get("EVAKA_SRC_CACHE", os.path.expanduser("~/.cache/evaka-src"))
PATHS = ["service/src/main/kotlin/", "docs/db/schema.sql"]


def _git(repo, *args, check=True):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=check)


def has_commit(repo, commit):
    return _git(repo, "cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode == 0


def ensure_source(commit: str, repo: str = None) -> str:
    """Return a git repo path that contains `commit` with its backend files present locally."""
    if repo:
        if not has_commit(repo, commit):
            _git(repo, "fetch", "-q", "--depth", "1", UPSTREAM, commit)
        return repo
    if not os.path.isdir(os.path.join(CACHE, ".git")):
        os.makedirs(CACHE, exist_ok=True)
        _git(CACHE, "init", "-q")
        _git(CACHE, "remote", "add", "origin", UPSTREAM)
        _git(CACHE, "sparse-checkout", "set", "--no-cone", *PATHS)
    head = _git(CACHE, "rev-parse", "-q", "--verify", "HEAD", check=False).stdout.strip()
    if not head.startswith(commit) and not (len(commit) >= 7 and head.startswith(commit[:7])):
        if not has_commit(CACHE, commit):
            _git(CACHE, "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", commit)
            target = "FETCH_HEAD"
        else:
            target = commit
        _git(CACHE, "checkout", "-q", "--detach", target)  # fetches the sparse blobs in one batch
    return CACHE


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        print(ensure_source(sys.argv[1]))
    except subprocess.CalledProcessError as e:
        sys.exit(f"git {' '.join(e.cmd[3:])} failed: {e.stderr.strip()}")
