import asyncio
import os
import time
from typing import Dict
from dotenv import load_dotenv
import httpx

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


_STATS: Dict[str, int] = {"scanned": 0, "passed": 0, "dispatched": 0}
_START_TIME = time.time()


def inc_scanned(count: int = 1) -> None:
  _STATS["scanned"] += count


def inc_passed(count: int = 1) -> None:
  _STATS["passed"] += count


def inc_dispatched(count: int = 1) -> None:
  _STATS["dispatched"] += count


def reset_stats() -> Dict[str, int]:
  snapshot = _STATS.copy()
  _STATS["scanned"] = 0
  _STATS["passed"] = 0
  _STATS["dispatched"] = 0
  return snapshot


async def send_system_message(text: str) -> bool:
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
  payload = {
      "chat_id": CHAT_ID,
      "text": text,
      "parse_mode": "HTML",
      "disable_web_page_preview": True,
  }
  async with httpx.AsyncClient(timeout=8.0) as client:
    try:
      res = await client.post(url, json=payload)
      return res.status_code == 200
    except Exception as e:
      print(f"[MONITOR] Failed to send system alert: {e}")
      return False


async def send_hourly_report() -> None:
  stats = reset_stats()
  uptime_hours = (time.time() - _START_TIME) / 3600
  rugs_blocked = max(0, stats["passed"] - stats["dispatched"])

  report = (
      f"📡 <b>MANTIS TELEMETRY (1H REPORT)</b>\n"
      f"━━━━━━━━━━━━━━━━━━━━━\n"
      f"🔍 <b>Scanned:</b> {stats['scanned']}<i> tokens</i>\n"
      f"✅ <b>Passed Liquidity/Vol:</b> {stats['passed']}\n"
      f"🛡️ <b>Rugs Blocked:</b> {rugs_blocked}\n"
      f"📨 <b>Dispatched:</b> {stats['dispatched']}\n"
      f"⏱️ <b>Uptime:</b> {uptime_hours:.1f}h\n"
      f"━━━━━━━━━━━━━━━━━━━━━"
  )
  await send_system_message(report)
  print(
      f"[MONITOR] Hourly report dispatched: Scanned={stats['scanned']} |"
      f" Passed={stats['passed']} | Sent={stats['dispatched']}"
  )


async def hourly_report_loop(interval_seconds: int = 3600) -> None:
  while True:
    await asyncio.sleep(interval_seconds)
    try:
      await send_hourly_report()
    except Exception as e:
      print(f"[MONITOR] Error in hourly report loop: {e}")


async def send_crash_alert(error_msg: str) -> None:
  alert = (
      "🚨 <b>⚠️ MANTIS ENGINE OFFLINE!</b>\n"
      "━━━━━━━━━━━━━━━━━━━━━\n"
      "Critical exception terminated the scanner process.\n"
      f"<b>Error:</b> <code>{error_msg[:300]}</code>\n"
      "<i>PM2 auto-recovery will attempt restart...</i>"
  )
  await send_system_message(alert)
