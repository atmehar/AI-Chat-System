def _contains_expected(actual, expected):
    if not expected:
        return True
    actual_text = (actual or '').lower()
    values = expected if isinstance(expected, list) else [expected]
    return all(str(value).lower() in actual_text for value in values)


def score_case(case, result=None, error=None):
    result = result or {}
    content = result.get('content') or result.get('response') or ''
    expected_tool = case.get('expected_tool')
    actual_tool = result.get('tool_name')
    passed = not error and _contains_expected(content, case.get('expected_contains'))
    if expected_tool:
        passed = passed and actual_tool == expected_tool
    if case.get('should_block'):
        passed = passed and bool(error)
    return {
        'id': case.get('id', 'unnamed'),
        'passed': bool(passed),
        'error': str(error) if error else None,
        'expected_tool': expected_tool,
        'actual_tool': actual_tool,
    }


def summarize(scores):
    total = len(scores)
    passed = sum(score['passed'] for score in scores)
    return {'total': total, 'passed': passed, 'failed': total - passed, 'pass_rate': passed / total if total else 0.0, 'cases': scores}