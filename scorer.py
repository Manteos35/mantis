# Dosya: ~/mantis/scorer.py
import asyncio
from typing import Any, Dict, Optional
import httpx

GOPLUS_CHAIN_MAP = {"base": "8453", "ethereum": "1", "bsc": "56"}

MAX_ACCEPTABLE_RISK = 30


async def _fetch_rugcheck(
    client: httpx.AsyncClient, address: str
) -> Optional[Dict[str, Any]]:
  url = f"https://api.rugcheck.xyz/v1/tokens/{address}/report"
  try:
    res = await client.get(url, timeout=6.0)
    if res.status_code == 200:
      return res.json()
  except Exception as e:
    print(f"[SCORER] RugCheck API error for {address}: {e}")
  return None


async def _fetch_goplus(
    client: httpx.AsyncClient, address: str, chain: str
) -> Optional[Dict[str, Any]]:
  try:
    if chain == "solana":
      url = f"https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses={address}"
    else:
      chain_id = GOPLUS_CHAIN_MAP.get(chain, "8453")
      url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={address}"

    res = await client.get(url, timeout=6.0)
    if res.status_code == 200:
      data = res.json()
      result = data.get("result", {})
      return result.get(address) or result.get(address.lower())
  except Exception as e:
    print(f"[SCORER] GoPlus API error for {address} ({chain}): {e}")
  return None


async def check_token(
    address: str,
    chain: str = "solana",
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
  """Evaluates on-chain token security via RugCheck & GoPlus.

  Returns risk_score (0-100), passed boolean (risk_score <= 30), and security
  flags.
  """
  chain = chain.lower()
  close_client = False
  if client is None:
    client = httpx.AsyncClient(
        timeout=8.0, headers={"User-Agent": "MantisCore/1.0"}
    )
    close_client = True

  risk_score = 0
  flags = {
      "mint_disabled": True,
      "freeze_disabled": True,
      "lp_locked": True,
      "top10_under_40": True,
      "not_honeypot": True,
  }

  try:
    if chain == "solana":
      rc_data, gp_data = await asyncio.gather(
          _fetch_rugcheck(client, address),
          _fetch_goplus(client, address, "solana"),
      )

      # Fallback penalty if both security APIs fail to respond
      if not rc_data and not gp_data:
        return {
            "passed": False,
            "risk_score": 50,
            "flags": flags,
            "reason": "Security APIs unreachable",
        }

      if rc_data:
        token_meta = rc_data.get("token") or {}
        # 1. Mint Authority Check
        if token_meta.get("mintAuthority") is not None:
          flags["mint_disabled"] = False
          risk_score += 35

        # 2. Freeze Authority Check
        if token_meta.get("freezeAuthority") is not None:
          flags["freeze_disabled"] = False
          risk_score += 25

        # 3. Rugged / Honeypot Check
        if rc_data.get("rugged") is True:
          flags["not_honeypot"] = False
          risk_score += 100

        # 4. Top 10 Holder Concentration (< 40%)
        top_holders = rc_data.get("topHolders") or []
        known_accounts = rc_data.get("knownAccounts") or {}
        top10_pct = 0.0
        count = 0
        for h in top_holders:
          owner = h.get("owner", "")
          # Ignore known AMM pools / burn addresses
          if owner in known_accounts and known_accounts[owner].get("type") in (
              "AMM",
              "LOCKER",
              "BURN",
          ):
            continue
          top10_pct += float(h.get("pct", 0) or 0)
          count += 1
          if count >= 10:
            break

        if top10_pct >= 40.0:
          flags["top10_under_40"] = False
          risk_score += 20

        # 5. LP Locked / Burned Check
        markets = rc_data.get("markets") or []
        if markets:
          lp_data = markets[0].get("lp") or {}
          lp_locked_pct = float(lp_data.get("lpLockedPct", 0) or 0)
          if lp_locked_pct < 80.0:
            flags["lp_locked"] = False
            risk_score += 20

      # Cross-check with GoPlus Solana if available
      if gp_data:
        if (
            gp_data.get("mintable", {}).get("status") == "1"
            and flags["mint_disabled"]
        ):
          flags["mint_disabled"] = False
          risk_score += 35
        if (
            gp_data.get("freezable", {}).get("status") == "1"
            and flags["freeze_disabled"]
        ):
          flags["freeze_disabled"] = False
          risk_score += 25

    else:
      # EVM Chains (Base, etc.) via GoPlus
      gp_data = await _fetch_goplus(client, address, chain)
      if not gp_data:
        return {
            "passed": False,
            "risk_score": 50,
            "flags": flags,
            "reason": "GoPlus API unreachable",
        }

      # 1. Mint Authority Check
      if gp_data.get("is_mintable") == "1":
        flags["mint_disabled"] = False
        risk_score += 35

      # 2. Freeze / Transfer Pause / Blacklist Check
      if (
          gp_data.get("transfer_pausable") == "1"
          or gp_data.get("is_blacklisted") == "1"
      ):
        flags["freeze_disabled"] = False
        risk_score += 25

      # 3. Honeypot Check
      if gp_data.get("is_honeypot") == "1" or gp_data.get("cannot_sell_all") == "1":
        flags["not_honeypot"] = False
        risk_score += 100

      # 4. Top 10 Holders Check (< 40%)
      holders = gp_data.get("holders") or []
      top10_pct = 0.0
      count = 0
      for h in holders:
        if h.get("is_contract") == 1 or h.get("tag"):
          continue
        top10_pct += float(h.get("percent", 0) or 0) * 100
        count += 1
        if count >= 10:
          break

      if top10_pct >= 40.0:
        flags["top10_under_40"] = False
        risk_score += 20

      # 5. LP Locked Check
      lp_holders = gp_data.get("lp_holders") or []
      locked_pct = sum(
          float(lp.get("percent", 0) or 0) * 100
          for lp in lp_holders
          if lp.get("is_locked") == 1
          or "burn" in str(lp.get("tag", "")).lower()
          or "dead" in str(lp.get("address", "")).lower()
      )
      if locked_pct < 80.0:
        flags["lp_locked"] = False
        risk_score += 20

    risk_score = min(100, risk_score)
    passed = risk_score <= MAX_ACCEPTABLE_RISK

    return {
        "passed": passed,
        "risk_score": risk_score,
        "flags": flags,
        "reason": "OK" if passed else f"High risk score ({risk_score}/100)",
    }

  except Exception as e:
    print(f"[SCORER] Unexpected evaluation error for {address}: {e}")
    return {
        "passed": False,
        "risk_score": 100,
        "flags": flags,
        "reason": f"Evaluation error: {e}",
    }
  finally:
    if close_client:
      await client.aclose()
