"""Wake a suspended Qdrant Cloud cluster before querying it."""

import os
import time
from collections.abc import Callable
from uuid import UUID

import httpx


def ensure_cloud_ready(notify: Callable[[str], None] = print) -> None:
    if os.getenv("QDRANT_STORAGE", "cloud").lower() != "cloud":
        return
    key = os.getenv("QDRANT_CLOUD_MANAGEMENT_KEY", "").strip()
    if not key or key.startswith("your-"):
        return
    account = os.getenv("QDRANT_CLOUD_ACCOUNT_ID", "").strip()
    cluster = os.getenv("QDRANT_CLOUD_CLUSTER_ID", "").strip()
    try:
        UUID(account)
        UUID(cluster)
    except ValueError:
        raise RuntimeError(
            "Set QDRANT_CLOUD_ACCOUNT_ID and QDRANT_CLOUD_CLUSTER_ID to valid UUIDs in .env."
        ) from None

    url = f"https://api.cloud.qdrant.io/api/cluster/v1/accounts/{account}/clusters/{cluster}"
    deadline = time.monotonic() + 180
    requested = False
    announced = False
    try:
        with httpx.Client(headers={"Authorization": f"apikey {key}"}, timeout=15) as api:
            while True:
                response = api.get(url)
                response.raise_for_status()
                phase = response.json()["cluster"]["state"]["phase"]
                if phase == "CLUSTER_PHASE_HEALTHY":
                    return
                if phase not in {
                    "CLUSTER_PHASE_SUSPENDED", "CLUSTER_PHASE_SUSPENDING",
                    "CLUSTER_PHASE_RESUMING", "CLUSTER_PHASE_NOT_READY",
                }:
                    raise RuntimeError(f"Qdrant cluster is {phase}; check the Cloud console.")
                if not announced:
                    notify("Waiting for Qdrant Cloud to become ready (up to 3 minutes)...")
                    announced = True
                if phase == "CLUSTER_PHASE_SUSPENDED" and not requested:
                    notify("Waking database...")
                    response = api.post(f"{url}/unsuspend", json={})
                    response.raise_for_status()
                    requested = True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("Qdrant is still starting. Try ser again shortly or check the Cloud console.")
                time.sleep(min(5, remaining))
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Qdrant Cloud management API returned HTTP {exc.response.status_code}. "
            "Check the management key, cluster IDs, and read:clusters/write:clusters permissions."
        ) from None
    except httpx.RequestError:
        raise RuntimeError("Cannot reach the Qdrant Cloud management API. Check your network and try again.") from None
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("Unexpected Qdrant Cloud status response; check the Cloud console.") from None
