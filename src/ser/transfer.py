import os
import shutil
import time
from pathlib import Path
from typing import Optional, Tuple

from qdrant_client import QdrantClient, models
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.prompt import Confirm
from rich.table import Table

from ser.db import (
    COLLECTION_NAME,
    PROJECT_ROOT,
    QDRANT_LOCAL_PATH,
    QDRANT_STORAGE,
    get_storage_client,
    init_collection,
)

console = Console()

ESTIMATED_BYTES_PER_POINT = 6000  # ~6 KB per point (384-dim vector + scalar quantization + payload + HNSW index)
CLOUD_FREE_TIER_MAX_POINTS = 1_000_000


def parse_transfer_direction(direction_raw: Optional[str] = None) -> Tuple[str, str]:
    """Resolves transfer direction into (source_mode, target_mode)."""
    current_storage = os.getenv("QDRANT_STORAGE", QDRANT_STORAGE).lower()
    
    if not direction_raw:
        # Default to opposite of current storage
        if current_storage == "cloud":
            return "cloud", "local"
        else:
            return "local", "cloud"

    norm = direction_raw.strip().lower().replace("_", "-")
    if norm in ("cloud-to-local", "c2l", "cloud2local", "to-local", "local"):
        return "cloud", "local"
    elif norm in ("local-to-cloud", "l2c", "local2cloud", "to-cloud", "cloud"):
        return "local", "cloud"
    else:
        raise ValueError(
            f"Invalid transfer direction '{direction_raw}'. Valid options: "
            "'cloud-to-local' (c2l) or 'local-to-cloud' (l2c)."
        )


def check_target_capacity(
    source_mode: str,
    target_mode: str,
    source_points: int,
    target_client: QdrantClient,
) -> Tuple[bool, str, dict]:
    """Pre-flight check verifying storage capacity and limits."""
    est_bytes = source_points * ESTIMATED_BYTES_PER_POINT
    est_gb = est_bytes / (1024**3)
    info = {
        "source_points": source_points,
        "estimated_bytes": est_bytes,
        "estimated_gb": est_gb,
    }

    if target_mode == "local":
        # Check SSD/HDD free space
        local_dir = Path(QDRANT_LOCAL_PATH).resolve()
        target_path = local_dir if local_dir.exists() else local_dir.parent
        if not target_path.exists():
            target_path = PROJECT_ROOT
        
        usage = shutil.disk_usage(target_path)
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        info["free_gb"] = free_gb
        info["total_gb"] = total_gb

        # Require at least estimated space + 1 GB safety buffer
        required_gb = est_gb + 1.0
        if usage.free < est_bytes:
            return (
                False,
                f"Insufficient local disk space! Estimated need: {est_gb:.2f} GB, "
                f"but only {free_gb:.2f} GB is free on disk ({target_path}).",
                info,
            )
        elif free_gb < required_gb:
            return (
                True,
                f"Disk space is tight: Transfer requires ~{est_gb:.2f} GB, leaving {free_gb - est_gb:.2f} GB free.",
                info,
            )
        return True, f"Disk space OK ({free_gb:.1f} GB free / {est_gb:.2f} GB required).", info

    elif target_mode == "cloud":
        # Verify cluster accessibility & capacity
        try:
            cluster_info = target_client.info()
            info["cluster_version"] = getattr(cluster_info, "version", "Unknown")
        except Exception as e:
            return False, f"Failed to connect to Qdrant Cloud cluster: {e}", info

        if source_points > CLOUD_FREE_TIER_MAX_POINTS:
            return (
                True,
                f"Warning: {source_points:,} points exceeds the recommended Free Tier limit (~1M points). Ensure your Qdrant Cloud plan has adequate RAM/storage.",
                info,
            )
        return True, f"Qdrant Cloud cluster verified and accessible (v{info.get('cluster_version', 'latest')}).", info

    return True, "Capacity check passed.", info


def render_preflight_table(
    source_mode: str,
    target_mode: str,
    collection_name: str,
    source_points: int,
    capacity_info: dict,
    status_msg: str,
) -> None:
    """Renders a formatted pre-flight summary table before transfer."""
    table = Table(title="Database Transfer Pre-Flight Check", border_style="cyan")
    table.add_column("Parameter", style="cyan bold")
    table.add_column("Details", style="white")

    table.add_row("Transfer Route", f"[bold yellow]{source_mode.upper()}[/bold yellow]  ➔  [bold green]{target_mode.upper()}[/bold green]")
    table.add_row("Collection Name", f"[magenta]{collection_name}[/magenta]")
    table.add_row("Source Records", f"[bold]{source_points:,}[/bold] points")
    table.add_row("Estimated Transfer Size", f"~{capacity_info['estimated_gb']:.2f} GB (~{ESTIMATED_BYTES_PER_POINT:,} bytes/point)")

    if target_mode == "local":
        free_gb = capacity_info.get("free_gb", 0)
        total_gb = capacity_info.get("total_gb", 0)
        table.add_row("Target Disk Free", f"[bold green]{free_gb:.2f} GB[/bold green] free of {total_gb:.2f} GB ({QDRANT_LOCAL_PATH})")
    else:
        v = capacity_info.get("cluster_version", "Cloud")
        table.add_row("Target Cloud Status", f"[bold green]Connected[/bold green] (Cluster v{v})")

    table.add_row("Capacity Assessment", f"[dim]{status_msg}[/dim]")
    console.print(table)


def update_env_storage(new_storage: str, env_path: Optional[Path] = None) -> bool:
    """Updates QDRANT_STORAGE in .env to the new target mode."""
    target_env = env_path or (PROJECT_ROOT / ".env")
    if not target_env.exists():
        return False

    content = target_env.read_text(encoding="utf-8")
    lines = content.splitlines()
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("QDRANT_STORAGE="):
            new_lines.append(f"QDRANT_STORAGE={new_storage.lower()}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"QDRANT_STORAGE={new_storage.lower()}")

    target_env.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.environ["QDRANT_STORAGE"] = new_storage.lower()
    return True


def transfer_database(
    direction: Optional[str] = None,
    collection_name: str = COLLECTION_NAME,
    batch_size: int = 500,
    auto_confirm: bool = False,
    keep_source: bool = False,
) -> bool:
    """
    Transfers all vectors and payloads between Cloud and Local Qdrant storage.
    Performs pre-flight capacity checks, streams data with progress,
    verifies point count integrity, prompts for safe source deletion,
    and updates .env storage setting.
    """
    try:
        source_mode, target_mode = parse_transfer_direction(direction)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return False

    console.print(f"[bold cyan]Initializing transfer: [yellow]{source_mode.upper()}[/yellow] ➔ [green]{target_mode.upper()}[/green]...[/bold cyan]")

    # 1. Connect to both clients
    try:
        source_client = get_storage_client(source_mode)
    except Exception as e:
        console.print(f"[red]Error connecting to source storage ({source_mode}): {e}[/red]")
        return False

    try:
        target_client = get_storage_client(target_mode)
    except Exception as e:
        console.print(f"[red]Error connecting to target storage ({target_mode}): {e}[/red]")
        return False

    # 2. Verify source collection exists and count points
    if not source_client.collection_exists(collection_name):
        console.print(f"[red]Source collection '{collection_name}' does not exist on {source_mode}. Nothing to transfer.[/red]")
        return False

    source_info = source_client.get_collection(collection_name)
    source_points = source_info.points_count or 0
    if source_points == 0:
        console.print(f"[yellow]Source collection '{collection_name}' has 0 points. Nothing to transfer.[/yellow]")
        return False

    # 3. Pre-flight capacity & space checks
    is_safe, status_msg, capacity_info = check_target_capacity(
        source_mode, target_mode, source_points, target_client
    )
    render_preflight_table(
        source_mode, target_mode, collection_name, source_points, capacity_info, status_msg
    )

    if not is_safe:
        console.print(f"[bold red]Transfer Aborted: {status_msg}[/bold red]")
        return False

    # 4. Confirmation prompt before transfer
    if not auto_confirm:
        proceed = Confirm.ask(
            f"\nReady to transfer [bold]{source_points:,}[/bold] points from [yellow]{source_mode.upper()}[/yellow] to [green]{target_mode.upper()}[/green]. Proceed?",
            default=True,
        )
        if not proceed:
            console.print("[yellow]Transfer cancelled by user.[/yellow]")
            return False

    # 5. Ensure target collection exists with identical schema
    with console.status(f"[cyan]Setting up target collection '{collection_name}' on {target_mode}...", spinner="dots"):
        init_collection(target_client, collection_name=collection_name)

    # 6. Stream scroll from source and upsert to target
    start_time = time.time()
    transferred_count = 0
    next_offset = None

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    task_id = progress.add_task(
        f"[cyan]Transferring {source_mode} ➔ {target_mode}",
        total=source_points,
    )

    with progress:
        while True:
            records, next_offset = source_client.scroll(
                collection_name=collection_name,
                limit=batch_size,
                with_payload=True,
                with_vectors=True,
                offset=next_offset,
            )

            if not records:
                break

            points = [
                models.PointStruct(id=r.id, vector=r.vector, payload=r.payload)
                for r in records
            ]

            # Upsert batch with retry logic
            max_retries = 5
            for attempt in range(1, max_retries + 1):
                try:
                    target_client.upsert(
                        collection_name=collection_name,
                        points=points,
                        wait=True,
                    )
                    break
                except Exception as e:
                    if attempt == max_retries:
                        progress.stop()
                        console.print(f"\n[red]Upsert failed after {max_retries} attempts: {e}[/red]")
                        return False
                    time.sleep(min(2**attempt, 15))

            transferred_count += len(points)
            progress.update(task_id, completed=transferred_count)

            if next_offset is None:
                break

    duration = time.time() - start_time
    rate = transferred_count / duration if duration > 0 else 0

    console.print(
        f"[bold green]✓ Stream complete: Transferred {transferred_count:,} points in {duration:.1f}s ({rate:.0f} pts/sec).[/bold green]"
    )

    # 7. Verification: Confirm target has received the points
    with console.status("[cyan]Verifying target integrity...", spinner="dots"):
        target_info = target_client.get_collection(collection_name)
        target_points = target_info.points_count or 0

    if target_points < source_points:
        console.print(
            f"[bold red]Integrity Warning: Target points count ({target_points:,}) is less than source ({source_points:,})![/bold red]\n"
            f"[yellow]Source collection on {source_mode} will NOT be deleted to prevent data loss.[/yellow]"
        )
        return False

    console.print(
        f"[bold green]✓ Integrity Verified: Target collection '{collection_name}' has {target_points:,} points (>= {source_points:,} source).[/bold green]"
    )

    # 8. Safe source deletion
    if keep_source:
        console.print(f"[dim]Flag --keep-source enabled: Retained source collection on {source_mode}.[/dim]")
    else:
        delete_confirmed = auto_confirm
        if not auto_confirm:
            delete_confirmed = Confirm.ask(
                f"\n[bold yellow]Delete source collection '{collection_name}' from {source_mode.upper()} now?[/bold yellow]",
                default=True,
            )

        if delete_confirmed:
            with console.status(f"[cyan]Deleting source collection from {source_mode}...", spinner="dots"):
                source_client.delete_collection(collection_name)
            console.print(f"[bold green]✓ Source collection deleted from {source_mode.upper()}.[/bold green]")
        else:
            console.print(f"[dim]Source collection preserved on {source_mode.upper()}.[/dim]")

    # 9. Update .env to target storage mode
    if update_env_storage(target_mode):
        console.print(f"[bold cyan]✓ Updated .env setting: QDRANT_STORAGE={target_mode}[/bold cyan]")

    summary_panel = Panel(
        f"[bold green]Transfer Successfully Completed![/bold green]\n\n"
        f"• Route       : [yellow]{source_mode.upper()}[/yellow] ➔ [green]{target_mode.upper()}[/green]\n"
        f"• Records     : [bold white]{target_points:,}[/bold white] points verified\n"
        f"• Duration    : [bold white]{duration:.1f}s[/bold white] (~{rate:.0f} pts/sec)\n"
        f"• Active Mode : [bold cyan]{target_mode.upper()}[/bold cyan] (ready for queries)\n\n"
        f"[dim]Run [bold]ser stats[/bold] or [bold]ser search[/bold] to query your active database.[/dim]",
        title="SER Transfer Summary",
        border_style="green",
        expand=False,
    )
    console.print(summary_panel)
    return True
