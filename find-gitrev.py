#!/usr/bin/env python

import os
import subprocess
import sys


CACHEDIR = os.path.join(os.getenv("HOME"), ".gitrev-cache")


def hash_objects(path):
    paths = []
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            paths.append(dirpath + '/' + f)

    cmd = ["git", "hash-object"] + paths
    return set(subprocess.check_output(cmd).strip().split())


def clone_repo(importpath):
    repopath = os.path.join(CACHEDIR, "src", importpath)
    if not os.path.isdir(repopath):
        if not os.path.isdir(CACHEDIR):
            os.makedirs(CACHEDIR)
        # os.chdir(CACHEDIR)
        # subprocess.check_call(["git", "clone", repo, gitpath])
        subprocess.call(["go", "get", "-d", importpath])
        os.chdir(repopath)
        return os.path.isdir(".git")
    else:
        if not os.path.isdir(os.path.join(repopath, ".git")):
            return False
        os.chdir(repopath)
        subprocess.check_call(["git", "reset", "-q", "--hard"])
        subprocess.check_call(["git", "clean", "-qfdx"])
        return True


def get_tags():
    ''' get tags from git repo in cwd '''
    tags = {}
    try:
        taglist = subprocess.check_output(["git", "show-ref", "--tags"]).strip().split('\n')
    except subprocess.CalledProcessError:
        return tags

    for line in taglist:
        rev, tag = line.strip().split(' ')
        if tag.startswith("refs/tags/"):
            tags[rev] = tag[10:]
    return tags


def find_matching_rev(objs, suggested=None):
    revs = subprocess.check_output(["git", "rev-list", "--all"]).strip().split()
    tags = get_tags()
    bestmatch, bestnmatches = None, None

    # try the tagged revisions first (even before suggested rev) but otherwise keep their order
    if len(revs) > 3000:  # we're not testing that many revs, no way... just try the tags
        revs = tags.keys()

    if suggested is not None:  # try suggested revision first (or if not a tag, after all the tags)
        if suggested in revs:
            revs.remove(suggested)
        revs = [suggested] + revs

    hastagrevs = sorted([(r not in tags, i, r) for i, r in enumerate(revs)])
    revs = [r for _, _, r in hastagrevs]

    for rev in revs:
        hashes = set(subprocess.check_output(["git", "ls-tree", "-r", rev]).strip().split())

        if len(objs) == 0:
            continue
        matches = 0
        for obj in objs:
            if obj in hashes:
                matches += 1
        if matches == len(objs):
            if rev in tags:
                rev = tags[rev]
            return rev, True
        if bestnmatches is None or matches > bestnmatches:
            bestnmatches, bestmatch = matches, rev

    if bestmatch is None:
        print >>sys.stderr, '*** no revisions?'
        return None, False

    if bestmatch in tags:
        bestmatch = tags[bestmatch]
    print >>sys.stderr, '*** closest match is', bestmatch
    print >>sys.stderr, "*** see", os.getcwd(), "to compare"
    subprocess.check_call(["git", "checkout", bestmatch])

    return bestmatch, False


def findrev(vendorpath, suggested=None):
    objs = hash_objects(vendorpath)

    abspath = os.path.abspath(vendorpath)

    is_git = clone_repo(vendorpath)
    if not is_git:
        # not a git repo, don't know how to deal with this
        print >>sys.stderr, "***", vendorpath, "not a git repo; skipping"
        if suggested is not None:
            print vendorpath, suggested
        sys.stdout.flush()
        return

    rev, exact = find_matching_rev(objs, suggested)
    if exact:
        if suggested is not None:
            if suggested == rev:
                print >>sys.stderr, "***", vendorpath, "unchanged"
            else:
                print >>sys.stderr, "***", vendorpath, rev, '<-- changed from', suggested
    else:
        print >>sys.stderr, '***', vendorpath, "closest match", rev, "(was", suggested, ')'
        subprocess.check_call(["cp", "-R", abspath, ".."])
        print >>sys.stderr, subprocess.check_output(["git", "diff"])

    print vendorpath, rev
    sys.stdout.flush()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'usage: %s [vendor path]' % sys.argv[0]
        sys.exit(1)

    os.environ["GOPATH"] = CACHEDIR

    if sys.argv[1].endswith("vendor.conf"):
        cwd = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "vendor")
        for line in open(sys.argv[1]):
            data = line.strip().split()
            if len(data) != 2:
                print line,
                continue
            repo, suggested = data
            os.chdir(cwd)
            if not os.path.isdir(repo):
                print >>sys.stderr, "***", repo, "not in vendor tree, removed"
                continue
            findrev(repo, suggested)
    else:
        cwd = os.getcwd()
        for arg in sys.argv[1:]:
            findrev(arg)
            os.chdir(cwd)
