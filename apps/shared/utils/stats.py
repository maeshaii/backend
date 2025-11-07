"""
Statistics utility helpers shared across apps.
Provides safe aggregation helpers that tolerate missing/invalid values
and support related field paths via double-underscore notation.

OPTIMIZED: Uses database aggregation where possible instead of Python loops.
"""

import re

from collections import Counter
from statistics import mean
from django.db.models import Q, Count, Avg, FloatField
from django.db.models.functions import Cast


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
		# Only add non-empty, non-null values
		if obj and str(obj).strip() and str(obj).strip().lower() not in ['nan', 'none', 'null', 'n/a', '']:
			vals.append(str(obj).strip())
	
	if vals:
		result = Counter(vals).most_common(1)[0][0]
		# Ensure we never return "nan"
		return result if result.lower() != 'nan' else "Not Available"
	return "Not Available"


def safe_mean_related(qs, field_path):
	"""Return the mean of values resolved via `field_path`, handling salary ranges properly."""
	vals = []
	for user in qs:
		obj = _resolve_path(user, field_path)
		
		if obj and isinstance(obj, (int, float)):
			vals.append(float(obj))
		elif obj and isinstance(obj, str):
			# Special handling for salary fields
			if 'salary' in field_path.lower():
				converted = convert_salary_range_to_number(obj)
				if converted is not None:
					vals.append(converted)
			else:
				# For non-salary fields, try direct conversion
				v = _coerce_numeric(obj)
				if v is not None:
					vals.append(v)
	
	if vals:
		result = round(mean(vals), 2)
		# Ensure we never return NaN
		return result if not (result != result) else 0  # NaN check: NaN != NaN is True
	return 0


def safe_sample_related(qs, field_path):
	"""Return the first non-empty value resolved via `field_path`, else None."""
	for user in qs:
		obj = _resolve_path(user, field_path)
		if obj and str(obj).strip() and str(obj).strip().lower() not in ['nan', 'none', 'null', 'n/a', '']:
			return str(obj).strip()
	return "Not Available"


def convert_salary_range_to_number(salary_str):
	"""Convert salary range strings to numerical values for averaging."""
	if not salary_str or not isinstance(salary_str, str):
		return None

	salary_str = salary_str.strip().lower()
	if not salary_str:
		return None

	# Remove common currency symbols/labels for easier matching
	mapped = salary_str
	for token in ['php', '₱', 'php:', 'php -', 'php-']:
		mapped = mapped.replace(token, '')
	mapped = mapped.strip()

	# Quick exit for non-disclosed style values
	if any(flag in mapped for flag in ['not disclosed', 'undisclosed', 'n/a', 'na', 'none']):
		return None

	normalized = mapped.replace(',', '')

	# Handle categorical salary ranges with textual cues
	if 'below' in normalized and '5000' in normalized:
		return 2500  # Midpoint of 0-5000
	if '5001' in normalized and '10000' in normalized:
		return 7500  # Midpoint of 5001-10000
	if '10001' in normalized and '20000' in normalized:
		return 15000  # Midpoint of 10001-20000
	if '20001' in normalized and '30000' in normalized:
		return 25000  # Midpoint of 20001-30000
	if 'above' in normalized and '30000' in normalized:
		return 35000  # Conservative estimate for 30000+

	# Extract numeric values (handles ranges like 5001 - 10000)
	matches = re.findall(r'\d+(?:\.\d+)?', normalized)
	if not matches:
		return None

	numbers = [float(val) for val in matches]
	if len(numbers) >= 2:
		return round((numbers[0] + numbers[1]) / 2, 2)
	return round(numbers[0], 2)


