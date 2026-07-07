"""Rating-system experiments over the historical BattleBots match set.

Run: python -m src.pitboss.exp_upgrades
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pitboss.aliases import canon, load as load_aliases
from pitboss.elo import BASE, TEST_SEASON, VAL_SEASONS, load_matches, metrics, p_win

CLEAN = Path("data/clean")
BASELINE_VAL_LL = 0.6502
BASELINE_TEST_LL = 0.6430
BASELINE_TEST_BRIER = 0.2299
SCALE = 173.7178
MU0 = 0.0
PHI0 = 350.0 / SCALE
SIGMA0 = 0.06
EPS = 1e-6


@dataclass(frozen=True)
class Candidate:
    candidate: str
    params: str
    kind: str
    cfg: dict


def load_weapon_classes() -> dict[str, str]:
    table = load_aliases()
    raw = pd.read_csv(CLEAN / "weapon_classes.csv")
    return {canon(r.bot, table): r.weapon_class for r in raw.itertuples()}


def score_elo_like(
    df: pd.DataFrame,
    k: float,
    lam: float = 1.0,
    prov_k: float | None = None,
    class_init: bool = False,
    wclass: dict[str, str] | None = None,
) -> pd.DataFrame:
    ratings: dict[str, float] = {}
    fights: dict[str, int] = defaultdict(int)
    probs = np.empty(len(df))

    def ensure(bot: str) -> float:
        if bot not in ratings:
            rating = BASE
            cls = (wclass or {}).get(bot)
            if class_init and cls and cls != "other":
                peer = [r for b, r in ratings.items() if (wclass or {}).get(b) == cls]
                if peer:
                    rating = sum(peer) / len(peer)
            ratings[bot] = rating
        return ratings[bot]

    for i, row in enumerate(df.itertuples()):
        ra, rb = ensure(row.bot_a), ensure(row.bot_b)
        p = p_win(ra, rb)
        probs[i] = p
        sa = 1.0 if row.winner == row.bot_a else 0.0
        method_mult = lam if row.method == "KO" else 1.0
        ka = (prov_k if prov_k is not None and fights[row.bot_a] < 5 else k) * method_mult
        kb = (prov_k if prov_k is not None and fights[row.bot_b] < 5 else k) * method_mult
        ratings[row.bot_a] = ra + ka * (sa - p)
        ratings[row.bot_b] = rb + kb * ((1.0 - sa) - (1.0 - p))
        fights[row.bot_a] += 1
        fights[row.bot_b] += 1

    out = df.copy()
    out["p_a"] = probs
    return out


def g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def ge(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-g(phi_j) * (mu - mu_j)))


def predict_glicko(mu_a: float, phi_a: float, mu_b: float, phi_b: float) -> float:
    return 1.0 / (1.0 + math.exp(-g(math.hypot(phi_a, phi_b)) * (mu_a - mu_b)))


def sigma_prime(phi: float, sigma: float, delta: float, v: float, tau: float) -> float:
    a = math.log(sigma * sigma)

    def f(x: float) -> float:
        ex = math.exp(x)
        den = 2.0 * (phi * phi + v + ex) ** 2
        return ex * (delta * delta - phi * phi - v - ex) / den - (x - a) / (tau * tau)

    A = a
    if delta * delta > phi * phi + v:
        B = math.log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * tau) < 0.0:
            k += 1
        B = a - k * tau

    fA, fB = f(A), f(B)
    while abs(B - A) > EPS:
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0.0:
            A, fA = B, fB
        else:
            fA /= 2.0
        B, fB = C, fC
    return math.exp(A / 2.0)


def update_glicko(mu: float, phi: float, sigma: float, games: list[tuple[float, float, float]], tau: float) -> tuple[float, float, float]:
    if not games:
        return mu, math.sqrt(phi * phi + sigma * sigma), sigma
    terms = [(g(opp_phi), ge(mu, opp_mu, opp_phi), score) for opp_mu, opp_phi, score in games]
    v = 1.0 / sum(gg * gg * e * (1.0 - e) for gg, e, _ in terms)
    delta = v * sum(gg * (score - e) for gg, e, score in terms)
    sp = sigma_prime(phi, sigma, delta, v, tau)
    phi_star = math.sqrt(phi * phi + sp * sp)
    phi_new = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_new = mu + phi_new * phi_new * sum(gg * (score - e) for gg, e, score in terms)
    return mu_new, phi_new, sp


def score_glicko(df: pd.DataFrame, tau: float) -> pd.DataFrame:
    ratings: dict[str, tuple[float, float, float]] = {}
    probs = np.empty(len(df))
    periods: dict[tuple, list[int]] = {}
    for i, row in enumerate(df.itertuples()):
        key = (row.season, "nan", i) if pd.isna(row.episode) else (row.season, float(row.episode))
        periods.setdefault(key, []).append(i)

    for idxs in periods.values():
        players = set()
        for i in idxs:
            row = df.iloc[i]
            players.update((row.bot_a, row.bot_b))
        for bot in players:
            ratings.setdefault(bot, (MU0, PHI0, SIGMA0))
        start = ratings.copy()
        games: dict[str, list[tuple[float, float, float]]] = defaultdict(list)

        for i in idxs:
            row = df.iloc[i]
            ma, pa, _ = start[row.bot_a]
            mb, pb, _ = start[row.bot_b]
            probs[i] = predict_glicko(ma, pa, mb, pb)
            sa = 1.0 if row.winner == row.bot_a else 0.0
            games[row.bot_a].append((mb, pb, sa))
            games[row.bot_b].append((ma, pa, 1.0 - sa))

        for bot, (mu, phi, sigma) in start.items():
            ratings[bot] = update_glicko(mu, phi, sigma, games.get(bot, []), tau)

    out = df.copy()
    out["p_a"] = probs
    return out


def score_candidate(df: pd.DataFrame, cand: Candidate, wclass: dict[str, str]) -> pd.DataFrame:
    if cand.kind == "glicko":
        return score_glicko(df, cand.cfg["tau"])
    return score_elo_like(df, wclass=wclass, **cand.cfg)


def evaluate(df: pd.DataFrame, cand: Candidate, wclass: dict[str, str], seasons: tuple[int, ...]) -> dict:
    scored = score_candidate(df, cand, wclass)
    m = metrics(scored[scored.season.isin(seasons)])
    return {**m, "candidate": cand.candidate, "params": cand.params, "object": cand}


def table(rows: list[dict]) -> None:
    print("candidate        | params                         | val log_loss | val brier | val acc")
    print("-----------------|--------------------------------|--------------|-----------|--------")
    for r in rows:
        print(f"{r['candidate']:<16} | {r['params']:<30} | {r['log_loss']:.4f}       | {r['brier']:.4f}    | {r['accuracy']:.3f}")


def main() -> None:
    df = load_matches()
    wclass = load_weapon_classes()
    rows: list[dict] = []

    baseline = Candidate("A Elo", "K=80", "elo", {"k": 80.0})
    rows.append(evaluate(df, baseline, wclass, VAL_SEASONS))
    if abs(rows[0]["log_loss"] - BASELINE_VAL_LL) > 0.0002:
        raise AssertionError(f"baseline val log_loss {rows[0]['log_loss']:.4f} != {BASELINE_VAL_LL:.4f}")

    for tau in (0.3, 0.6, 1.0):
        rows.append(evaluate(df, Candidate("B Glicko-2", f"tau={tau}", "glicko", {"tau": tau}), wclass, VAL_SEASONS))

    for k in (48, 64, 80, 96):
        for lam in (1.0, 1.25, 1.5, 2.0):
            rows.append(evaluate(df, Candidate("C MOV-Elo", f"K={k}, lam={lam}", "elo", {"k": float(k), "lam": lam}), wclass, VAL_SEASONS))

    for prov_k in (80, 120, 160):
        for class_init in (False, True):
            label = "on" if class_init else "off"
            cfg = {"k": 80.0, "prov_k": None if prov_k == 80 else float(prov_k), "class_init": class_init}
            rows.append(evaluate(df, Candidate("D Cold-Elo", f"K_prov={prov_k}, class={label}", "elo", cfg), wclass, VAL_SEASONS))

    baseline_row = rows[0]
    best_c = min((r for r in rows if r["candidate"] == "C MOV-Elo"), key=lambda r: r["log_loss"])
    best_d = min((r for r in rows if r["candidate"] == "D Cold-Elo"), key=lambda r: r["log_loss"])
    if best_c["log_loss"] < baseline_row["log_loss"] and best_d["log_loss"] < baseline_row["log_loss"]:
        c_cfg = dict(best_c["object"].cfg)
        d_cfg = best_d["object"].cfg
        c_cfg["prov_k"] = d_cfg.get("prov_k")
        c_cfg["class_init"] = d_cfg.get("class_init", False)
        params = f"{best_c['params']}; {best_d['params']}"
        rows.append(evaluate(df, Candidate("E MOV+Cold", params, "elo", c_cfg), wclass, VAL_SEASONS))

    print(f"{len(df)} matches, validation seasons {VAL_SEASONS}, test season {TEST_SEASON}")
    print()
    table(rows)

    best = min(rows, key=lambda r: r["log_loss"])
    delta = baseline_row["log_loss"] - best["log_loss"]
    winner = best if delta > 0.003 else baseline_row
    if winner is baseline_row:
        print(f"\nWinner by val: A Elo K=80; no candidate beat baseline by >0.003 (best delta {delta:.4f}).")
    else:
        print(f"\nWinner by val: {winner['candidate']} {winner['params']} (delta {delta:.4f}).")

    test = evaluate(df, winner["object"], wclass, (TEST_SEASON,))
    print(f"\nHeld-out season {TEST_SEASON}:")
    print(f"  baseline(spec): log_loss={BASELINE_TEST_LL:.4f} brier={BASELINE_TEST_BRIER:.4f} acc=not-provided")
    print(
        f"  winner: {winner['candidate']} {winner['params']} "
        f"log_loss={test['log_loss']:.4f} brier={test['brier']:.4f} acc={test['accuracy']:.3f} n={test['n']}"
    )

    cold_tweaks = [
        r for r in rows
        if r["candidate"] == "D Cold-Elo" and r["params"] != "K_prov=80, class=off"
    ]
    cold_best = min(cold_tweaks, key=lambda r: r["log_loss"])
    cold_note = ""
    if abs(cold_best["log_loss"] - baseline_row["log_loss"]) <= 0.003:
        cold_note = f" (NEUTRAL-ADOPTABLE cold-start: {cold_best['params']}, val ll={cold_best['log_loss']:.4f})"

    if test["log_loss"] < BASELINE_TEST_LL - 0.010 and test["brier"] <= BASELINE_TEST_BRIER:
        print(f"ADOPT {winner['candidate']} {winner['params']}")
    else:
        print(f"KEEP ELO K=80{cold_note}")


if __name__ == "__main__":
    main()
