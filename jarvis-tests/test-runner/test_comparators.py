#!/usr/bin/env python3
"""
Test Comparators
Standard comparison functions for test validation as specified in the plan.
These replace the ad-hoc check types with standardized comparators.
"""

from typing import Any, List, Dict, Set, Tuple
import json
import re


class TestComparators:
    """Standard test comparison functions"""

    @staticmethod
    def equals(actual: Any, expected: Any) -> Tuple[bool, str]:
        """
        Exact equality check.
        Returns (is_match, message)
        """
        if actual == expected:
            return True, f"equals: {actual} == {expected}"
        else:
            return False, f"equals: expected {expected}, got {actual}"

    @staticmethod
    def set_equals(actual: List[Any], expected: List[Any]) -> Tuple[bool, str]:
        """
        Set equality check (order doesn't matter).
        Returns (is_match, message)
        """
        actual_set = set(actual) if isinstance(actual, (list, set)) else {actual}
        expected_set = set(expected) if isinstance(expected, (list, set)) else {expected}

        if actual_set == expected_set:
            return True, f"set_equals: sets match"
        else:
            missing = expected_set - actual_set
            extra = actual_set - expected_set
            msg = f"set_equals: mismatch"
            if missing:
                msg += f", missing: {missing}"
            if extra:
                msg += f", extra: {extra}"
            return False, msg

    @staticmethod
    def contains_all(actual: Any, expected_items: List[Any]) -> Tuple[bool, str]:
        """
        Check that actual contains all expected items.
        Returns (is_match, message)
        """
        actual_str = str(actual)
        missing = []

        for item in expected_items:
            if str(item) not in actual_str:
                missing.append(item)

        if not missing:
            return True, f"contains_all: all {len(expected_items)} items found"
        else:
            return False, f"contains_all: missing items: {missing}"

    @staticmethod
    def must_not_contain(actual: Any, forbidden_items: List[Any]) -> Tuple[bool, str]:
        """
        Check that actual does not contain any forbidden items.
        Returns (is_match, message)
        """
        actual_str = str(actual)
        found = []

        for item in forbidden_items:
            if str(item) in actual_str:
                found.append(item)

        if not found:
            return True, f"must_not_contain: no forbidden items found"
        else:
            return False, f"must_not_contain: found forbidden items: {found}"

    @staticmethod
    def ordered(actual: List[Any], expected: List[Any]) -> Tuple[bool, str]:
        """
        Check that actual is in the same order as expected.
        Returns (is_match, message)
        """
        if not isinstance(actual, list):
            return False, f"ordered: actual is not a list"

        if actual == expected:
            return True, f"ordered: sequence matches exactly"
        else:
            # Find first mismatch
            for i, (a, e) in enumerate(zip(actual, expected)):
                if a != e:
                    return False, f"ordered: mismatch at position {i}: expected {e}, got {a}"
            return False, f"ordered: length mismatch: expected {len(expected)}, got {len(actual)}"

    @staticmethod
    def json_path(actual: Dict, path: str, expected: Any) -> Tuple[bool, str]:
        """
        Check value at JSON path matches expected.
        Path format: "field.nested.field" or "array[0].field"
        Returns (is_match, message)
        """
        try:
            # Navigate the path
            current = actual
            parts = path.split('.')

            for part in parts:
                # Handle array indexing
                if '[' in part and part.endswith(']'):
                    field_name = part.split('[')[0]
                    index = int(part.split('[')[1].rstrip(']'))

                    if field_name:
                        current = current[field_name]
                    current = current[index]
                else:
                    current = current[part]

            if current == expected:
                return True, f"json_path: {path} = {current}"
            else:
                return False, f"json_path: {path} expected {expected}, got {current}"
        except (KeyError, IndexError, TypeError) as e:
            return False, f"json_path: error navigating path {path}: {e}"

    @staticmethod
    def line_numbers(content: str, expected_lines: Dict[str, int]) -> Tuple[bool, str]:
        """
        Check line counts match expected.
        Expected format: {"total": N, "non_empty": M, "comment": K}
        Returns (is_match, message)
        """
        if not isinstance(content, str):
            return False, f"line_numbers: content is not a string"

        lines = content.split('\n')
        total = len(lines)
        non_empty = len([l for l in lines if l.strip()])
        comment = len([l for l in lines if l.strip().startswith('#')])

        mismatches = []
        if 'total' in expected_lines and total != expected_lines['total']:
            mismatches.append(f"total: expected {expected_lines['total']}, got {total}")
        if 'non_empty' in expected_lines and non_empty != expected_lines['non_empty']:
            mismatches.append(f"non_empty: expected {expected_lines['non_empty']}, got {non_empty}")
        if 'comment' in expected_lines and comment != expected_lines['comment']:
            mismatches.append(f"comment: expected {expected_lines['comment']}, got {comment}")

        if not mismatches:
            return True, f"line_numbers: total={total}, non_empty={non_empty}, comment={comment}"
        else:
            return False, f"line_numbers: {', '.join(mismatches)}"

    @staticmethod
    def precision_recall(actual: List[Any], expected: List[Any],
                       min_precision: float = 0.95, min_recall: float = 0.90) -> Tuple[bool, str]:
        """
        Check precision and recall against expected set.
        Returns (is_match, message)
        """
        actual_set = set(actual) if isinstance(actual, (list, set)) else set()
        expected_set = set(expected) if isinstance(expected, (list, set)) else set()

        true_positives = actual_set & expected_set
        false_positives = actual_set - expected_set
        false_negatives = expected_set - actual_set

        precision = len(true_positives) / len(actual_set) if actual_set else 0.0
        recall = len(true_positives) / len(expected_set) if expected_set else 0.0

        msg = f"precision_recall: precision={precision:.2f}, recall={recall:.2f}"

        if precision >= min_precision and recall >= min_recall:
            return True, f"{msg} (within thresholds)"
        else:
            issues = []
            if precision < min_precision:
                issues.append(f"precision {precision:.2f} < {min_precision}")
            if recall < min_recall:
                issues.append(f"recall {recall:.2f} < {min_recall}")
            return False, f"{msg}, FAILED: {', '.join(issues)}"

    @staticmethod
    def within_range(actual: float, min_val: float, max_val: float) -> Tuple[bool, str]:
        """
        Check that actual value is within [min_val, max_val].
        Returns (is_match, message)
        """
        if min_val <= actual <= max_val:
            return True, f"within_range: {actual} in [{min_val}, {max_val}]"
        else:
            return False, f"within_range: {actual} not in [{min_val}, {max_val}]"


class UnknownCheckTypeError(Exception):
    """Raised when an unknown check type is encountered"""
    pass


def run_comparator(check_type: str, actual: Any, expected: Any, **kwargs) -> Tuple[bool, str]:
    """
    Run a comparator by type name.
    Raises UnknownCheckTypeError for unknown types.
    """
    comparators = {
        'equals': TestComparators.equals,
        'set_equals': TestComparators.set_equals,
        'contains_all': TestComparators.contains_all,
        'must_not_contain': TestComparators.must_not_contain,
        'ordered': TestComparators.ordered,
        'json_path': TestComparators.json_path,
        'line_numbers': TestComparators.line_numbers,
        'precision_recall': TestComparators.precision_recall,
        'within_range': TestComparators.within_range,
    }

    if check_type not in comparators:
        raise UnknownCheckTypeError(f"Unknown check type: {check_type}. "
                                   f"Valid types: {list(comparators.keys())}")

    comparator = comparators[check_type]

    # Special handling for json_path and within_range which need extra args
    if check_type == 'json_path':
        path = kwargs.get('path')
        return comparator(actual, path, expected)
    elif check_type == 'within_range':
        min_val = kwargs.get('min_val', 0)
        max_val = kwargs.get('max_val', float('inf'))
        return comparator(actual, min_val, max_val)
    elif check_type == 'precision_recall':
        min_precision = kwargs.get('min_precision', 0.95)
        min_recall = kwargs.get('min_recall', 0.90)
        return comparator(actual, expected, min_precision, min_recall)
    else:
        return comparator(actual, expected)
