"""
Statistics utility helpers shared across apps.
Provides safe aggregation helpers that tolerate missing/invalid values
and support related field paths via double-underscore notation.
"""

from collections import Counter
from statistics import mean


def safe_mode(qs, field):
	"""Return the most common non-empty value for attribute `field` in an iterable of objects."""
	vals = [getattr(a, field) for a in qs if getattr(a, field)]
	return Counter(vals).most_common(1)[0][0] if vals else None


def _coerce_numeric(value):
	if value is None:
		return None
	if isinstance(value, (int, float)):
		return float(value)
	if isinstance(value, str):
		try:
			return float(value.replace(',', '').replace(' ', ''))
		except Exception:
			return None
	return None


def safe_mean(qs, field):
	"""Return the mean of numeric values for attribute `field`, coercing strings when possible."""
	vals = []
	for a in qs:
		v = _coerce_numeric(getattr(a, field))
		if v is not None:
			vals.append(v)
	return round(mean(vals), 2) if vals else None


def safe_sample(qs, field):
	"""Return the first non-empty value for attribute `field`, else None."""
	for a in qs:
		v = getattr(a, field)
		if v:
			return v
	return None


def _resolve_path(obj, field_path):
	parts = field_path.split('__')
	cur = obj
	for part in parts:
		cur = getattr(cur, part, None)
		if cur is None:
			break
	return cur


def safe_mode_related(qs, field_path):
	"""Return the most common non-empty value resolved via a double-underscore `field_path`."""
	vals = []
	for user in qs:
		obj = _resolve_path(user, field_path)
		if obj:
			vals.append(obj)
	return Counter(vals).most_common(1)[0][0] if vals else None


def safe_mean_related(qs, field_path):
	"""Return the mean of values resolved via `field_path`, coercing strings when possible."""
	vals = []
	for user in qs:
		obj = _resolve_path(user, field_path)
		v = _coerce_numeric(obj)
		if v is not None:
			vals.append(v)
	return round(mean(vals), 2) if vals else None


def safe_sample_related(qs, field_path):
	"""Return the first non-empty value resolved via `field_path`, else None."""
	for user in qs:
		obj = _resolve_path(user, field_path)
		if obj:
			return obj
	return None


