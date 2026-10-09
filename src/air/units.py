"""Explicit exact unit conversions for AIR-Expr 0.2; no calendar or FX assumptions."""
from decimal import Decimal

VERSION = 'air.units/1'
# Dimension and exact multiplier to the dimension's base unit.
UNITS = {
    's': ('elapsed_time', '1'), 'ms': ('elapsed_time', '0.001'),
    'us': ('elapsed_time', '0.000001'), 'min': ('elapsed_time', '60'),
    'h': ('elapsed_time', '3600'), 'day': ('elapsed_time', '86400'),
    'm': ('length', '1'), 'mm': ('length', '0.001'), 'cm': ('length', '0.01'),
    'km': ('length', '1000'), 'kg': ('mass', '1'), 'g': ('mass', '0.001'),
    'B': ('information', '1'), 'kB': ('information', '1000'), 'MB': ('information', '1000000'),
    'KiB': ('information', '1024'), 'MiB': ('information', '1048576'),
    'FTE': ('staffing_ratio', '1'), 'person_day': ('work_effort', '1'),
    'count': ('count', '1'), 'requests': ('requests', '1'),
}


def dimension(unit):
    if unit not in UNITS: raise ValueError('Unit is not in ' + VERSION + ': ' + unit)
    return UNITS[unit][0]


def compatible(source, target):
    return dimension(source) == dimension(target)


def convert(value, source, target):
    if not compatible(source, target): raise ValueError('Incompatible unit dimensions')
    return value * Decimal(UNITS[source][1]) / Decimal(UNITS[target][1])
