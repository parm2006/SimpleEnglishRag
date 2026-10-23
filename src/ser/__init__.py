def main() -> None:
    import sys
    from pathlib import Path

    from dotenv import load_dotenv

    from ser.cloud import ensure_cloud_ready

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    load_dotenv()
    try:
        ensure_cloud_ready()
    except RuntimeError as exc:
        print(f"ser: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    # Wake the database before importing CLI modules that connect to it.
    from ser.cli import main as cli_main

    cli_main()

__all__ = ["main"]

if __name__ == "__main__":
    main()
