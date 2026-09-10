"""Apple Music API plumbing: ES256 via openssl, key guard, pagination, summary.

The signing test builds a throwaway P-256 key with openssl in ``tmp_path`` and
verifies the JWT signature with openssl too — the module's DER→raw conversion
is exercised by converting back and letting openssl accept it.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dancelab.ingestion import apple_music_api as am

openssl = shutil.which("openssl")
pytestmark = pytest.mark.skipif(openssl is None, reason="openssl binary required")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _raw_to_der(raw: bytes) -> bytes:
    def integer(v: bytes) -> bytes:
        v = v.lstrip(b"\x00") or b"\x00"
        if v[0] & 0x80:
            v = b"\x00" + v
        return b"\x02" + bytes([len(v)]) + v
    body = integer(raw[:32]) + integer(raw[32:])
    return b"\x30" + bytes([len(body)]) + body


@pytest.fixture()
def key(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".dancelab" / "musickit").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    raw = tmp_path / "raw.pem"
    p8 = home / ".dancelab" / "musickit" / "AuthKey_TEST.p8"
    pub = tmp_path / "pub.pem"
    subprocess.run([openssl, "ecparam", "-name", "prime256v1", "-genkey", "-noout",
                    "-out", str(raw)], check=True, capture_output=True)
    subprocess.run([openssl, "pkcs8", "-topk8", "-nocrypt", "-in", str(raw), "-out", str(p8)],
                   check=True, capture_output=True)
    subprocess.run([openssl, "ec", "-in", str(raw), "-pubout", "-out", str(pub)],
                   check=True, capture_output=True)
    return p8, pub


def test_developer_token_is_a_valid_es256_jwt(key, tmp_path):
    p8, pub = key
    tok = am.developer_token(p8, "KEYID1234", "TEAMID1234", ttl_s=3600, now=1_700_000_000)
    head, payload, sig = tok.split(".")
    assert json.loads(_b64d(head)) == {"alg": "ES256", "kid": "KEYID1234"}
    body = json.loads(_b64d(payload))
    assert body["iss"] == "TEAMID1234"
    assert body["exp"] - body["iat"] == 3600
    raw = _b64d(sig)
    assert len(raw) == 64
    der = tmp_path / "sig.der"
    der.write_bytes(_raw_to_der(raw))
    verify = subprocess.run([openssl, "dgst", "-sha256", "-verify", str(pub),
                             "-signature", str(der)],
                            input=f"{head}.{payload}".encode(), capture_output=True)
    assert verify.returncode == 0, verify.stderr


def test_ttl_is_clamped_to_six_months(key):
    p8, _ = key
    tok = am.developer_token(p8, "K", "T", ttl_s=10 ** 9, now=0)
    body = json.loads(_b64d(tok.split(".")[1]))
    assert body["exp"] == am.MAX_TTL_S


def test_key_on_desktop_is_refused(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "Desktop").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    k = home / "Desktop" / "AuthKey.p8"
    k.write_text("x")
    with pytest.raises(ValueError, match="Desktop"):
        am.check_key_path(k)


def test_key_inside_repo_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    k = am.REPO_ROOT / "experiments_priv" / "_test_key.p8"
    k.parent.mkdir(parents=True, exist_ok=True)
    k.write_text("x")
    try:
        with pytest.raises(ValueError, match="repository"):
            am.check_key_path(k)
    finally:
        k.unlink()


def test_der_to_raw_pads_short_integers():
    r = b"\x01" * 31
    s = b"\x7f" + b"\x02" * 31
    der = b"\x30" + bytes([2 + 31 + 2 + 32]) + b"\x02\x1f" + r + b"\x02\x20" + s
    raw = am.der_to_raw(der)
    assert raw == b"\x00" + r + s


def test_all_pages_follows_next():
    pages = {
        f"{am.API}/v1/me/library/songs": {"data": [{"id": "1"}], "next": "/v1/me/library/songs?offset=1"},
        f"{am.API}/v1/me/library/songs?offset=1": {"data": [{"id": "2"}], "next": "/v1/me/library/songs?offset=2"},
        f"{am.API}/v1/me/library/songs?offset=2": {"data": [{"id": "3"}]},
    }
    seen_headers = []

    def fetch(url, params, headers):
        seen_headers.append(headers)
        return 200, {}, json.dumps(pages[url]).encode()

    c = am.AppleMusicClient("dev-secret-xyz", "user-secret-abc", fetch=fetch)
    ids = [d["id"] for d in c.all_pages("/v1/me/library/songs", {"limit": "100"})]
    assert ids == ["1", "2", "3"]
    assert seen_headers[0]["Music-User-Token"] == "user-secret-abc"
    assert "dev-secret-xyz" not in repr(c) and "user-secret-abc" not in repr(c)


def test_429_backs_off_then_succeeds():
    calls = {"n": 0}
    waits = []

    def fetch(url, params, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            return 429, {"retry-after": "7"}, b""
        return 200, {}, b'{"data": []}'

    c = am.AppleMusicClient("dev", fetch=fetch, sleep=waits.append)
    assert c.get("/v1/me/storefront") == {"data": []}
    assert waits == [7.0]


def test_summary_counts_catalog_join():
    lib = {"songs": [
        {"id": "l1", "attributes": {"playParams": {"catalogId": "100"}, "genreNames": ["Dance"]}},
        {"id": "l2", "attributes": {"playParams": {"catalogId": "200"}}},
        {"id": "l3", "attributes": {"genreNames": ["Rock"]}},          # upload, no catalog id
    ], "playlists": [{"id": "p1"}]}
    s = am.summarize(lib, {"100", "999"})
    assert s == {"songs": 3, "with_catalog_id": 2, "with_genre": 2, "playlists": 1,
                 "collection_streams": 2, "matching_collection": 1}
    assert am.summarize(lib, None)["matching_collection"] is None


def test_401_mid_run_refreshes_the_developer_token_once():
    seen = []

    def fetch(url, params, headers):
        seen.append(headers["Authorization"])
        return (401, {}, b"") if len(seen) == 1 else (200, {}, b'{"data": [1]}')

    c = am.AppleMusicClient("old-token", fetch=fetch, sleep=lambda _: None,
                            refresh=lambda: "new-token")
    assert c.get("/v1/me/library/songs") == {"data": [1]}
    assert seen == ["Bearer old-token", "Bearer new-token"]


def test_persistent_401_raises_after_the_retry_budget():
    calls = []
    c = am.AppleMusicClient("t", fetch=lambda u, p, h: (calls.append(u), (401, {}, b""))[1],
                            sleep=lambda _: None, max_retries=3)
    with pytest.raises(RuntimeError, match="401"):
        c.get("/v1/me/storefront")
    assert len(calls) == 4


def test_transient_401_is_retried_like_429():
    n = {"i": 0}

    def fetch(url, params, headers):
        n["i"] += 1
        return (401, {}, b"") if n["i"] < 3 else (200, {}, b'{"data": []}')

    c = am.AppleMusicClient("t", fetch=fetch, sleep=lambda _: None)
    assert c.get("/v1/me/library/songs") == {"data": []}
    assert n["i"] == 3
