"""Prevision du sechage du sol par regression lineaire.

On garde les mesures d'humidite depuis le dernier arrosage, on ajuste une droite
humidite = pente x temps + origine, et on en deduit dans combien d'heures la
droite passera sous le seuil d'arrosage.
"""

from collections import deque
from statistics import StatisticsError, linear_regression

MIN_POINTS = 10  # en dessous, la pente n'est pas fiable


class Forecaster:
    def __init__(self, window: int, threshold: float = 35.0):
        self.samples: deque[tuple[float, float]] = deque(maxlen=window)  # (timestamp, humidite %)
        self.threshold = threshold

    def reset(self) -> None:
        """Appele a chaque arrosage : la courbe de sechage repart de zero."""
        self.samples.clear()

    def add(self, ts: float, moisture: float) -> dict | None:
        self.samples.append((ts, moisture))
        return self.predict()

    def predict(self) -> dict | None:
        if len(self.samples) < MIN_POINTS:
            return None

        t0 = self.samples[0][0]
        hours = [(t - t0) / 3600 for t, _ in self.samples]
        moisture = [m for _, m in self.samples]
        try:
            slope, intercept = linear_regression(hours, moisture)
        except StatisticsError:  # toutes les mesures au meme instant
            return None

        current = slope * hours[-1] + intercept
        if slope >= 0:
            remaining = None  # le sol ne seche pas (ou vient d'etre arrose)
        else:
            remaining = max(0.0, (self.threshold - current) / slope)

        return {
            "slope_pct_per_h": round(slope, 2),
            "hours_to_threshold": None if remaining is None else round(remaining, 1),
            "threshold": self.threshold,
            "points": len(self.samples),
        }
