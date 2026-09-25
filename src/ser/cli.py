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
from ser.eval import BENCHMARK_DATASET, render_console_report, run_benchmark, save_markdown_report
from ser.generate import get_local_model, stream_answer
from ser.ingest import fetch_wiki_article, resolve_target
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
        status_str = str(info.status).lower()
        border_color = "green" if status_str == "green" else "yellow" if status_str == "yellow" else "red"
        status_badge = (
            "[bold green]● Healthy (green)[/bold green]"
            if status_str == "green"
            else f"[{border_color}]● {info.status}[/{border_color}]"
        )

        table = Table(title=f"Qdrant Collection: {COLLECTION_NAME}", border_style=border_color)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Storage Mode", f"[bold cyan]{QDRANT_STORAGE.upper()}[/bold cyan]")
        table.add_row("Points Count", f"[bold white]{(info.points_count or 0):,}[/bold white]")
        table.add_row("Status", status_badge)
        table.add_row("Vector Dimension", "384 (bge-small-en-v1.5)")
        table.add_row("Quantization", "INT8 Scalar (4x RAM reduction)")
        table.add_row("On Disk Vectors", str(info.config.params.vectors.on_disk))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching stats: {e}[/red]")


def cmd_add(target: str) -> None:
    target_clean = target.strip()
    if not target_clean:
        console.print("[red]Usage: ser add <file | folder | url | 'Wikipedia Title'>[/red]")
        return

    with console.status(f"[cyan]Analyzing target: {target_clean}...", spinner="dots"):
        try:
            resolution, payload = resolve_target(target_clean)
        except Exception as e:
            console.print(f"[red]Error analyzing target: {e}[/red]")
            return

    if resolution == "wiki_404":
        console.print(f"[red]Error 404: No local file, directory, or Wikipedia article found for '{target_clean}'.[/red]")
        return
    elif resolution == "wiki_suggestions":
        suggestions_str = ", ".join(f"[bold cyan]'{s}'[/bold cyan]" for s in payload)
        console.print(
            f"[yellow]No exact Wikipedia article found for '{target_clean}'.[/yellow]\n"
            f"[dim]Did you mean:[/dim] {suggestions_str}\n"
            f"[dim]To index one, run:[/dim] [cyan]ser add \"{payload[0]}\"[/cyan]"
        )
        return
    elif resolution == "empty_directory":
        console.print(f"[yellow]Directory '{target_clean}' contains no supported files.[/yellow]")
        return

    docs = payload
    if not docs:
        console.print(f"[yellow]No content extracted from '{target_clean}'.[/yellow]")
        return

    desc = f"{len(docs)} document(s)" if len(docs) > 1 else f"'{docs[0].title}'"
    with console.status(f"[cyan]Chunking, embedding and indexing {desc} into Qdrant...", spinner="dots"):
        total_chunks = index_documents(docs, client=client)

    console.print(f"[bold green]✓ Successfully indexed {total_chunks:,} chunks from {desc} into '{COLLECTION_NAME}'![/bold green]")
    for d in docs[:5]:
        console.print(f"  [dim]• [{d.source_type.upper()}] {d.title} ({d.url})[/dim]")
    if len(docs) > 5:
        console.print(f"  [dim]... and {len(docs) - 5} more files.[/dim]")


def cmd_ingest_wiki(title: str) -> None:
    with console.status(f"[cyan]Fetching article '{title}' from Wikipedia API...", spinner="dots"):
        doc = fetch_wiki_article(title)
    if not doc:
        console.print(f"[red]Article '{title}' could not be found.[/red]")
        return

    with console.status(f"[cyan]Chunking and indexing '{doc.title}' into Qdrant...", spinner="dots"):
        count = index_documents([doc], client=client)
    console.print(f"[green]Successfully indexed {count} chunks for '{doc.title}' ({doc.url})[/green]")


def _extract_search_flags(args: list[str]) -> tuple[list[str], bool, bool]:
    """Helper to detect and remove --hybrid (-H) and --rerank (-r) flags from arguments."""
    hybrid = False
    rerank = False
    clean = []
    for a in args:
        low = a.lower()
        if low in ("--rerank", "-r", "--re-rank"):
            rerank = True
        elif low in ("--hybrid", "-h", "-H", "--hyb"):
            hybrid = True
        else:
            clean.append(a)
    return clean, hybrid, rerank


def cmd_search(query: str, k: int = 3, hybrid: bool = False, rerank: bool = False) -> None:
    if hybrid and rerank:
        status_msg = "[cyan]Running hybrid retrieval & cross-encoder re-ranking..."
        tag = " [dim](Hybrid + Re-ranked)[/dim]"
    elif hybrid:
        status_msg = "[cyan]Running hybrid search (Dense + BM25 via RRF)..."
        tag = " [dim](Hybrid: Dense + BM25)[/dim]"
    elif rerank:
        status_msg = "[cyan]Retrieving and re-ranking matches..."
        tag = " [dim](Re-ranked)[/dim]"
    else:
        status_msg = "[cyan]Retrieving semantic matches..."
        tag = ""

    with console.status(status_msg, spinner="dots"):
        results = ask(client, query, k=k, hybrid=hybrid, rerank=rerank)

    if not results:
        console.print("[yellow]No matching passages found.[/yellow]")
        return

    console.print(f"\n[bold]Top {len(results)} Chunks for:[/bold] [italic]\"{query}\"[/italic]{tag}\n")
    for idx, r in enumerate(results, 1):
        payload = r.payload or {}
        title = payload.get("title", "Unknown")
        breadcrumb = payload.get("breadcrumb", "")
        url = payload.get("url", "")
        text = payload.get("text", "")
        display_title = breadcrumb if breadcrumb else title
        score_label = "Re-rank Score" if rerank else "RRF Score" if hybrid else "Score"
        score_color = "green" if r.score >= 0.70 else "yellow" if r.score >= 0.50 else "red"
        header = f"[{idx}] {display_title} — {score_label}: [{score_color}]{r.score:.4f}[/{score_color}]"
        console.print(Panel(f"[dim]{url}[/dim]\n\n{text}", title=header, border_style="dim"))


def cmd_ask(query: str, k: int = 3, hybrid: bool = False, rerank: bool = False) -> None:
    if hybrid and rerank:
        status_msg = "[cyan]Retrieving knowledge (Hybrid + Re-rank)..."
    elif hybrid:
        status_msg = "[cyan]Retrieving knowledge (Hybrid: Dense + BM25)..."
    elif rerank:
        status_msg = "[cyan]Retrieving and re-ranking knowledge..."
    else:
        status_msg = "[cyan]Retrieving knowledge..."

    with console.status(status_msg, spinner="dots"):
        chunks = ask(client, query, k=k, hybrid=hybrid, rerank=rerank)

    if not chunks:
        console.print("[yellow]No relevant sources found in database.[/yellow]")
        return

    console.print(f"\n[bold cyan]Question:[/bold cyan] {query}\n")
    console.print("[bold green]Answer:[/bold green]")
    collected_answer = []
    # Bouncing spinner while the LLM is thinking
    with console.status("[italic cyan]Thinking...[/italic cyan]", spinner="dots"):
        answer_stream = stream_answer(query, chunks)
        try:
            first_token = next(answer_stream)
        except StopIteration:
            first_token = ""
    # Once the first token arrives, the spinner clears and streaming begins
    if first_token:
        sys.stdout.write(first_token)
        sys.stdout.flush()
        collected_answer.append(first_token)
    for token in answer_stream:
        sys.stdout.write(token)
        sys.stdout.flush()
        collected_answer.append(token)
    print("\n")

    # Display citations table
    cite_table = Table(title="Sources Cited", border_style="dim", show_header=True)
    cite_table.add_column("Ref", style="bold cyan", width=6)
    cite_table.add_column("Article", style="bold")
    score_col_name = "Re-rank Score" if rerank else "RRF Score" if hybrid else "Similarity Score"
    cite_table.add_column(score_col_name, justify="right")
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


def cmd_eval(k: int = 5, hybrid: bool = False, rerank: bool = False, save_report: bool = True) -> None:
    if hybrid and rerank:
        tag = " [dim](Hybrid + Re-ranker)[/dim]"
    elif hybrid:
        tag = " [dim](Hybrid: Dense + BM25)[/dim]"
    elif rerank:
        tag = " [dim](with Re-ranker)[/dim]"
    else:
        tag = ""

    console.print(f"[bold cyan]Running SER Retrieval Benchmark across {len(BENCHMARK_DATASET)} canonical queries (k={k}){tag}...[/bold cyan]\n")
    scorecard, results = run_benchmark(client, k=k, hybrid=hybrid, rerank=rerank)
    render_console_report(scorecard, results, console)
    if save_report:
        report_path = Path("reports/eval_results.md")
        save_markdown_report(scorecard, results, report_path)
        console.print(f"\n[bold green]✓ Benchmark scorecard saved to: {report_path}[/bold green]")


def show_help() -> None:
    help_table = Table(title="Available Commands", border_style="cyan")
    help_table.add_column("Command", style="bold yellow")
    help_table.add_column("Description")
    help_table.add_row(r"<question> \[--hybrid] \[--rerank]", "Ask any question (runs full RAG with local Ollama; add --hybrid / --rerank)")
    help_table.add_row(r"/add <target>", "Polymorphic ingest: local file, folder, PDF, URL, or Wikipedia title")
    help_table.add_row(r"/search <query> \[--hybrid] \[--rerank]", "Semantic search only (shows matching chunks and scores; optional --hybrid / --rerank)")
    help_table.add_row(r"/ask <question> \[--hybrid] \[--rerank]", "Full RAG answer with optional hybrid search and cross-encoder re-ranking")
    help_table.add_row(r"/eval \[k] \[--hybrid] \[--rerank]", "Run automated benchmark measuring Hit Rate and latency")
    help_table.add_row(r"/ingest-wiki <title>", "Crawl and index a Wikipedia article live by title")
    help_table.add_row(r"/download-dump", "Download official Simple Wikipedia compressed dump (339 MB)")
    help_table.add_row(r"/ingest-dump \[N]", "Stream-ingest N articles from dump (default: 500)")
    help_table.add_row(r"/stats", "Show Qdrant collection size and storage metrics")
    help_table.add_row(r"/help", "Show this help table")
    help_table.add_row(r"/exit, /quit", "Exit the CLI")
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
        elif first_arg in ("eval", "benchmark", "--eval"):
            clean_args, hybrid, rerank = _extract_search_flags(sys.argv[2:])
            k = 5
            for a in clean_args:
                if a.isdigit():
                    k = int(a)
            cmd_eval(k=k, hybrid=hybrid, rerank=rerank)
            return
        elif first_arg in ("download-dump", "--download-dump"):
            cmd_download_dump()
            return
        elif first_arg in ("add", "--add"):
            if len(sys.argv) > 2:
                cmd_add(" ".join(sys.argv[2:]))
            else:
                console.print("[red]Usage: ser add <file | folder | url | 'Wikipedia Title'>[/red]")
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
            clean_args, hybrid, rerank = _extract_search_flags(sys.argv[2:])
            cmd_search(" ".join(clean_args), hybrid=hybrid, rerank=rerank)
            return
        elif first_arg == "ask" and len(sys.argv) > 2:
            clean_args, hybrid, rerank = _extract_search_flags(sys.argv[2:])
            cmd_ask(" ".join(clean_args), hybrid=hybrid, rerank=rerank)
            return
        else:
            # Direct query: ser "What is physics?" [--hybrid] [--rerank]
            clean_args, hybrid, rerank = _extract_search_flags(sys.argv[1:])
            cmd_ask(" ".join(clean_args), hybrid=hybrid, rerank=rerank)
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
            elif user_input.lower().startswith("/eval") or user_input.lower().startswith("/benchmark"):
                parts = user_input.split()
                clean_parts, hybrid, rerank = _extract_search_flags(parts[1:])
                k = int(clean_parts[0]) if clean_parts and clean_parts[0].isdigit() else 5
                cmd_eval(k=k, hybrid=hybrid, rerank=rerank)
            elif user_input.lower() == "/download-dump":
                cmd_download_dump()
            elif user_input.lower().startswith("/add") or user_input.lower().startswith("add "):
                parts = user_input.split(maxsplit=1)
                if len(parts) > 1:
                    cmd_add(parts[1])
                else:
                    console.print("[red]Usage: /add <file | folder | url | 'Wikipedia Title'>[/red]")
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
                    clean_parts, hybrid, rerank = _extract_search_flags(parts[1].split())
                    cmd_search(" ".join(clean_parts), hybrid=hybrid, rerank=rerank)
                else:
                    console.print("[red]Usage: /search <query> [--hybrid] [--rerank][/red]")
            elif user_input.lower().startswith("/ask"):
                parts = user_input.split(maxsplit=1)
                if len(parts) > 1:
                    clean_parts, hybrid, rerank = _extract_search_flags(parts[1].split())
                    cmd_ask(" ".join(clean_parts), hybrid=hybrid, rerank=rerank)
                else:
                    console.print("[red]Usage: /ask <question> [--hybrid] [--rerank][/red]")
            else:
                # Default: any plain text input is treated as a question
                clean_parts, hybrid, rerank = _extract_search_flags(user_input.split())
                cmd_ask(" ".join(clean_parts), hybrid=hybrid, rerank=rerank)

        except (KeyboardInterrupt, EOFError):
            console.print("\n[cyan]Goodbye![/cyan]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    main()
