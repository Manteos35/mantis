import functools, builtins; builtins.print = functools.partial(print, flush=True)
import asyncio
from typing import Any, Dict, List, Optional
import httpx
import monitor
import notifier
from scorer import check_token
from state import cleanup_old, is_seen, mark_seen

MIN_LIQUIDITY_USD = 15000
MIN_VOLUME_M5 = 5000
TARGET_CHAINS = ["solana", "base"]

DEX_SEMAPHORE = asyncio.Semaphore(3)
ALERT_LOCK = asyncio.Lock()


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    sem: asyncio.Semaphore,
    max_retries: int = 3,
) -> Optional[Any]:
  """Fetches JSON with concurrency control, 429 rate-limit handling (60s), and exponential backoff."""
  for attempt in range(max_retries):
    async with sem:
      try:
        res = await client.get(url)
        if res.status_code == 200:
          return res.json()
        if res.status_code == 429:
          print(
              f"[!] Rate limit (429) hit on {url}. Backing off for 60"
              " seconds..."
          )
          await asyncio.sleep(60)
          continue
        if res.status_code >= 500:
          wait_time = 2**attempt
          print(
              f"[!] Server error ({res.status_code}). Retrying in"
              f" {wait_time}s..."
          )
          await asyncio.sleep(wait_time)
          continue
        return None
      except (httpx.RequestError, httpx.TimeoutException) as e:
        wait_time = 2**attempt
        print(
            f"[!] Network error ({e}). Attempt {attempt + 1}/{max_retries},"
            f" retrying in {wait_time}s..."
        )
        await asyncio.sleep(wait_time)
      except Exception as e:
        print(f"[!] Unexpected fetch error: {e}")
        return None
  return None


async def process_token(
    client: httpx.AsyncClient, chain_id: str, token_address: str
) -> None:
  """Evaluates liquidity, volume, and security for a single token."""
  if is_seen(token_address):
    return

  monitor.inc_scanned()

  pair_url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
  pair_data = await fetch_json(client, pair_url, DEX_SEMAPHORE)
  if not pair_data or not isinstance(pair_data, dict):
    return

  pairs = pair_data.get("pairs")
  if not pairs:
    return

  best_pair = max(
      pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0)
  )

  liquidity = float(best_pair.get("liquidity", {}).get("usd", 0) or 0)
  vol_m5 = float(best_pair.get("volume", {}).get("m5", 0) or 0)

  if liquidity < MIN_LIQUIDITY_USD or vol_m5 < MIN_VOLUME_M5:
    return

  monitor.inc_passed()
  mark_seen(token_address)

  price_usd = best_pair.get("priceUsd", "N/A")
  price_change_m5 = best_pair.get("priceChange", {}).get("m5", 0) or 0
  symbol = best_pair.get("baseToken", {}).get("symbol", "UNKNOWN")
  name = best_pair.get("baseToken", {}).get("name", "Unknown")
  dex_url = best_pair.get(
      "url", f"https://dexscreener.com/{chain_id}/{token_address}"
  )

  # Stage 1: On-Chain Security Verification
  security = await check_token(token_address, chain_id, client)
  risk_score = security["risk_score"]

  if not security["passed"]:
    print(
        f"[-] Rejected {symbol} ({token_address[:6]}...) on {chain_id.upper()}"
        f" | Risk: {risk_score}/100 | Reason: {security['reason']}"
    )
    return

  notes = (
      f"💧 <b>Liq:</b> ${liquidity:,.0f} | 📊 <b>5m Vol:</b> ${vol_m5:,.0f}\n"
      f"🛡️ <b>Risk Score:</b> {risk_score}/100 (VERIFIED)\n"
      f"🔗 <b>CA:</b> <code>{token_address}</code>"
  )
  change_str = (
      f"+{price_change_m5}%" if price_change_m5 > 0 else f"{price_change_m5}%"
  )

  async with ALERT_LOCK:
    sent = await notifier.send_mantis_alert(
        title=f"{name} (${symbol})",
        price=f"${price_usd}",
        discount=f"5m Surge: {change_str}",
        source=f"DexScreener ({chain_id.upper()})",
        link=dex_url,
        extra_info=notes,
        contract=token_address,
    )
    if sent:
      monitor.inc_dispatched()
    await asyncio.sleep(2.5)


async def scan_chain(
    client: httpx.AsyncClient, chain_id: str, addresses: List[str]
) -> None:
  """Processes all candidate tokens for a specific chain concurrently."""
  if not addresses:
    return
  tasks = [process_token(client, chain_id, addr) for addr in addresses]
  await asyncio.gather(*tasks, return_exceptions=True)


async def scan_market(client: httpx.AsyncClient) -> None:
  """Fetches discovery feeds and fans out parallel tasks per chain."""
  urls = [
      "https://api.dexscreener.com/token-profiles/latest/v1",
      "https://api.dexscreener.com/token-boosts/latest/v1",
  ]

  feeds = await asyncio.gather(
      *(fetch_json(client, u, DEX_SEMAPHORE) for u in urls),
      return_exceptions=True,
  )

  chain_buckets: Dict[str, List[str]] = {chain: [] for chain in TARGET_CHAINS}

  for feed in feeds:
    if not isinstance(feed, list):
      continue
    for item in feed:
      if not isinstance(item, dict):
        continue
      addr = item.get("tokenAddress")
      chain = str(item.get("chainId", "")).lower()
      if addr and chain in chain_buckets and not is_seen(addr):
        if addr not in chain_buckets[chain]:
          chain_buckets[chain].append(addr)

  await asyncio.gather(
      *(
          scan_chain(client, chain, addrs)
          for chain, addrs in chain_buckets.items()
      ),
      return_exceptions=True,
  )


async def main() -> None:
  print(
      "[*] Mantis Engine v5 online. Telemetry, Security Pipeline & Parallel"
      " Scanners active..."
  )

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      ),
      "Accept": "application/json",
  }
  limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)

  report_task = asyncio.create_task(monitor.hourly_report_loop(3600))

  try:
    async with httpx.AsyncClient(
        timeout=10.0, headers=headers, limits=limits
    ) as client:
      while True:
        cleanup_old(hours=24)
        await scan_market(client)
        await asyncio.sleep(15)
  except Exception as e:
    print(f"[!] Critical engine failure: {e}")
    await monitor.send_crash_alert(str(e))
    raise
  finally:
    report_task.cancel()


if __name__ == "__main__":
  asyncio.run(main())
