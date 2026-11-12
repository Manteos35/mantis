# Dosya: ~/mantis/notifier.py
import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv
import httpx

# .env dosyasını otomatik yükle
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def send_mantis_alert(
    title: str,
    price: str,
    discount: str,
    source: str,
    link: str,
    extra_info: str = "",
    contract: Optional[str] = None,
) -> bool:
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

  text = (
      f"🎯 <b>MANTIS RADAR: NEW OPPORTUNITY</b>\n"
      f"━━━━━━━━━━━━━━━━━━━━━\n"
      f"📦 <b>Asset:</b> {title}\n"
      f"💵 <b>Price:</b> <code>{price}</code>\n"
      f"🔥 <b>Momentum:</b> <b>{discount}</b>\n"
      f"🌐 <b>Network:</b> {source}\n"
      f"{f'{extra_info}\n' if extra_info else ''}"
      f"━━━━━━━━━━━━━━━━━━━━━\n"
      f"⚡ <a href='{link}'>OPEN DIRECT TERMINAL</a>"
  )

  payload: Dict[str, Any] = {
      "chat_id": CHAT_ID,
      "text": text,
      "parse_mode": "HTML",
      "disable_web_page_preview": True,
  }

  if contract:
    # All buttons MUST be URL buttons for Telegram Channels
    payload["reply_markup"] = {
        "inline_keyboard": [
            [
                {
                    "text": "🦅 Trojan",
                    "url": f"https://t.me/trojanbot?start=snipe_{contract}",
                },
                {
                    "text": "⚡ BullX",
                    "url": f"https://bullx.io/terminal?chainId=1399811149&address={contract}",
                },
            ],
            [
                {
                    "text": "📋 Share / Copy CA",
                    "url": f"https://t.me/share/url?url={contract}",
                },
                {"text": "📊 DexScreener", "url": link},
            ],
        ]
    }
  else:
    payload["reply_markup"] = {
        "inline_keyboard": [[{"text": "📊 DexScreener", "url": link}]]
    }

  async with httpx.AsyncClient(timeout=10.0) as client:
    try:
      response = await client.post(url, json=payload)
      if response.status_code == 200:
        print(f"[+] Alert dispatched: {title}")
        return True
      else:
        print(
            f"[-] Telegram API Error ({response.status_code}): {response.text}"
        )
        return False
    except Exception as e:
      print(f"[-] Dispatch request failed: {e}")
      return False
