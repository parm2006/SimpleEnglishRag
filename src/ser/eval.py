import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ser.db import COLLECTION_NAME, client
from ser.pipeline import ask


@dataclass
class BenchmarkCase:
    query: str
    expected_title: str
    acceptable_titles: list[str]
    category: str


@dataclass
class QueryEvalResult:
    case: BenchmarkCase
    rank: Optional[int]  # 1-indexed rank of first match, or None if not in top k
    top_score: float
    retrieved_titles: list[str]
    latency_ms: float
    hit_1: bool
    hit_3: bool
    hit_5: bool
    reciprocal_rank: float


@dataclass
class BenchmarkScorecard:
    total_queries: int
    hit_rate_1: float
    hit_rate_3: float
    hit_rate_5: float
    mrr: float
    avg_top_score: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    per_category: dict[str, dict[str, float]] = field(default_factory=dict)


# ==============================================================================
# CHALLENGING RETRIEVAL BENCHMARK (Zero Literal Keyword Overlap, Conceptual Riddles)
# ==============================================================================
BENCHMARK_DATASET: list[BenchmarkCase] = [
    # --------------------------------------------------------------------------
    # 1. Advanced History & Conflict (Conceptual clues, no title keywords)
    # --------------------------------------------------------------------------
    BenchmarkCase(
        query="The 1815 battle in modern Belgium where the Seventh Coalition led by Wellington and Blücher decisively ended the French Emperor's rule",
        expected_title="Battle of Waterloo",
        acceptable_titles=["Battle of Waterloo", "Waterloo", "Napoleon"],
        category="History & Events",
    ),
    BenchmarkCase(
        query="The 1962 intense 13-day confrontation between Kennedy and Khrushchev triggered by Soviet ballistic installations in the Caribbean",
        expected_title="Cuban Missile Crisis",
        acceptable_titles=["Cuban Missile Crisis", "Cold War"],
        category="History & Events",
    ),
    BenchmarkCase(
        query="The catastrophic 1986 steam explosion and graphite fire at reactor unit four in Soviet Ukraine",
        expected_title="Chernobyl disaster",
        acceptable_titles=["Chernobyl disaster", "Chernobyl", "Nuclear meltdown"],
        category="History & Events",
    ),
    BenchmarkCase(
        query="The 1944 massive Allied amphibious invasion of Normandy beaches codenamed Operation Overlord",
        expected_title="Invasion of Normandy",
        acceptable_titles=["Invasion of Normandy", "Normandy landings", "D-Day", "Operation Overlord"],
        category="History & Events",
    ),
    BenchmarkCase(
        query="The ancient Macedonian king who conquered the Persian Empire by age thirty before dying in Babylon in 323 BC",
        expected_title="Alexander the Great",
        acceptable_titles=["Alexander the Great"],
        category="History & Events",
    ),
    BenchmarkCase(
        query="The peace treaty signed in the Hall of Mirrors in 1919 that imposed heavy reparations on Germany and created the League of Nations",
        expected_title="Treaty of Versailles",
        acceptable_titles=["Treaty of Versailles", "League of Nations"],
        category="History & Events",
    ),

    # --------------------------------------------------------------------------
    # 2. Advanced Physics & Space (Mechanisms and paradoxes)
    # --------------------------------------------------------------------------
    BenchmarkCase(
        query="The quantum mechanical paradox involving a feline that remains simultaneously alive and dead inside a sealed chamber with a radioactive trigger",
        expected_title="Schrödinger's cat",
        acceptable_titles=["Schrödinger's cat", "Erwin Schrödinger", "Superposition principle"],
        category="Physics & Space",
    ),
    BenchmarkCase(
        query="The boundary surface around a collapsed gravitational singularity from which no radiation or matter can escape to the outside universe",
        expected_title="Event horizon",
        acceptable_titles=["Event horizon", "Black hole", "Singularity"],
        category="Physics & Space",
    ),
    BenchmarkCase(
        query="The theoretical subatomic particle predicted by the Standard Model that gives mass to elementary particles through spontaneous symmetry breaking",
        expected_title="Higgs boson",
        acceptable_titles=["Higgs boson", "Standard Model", "Large Hadron Collider"],
        category="Physics & Space",
    ),
    BenchmarkCase(
        query="The optical wave phenomenon where light bends as it passes through a narrow aperture or around obstacles creating fringe patterns",
        expected_title="Diffraction",
        acceptable_titles=["Diffraction", "Interference", "Wave"],
        category="Physics & Space",
    ),
    BenchmarkCase(
        query="The moon of Saturn with a subsurface liquid water ocean that ejects supersonic geysers into space feeding the E ring",
        expected_title="Enceladus",
        acceptable_titles=["Enceladus", "Enceladus (moon)", "Saturn"],
        category="Physics & Space",
    ),
    BenchmarkCase(
        query="The hypothetical form of matter that does not interact with electromagnetic radiation but accounts for approximately 85 percent of all mass in the universe",
        expected_title="Dark matter",
        acceptable_titles=["Dark matter", "Cosmology"],
        category="Physics & Space",
    ),

    # --------------------------------------------------------------------------
    # 3. Computing & Algorithms (Abstract specifications)
    # --------------------------------------------------------------------------
    BenchmarkCase(
        query="The recursive divide-and-conquer sorting procedure that partitions elements around a selected pivot",
        expected_title="Quicksort",
        acceptable_titles=["Quicksort", "Sorting algorithm"],
        category="Computing & Algorithms",
    ),
    BenchmarkCase(
        query="The high-level programming language created by Guido van Rossum named after a British sketch comedy series",
        expected_title="Python",
        acceptable_titles=["Python (programming language)", "Python", "Guido van Rossum"],
        category="Computing & Algorithms",
    ),
    BenchmarkCase(
        query="The decentralized consensus mechanism used in blockchain networks where miners solve computationally intensive cryptographic puzzles",
        expected_title="Proof of work",
        acceptable_titles=["Proof of work", "Bitcoin", "Blockchain"],
        category="Computing & Algorithms",
    ),
    BenchmarkCase(
        query="The core software subsystem running in privileged supervisor mode that multiplexes CPU execution, memory pages, and device drivers",
        expected_title="Operating system",
        acceptable_titles=["Operating system", "Kernel (computer science)", "Kernel", "Linux"],
        category="Computing & Algorithms",
    ),
    BenchmarkCase(
        query="The mathematical scheme using asymmetric trapdoor functions where a public key encrypts data that only a private key can decrypt",
        expected_title="Cryptography",
        acceptable_titles=["Cryptography", "Public-key cryptography", "Encryption", "RSA"],
        category="Computing & Algorithms",
    ),

    # --------------------------------------------------------------------------
    # 4. Geography & Enclaves (Geopolitical and geological riddles)
    # --------------------------------------------------------------------------
    BenchmarkCase(
        query="The sovereign enclaved monarchy completely surrounded within the borders of South Africa in the Maloti Mountains",
        expected_title="Lesotho",
        acceptable_titles=["Lesotho"],
        category="Geography & Earth",
    ),
    BenchmarkCase(
        query="The deepest oceanic depression in the world located in the western North Pacific Ocean near the Mariana Islands",
        expected_title="Mariana Trench",
        acceptable_titles=["Mariana Trench", "Challenger Deep", "Pacific Ocean"],
        category="Geography & Earth",
    ),
    BenchmarkCase(
        query="The geologic zone where one heavier tectonic plate slides underneath another lighter plate down into the Earth's mantle",
        expected_title="Subduction",
        acceptable_titles=["Subduction", "Subduction zone", "Plate tectonics", "Convergent boundary"],
        category="Geography & Earth",
    ),
    BenchmarkCase(
        query="The transcontinental strait connecting the Black Sea to the Sea of Marmara that divides the European and Asian parts of Istanbul",
        expected_title="Bosphorus",
        acceptable_titles=["Bosphorus", "Bosporus", "Istanbul"],
        category="Geography & Earth",
    ),
    BenchmarkCase(
        query="The hyper-saline endorheic lake bordered by Jordan and Israel whose surface is the lowest land elevation on Earth",
        expected_title="Dead Sea",
        acceptable_titles=["Dead Sea"],
        category="Geography & Earth",
    ),

    # --------------------------------------------------------------------------
    # 5. Medicine & Biochemistry (Mechanisms, pathology, physiology)
    # --------------------------------------------------------------------------
    BenchmarkCase(
        query="The emergency medical condition where a dislodged thrombus travels through the venous circulation and occludes the arterial supply of the lungs",
        expected_title="Pulmonary embolism",
        acceptable_titles=["Pulmonary embolism", "Thrombosis", "Deep vein thrombosis", "Embolism"],
        category="Medicine & Biology",
    ),
    BenchmarkCase(
        query="The specialized intracellular organelle known as the powerhouse that produces ATP via oxidative phosphorylation",
        expected_title="Mitochondrion",
        acceptable_titles=["Mitochondrion", "Mitochondria", "Cell (biology)"],
        category="Medicine & Biology",
    ),
    BenchmarkCase(
        query="The infectious transmissible spongiform encephalopathy affecting bovines caused by abnormally folded prion proteins",
        expected_title="Bovine spongiform encephalopathy",
        acceptable_titles=["Bovine spongiform encephalopathy", "Mad cow disease", "Prion"],
        category="Medicine & Biology",
    ),
    BenchmarkCase(
        query="The noble gas element with atomic number 2 that remains liquid at normal pressure near absolute zero and exhibits superfluidity",
        expected_title="Helium",
        acceptable_titles=["Helium", "Superfluidity"],
        category="Medicine & Biology",
    ),
    BenchmarkCase(
        query="The acute infectious respiratory illness caused by Bordetella bacteria causing violent coughing spells with an inspiratory gasp sound",
        expected_title="Pertussis",
        acceptable_titles=["Pertussis", "Whooping cough"],
        category="Medicine & Biology",
    ),
    BenchmarkCase(
        query="The biological preparation that exposes the adaptive immune system to attenuated antigens to stimulate protective antibody memory",
        expected_title="Vaccine",
        acceptable_titles=["Vaccine", "Immune system", "Immunity (medical)", "Immunology"],
        category="Medicine & Biology",
    ),
    BenchmarkCase(
        query="The antiparallel double-stranded biopolymer carrying genetic instructions composed of adenine, cytosine, guanine, and thymine",
        expected_title="DNA",
        acceptable_titles=["DNA", "Deoxyribonucleic acid", "Double helix", "Genetics"],
        category="Medicine & Biology",
    ),

    # --------------------------------------------------------------------------
    # 6. Philosophy & Economics (Conceptual synthesis)
    # --------------------------------------------------------------------------
    BenchmarkCase(
        query="The classical philosopher of Athens sentenced to death by drinking a cup of hemlock for corrupting the young minds",
        expected_title="Socrates",
        acceptable_titles=["Socrates", "Plato", "Ancient Greece"],
        category="Philosophy & Economics",
    ),
    BenchmarkCase(
        query="The epic Mesopotamian poem regarded as the earliest surviving notable work of literature featuring a king searching for immortality with Enkidu",
        expected_title="Epic of Gilgamesh",
        acceptable_titles=["Epic of Gilgamesh", "Gilgamesh", "Mesopotamia"],
        category="Philosophy & Economics",
    ),
    BenchmarkCase(
        query="The economic situation where stagnant output and rising unemployment coincided with rapid price inflation",
        expected_title="Stagflation",
        acceptable_titles=["Stagflation", "Inflation", "Macroeconomics"],
        category="Philosophy & Economics",
    ),
]

# ==============================================================================
# COMMENTED OUT: PREVIOUS 100% TRIVIAL QUERIES
# These queries scored 100% Hit@1 in baseline benchmarks because they contained
# direct literal title keywords (e.g. "Photosynthesis", "Canberra", "Mars", etc.)
# ==============================================================================
# BASELINE_100_PERCENT_QUERIES = [
#     # Science & Physics (100% Hit @ 1)
#     BenchmarkCase(
#         query="What is photosynthesis and how does it produce oxygen?",
#         expected_title="Photosynthesis",
#         acceptable_titles=["Photosynthesis", "Chloroplast", "Plant"],
#         category="Science & Physics",
#     ),
#     BenchmarkCase(
#         query="Albert Einstein theory of general relativity",
#         expected_title="General relativity",
#         acceptable_titles=["General relativity", "Albert Einstein", "Theory of relativity"],
#         category="Science & Physics",
#     ),
#     BenchmarkCase(
#         query="How does a laser work?",
#         expected_title="Laser",
#         acceptable_titles=["Laser", "Optics", "Light"],
#         category="Science & Physics",
#     ),
#     BenchmarkCase(
#         query="Structure of an atom and subatomic particles",
#         expected_title="Atom",
#         acceptable_titles=["Atom", "Subatomic particle", "Electron", "Proton"],
#         category="Science & Physics",
#     ),
#     BenchmarkCase(
#         query="Newton's laws of motion",
#         expected_title="Newton's laws of motion",
#         acceptable_titles=["Newton's laws of motion", "Isaac Newton", "Classical mechanics"],
#         category="Science & Physics",
#     ),
#
#     # Astronomy & Space (100% Hit @ 1)
#     BenchmarkCase(
#         query="James Webb Space Telescope mission and discoveries",
#         expected_title="James Webb Space Telescope",
#         acceptable_titles=["James Webb Space Telescope", "Hubble Space Telescope", "Space observatory"],
#         category="Astronomy & Space",
#     ),
#     BenchmarkCase(
#         query="What is a black hole and event horizon?",
#         expected_title="Black hole",
#         acceptable_titles=["Black hole", "Event horizon", "Singularity"],
#         category="Astronomy & Space",
#     ),
#     BenchmarkCase(
#         query="The planet Mars surface and atmosphere",
#         expected_title="Mars",
#         acceptable_titles=["Mars", "Solar System", "Terrestrial planet"],
#         category="Astronomy & Space",
#     ),
#     BenchmarkCase(
#         query="How does the Sun produce energy through nuclear fusion?",
#         expected_title="Sun",
#         acceptable_titles=["Sun", "Nuclear fusion", "Star"],
#         category="Astronomy & Space",
#     ),
#     BenchmarkCase(
#         query="Milky Way galaxy structure",
#         expected_title="Milky Way",
#         acceptable_titles=["Milky Way", "Galaxy", "Spiral galaxy"],
#         category="Astronomy & Space",
#     ),
#
#     # History & Civilizations (100% Hit @ 1)
#     BenchmarkCase(
#         query="Fall of the Western Roman Empire",
#         expected_title="Fall of the Western Roman Empire",
#         acceptable_titles=["Fall of the Western Roman Empire", "Roman Empire", "Ancient Rome"],
#         category="History & Civilizations",
#     ),
#     BenchmarkCase(
#         query="Who was Joan of Arc in the Hundred Years' War?",
#         expected_title="Joan of Arc",
#         acceptable_titles=["Joan of Arc", "Hundred Years' War", "France"],
#         category="History & Civilizations",
#     ),
#     BenchmarkCase(
#         query="The Industrial Revolution changes in manufacturing",
#         expected_title="Industrial Revolution",
#         acceptable_titles=["Industrial Revolution", "Steam engine", "Manufacturing"],
#         category="History & Civilizations",
#     ),
#     BenchmarkCase(
#         query="Ancient Egyptian pyramids and Pharaohs",
#         expected_title="Ancient Egypt",
#         acceptable_titles=["Ancient Egypt", "Egyptian pyramids", "Pharaoh", "Pyramid"],
#         category="History & Civilizations",
#     ),
#     BenchmarkCase(
#         query="The Renaissance period in Europe",
#         expected_title="Renaissance",
#         acceptable_titles=["Renaissance", "Middle Ages", "History of Europe"],
#         category="History & Civilizations",
#     ),
#
#     # Geography & Earth (100% Hit @ 1)
#     BenchmarkCase(
#         query="What is the capital city of Australia?",
#         expected_title="Canberra",
#         acceptable_titles=["Canberra", "Australia", "Capital of Australia"],
#         category="Geography & Earth",
#     ),
#     BenchmarkCase(
#         query="Amazon River length and basin",
#         expected_title="Amazon River",
#         acceptable_titles=["Amazon River", "Amazon rainforest", "South America"],
#         category="Geography & Earth",
#     ),
#     BenchmarkCase(
#         query="Mount Everest elevation and Himalayas",
#         expected_title="Mount Everest",
#         acceptable_titles=["Mount Everest", "Himalayas", "Mountain"],
#         category="Geography & Earth",
#     ),
#     BenchmarkCase(
#         query="Sahara Desert climate and geography",
#         expected_title="Sahara Desert",
#         acceptable_titles=["Sahara", "Sahara Desert", "Desert", "North Africa"],
#         category="Geography & Earth",
#     ),
#     BenchmarkCase(
#         query="Plate tectonics and continental drift",
#         expected_title="Plate tectonics",
#         acceptable_titles=["Plate tectonics", "Continental drift", "Earthquake"],
#         category="Geography & Earth",
#     ),
#
#     # Computing & Biology (The remaining 100% Hit @ 1 queries)
#     BenchmarkCase(
#         query="Alan Turing and the Turing machine",
#         expected_title="Turing machine",
#         acceptable_titles=["Turing machine", "Alan Turing", "Computer science"],
#         category="Computing & Technology",
#     ),
#     BenchmarkCase(
#         query="How does the Internet and World Wide Web work?",
#         expected_title="Internet",
#         acceptable_titles=["Internet", "World Wide Web", "Computer network"],
#         category="Computing & Technology",
#     ),
#     BenchmarkCase(
#         query="Binary number system and bits",
#         expected_title="Binary number",
#         acceptable_titles=["Binary number", "Binary numeral system", "Bit", "Byte"],
#         category="Computing & Technology",
#     ),
#     BenchmarkCase(
#         query="Human circulatory system and the heart",
#         expected_title="Circulatory system",
#         acceptable_titles=["Circulatory system", "Heart", "Blood"],
#         category="Biology & Medicine",
#     ),
#     BenchmarkCase(
#         query="Antibiotics and bacterial infections",
#         expected_title="Antibiotic",
#         acceptable_titles=["Antibiotic", "Bacteria", "Penicillin"],
#         category="Biology & Medicine",
#     ),
#     BenchmarkCase(
#         query="How does the human brain and neurons process signals?",
#         expected_title="Brain",
#         acceptable_titles=["Brain", "Neuron", "Nervous system", "Human brain"],
#         category="Biology & Medicine",
#     ),
# ]


def evaluate_query(
    qdrant_client: Any,
    case: BenchmarkCase,
    k: int = 5,
    rerank: bool = False,
) -> QueryEvalResult:
    """Executes a single benchmark query and measures accuracy & latency."""
    t0 = time.perf_counter()
    chunks = ask(qdrant_client, query=case.query, k=k, rerank=rerank)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    retrieved_titles = [c.payload.get("title", "") for c in chunks]
    top_score = chunks[0].score if chunks else 0.0

    # Match check: match if any acceptable title is an exact match or substring
    rank: Optional[int] = None
    acceptable_lower = [t.lower().strip() for t in case.acceptable_titles]

    for idx, title in enumerate(retrieved_titles):
        t_low = title.lower().strip()
        matched = any(
            acc == t_low or acc in t_low or t_low in acc
            for acc in acceptable_lower
        )
        if matched:
            rank = idx + 1
            break

    hit_1 = rank == 1
    hit_3 = rank is not None and rank <= 3
    hit_5 = rank is not None and rank <= 5
    reciprocal_rank = 1.0 / rank if rank is not None else 0.0

    return QueryEvalResult(
        case=case,
        rank=rank,
        top_score=top_score,
        retrieved_titles=retrieved_titles,
        latency_ms=elapsed_ms,
        hit_1=hit_1,
        hit_3=hit_3,
        hit_5=hit_5,
        reciprocal_rank=reciprocal_rank,
    )


def run_benchmark(
    qdrant_client: Any = client,
    k: int = 5,
    cases: Optional[list[BenchmarkCase]] = None,
    rerank: bool = False,
) -> tuple[BenchmarkScorecard, list[QueryEvalResult]]:
    """Runs the full evaluation benchmark across all test queries."""
    benchmark_cases = cases or BENCHMARK_DATASET
    results: list[QueryEvalResult] = []

    for case in benchmark_cases:
        res = evaluate_query(qdrant_client, case, k=k, rerank=rerank)
        results.append(res)

    total = len(results)
    if total == 0:
        raise ValueError("No benchmark cases provided.")

    hit_1_count = sum(1 for r in results if r.hit_1)
    hit_3_count = sum(1 for r in results if r.hit_3)
    hit_5_count = sum(1 for r in results if r.hit_5)
    mrr_val = sum(r.reciprocal_rank for r in results) / total

    scores = [r.top_score for r in results]
    latencies = [r.latency_ms for r in results]

    sorted_latencies = sorted(latencies)
    p50_idx = int(len(sorted_latencies) * 0.50)
    p95_idx = min(int(len(sorted_latencies) * 0.95), len(sorted_latencies) - 1)

    # Category breakdown
    categories: set[str] = {r.case.category for r in results}
    per_category: dict[str, dict[str, float]] = {}
    for cat in sorted(categories):
        cat_results = [r for r in results if r.case.category == cat]
        cat_total = len(cat_results)
        per_category[cat] = {
            "total": float(cat_total),
            "hit_1": sum(1 for r in cat_results if r.hit_1) / cat_total,
            "hit_3": sum(1 for r in cat_results if r.hit_3) / cat_total,
            "hit_5": sum(1 for r in cat_results if r.hit_5) / cat_total,
            "mrr": sum(r.reciprocal_rank for r in cat_results) / cat_total,
            "avg_latency_ms": statistics.mean([r.latency_ms for r in cat_results]),
        }

    scorecard = BenchmarkScorecard(
        total_queries=total,
        hit_rate_1=hit_1_count / total,
        hit_rate_3=hit_3_count / total,
        hit_rate_5=hit_5_count / total,
        mrr=mrr_val,
        avg_top_score=statistics.mean(scores),
        avg_latency_ms=statistics.mean(latencies),
        p50_latency_ms=sorted_latencies[p50_idx],
        p95_latency_ms=sorted_latencies[p95_idx],
        min_latency_ms=min(latencies),
        max_latency_ms=max(latencies),
        per_category=per_category,
    )

    return scorecard, results


def render_console_report(
    scorecard: BenchmarkScorecard,
    results: list[QueryEvalResult],
    console: Console,
) -> None:
    """Renders the detailed per-query table and executive scorecard to the terminal."""
    # 1. Detailed Query Table
    table = Table(title="SER Retrieval Evaluation: Per-Query Results", border_style="cyan")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Query", style="white", max_width=32)
    table.add_column("Expected", style="cyan", max_width=18)
    table.add_column("Rank #1 Retrieved", style="yellow", max_width=22)
    table.add_column("Score", justify="right")
    table.add_column("Hit Rank", justify="center")
    table.add_column("Latency", justify="right")

    for i, r in enumerate(results, 1):
        top_title = r.retrieved_titles[0] if r.retrieved_titles else "—"
        if r.rank == 1:
            hit_badge = "[bold green]Hit @ 1[/bold green]"
        elif r.rank in (2, 3):
            hit_badge = f"[bold cyan]Hit @ {r.rank}[/bold cyan]"
        elif r.rank in (4, 5):
            hit_badge = f"[yellow]Hit @ {r.rank}[/yellow]"
        else:
            hit_badge = "[bold red]Miss[/bold red]"

        score_style = "green" if r.top_score >= 0.70 else "yellow" if r.top_score >= 0.50 else "red"

        table.add_row(
            str(i),
            r.case.query,
            r.case.expected_title,
            top_title,
            f"[{score_style}]{r.top_score:.4f}[/{score_style}]",
            hit_badge,
            f"{r.latency_ms:.0f} ms",
        )

    console.print(table)
    console.print()

    # 2. Executive Scorecard Panel
    scorecard_table = Table(title="Executive Retrieval Benchmark Scorecard", border_style="green")
    scorecard_table.add_column("Metric", style="cyan", justify="left")
    scorecard_table.add_column("Result", style="bold white", justify="right")
    scorecard_table.add_column("Benchmark Target", style="dim", justify="left")

    scorecard_table.add_row("Total Benchmark Queries", str(scorecard.total_queries), "30 queries across 6 domains")
    scorecard_table.add_row(
        "Hit Rate @ 1 (Top-1 Accuracy)",
        f"[bold {'green' if scorecard.hit_rate_1 >= 0.80 else 'yellow'}]{scorecard.hit_rate_1 * 100:.1f}%[/]",
        "Target: > 75.0%",
    )
    scorecard_table.add_row(
        "Hit Rate @ 3 (Top-3 Recall)",
        f"[bold {'green' if scorecard.hit_rate_3 >= 0.90 else 'yellow'}]{scorecard.hit_rate_3 * 100:.1f}%[/]",
        "Target: > 85.0%",
    )
    scorecard_table.add_row(
        "Hit Rate @ 5 (Top-5 Recall)",
        f"[bold {'green' if scorecard.hit_rate_5 >= 0.95 else 'yellow'}]{scorecard.hit_rate_5 * 100:.1f}%[/]",
        "Target: > 90.0%",
    )
    scorecard_table.add_row(
        "Mean Reciprocal Rank (MRR)",
        f"[bold {'green' if scorecard.mrr >= 0.85 else 'yellow'}]{scorecard.mrr:.4f}[/]",
        "Target: > 0.8000",
    )
    scorecard_table.add_row(
        "Average Top Similarity Score",
        f"{scorecard.avg_top_score:.4f}",
        "Cosine similarity (0.0 - 1.0)",
    )
    scorecard_table.add_row(
        "Median Latency (p50)",
        f"[bold green]{scorecard.p50_latency_ms:.1f} ms[/bold green]",
        "FastEmbed ONNX + HTTPS Qdrant Cloud",
    )
    scorecard_table.add_row(
        "95th Percentile Latency (p95)",
        f"[bold yellow]{scorecard.p95_latency_ms:.1f} ms[/bold yellow]",
        "Tail network latency threshold",
    )
    scorecard_table.add_row(
        "Latency Range (Min / Max)",
        f"{scorecard.min_latency_ms:.0f} ms / {scorecard.max_latency_ms:.0f} ms",
        "—",
    )

    console.print(scorecard_table)
    console.print()

    # 3. Category Breakdown Table
    cat_table = Table(title="Accuracy by Knowledge Domain", border_style="magenta")
    cat_table.add_column("Domain", style="cyan")
    cat_table.add_column("Queries", justify="right")
    cat_table.add_column("Hit @ 1", justify="right")
    cat_table.add_column("Hit @ 3", justify="right")
    cat_table.add_column("Hit @ 5", justify="right")
    cat_table.add_column("MRR", justify="right")
    cat_table.add_column("Avg Latency", justify="right")

    for cat, stats in scorecard.per_category.items():
        cat_table.add_row(
            cat,
            str(int(stats["total"])),
            f"{stats['hit_1'] * 100:.0f}%",
            f"{stats['hit_3'] * 100:.0f}%",
            f"{stats['hit_5'] * 100:.0f}%",
            f"{stats['mrr']:.3f}",
            f"{stats['avg_latency_ms']:.0f} ms",
        )

    console.print(cat_table)


def save_markdown_report(
    scorecard: BenchmarkScorecard,
    results: list[QueryEvalResult],
    report_path: Path = Path("reports/eval_results.md"),
) -> None:
    """Saves a comprehensive markdown report of the benchmark evaluation."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# SER Retrieval Benchmark Report",
        "",
        f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Collection**: `{COLLECTION_NAME}`",
        f"**Embedding Model**: `BAAI/bge-small-en-v1.5` (FastEmbed ONNX 384-dim)",
        "",
        "---",
        "",
        "## Executive Scorecard",
        "",
        "| Metric | Value | Benchmark Target | Status |",
        "|---|:---:|:---:|:---:|",
        f"| **Hit Rate @ 1 (Top-1 Accuracy)** | **{scorecard.hit_rate_1 * 100:.1f}%** | > 75.0% | {'✅ Pass' if scorecard.hit_rate_1 >= 0.75 else '⚠️ Low'} |",
        f"| **Hit Rate @ 3 (Top-3 Recall)** | **{scorecard.hit_rate_3 * 100:.1f}%** | > 85.0% | {'✅ Pass' if scorecard.hit_rate_3 >= 0.85 else '⚠️ Low'} |",
        f"| **Hit Rate @ 5 (Top-5 Recall)** | **{scorecard.hit_rate_5 * 100:.1f}%** | > 90.0% | {'✅ Pass' if scorecard.hit_rate_5 >= 0.90 else '⚠️ Low'} |",
        f"| **Mean Reciprocal Rank (MRR)** | **{scorecard.mrr:.4f}** | > 0.8000 | {'✅ Pass' if scorecard.mrr >= 0.80 else '⚠️ Low'} |",
        f"| **Average Top Score** | **{scorecard.avg_top_score:.4f}** | > 0.7000 | {'✅ Pass' if scorecard.avg_top_score >= 0.70 else '⚠️ Low'} |",
        f"| **Median Latency (p50)** | **{scorecard.p50_latency_ms:.1f} ms** | < 350 ms | {'✅ Pass' if scorecard.p50_latency_ms < 350 else '⚠️ Slow'} |",
        f"| **95th Percentile Latency (p95)** | **{scorecard.p95_latency_ms:.1f} ms** | < 500 ms | {'✅ Pass' if scorecard.p95_latency_ms < 500 else '⚠️ Slow'} |",
        "",
        "---",
        "",
        "## Domain Breakdown",
        "",
        "| Domain | Queries | Hit @ 1 | Hit @ 3 | Hit @ 5 | MRR | Avg Latency |",
        "|---|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for cat, stats in scorecard.per_category.items():
        lines.append(
            f"| {cat} | {int(stats['total'])} | {stats['hit_1'] * 100:.0f}% | {stats['hit_3'] * 100:.0f}% | {stats['hit_5'] * 100:.0f}% | {stats['mrr']:.3f} | {stats['avg_latency_ms']:.0f} ms |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Detailed Per-Query Results",
        "",
        "| # | Query | Expected Article | Rank #1 Retrieved | Score | Hit Rank | Latency |",
        "|---|---|---|---|:---:|:---:|:---:|",
    ])

    for i, r in enumerate(results, 1):
        top_title = r.retrieved_titles[0] if r.retrieved_titles else "—"
        hit_str = f"Hit @ {r.rank}" if r.rank else "❌ Miss"
        lines.append(
            f"| {i} | {r.case.query} | {r.case.expected_title} | {top_title} | {r.top_score:.4f} | {hit_str} | {r.latency_ms:.0f} ms |"
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")
