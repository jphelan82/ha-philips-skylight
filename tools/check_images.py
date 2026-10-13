"""Check that anyone can download both add-on images of a version, without a login.

Run: python tools/check_images.py 0.4.5
"""

import json
import sys
import urllib.error
import urllib.request

OWNER = "jphelan82"
ARCHES = ("amd64", "aarch64")
ACCEPT = ", ".join(
    (
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
    )
)


def public(arch, version):
    name = f"{OWNER}/{arch}-philips-skylight"
    try:
        url = f"https://ghcr.io/token?scope=repository:{name}:pull"
        with urllib.request.urlopen(url) as reply:
            token = json.load(reply)["token"]
    except urllib.error.HTTPError:
        return False  # A private or missing package gives no anonymous token.
    request = urllib.request.Request(
        f"https://ghcr.io/v2/{name}/manifests/{version}",
        method="HEAD",
        headers={"Authorization": f"Bearer {token}", "Accept": ACCEPT},
    )
    try:
        with urllib.request.urlopen(request) as reply:
            return reply.status == 200
    except urllib.error.HTTPError:
        return False


def main():
    version = sys.argv[1]
    results = {arch: public(arch, version) for arch in ARCHES}
    for arch, ok in results.items():
        print(f"{arch}-philips-skylight:{version}", "public" if ok else "NOT downloadable")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
