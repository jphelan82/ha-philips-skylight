# Releasing a new version

Home Assistant installs the add-on from a prebuilt image. The `image:` line in
`philips_skylight/config.yaml` names it: `ghcr.io/jphelan82/{arch}-philips-skylight`.
Each user's Home Assistant offers an update as soon as a new version reaches
`main`. If the image for that version does not exist yet, the update fails. So
a release always publishes the images first and pushes `main` last.

## Steps

1. **Change the version.** Set the same number in `philips_skylight/config.yaml`
   and in `VERSION` in `philips_skylight/app/skylight_addon/__init__.py`.
2. **Write the changelog.** Add a `## <version>` section at the top of
   `philips_skylight/CHANGELOG.md`. The release page uses this section as its
   notes, and the release fails without it.
3. **Check.** Run `python tools/sync_addon.py`, then the tests:

   ```bash
   python -m pytest -q
   ```

4. **Commit locally. Do not push `main` yet.**
5. **Tag the commit and push only the tag:**

   ```bash
   git tag v0.4.5
   ```

   ```bash
   git push origin v0.4.5
   ```

   The tag starts the **Publish add-on images** workflow. It refuses a tag that
   does not match the version in `config.yaml`. It builds the amd64 and aarch64
   images, pushes them, and then creates the GitHub release.

6. **Wait for the workflow to pass.** Then check that anyone can download both
   new images, without a login:

   ```bash
   python tools/check_images.py 0.4.5
   ```

   It prints `public` for each image, or `NOT downloadable`.

7. **Push `main`.** Users now see the update.

## The first release only

GitHub makes a new container package private. After the first publish, open
each package on GitHub, **amd64-philips-skylight** and
**aarch64-philips-skylight**, and choose **Package settings → Change
visibility → Public**. Later versions stay public.

## If something goes wrong

- **The workflow fails before the push.** No image exists, and `main` still
  has the old version. Fix the problem, delete the tag, and tag again:

  ```bash
  git push origin :refs/tags/v0.4.5
  ```

- **The images exist but the release page failed.** Run the release job again
  from the workflow page, or create the release by hand with the changelog
  section as notes.
- **`main` was pushed before the images existed.** Updates fail until the
  images are published. Push the tag at once.

## HACS

HACS (the Home Assistant Community Store) installs the integration from the
same GitHub releases. It shows the release tag, which is the add-on version.
The integration inside has its own version in its `manifest.json`.
