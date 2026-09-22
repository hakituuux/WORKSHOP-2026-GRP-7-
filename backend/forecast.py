# prevision de sechage du sol (regression lineaire basique)
# idee : depuis le dernier arrosage, on fit humidite = pente * temps + b
# et on estime quand ca va passer sous le seuil

from collections import deque
from statistics import StatisticsError, linear_regression

MIN_POINTS = 10  # en dessous c'est trop flou, on attend


class Forecaster:
    def __init__(self, window: int, threshold: float = 35.0):
        # fenetre glissante de samples (ts, humidite %)
        self.samples: deque[tuple[float, float]] = deque(maxlen=window)
        self.threshold = threshold

    def reset(self) -> None:
        # appele quand la pompe tourne : nouvelle courbe de sechage
        self.samples.clear()

    def add(self, ts: float, moisture: float) -> dict | None:
        # ajoute un point et tente une pred
        self.samples.append((ts, moisture))
        return self.predict()

    def predict(self) -> dict | None:
        # calcule pente + temps restant avant seuil (ou None si ca seche pas)
        if len(self.samples) < MIN_POINTS:
            return None

        t0 = self.samples[0][0]
        hours = [(t - t0) / 3600 for t, _ in self.samples]
        moisture = [m for _, m in self.samples]
        try:
            slope, intercept = linear_regression(hours, moisture)
        except StatisticsError:
            # toutes les mesures pile au meme instant -> nope
            return None

        current = slope * hours[-1] + intercept
        if slope >= 0:
            remaining = None  # ca monte / stagne (genre apres arrosage)
        else:
            remaining = max(0.0, (self.threshold - current) / slope)

        return {
            "slope_pct_per_h": round(slope, 2),
            "hours_to_threshold": None if remaining is None else round(remaining, 1),
            "threshold": self.threshold,
            "points": len(self.samples),
        }
