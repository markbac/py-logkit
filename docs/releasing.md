# Releasing

Releases follow [Semantic Versioning](https://semver.org/). The version lives in one place,
`ctxlogkit/_version.py`, and the build reads it from there.

## Cutting a release

1. Move the entries under `## Unreleased` in `CHANGELOG.md` into a new `## X.Y.Z - YYYY-MM-DD`
   heading, and leave an empty `## Unreleased` section above it.
1. Set `__version__` in `ctxlogkit/_version.py` to `X.Y.Z`.
1. Open a pull request with those two changes and merge it once CI is green.
1. Tag the merge commit and push the tag:

    ```bash
    git tag -a vX.Y.Z -m "Release X.Y.Z"
    git push origin vX.Y.Z
    ```

Pushing a `v*` tag runs `.github/workflows/release.yml`. It checks that the tag matches
`__version__`, builds the sdist and wheel, runs `twine check`, attaches both to a GitHub release
whose notes are generated from the merged pull requests, and publishes them to PyPI.

## Publishing to PyPI

Publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/), so no API token is
stored in the repository. Set it up once, before the first release:

1. On pypi.org, go to *Your projects* then *Publishing* and add a pending publisher for the project
   name `ctxlogkit`. A pending publisher reserves the name and creates the project on the first upload.
2. Use owner `markbac`, repository `py-logkit`, workflow `release.yml` and environment `pypi`.
3. In the repository settings, create an environment called `pypi`. Adding a required reviewer there
   makes each publish wait for an approval.

The name `ctxlogkit` was checked and was free when the project was renamed from `pylogkit` (issue #44).
