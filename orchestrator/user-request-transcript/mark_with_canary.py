from __future__ import annotations

import argparse
import secrets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--digits",
        type=int,
        default=20,
        help="Number of random decimal digits to emit.",
    )
    parser.add_argument(
        "--prefix",
        default="trycycle-canary",
        help="Prefix added ahead of the random decimal payload.",
    )
    args = parser.parse_args()
    if not 8 <= args.digits <= 64:
        parser.error("--digits must be between 8 and 64")
    return args


def main() -> None:
    args = parse_args()
    limit = 10**args.digits
    payload = f"{secrets.randbelow(limit):0{args.digits}d}"
    print(f"{args.prefix}-{payload}")


if __name__ == "__main__":
    main()
