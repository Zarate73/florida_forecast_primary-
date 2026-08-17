"""
Backtest 2018/2022: corre la MISMA metodología nuclear de los pipelines
vigentes (ponderación por encuestas con time-decay half_life=14,
ensamble Bayesiano conjugado-normal, árbol Beta/Dirichlet moment-matched)
sobre encuestas REALES de primarias de gobernador de Florida ya
resueltas, y compara el pronóstico contra el resultado real conocido.

QUÉ SÍ REPLICA (idéntico a los pipelines 2026):
  - extract_end_date(): mismo parser de fechas.
  - Poll_Weight = Sample * exp(-ln(2)/half_life * Days_Since_Poll),
    half_life=14 (el MISMO valor, sin recalibrar con datos históricos --
    recalibrarlo aquí sería sobreajustar el hiperparámetro a la
    respuesta que ya conocemos).
  - weighted_average() / poll_dispersion(): idénticas.
  - bayesian_update(): idéntica (Normal-Normal conjugada, precisión
    inversa).
  - Árbol Beta/Dirichlet moment-matched: Nivel 0 (Undecided vs Decided,
    Beta) + Nivel 1 (reparto DENTRO de Decided vía Dirichlet moment-
    matched, kappa = mediana de las kappas implícitas por candidato --
    mismo criterio que "kappa_within" en ambos pipelines 2026).

QUÉ NO REPLICA (y por qué):
  - House effects por encuestadora: no hay house effects documentados
    para pollsters de 2018/2022 en este proyecto -- inventarlos ahora,
    sabiendo el resultado, sería lookahead bias. Se corre SIN ajuste de
    house effects (equivalente a use_house_effects=False).
  - Early vote / turnout day-by-day: los pipelines 2026 dividen el
    pronóstico en "ya votado temprano" + "falta por votar" usando datos
    de early vote 2026 que no existen para 2018/2022 con el mismo
    detalle. El backtest pronostica el voto TOTAL final directamente
    desde encuestas, sin ese quiebre -- una simplificación real, no un
    intento de replicar 1:1 esa celda.
  - Prior subjetivo/fundamentales: para 2026-REP el prior es un juicio
    subjetivo declarado ANTES de ver el resultado. Aquí no existe ese
    juicio histórico documentado, y construirlo ahora (conociendo Gillum
    2018, Crist 2022...) sería la forma más directa de lookahead bias
    posible. Se usa el MISMO prior NEUTRO que ya usa el modelo DEM 2026
    (centrado en el propio promedio de encuestas, NEUTRAL_PRIOR_STD=0.30
    -- un prior 30 puntos de ancho es, en la práctica, casi un no-op:
    dejar que domine el dato es la decisión correcta cuando no hay un
    prior verdaderamente independiente del resultado).
  - Reparto de indecisos: los pipelines 2026 usan una fracción de
    reparto declarada a mano (juicio del analista) o escenarios
    explícitos. Aquí, para no inyectar un supuesto ad-hoc calibrado
    post-hoc, los indecisos se reparten PROPORCIONALMENTE a la
    composición ya estimada del bloque decidido (supuesto neutro
    estándar en forecasting electoral cuando no hay encuesta de
    "leaners").

LÍMITE DE FONDO (léase antes de interpretar los resultados): esto son
n=3 elecciones. Ninguna cantidad de encuestas DENTRO de cada carrera
mejora ese n=3 -- un backtest con n=3 no calibra el modelo (no se puede
estimar, por ejemplo, si el 90% de los intervalos de confianza
efectivamente cubren el resultado real 90% de las veces con solo 3
observaciones). Lo que SÍ permite es una prueba de sanidad direccional:
¿el modelo, corrido de forma honesta con datos conocidos únicamente
ANTES del día de la elección, habría señalado como más probable al
candidato que efectivamente ganó? ¿Qué tan lejos quedó el punto
estimado del resultado real?
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
HALF_LIFE = 14
DECAY_RATE = np.log(2) / HALF_LIFE
NEUTRAL_PRIOR_STD = 0.30   # mismo valor que subjective_priors_dem (v8) para candidatos sin prior propio
MIN_POLL_STD = 8.0         # mismo criterio que JOSEPH_MIN_POLL_STD (v8): piso cuando n<=1 encuesta
N_SIMULATIONS = 10_000
SEED = 42


def extract_end_date(date_str):
    """Copia exacta del parser usado en ambos pipelines 2026."""
    if pd.isna(date_str):
        return pd.NaT
    s = str(date_str)
    s = re.sub(r'\[\d+\]', '', s)
    s = re.sub(r'\bthrough\b', '-', s, flags=re.IGNORECASE).strip()
    year_match = re.search(r'(\d{4})', s)
    if not year_match:
        return pd.NaT
    year = year_match.group(1)
    pieces = re.split(r'\s*[-–—]\s*', s)
    last_piece = pieces[-1]
    month_pat = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2})'
    m = re.search(month_pat, last_piece)
    if m:
        mon, day = m.group(1), m.group(2)
    else:
        day_match = re.search(r'(\d{1,2})', last_piece)
        mon_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', s)
        if not (day_match and mon_match):
            return pd.NaT
        mon, day = mon_match.group(1), day_match.group(1)
    try:
        return pd.to_datetime(f"{mon} {day} {year}", format='%b %d %Y')
    except ValueError:
        return pd.NaT


def weighted_average(df, value_col, weight_col):
    subset = df.dropna(subset=[value_col, weight_col])
    if subset.empty:
        return np.nan
    return np.average(subset[value_col], weights=subset[weight_col])


def poll_dispersion(df, value_col, weight_col, mean_val_pct):
    subset = df.dropna(subset=[value_col, weight_col])
    if subset.empty:
        return np.nan
    variance = np.average((subset[value_col] - mean_val_pct) ** 2, weights=subset[weight_col])
    return np.sqrt(variance)


def bayesian_update(prior_mean, prior_std, data_mean, data_std):
    prior_precision = 1.0 / (prior_std ** 2)
    data_precision = 1.0 / (data_std ** 2)
    posterior_precision = prior_precision + data_precision
    posterior_mean = ((prior_mean * prior_precision) + (data_mean * data_precision)) / posterior_precision
    posterior_std = np.sqrt(1.0 / posterior_precision)
    return posterior_mean, posterior_std


class RaceConfig:
    def __init__(self, name, sheet, election_date, candidates, other_col, actual_shares, min_cutoff):
        self.name = name
        self.sheet = sheet
        self.election_date = pd.Timestamp(election_date)
        self.candidates = candidates          # lista de columnas de candidatos individuales
        self.other_col = other_col            # nombre de la columna "Other" (agregado)
        self.actual_shares = actual_shares    # dict candidato/Other -> fracción real de voto (0-1)
        self.min_cutoff = pd.Timestamp(min_cutoff)


RACES = [
    RaceConfig(
        name="REP 2018 (DeSantis vs. Putnam)",
        sheet="REP_2018",
        election_date="2018-08-28",
        candidates=["DeSantis", "Putnam"],
        other_col="Other",
        actual_shares={"DeSantis": 0.564875, "Putnam": 0.365273, "Other": 1 - 0.564875 - 0.365273},
        min_cutoff="2018-06-01",
    ),
    RaceConfig(
        name="DEM 2018 (Gillum/Graham/Levine/Greene/King)",
        sheet="DEM_2018",
        election_date="2018-08-28",
        candidates=["Gillum", "Graham", "Levine", "Greene", "King"],
        other_col="Other",
        actual_shares={
            "Gillum": 0.343644, "Graham": 0.312522, "Levine": 0.203226,
            "Greene": 0.100662, "King": 0.024756,
            "Other": 1 - (0.343644 + 0.312522 + 0.203226 + 0.100662 + 0.024756),
        },
        min_cutoff="2018-06-01",
    ),
    RaceConfig(
        name="DEM 2022 (Crist vs. Fried)",
        sheet="DEM_2022",
        election_date="2022-08-23",
        candidates=["Crist", "Fried"],
        other_col="Other",
        actual_shares={"Crist": 0.597050, "Fried": 0.353455, "Other": 1 - 0.597050 - 0.353455},
        min_cutoff="2022-06-01",
    ),
]


def run_backtest(cfg, n_simulations=N_SIMULATIONS, seed=SEED, verbose=True):
    polls = pd.read_excel(DATA_DIR / "Historical_Polls_2018_2022.xlsx", sheet_name=cfg.sheet)
    polls["End_Date"] = polls["Date"].apply(extract_end_date)
    n_total = len(polls)
    polls = polls[polls["End_Date"].notna()].copy()
    n_dropped_unparsed = n_total - len(polls)
    polls = polls[polls["End_Date"] >= cfg.min_cutoff].copy()

    polls["Sample_Imputed"] = polls["Sample"].isna()
    polls["Sample"] = pd.to_numeric(polls["Sample"], errors="coerce").fillna(500)
    polls["Days_Since_Poll"] = (cfg.election_date - polls["End_Date"]).dt.days
    assert (polls["Days_Since_Poll"] >= 0).all(), "Encuesta posterior al día de la elección -- revisar."
    polls["Poll_Weight"] = polls["Sample"] * np.exp(-DECAY_RATE * polls["Days_Since_Poll"])

    all_cols = cfg.candidates + [cfg.other_col]
    n_polls_by_cand = {c: polls[c].notna().sum() for c in all_cols}

    posteriors = {}
    for c in all_cols:
        mean_pct = weighted_average(polls, c, "Poll_Weight")
        std_pct = poll_dispersion(polls, c, "Poll_Weight", mean_pct)
        n_c = n_polls_by_cand[c]
        if n_c <= 1 or not np.isfinite(std_pct) or std_pct <= 0:
            std_pct = max(std_pct if np.isfinite(std_pct) else 0.0, MIN_POLL_STD)
        data_mean, data_std = mean_pct / 100.0, std_pct / 100.0
        post_mean, post_std = bayesian_update(data_mean, NEUTRAL_PRIOR_STD, data_mean, data_std)
        posteriors[c] = {"mean": post_mean, "std": post_std, "n_polls": int(n_c), "raw_avg_pct": mean_pct}

    undecided_avg = weighted_average(polls, "Undecided", "Poll_Weight") / 100.0
    undecided_std = poll_dispersion(polls, "Undecided", "Poll_Weight", undecided_avg * 100) / 100.0
    if not np.isfinite(undecided_std) or undecided_std <= 0:
        undecided_std = max(undecided_std if np.isfinite(undecided_std) else 0.0, MIN_POLL_STD) / 100.0

    # --- Nivel 0: Undecided vs Decided (Beta moment-matched) ---
    kappa_ud = max(undecided_avg * (1 - undecided_avg) / (undecided_std ** 2) - 1, 1.0)
    alpha_ud, beta_ud = undecided_avg * kappa_ud, (1 - undecided_avg) * kappa_ud

    # --- Nivel 1: reparto dentro de Decided (Dirichlet moment-matched) ---
    pool_mean = sum(posteriors[c]["mean"] for c in all_cols)
    means_raw = np.array([posteriors[c]["mean"] for c in all_cols]) / pool_mean
    stds_raw = np.array([posteriors[c]["std"] for c in all_cols]) / pool_mean
    within_kappas = (means_raw * (1 - means_raw)) / (stds_raw ** 2) - 1
    kappa_within = max(np.median(within_kappas), 1.0)
    within_alphas = np.clip(means_raw * kappa_within, 1e-3, None)

    rng = np.random.default_rng(seed)
    S_undecided = rng.beta(alpha_ud, beta_ud, size=n_simulations)
    S_decided = 1.0 - S_undecided
    simulated_within = rng.dirichlet(within_alphas, size=n_simulations)

    sim = pd.DataFrame(index=range(n_simulations), columns=all_cols, dtype=float)
    for i, c in enumerate(all_cols):
        decided_share = S_decided * simulated_within[:, i]
        # Indecisos repartidos proporcional a la composición YA decidida
        # de esta misma simulación (supuesto neutro, no calibrado post-hoc).
        undecided_share = S_undecided * simulated_within[:, i]
        sim[c] = decided_share + undecided_share

    winner_pool = cfg.candidates  # "Other" no compite (mismo criterio que winner_pool en los pipelines 2026)
    sim["Winner"] = sim[winner_pool].idxmax(axis=1)

    actual_winner = max(cfg.actual_shares, key=cfg.actual_shares.get)
    win_probs = {c: float((sim["Winner"] == c).mean()) for c in winner_pool}

    results_rows = []
    for c in all_cols:
        pred_median = float(sim[c].median())
        pred_p05, pred_p95 = float(sim[c].quantile(0.05)), float(sim[c].quantile(0.95))
        actual = cfg.actual_shares[c]
        results_rows.append({
            "Candidato": c,
            "Encuestas_usadas": posteriors[c]["n_polls"],
            "Promedio_crudo_%": posteriors[c]["raw_avg_pct"],
            "Pronostico_mediana_%": pred_median * 100,
            "Pronostico_P05_%": pred_p05 * 100,
            "Pronostico_P95_%": pred_p95 * 100,
            "Resultado_real_%": actual * 100,
            "Error_abs_pts": abs(pred_median * 100 - actual * 100),
            "Dentro_P05_P95": bool(pred_p05 <= actual <= pred_p95),
            "P(gana)_%": win_probs.get(c, np.nan) * 100 if c in win_probs else np.nan,
        })
    results_df = pd.DataFrame(results_rows)

    mae = results_df.loc[results_df["Candidato"] != cfg.other_col, "Error_abs_pts"].mean()
    coverage = results_df["Dentro_P05_P95"].mean()

    summary = {
        "race": cfg.name,
        "n_polls_used": len(polls),
        "n_polls_dropped_unparsed": n_dropped_unparsed,
        "date_range": (polls["End_Date"].min(), polls["End_Date"].max()),
        "actual_winner": actual_winner,
        "predicted_winner_prob_pct": win_probs.get(actual_winner, np.nan) * 100,
        "predicted_top_pick": max(win_probs, key=win_probs.get),
        "correct_call": max(win_probs, key=win_probs.get) == actual_winner,
        "mae_pts": mae,
        "coverage_90pct_interval": coverage,
        "kappa_within": kappa_within,
        "kappa_undecided": kappa_ud,
        "results_table": results_df,
    }

    if verbose:
        print("=" * 78)
        print(cfg.name)
        print("=" * 78)
        print(f"Encuestas usadas: {summary['n_polls_used']} "
              f"(descartadas por fecha imprecisa: {n_dropped_unparsed}) | "
              f"rango: {summary['date_range'][0].date()} -> {summary['date_range'][1].date()}")
        print(results_df.to_string(index=False, float_format=lambda x: f"{x:6.2f}"))
        print(f"\nGanador real: {actual_winner} | "
              f"Candidato con mayor P(gana) del modelo: {summary['predicted_top_pick']} | "
              f"P(gana) asignada al ganador real: {summary['predicted_winner_prob_pct']:.1f}% | "
              f"¿Acertó el pronóstico direccional?: {'SÍ' if summary['correct_call'] else 'NO'}")
        print(f"MAE (candidatos individualizados, pts porcentuales): {mae:.2f}")
        print(f"Cobertura del intervalo 90% (P05-P95) sobre el resultado real: {coverage*100:.0f}% "
              f"de las categorías (n={len(results_df)}, NO interpretar como calibración -- ver docstring)")
        print()

    return summary


if __name__ == "__main__":
    all_summaries = [run_backtest(cfg) for cfg in RACES]

    print("=" * 78)
    print("RESUMEN AGREGADO (n=3 elecciones -- ver limitaciones en docstring)")
    print("=" * 78)
    agg = pd.DataFrame([{
        "Carrera": s["race"],
        "Encuestas": s["n_polls_used"],
        "Ganador real": s["actual_winner"],
        "Pronóstico top-pick": s["predicted_top_pick"],
        "¿Acertó?": "SÍ" if s["correct_call"] else "NO",
        "P(gana) al ganador real, %": round(s["predicted_winner_prob_pct"], 1),
        "MAE, pts": round(s["mae_pts"], 2),
    } for s in all_summaries])
    print(agg.to_string(index=False))
    n_correct = sum(s["correct_call"] for s in all_summaries)
    mean_mae = np.mean([s["mae_pts"] for s in all_summaries])
    print(f"\nAciertos direccionales: {n_correct}/3 | MAE promedio entre las 3 carreras: {mean_mae:.2f} pts")
