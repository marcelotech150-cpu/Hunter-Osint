"""
Bot OSINT de Telegram para Termux.
Extrae información de usuarios usando Pyrogram con tu cuenta propia.
"""

import asyncio
import logging
from datetime import datetime
from io import BytesIO

from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.errors import UsernameNotOccupied, InvalidId, UserNotFound
from pyrogram.types import Message

load_dotenv()

# ── Configuración ──────────────────────────────────────────────
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION = os.environ.get("SESSION_NAME", "osint")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("osint_bot")

app = Client(SESSION, api_id=API_ID, api_hash=API_HASH, plugins=dict(root=""))


# ── Helpers ────────────────────────────────────────────────────

def parse_target(text: str):
    """Resuelve '@usuario', 'usuario' o 'ID numérico' a identificador."""
    text = text.strip()
    if text.startswith("@"):
        return text[1:]
    if text.isdigit():
        return int(text)
    return text


def fmt_last_seen(user) -> str:
    """Formatea el campo last_seen en texto legible."""
    import pyrogram.helpers as h
    try:
        return h.parse_last_online(user.last_online_date, user.is_bot)
    except Exception:
        return "desconocido"


async def get_user_details(app, target):
    """Devuelve un dict con toda la info extraíble del usuario."""
    user = await app.get_users(target)
    if isinstance(user, tuple):
        user = user[0]

    photo_url = f"https://t.me{i}.telegram.org/img/{user.id}.jpg" if False else None

    # Construir enlace de perfil
    profile_link = f"https://t.me/{user.username}" if user.username else None

    details = {
        "id": user.id,
        "primer_nombre": user.first_name or "",
        "apellidos": user.last_name or "",
        "nombre_completo": user.first_name and f"{user.first_name} {user.last_name}".strip() or "",
        "username": f"@{user.username}" if user.username else "—",
        "bio": user.bio or "—",
        "verificado": bool(user.verified),
        "premium": bool(getattr(user, "is_premium", False)),
        "scam": bool(getattr(user, "is_scam_confirmed", False)),
        "es_bot": user.is_bot,
        "en_linea": fmt_last_seen(user),
        "es_contacto": bool(getattr(user, "is_contact", False)),
        "tiene_foto": bool(user.photo),
        "enlace": profile_link or "—",
        "objeto": user,
    }
    return details


def format_profile(d: dict) -> str:
    """Renderiza el perfil en texto bonito."""
    verif = "✅ Sí" if d["verificado"] else "❌ No"
    prem = "✅ Sí" if d["premium"] else "❌ No"
    scam = "⚠️ Posible" if d["scam"] else "❌ No"
    bot = "🤖 Sí" if d["es_bot"] else "❌ No"
    contact = "✅ Sí" if d["es_contacto"] else "❌ No"
    foto = "📷 Sí" if d["tiene_foto"] else "📷 No"

    lines = [
        "👤 INFORMACIÓN DEL USUARIO",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        f"🆔 ID numérico : {d['id']}",
        f"👁 Nombre       : {d['primer_nombre']} {d['apellidos']}".rstrip(),
        f"🔤 Username     : {d['username']}",
        f"📝 Bio          : {d['bio']}",
        f"✅ Verificado   : {verif}",
        f"⭐ Premium      : {prem}",
        f"⚠️ Scam         : {scam}",
        f"🤖 Es bot       : {bot}",
        f"🟢 Última vez   : {d['en_linea']}",
        f"📇 Contacto     : {contact}",
        f"📷 Foto         : {foto}",
        f"🔗 Enlace       : {d['enlace']}",
    ]
    return "\n".join(lines)


async def enviar_foto(msg: Message, user) -> bool:
    """Descarga y envía la foto de perfil. Devuelve True si hubo foto."""
    if not user.photo:
        return False
    try:
        data = await app.download_media(user.photo.file_id, in_memory=True)
        buf = BytesIO(data)
        buf.name = f"perfil_{user.id}.jpg"
        await msg.reply_photo(buf, caption=f"📷 Foto de perfil — {user.first_name}")
        return True
    except Exception as e:
        logger.warning(f"No se pudo descargar la foto: {e}")
        await msg.reply_text("⚠️ No pude descargar la foto de perfil.")
        return False


# ── Comandos ───────────────────────────────────────────────────

@app.on_message(filters.command(["help", "ayuda"]))
async def cmd_ayuda(msg: Message):
    text = (
        "🔍 BOT OSINT DE TELEGRAM\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "/id <username>    — Resuelve a ID numérico\n"
        "/info <username o ID> — Perfil completo\n"
        "/foto <username o ID> — Foto de perfil\n"
        "/ayuda            — Esta ayuda\n"
        "\nEjemplos:\n"
        "/id duqueleo\n"
        "/info 123456789\n"
        "/foto duqueleo"
    )
    await msg.reply_text(text)


@app.on_message(filters.command(["id"]))
async def cmd_id(msg: Message):
    if len(msg.command) < 2:
        await msg.reply_text("Usa: /id <username>")
        return
    try:
        user = await app.get_users(parse_target(msg.command[1]))
        if isinstance(user, tuple):
            user = user[0]
        await msg.reply_text(f"🆔 ID numérico de @{msg.command[1]}: {user.id}")
    except (UsernameNotOccupied, InvalidId, UserNotFound):
        await msg.reply_text("❌ Usuario no encontrado.")


@app.on_message(filters.command(["info"]))
async def cmd_info(msg: Message):
    if len(msg.command) < 2:
        await msg.reply_text("Usa: /info <username o ID>")
        return
    try:
        d = await get_user_details(app, parse_target(msg.command[1]))
        await msg.reply_text(format_profile(d))
        await enviar_foto(msg, d["objeto"])
    except (UsernameNotOccupied, InvalidId, UserNotFound):
        await msg.reply_text("❌ Usuario no encontrado.")
    except Exception as e:
        logger.exception("Error en /info")
        await msg.reply_text(f"⚠️ Error: {e}")


@app.on_message(filters.command(["foto"]))
async def cmd_foto(msg: Message):
    if len(msg.command) < 2:
        await msg.reply_text("Usa: /foto <username o ID>")
        return
    try:
        user = await app.get_users(parse_target(msg.command[1]))
        if isinstance(user, tuple):
            user = user[0]
        if not user.photo:
            await msg.reply_text("❌ Este usuario no tiene foto de perfil.")
        else:
            await enviar_foto(msg, user)
    except (UsernameNotOccupied, InvalidId, UserNotFound):
        await msg.reply_text("❌ Usuario no encontrado.")


# ── Inicio ─────────────────────────────────────────────────────

@app.on_message(filters.private & filters.command(["start"]))
async def cmd_start(msg: Message):
    await msg.reply_text(
        "🔍 Bot OSINT iniciado. Escribe /ayuda para ver los comandos."
    )


if __name__ == "__main__":
    import os
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Bot detenido.")
