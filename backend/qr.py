"""SAP-Charitas | Imagem do QR code (precisa do pacote qrcode[pil], veja requirements.txt)."""
import io
import os


def base_url(request) -> str:
    """Endereco publico do site: APP_BASE_URL do .env ou, se nao houver, o endereco da requisicao."""
    return (os.getenv("APP_BASE_URL") or request.url_root).rstrip("/")


def png_bytes(url: str) -> bytes:
    import qrcode
    buf = io.BytesIO()
    qrcode.make(url).save(buf, format="PNG")
    return buf.getvalue()
