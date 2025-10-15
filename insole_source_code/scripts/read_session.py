#!/usr/bin/env python
import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.session_reader import load_session, print_session_summary, to_dataframe


def main():
    parser = argparse.ArgumentParser(description="Read and inspect insole session JSONL files")
    parser.add_argument("file", help="Path to session .jsonl file")
    parser.add_argument("--print", dest="do_print", action="store_true", help="Print summary to terminal")
    parser.add_argument("--to-csv", dest="csv_path", default=None, help="Export frame summary to CSV path")
    parser.add_argument("--flat", action="store_true", help="When exporting, output flattened per-point table (heavy)")
    args = parser.parse_args()

    sess = load_session(args.file)

    if args.do_print:
        print_session_summary(sess)

    if args.csv_path:
        df = to_dataframe(sess, flat=args.flat)
        df.to_csv(args.csv_path, index=False)
        print(f"Exported to {args.csv_path}")


if __name__ == "__main__":
    main()

# 使用示例（PowerShell）：
# 打印概要
# python scripts\read_session.py records\session_YYYYMMDD-HHMMSS.jsonl --print
# python scripts\read_session.py records\session_20251014-180934.jsonl --print
# 导出帧级摘要 CSV
# python scripts\read_session.py records\session_YYYYMMDD-HHMMSS.jsonl --to-csv out\frames.csv
# python scripts\read_session.py records\session_20251014-160032.jsonl --to-csv out\frames.csv
# 导出逐点展开 CSV
# python scripts\read_session.py records\session_YYYYMMDD-HHMMSS.jsonl --to-csv out\points.csv --flat