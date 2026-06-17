import math


def compute_cover_price(cost_per_book: float, multiplier: float) -> float:
    return cost_per_book * multiplier


def compute_net_revenue_per_copy(cover_price: float, distribution_pct: float,
                                  author_royalty_pct: float) -> float:
    distribution_cost = cover_price * distribution_pct / 100.0
    royalty_cost = cover_price * author_royalty_pct / 100.0
    return cover_price - distribution_cost - royalty_cost


def compute_break_even(total_cost: float, net_revenue_per_copy: float) -> int:
    # Returns 0 for both "breaks even at 0 copies" (total_cost=0) and
    # "never breaks even" (net_revenue_per_copy<=0). Callers should check
    # net_revenue_per_copy > 0 before interpreting a 0 return as meaningful.
    if net_revenue_per_copy <= 0:
        return 0
    return math.ceil(total_cost / net_revenue_per_copy)


def compute_breakdown_pcts(cover_price: float, cost_per_book: float,
                            distribution_pct: float, author_royalty_pct: float) -> dict:
    if cover_price <= 0:
        return {k: 0.0 for k in ['production_pct', 'distribution_pct', 'royalty_pct',
                                   'publisher_pct', 'production', 'distribution',
                                   'royalty', 'publisher']}
    production_pct = round(cost_per_book / cover_price * 100, 2)
    publisher_pct = max(0.0, round(100.0 - production_pct - distribution_pct - author_royalty_pct, 2))
    return {
        'production_pct':    production_pct,
        'distribution_pct':  distribution_pct,
        'royalty_pct':       author_royalty_pct,
        'publisher_pct':     publisher_pct,
        'production':        cost_per_book,
        'distribution':      cover_price * distribution_pct / 100.0,
        'royalty':           cover_price * author_royalty_pct / 100.0,
        'publisher':         cover_price * publisher_pct / 100.0,
    }


def compute_scenarios(total_cost: float, cost_per_book: float, tiraj: int,
                       distribution_pct: float, author_royalty_pct: float,
                       multipliers: list) -> list:
    rows = []
    for pct in [0.25, 0.5, 0.75, 1.0]:
        sales = max(1, int(tiraj * pct))
        for mult in multipliers:
            cover = compute_cover_price(cost_per_book, mult)
            net_per = compute_net_revenue_per_copy(cover, distribution_pct, author_royalty_pct)
            profit = net_per * sales - total_cost
            rows.append({'multiplier': mult, 'sales_qty': sales, 'net_profit': profit})
    return rows
