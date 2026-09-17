import json
from pathlib import Path

from .metrics import score_case, summarize


def load_cases(dataset_path):
    path = Path(dataset_path)
    with path.open(encoding='utf-8') as dataset:
        return [json.loads(line) for line in dataset if line.strip() and not line.lstrip().startswith('#')]


def run_cases(cases, responder):
    scores = []
    for case in cases:
        try:
            result = responder(case['input'], case)
            scores.append(score_case(case, result=result))
        except Exception as exc:
            scores.append(score_case(case, error=exc))
    return summarize(scores)


def run_dataset(dataset_path, responder):
    return run_cases(load_cases(dataset_path), responder)


if __name__ == '__main__':
    raise SystemExit('Import run_dataset and provide a responder function.')