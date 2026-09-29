"""Evaluate a frozen geometry protocol; relative artifacts resolve beside each manifest."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from r2s.contracts import digest
from r2s.geometry_feedback import evaluate_geometry_feedback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--expected-protocol-sha256', required=True,
                        help='Canonical JSON digest pinned before candidate generation')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding='utf-8-sig'))
    if digest(protocol) != args.expected_protocol_sha256:
        parser.error('Protocol changed relative to the predeclared digest')
    candidate = json.loads(args.candidate.read_text(encoding='utf-8-sig'))
    report = evaluate_geometry_feedback(protocol, candidate, args.protocol.parent,
                                        args.candidate.parent, args.output.parent / (args.output.stem + '_overlays'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'summary': report['summary'], 'report': str(args.output)}))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
