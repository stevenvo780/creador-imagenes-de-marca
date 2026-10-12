"""Capacidades exactas emitidas por Eikón; nunca URL local inventada."""

from urllib.parse import urlsplit


def _atoms(raw):
    pos = 0
    while pos + 8 <= len(raw):
        size, name = int.from_bytes(raw[pos : pos + 4], "big"), raw[pos + 4 : pos + 8]
        header = 8
        if size == 1:
            size, header = int.from_bytes(raw[pos + 8 : pos + 16], "big"), 16
        if size == 0:
            size = len(raw) - pos
        if size < header or pos + size > len(raw):
            raise ValueError("invalid_mp4")
        yield name, raw[pos + header : pos + size]
        pos += size
    if pos != len(raw):
        raise ValueError("invalid_mp4")


def _no_edit_lists(raw):
    for name, child in _atoms(raw):
        if name == b"elst":
            return False
        if name in {b"trak", b"edts", b"mdia", b"minf", b"stbl"} and not _no_edit_lists(child):
            return False
    return True


def _closed_h264(raw):
    """Regla conservadora: toda slice intra debe ser IDR (no open-GOP/recovery)."""
    import re

    idr = False
    for nal in re.split(b"\x00\x00\x00?\x01", raw):
        if not nal:
            continue
        kind = nal[0] & 31
        if kind == 5:
            idr = True
        if kind != 1:
            continue
        header = nal[1:32].replace(b"\x00\x00\x03", b"\x00\x00")
        bits = "".join(f"{n:08b}" for n in header)
        pos, values = 0, []
        for _ in range(2):
            zeros = 0
            while pos < len(bits) and bits[pos] == "0":
                pos += 1
                zeros += 1
            if pos + zeros >= len(bits):
                return False
            values.append(int(bits[pos : pos + zeros + 1], 2) - 1)
            pos += zeros + 1
        if values[1] % 5 in (2, 4):
            return False
    return idr


def _bounded_tool(command, directory, maximum):
    import subprocess
    from pathlib import Path

    output = Path(directory) / "probe-output"
    with output.open("wb") as handle:
        subprocess.run(
            [
                "/usr/bin/prlimit",
                "--as=1073741824",
                "--cpu=20",
                "--nofile=64",
                f"--fsize={maximum}",
                "--",
                *command,
            ],
            stdout=handle,
            stderr=subprocess.DEVNULL,
            timeout=25,
            check=True,
        )
    return output.read_bytes()


def _qualify_video(variant, platform):
    import json
    import math
    import tempfile
    from fractions import Fraction
    from pathlib import Path

    raw = variant["content"]
    if not 0 < len(raw) <= 32 * 1024 * 1024:
        return False
    atoms = list(_atoms(raw))
    if platform == "instagram":
        names = [name for name, _ in atoms]
        if names.index(b"moov") > names.index(b"mdat"):
            return False
        if not _no_edit_lists(atoms[names.index(b"moov")][1]):
            return False
    with tempfile.TemporaryDirectory(prefix="eikon-qualify-") as directory:
        path = Path(directory) / "approved.mp4"
        path.write_bytes(raw)
        probe = json.loads(
            _bounded_tool(
                [
                    "/usr/bin/ffprobe",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file",
                    "-threads",
                    "1",
                    "-show_entries",
                    "format=duration:stream=codec_type,codec_name,width,height,pix_fmt,field_order,avg_frame_rate,bit_rate,sample_rate,channels",
                    "-of",
                    "json",
                    str(path),
                ],
                directory,
                1024 * 1024,
            )
        )
        videos = [s for s in probe["streams"] if s["codec_type"] == "video"]
        audio = [s for s in probe["streams"] if s["codec_type"] == "audio"]
        if len(videos) != 1 or len(audio) > 1 or len(probe["streams"]) != 1 + len(audio):
            return False
        v, duration = videos[0], float(probe["format"]["duration"])
        fps, width, height = float(Fraction(v["avg_frame_rate"])), int(v["width"]), int(v["height"])
        if not (
            math.isfinite(duration)
            and 3 <= duration <= 60
            and 23 <= fps <= 60
            and 0 < width <= 1920
            and height > 0
            and 0.01 <= width / height <= 10
            and v["codec_name"] == "h264"
            and v["pix_fmt"] == "yuv420p"
            and v.get("field_order") == "progressive"
            and 0 < int(v.get("bit_rate", 0)) <= 25_000_000
        ):
            return False
        if (
            platform == "facebook"
            and variant.get("channel_metadata", {}).get("publication_format") == "reel"
            and (width < 540 or height < 960 or width * 16 != height * 9 or fps < 24)
        ):
            return False
        if audio and not (
            audio[0]["codec_name"] == "aac"
            and 0 < int(audio[0].get("sample_rate", 0)) <= 48000
            and audio[0].get("channels") in (1, 2)
            and 0 < int(audio[0].get("bit_rate", 0)) <= 128000
        ):
            return False
        elementary = _bounded_tool(
            [
                "/usr/bin/ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-protocol_whitelist",
                "file,pipe",
                "-threads",
                "1",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-bsf:v",
                "h264_mp4toannexb",
                "-f",
                "h264",
                "pipe:1",
            ],
            directory,
            40 * 1024 * 1024,
        )
        return _closed_h264(elementary)


def qualify_media(variant, platform):
    """Verifica bytes sin convertirlos. Un fallo local no certifica límites remotos."""
    import io

    from PIL import Image

    try:
        if variant["media"]["mime"] == "video/mp4":
            return "verified" if _qualify_video(variant, platform) else "unsupported_media"
        with Image.open(io.BytesIO(variant["content"])) as image:
            expected = {"image/jpeg": "JPEG", "image/png": "PNG"}.get(variant["media"]["mime"])
            if image.format != expected:
                return "unsupported_media"
            width, height = image.size
            image.verify()
        if platform == "instagram" and (
            expected != "JPEG"
            or len(variant["content"]) > 8_000_000
            or not 320 <= width <= 1440
            or not 0.8 <= width / height <= 1.91
        ):
            return "unsupported_media"
        if platform == "tiktok" and (
            expected != "JPEG" or len(variant["content"]) > 20_000_000 or max(width, height) > 1080
        ):
            return "unsupported_media"
        return "verified"
    except Exception:
        return "unsupported_media"


class MediaDelivery:
    def __init__(self, client, outbox):
        self.client, self.outbox = client, outbox

    def issue(self, claim, sha256, *, now, minimum_seconds):
        ticket = self.client.issue_ticket(claim)
        parsed = urlsplit(ticket["url"])
        if (
            ticket["attempt_id"] != claim["attempt_id"]
            or ticket["media_sha256"] != sha256
            or parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/api/v1/publications/delivery-media/")
        ):
            raise ValueError("invalid_delivery_capability")
        self.outbox.record_ticket(claim["attempt_id"], ticket)
        current = now() if callable(now) else now
        if ticket["expires_at"] - current < minimum_seconds:
            self.client.revoke_ticket(claim["attempt_id"], ticket["id"])
            self.outbox.revoked(claim["attempt_id"], ticket["id"])
            raise ValueError("delivery_lifetime_insufficient")
        return ticket

    def revoke(self, attempt):
        for current, ticket, _ in self.outbox.tickets():
            if current == attempt:
                self.client.revoke_ticket(current, ticket)
                self.outbox.revoked(current, ticket)

    def expire(self, now):
        for attempt, ticket, expiry in self.outbox.tickets():
            if expiry <= now:
                try:
                    self.client.revoke_ticket(attempt, ticket)
                    self.outbox.revoked(attempt, ticket)
                except Exception:
                    # El servidor también aplica TTL; conservar el revoke pendiente.
                    pass
