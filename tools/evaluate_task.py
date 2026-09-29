"""Evaluate an immutable recorded task trace against a fixed protocol."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.task_evaluation import evaluate_container_task

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace',type=Path,required=True)
    parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Output already exists; retain prior verdict')
    report=evaluate_container_task(json.loads(args.trace.read_text()),json.loads(args.protocol.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,allow_nan=False))
    sys.exit(0 if report['simulation_task_pass'] else 1)
