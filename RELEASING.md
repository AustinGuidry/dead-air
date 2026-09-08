# Releasing

Cutting a release is a tag push. GitHub Actions builds it, checks it, plays
it, and uploads it to PyPI.

## The four commands

Bump `version` in `pyproject.toml`, then:

    git commit -am "Release 1.0.1"
    git tag -a v1.0.1 -m "DEAD AIR 1.0.1"
    git push origin main --follow-tags

That is the whole procedure. There is no token to find and nothing to type
into a prompt.

## What happens next

`.github/workflows/publish.yml` runs on any `v*` tag. Because **a PyPI version
number can never be reused**, it tries hard not to upload something broken:

1. a tag whose version disagrees with `pyproject.toml` fails the build
2. `twine check --strict` has to pass
3. the built wheel is installed into a clean virtualenv and the game is
   played through headlessly — trailhead, brief, descent, an ending — with a
   frame actually rendered

Only then does a separate job upload, authenticating with a short-lived
credential GitHub mints for this workflow in this repository. No API token
exists on anyone's laptop or in GitHub secrets.

To exercise the build and the smoke test without releasing anything, run the
workflow by hand from the Actions tab (`workflow_dispatch`).

## If it fails

Nothing is uploaded unless every check passed, so a failed run has published
nothing. Delete the tag, fix the problem, tag again:

    git tag -d v1.0.1
    git push origin :v1.0.1

No version number is spent. Only a successful upload spends one.

## If Trusted Publishing ever needs setting up again

At <https://pypi.org/manage/project/deadair/settings/publishing/>, under
GitHub:

| field | value |
|-------|-------|
| Owner | `AustinGuidry` |
| Repository name | `dead-air` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

Two of those are easy to get wrong. The repository is `dead-air` with a
hyphen, though the PyPI project is `deadair` without one — the form wants the
GitHub name. And the workflow is the *filename*, `publish.yml`, not the
"Publish" title shown in the Actions tab.

## Version numbers

`MAJOR.MINOR.PATCH`. Prose and tuning fixes are a patch. New rooms, new
mechanics or a new act are a minor. Anything that changes what `deadair` does
on the command line, or drops a Python version, is a major.

A release can be deleted from PyPI but never re-uploaded under the same
number. If `1.0.1` goes out wrong, the fix is `1.0.2`.
