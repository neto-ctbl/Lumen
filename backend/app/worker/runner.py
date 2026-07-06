import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Lumen worker stub")
    parser.add_argument("--once", action="store_true", help="Run worker stub once and exit")
    parser.parse_args()

    print("Lumen worker stub OK - Stage S1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
