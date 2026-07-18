"""Unified cost-line model.

Every project cost — built-in, custom, or a sub-line of another field — is a
:class:`CostLine` carrying an ``amount`` plus a :class:`CalcType` that says how
that amount becomes a contribution to the project total:

    FIXED       amount is the total for the whole project (one-time)
    PER_TIRAJ   amount is per printed copy        → amount × tiraj
    PER_FORM    amount is per print form          → amount × total_forms
    PER_VOLUME  amount is per volume of the book  → amount × volume_count

For a single-volume project ``volume_count == 1`` so PER_VOLUME collapses to a
one-off amount. ``total_forms`` is the sum of every print form across all
volumes (text + cover), so PER_FORM costs scale with the real press work.

This module is pure (no Qt, no DB) and is the single source of truth for how a
list of cost lines resolves to a number.
"""

from dataclasses import dataclass, field
from enum import Enum


class CalcType(str, Enum):
    FIXED = 'fixed'
    PER_TIRAJ = 'per_tiraj'
    PER_FORM = 'per_form'
    PER_VOLUME = 'per_volume'

    @classmethod
    def coerce(cls, value, default=None):
        """Lenient parse: accepts a CalcType, its value, or None."""
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except (ValueError, KeyError):
            return default or cls.FIXED


# Persian labels for the calculation-type combo (order = combo order)
CALC_TYPE_LABELS = {
    CalcType.FIXED: 'ثابت (کل پروژه)',
    CalcType.PER_TIRAJ: 'به ازای هر جلد (× تیراژ)',
    CalcType.PER_FORM: 'به ازای هر فرم چاپی',
    CalcType.PER_VOLUME: 'به ازای هر جلد از سری',
}
CALC_TYPE_ORDER = [CalcType.FIXED, CalcType.PER_TIRAJ, CalcType.PER_FORM, CalcType.PER_VOLUME]

# One-line hint shown under the combo
CALC_TYPE_HINTS = {
    CalcType.FIXED: 'این مبلغ، هزینه کل و یک‌باره است.',
    CalcType.PER_TIRAJ: 'این مبلغ برای هر نسخه است و در تیراژ ضرب می‌شود.',
    CalcType.PER_FORM: 'این مبلغ برای هر فرم چاپی است و در تعداد کل فرم‌ها ضرب می‌شود.',
    CalcType.PER_VOLUME: 'این مبلغ برای هر جلد از سری است و در تعداد جلدها ضرب می‌شود.',
}


@dataclass
class CostContext:
    """Runtime numbers a project's cost lines resolve against."""
    tiraj: int = 0
    total_forms: int = 0      # sum of all print forms across all volumes
    volume_count: int = 1


@dataclass
class CostLine:
    key: str                       # stable id (built-in field key or custom uid)
    display_name: str
    amount: float = 0.0
    calc_type: CalcType = CalcType.FIXED
    parent_key: str | None = None  # set for a sub-line of another field
    is_custom: bool = False
    order: int = 0

    def resolve(self, ctx: CostContext) -> float:
        return resolve_amount(self.amount, self.calc_type, ctx)


def resolve_amount(amount: float, calc_type, ctx: CostContext) -> float:
    """The total contribution of a single amount under a calculation type."""
    ct = CalcType.coerce(calc_type)
    amount = amount or 0.0
    if ct is CalcType.PER_TIRAJ:
        return amount * max(0, ctx.tiraj)
    if ct is CalcType.PER_FORM:
        return amount * max(0, ctx.total_forms)
    if ct is CalcType.PER_VOLUME:
        return amount * max(1, ctx.volume_count)
    return amount  # FIXED


def resolve_total(lines, ctx: CostContext) -> float:
    """Sum of every line's resolved contribution (sub-lines included — they are
    ordinary lines that merely carry a ``parent_key``)."""
    return sum(line.resolve(ctx) for line in lines)


def resolved_breakdown(lines, ctx: CostContext) -> dict:
    """{display_name: resolved_total} for charting/reporting, top-level lines
    and sub-lines rolled into their own entries."""
    out = {}
    for line in lines:
        out[line.display_name] = out.get(line.display_name, 0.0) + line.resolve(ctx)
    return out
