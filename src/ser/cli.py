import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from ser.db import COLLECTION_NAME, QDRANT_STORAGE, client, init_collection
from ser.download import download_dump
from ser.dump import iter_dump_articles
from ser.generate import get_local_model, stream_answer
from ser.ingest import fetch_wiki_article
from ser.pipeline import ask, index_documents

console = Console()


def show_banner() -> None:
    model_name = get_local_model() or "None detected (Run 'ollama run llama3.2:3b')"
    storage_info = f"[bold green]{QDRANT_STORAGE.upper()}[/bold green]"
    if QDRANT_STORAGE == "local":
        storage_info += " (data/qdrant_db on SSD)"
    else:
        storage_info += " (Hosted Qdrant Cloud)"

    banner_text = (
        f"[bold cyan]SER — Simple English RAG (Universal Local Engine)[/bold cyan]\n"
        f"Storage Engine : {storage_info}\n"
        f"Local LLM      : [bold yellow]{model_name}[/bold yellow]\n"
        f"Collection     : [bold magenta]{COLLECTION_NAME}[/bold magenta]\n\n"
        f"[dim]Type a question to ask, or type [bold]/help[/bold] for commands.[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan", expand=False))


def cmd_stats() -> None:
    try:
        info = client.get_collection(COLLECTION_NAME)
        table = Table(title=f"Qdrant Collection: {COLLECTION_NAME}", border_style="magenta")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Storage Mode", QDRANT_STORAGE.upper())
        table.add_row("Points Count", str(info.points_count or 0))
        table.add_row("Status", str(info.status))
        table.add_row("Vector Dimension", "384 (bge-small-en-v1.5)")
        table.add_row("Quantization", "INT8 Scalar (4x RAM reduction)")
        table.add_row("On Disk Vectors", str(info.config.params.vectors.on_disk))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching stats: {e}[/red]")


def cmd_ingest_wiki(title: str) -> None:
    with console.status(f"[cyan]Fetching article '{title}' from Wikipedia API...", spinner="dots"):
        doc = fetch_wiki_article(title)
    if not doc:
        console.print(f"[red]Article '{title}' could not be found.[/red]")
        return

    with console.status(f"[cyan]Chunking and indexing '{doc.title}' into Qdrant...", spinner="dots"):
        count = index_documents([doc], client=client)
    console.print(f"[green]Successfully indexed {count} chunks for '{doc.title}' ({doc.url})[/green]")


def cmd_search(query: str, k: int = 3) -> None:
    with console.status("[cyan]Retrieving semantic matches...", spinner="dots"):
        results = ask(client, query, k=k)

    if not results:
        console.print("[yellow]No matching passages found.[/yellow]")
        return

    console.print(f"\n[bold]Top {len(results)} Chunks for:[/bold] [italic]\"{query}\"[/italic]\n")
    for idx, r in enumerate(results, 1):
        payload = r.payload or {}
        title = payload.get("title", "Unknown")
        url = payload.get("url", "")
        text = payload.get("text", "")
        score_color = "green" if r.score >= 0.70 else "yellow" if r.score >= 0.50 else "red"
        header = f"[{idx}] {title} — Score: [{score_color}]{r.score:.4f}[/{score_color}]"
        console.print(Panel(f"[dim]{url}[/dim]\n\n{text}", title=header, border_style="dim"))


def cmd_ask(query: str, k: int = 3) -> None:
    with console.status("[cyan]Retrieving knowledge...", spinner="dots"):
        chunks = ask(client, query, k=k)

    if not chunks:
        console.print("[yellow]No relevant sources found in database.[/yellow]")
        return

    console.print(f"\n[bold cyan]Question:[/bold cyan] {query}\n")
    console.print("[bold green]Answer:[/bold green]")

    collected_answer = []
    for token in stream_answer(query, chunks):
        sys.stdout.write(token)
        sys.stdout.flush()
        collected_answer.append(token)
    print("\n")

    # Display citations table
    cite_table = Table(title="Sources Cited", border_style="dim", show_header=True)
    cite_table.add_column("Ref", style="bold cyan", width=6)
    cite_table.add_column("Article", style="bold")
    cite_table.add_column("Similarity Score", justify="right")
    cite_table.add_column("URL", style="dim underline")

    for idx, c in enumerate(chunks, 1):
        payload = c.payload or {}
        title = payload.get("title", "Unknown")
        url = payload.get("url", "")
        score_val = f"{c.score:.4f}" if c.score else "N/A"
        cite_table.add_row(f"[{idx}]", title, score_val, url)

    console.print(cite_table)
    print()


def cmd_download_dump() -> None:
    try:
        path = download_dump(dest_dir="data")
        console.print(f"[bold green]Dump ready at: {path}[/bold green]")
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")


def cmd_ingest_dump(limit_str: str = "all", reset: bool = False, batch_size: int = 128) -> None:
    from ser.db import PROJECT_ROOT
    dump_path = PROJECT_ROOT / "data" / "simplewiki-latest-pages-articles.xml.bz2"
    if not dump_path.exists():
        console.print(f"[yellow]Dump file not found at {dump_path}. Run [bold]/download-dump[/bold] first.[/yellow]")
        return

    limit = None
    if limit_str and limit_str.lower() not in ("all", "none", "full"):
        try:
            limit = int(limit_str)
        except ValueError:
            limit = None

    checkpoint_file = PROJECT_ROOT / "data" / "ingest_checkpoint.json"
    target_desc = f"{limit:,} articles" if limit else "ENTIRE Simple English Wikipedia corpus (~238k articles)"
    console.print(f"[cyan]Streaming and indexing {target_desc} into Qdrant Cloud...[/cyan]")
    if reset:
        console.print("[yellow]Reset flag enabled: Starting from article #1 (clearing checkpoint)[/yellow]")

    articles_stream = iter_dump_articles(
        dump_path,
        max_articles=limit,
        checkpoint_path=checkpoint_file,
        reset=reset,
    )

    indexed = index_documents(articles_stream, client=client, batch_size=batch_size)
    console.print(f"[bold green]Bulk ingestion complete: {indexed:,} chunks indexed into '{COLLECTION_NAME}'.[/bold green]")


def show_help() -> None:
    help_table = Table(title="Available Commands", border_style="cyan")
    help_table.add_column("Command", style="bold yellow")
    help_table.add_column("Description")
    help_table.add_row("<question>", "Ask any question (runs full RAG with local Ollama)")
    help_table.add_row("/search <query>", "Semantic search only (shows matching chunks and scores)")
    help_table.add_row("/ingest-wiki <title>", "Crawl and index a Wikipedia article live by title")
    help_table.add_row("/download-dump", "Download official Simple Wikipedia compressed dump (339 MB)")
    help_table.add_row("/ingest-dump [N]", "Stream-ingest N articles from dump (default: 500)")
    help_table.add_row("/stats", "Show Qdrant collection size and storage metrics")
    help_table.add_row("/help", "Show this help table")
    help_table.add_row("/exit, /quit", "Exit the CLI")
    console.print(help_table)


def main() -> None:
    init_collection(client)

    # Non-interactive CLI mode for AI agents, scripts, and terminal shortcuts
    if len(sys.argv) > 1:
        first_arg = sys.argv[1].lower()
        if first_arg in ("--help", "-h", "help"):
            show_help()
            return
        elif first_arg in ("stats", "--stats"):
            cmd_stats()
            return
        elif first_arg == "download-dump":
            cmd_download_dump()
            return
        elif first_arg == "ingest-wiki" and len(sys.argv) > 2:
            cmd_ingest_wiki(" ".join(sys.argv[2:]))
            return
        elif first_arg == "ingest-dump":
            args = sys.argv[2:]
            reset = "--reset" in args
            args = [a for a in args if a != "--reset"]
            limit = args[0] if args else "all"
            cmd_ingest_dump(limit, reset=reset)
            return
        elif first_arg == "search" and len(sys.argv) > 2:
            cmd_search(" ".join(sys.argv[2:]))
            return
        elif first_arg == "ask" and len(sys.argv) > 2:
            cmd_ask(" ".join(sys.argv[2:]))
            return
        else:
            # Direct query: ser "What is physics?"
            cmd_ask(" ".join(sys.argv[1:]))
            return

    # Interactive REPL mode (when run without arguments)
    show_banner()

    while True:
        try:
            user_input = console.input("[bold blue]ser>[/bold blue] ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                console.print("[cyan]Goodbye![/cyan]")
                break
            elif user_input.lower() == "/help":
                show_help()
            elif user_input.lower() == "/stats":
                cmd_stats()
            elif user_input.lower() == "/download-dump":
                cmd_download_dump()
            elif user_input.lower().startswith("/ingest-dump"):
                parts = user_input.split()
                reset = "--reset" in parts
                clean_parts = [p for p in parts[1:] if p != "--reset"]
                limit = clean_parts[0] if clean_parts else "all"
                cmd_ingest_dump(limit, reset=reset)
            elif user_input.lower().startswith("/ingest-wiki"):
                parts = user_input.split(maxsplit=1)
                if len(parts) > 1:
                    cmd_ingest_wiki(parts[1])
                else:
                    console.print("[red]Usage: /ingest-wiki <Article Title>[/red]")
            elif user_input.lower().startswith("/search"):
                parts = user_input.split(maxsplit=1)
                if len(parts) > 1:
                    cmd_search(parts[1])
                else:
                    console.print("[red]Usage: /search <query>[/red]")
            elif user_input.lower().startswith("/ask"):
                parts = user_input.split(maxsplit=1)
                if len(parts) > 1:
                    cmd_ask(parts[1])
                else:
                    console.print("[red]Usage: /ask <question>[/red]")
            else:
                # Default: any plain text input is treated as a question
                cmd_ask(user_input)

        except (KeyboardInterrupt, EOFError):
            console.print("\n[cyan]Goodbye![/cyan]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()
