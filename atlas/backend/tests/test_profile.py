import io

from PIL import Image


def _img(fmt: str, size=(800, 600), exif_gps=False) -> bytes:
    im = Image.new("RGB", size, (200, 30, 40))
    buf = io.BytesIO()
    kw = {}
    if exif_gps and fmt == "JPEG":
        exif = Image.Exif()
        exif[0x010F] = "MiCamara"  # Make
        kw["exif"] = exif.tobytes()
    im.save(buf, fmt, **kw)
    return buf.getvalue()


def test_profile_defaults_and_update(client):
    p = client.get("/api/profile").json()
    assert p["display_name"] == "" and p["has_avatar"] is False and p["created_at"]
    created = p["created_at"]
    r = client.put("/api/profile", json={"display_name": "  Lance ", "username": "Lance.H", "preferences": "Respuestas directas"}).json()
    assert r["display_name"] == "Lance" and r["username"] == "lance.h" and r["created_at"] == created
    assert client.get("/api/settings").json()["user_name"] == "Lance"  # el saludo usa el mismo nombre
    assert "username" not in client.get("/api/settings").json()
    assert client.put("/api/profile", json={"username": "a b"}).status_code == 422


def test_avatar_upload_formats_crop_and_strip_metadata(client, tmp_path):
    for fmt, ct in (("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")):
        r = client.post("/api/profile/avatar", files={"file": (f"foto.{fmt.lower()}", _img(fmt, exif_gps=True), ct)})
        assert r.status_code == 200, r.text
        assert r.json()["has_avatar"] is True
    got = client.get("/api/profile/avatar")
    assert got.status_code == 200 and got.headers["content-type"] == "image/webp"
    im = Image.open(io.BytesIO(got.content))
    assert im.size == (512, 512) and im.format == "WEBP"
    assert not im.getexif()  # sin metadatos
    assert (tmp_path / "avatar.webp").exists()  # guardada en la carpeta de datos local


def test_avatar_rejects_bad_files(client):
    assert client.post("/api/profile/avatar", files={"file": ("x.jpg", b"no soy una imagen", "image/jpeg")}).status_code == 415
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, "GIF")
    assert client.post("/api/profile/avatar", files={"file": ("x.gif", gif.getvalue(), "image/gif")}).status_code == 415
    # extensión engañosa: un PNG renombrado a .jpg se acepta por su contenido real
    assert client.post("/api/profile/avatar", files={"file": ("x.jpg", _img("PNG"), "image/jpeg")}).status_code == 200


def test_avatar_delete(client):
    client.post("/api/profile/avatar", files={"file": ("f.png", _img("PNG"), "image/png")})
    assert client.delete("/api/profile/avatar").status_code == 204
    assert client.get("/api/profile/avatar").status_code == 404
    assert client.get("/api/profile").json()["has_avatar"] is False


def test_system_metrics_are_real(client):
    m = client.get("/api/system/metrics").json()
    assert 0 <= m["cpu_percent"] <= 100 and 0 < m["ram_percent"] <= 100 and m["ram_total_bytes"] > 0
