// Dashboard BiOrbite : télémétrie, embeds Grafana (si configurés), repli Chart.js, commandes.

const STATUS_PERIOD_MS = 2000;
const HISTORY_PERIOD_MS = 30000;
const STALE_AFTER_S = 30;

const $ = (id) => document.getElementById(id);

function setText(id, text, cls = "") {
  const el = $(id);
  el.textContent = text;
  el.className = el.className.replace(/\b(ok|warn|bad)\b/g, "").trim();
  if (cls) el.classList.add(cls);
}

function formatTime(ts, withDate = false) {
  const d = new Date(ts * 1000);
  const opts = withDate
    ? { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }
    : { hour: "2-digit", minute: "2-digit", second: "2-digit" };
  return d.toLocaleString("fr-FR", opts);
}

const STATE_CLASS = { NORMAL: "ok", AUTONOME: "warn", PENURIE: "bad", ERREUR: "bad" };

async function refreshStatus() {
  let data;
  try {
    data = await (await fetch("/api/status")).json();
  } catch {
    setText("conn", "Backend injoignable", "bad");
    return;
  }

  const t = data.topics;
  const v = (topic) => t[topic]?.value;
  const age = (topic) => (t[topic] ? data.now - t[topic].ts : Infinity);

  if (!data.broker_connected) setText("conn", "Broker déconnecté", "bad");
  else if (v("status") !== "online") setText("conn", "Module hors ligne", "bad");
  else if (age("soil") > STALE_AFTER_S) setText("conn", "Module muet", "warn");
  else setText("conn", "Module en ligne", "ok");

  const state = v("state");
  if (state) {
    setText("state", state.state, STATE_CLASS[state.state]);
    setText("state-sub", `uptime ${Math.round(state.uptime_s / 60)} min`);
    setText("tank", state.tank_ok ? "OK" : "Vide", state.tank_ok ? "ok" : "bad");
    fillSettingIfEmpty("soil_min", state.soil_min);
  }

  const soil = v("soil");
  if (soil) {
    setText("soil", soil.valid ? `${soil.moisture} %` : "Capteur ?", soil.valid ? "" : "bad");
    setText("soil-sub", `brut ${soil.raw}${state ? ` · seuil ${state.soil_min} %` : ""}`);
  }

  const temp = v("temp");
  if (temp) setText("temp", temp.celsius === null ? "—" : `${temp.celsius}`);

  const humidity = v("humidity");
  if (humidity && humidity.percent != null) setText("humidity", `${humidity.percent}`);

  const lightSensor = v("light");
  if (lightSensor && lightSensor.lux != null) setText("lux", `${Math.round(lightSensor.lux)}`);

  const pump = v("pump/state");
  if (pump) setText("pump", pump.on ? "En marche" : "Arrêt", pump.on ? "ok" : "");

  const light = v("light/state");
  if (light) {
    setText("light", light.on ? "Allumé" : "Éteint");
    setText("light-sub", light.mode === "manual" ? "mode manuel" : "planning auto");
  }

  const fc = v("forecast");
  if (fc) {
    if (fc.hours_to_threshold === null) setText("forecast", "Stable");
    else if (fc.hours_to_threshold === 0) setText("forecast", "Imminent", "warn");
    else setText("forecast", `≈ ${fc.hours_to_threshold} h`);
    setText("forecast-sub", `${fc.slope_pct_per_h} %/h · ${fc.points} pts`);
  }
}

function fillSettingIfEmpty(name, value) {
  const input = document.querySelector(`#settings [name="${name}"]`);
  if (input && input.value === "" && document.activeElement !== input) input.value = value;
}

// ---------- Grafana embeds / Chart.js local ----------

const css = getComputedStyle(document.documentElement);
const color = (name) => css.getPropertyValue(name).trim();

function lineDataset(label, colorVar, yAxisID) {
  return {
    label,
    data: [],
    borderColor: color(colorVar),
    backgroundColor: color(colorVar),
    yAxisID,
  };
}

const chartDefaults = {
  maintainAspectRatio: false,
  animation: false,
  parsing: false,
  elements: { point: { radius: 0 }, line: { borderWidth: 2, tension: 0.2 } },
  interaction: { mode: "nearest", axis: "x", intersect: false },
  plugins: {
    legend: { labels: { color: color("--ink"), boxWidth: 12 } },
    tooltip: { callbacks: { title: (items) => formatTime(items[0].parsed.x, true) } },
  },
};

const chartSoil = new Chart($("chart-soil"), {
  type: "line",
  data: {
    datasets: [
      lineDataset("Sol (%)", "--soil", "ySoil"),
      lineDataset("Air (%)", "--humidity", "ySoil"),
    ],
  },
  options: {
    ...chartDefaults,
    scales: {
      x: {
        type: "linear",
        ticks: {
          color: color("--muted"),
          maxTicksLimit: 8,
          callback: (ts) => formatTime(ts, Number($("hours").value) > 24),
        },
        grid: { color: color("--line") },
      },
      ySoil: {
        position: "left",
        min: 0,
        max: 100,
        ticks: { color: color("--soil") },
        grid: { color: color("--line") },
      },
    },
  },
});

const chartClimate = new Chart($("chart-climate"), {
  type: "line",
  data: {
    datasets: [
      lineDataset("Temp (°C)", "--temp", "yTemp"),
      lineDataset("Lux", "--lux", "yLux"),
    ],
  },
  options: {
    ...chartDefaults,
    scales: {
      x: {
        type: "linear",
        ticks: {
          color: color("--muted"),
          maxTicksLimit: 8,
          callback: (ts) => formatTime(ts, Number($("hours").value) > 24),
        },
        grid: { color: color("--line") },
      },
      yTemp: {
        position: "left",
        ticks: { color: color("--temp") },
        grid: { color: color("--line") },
      },
      yLux: {
        position: "right",
        ticks: { color: color("--lux") },
        grid: { drawOnChartArea: false },
      },
    },
  },
});

async function refreshHistory() {
  const hours = $("hours").value;
  try {
    const [soil, humidity, temp, lux] = await Promise.all(
      ["soil", "humidity", "temp", "lux"].map((m) =>
        fetch(`/api/history?metric=${m}&hours=${hours}`).then((r) => r.json()),
      ),
    );
    chartSoil.data.datasets[0].data = soil.points.map(([x, y]) => ({ x, y }));
    chartSoil.data.datasets[1].data = humidity.points.map(([x, y]) => ({ x, y }));
    chartClimate.data.datasets[0].data = temp.points.map(([x, y]) => ({ x, y }));
    chartClimate.data.datasets[1].data = lux.points.map(([x, y]) => ({ x, y }));
    chartSoil.update();
    chartClimate.update();
  } catch {
    /* le bandeau de connexion signale déjà le problème */
  }
}

$("hours").addEventListener("change", refreshHistory);

async function setupGrafana() {
  try {
    const cfg = await (await fetch("/api/grafana")).json();
    const mode = $("grafana-mode");
    if (!cfg.enabled) {
      mode.textContent = "Mode local";
      mode.classList.remove("grafana");
      $("grafana-grid").hidden = true;
      $("local-charts").hidden = false;
      return;
    }

    const map = {
      soil: "gf-soil",
      air: "gf-air",
      light: "gf-light",
      overview: "gf-overview",
    };
    let any = false;
    for (const [key, iframeId] of Object.entries(map)) {
      const url = cfg.panels[key];
      const frame = $(iframeId);
      if (url) {
        frame.src = url;
        frame.closest("figure").hidden = false;
        any = true;
      } else {
        frame.closest("figure").hidden = true;
      }
    }

    if (any) {
      mode.textContent = "Grafana";
      mode.classList.add("grafana");
      $("grafana-grid").hidden = false;
      // Garde aussi le local comme contrôle croisé tant que Grafana n'est pas validé.
      $("local-charts").hidden = false;
    }
  } catch {
    $("grafana-mode").textContent = "Mode local";
  }
}

// ---------- Événements ----------

const EVENT_LABEL = {
  pump: "Pompe",
  light: "Lumière",
  state: "État",
  status: "Module",
  command: "Commande",
};

async function refreshEvents() {
  try {
    const events = await (await fetch("/api/events?limit=30")).json();
    $("events").replaceChildren(
      ...events.map((e) => {
        const li = document.createElement("li");
        const time = document.createElement("time");
        time.textContent = formatTime(e.ts, true);
        const kind = document.createElement("span");
        kind.className = "kind";
        kind.textContent = EVENT_LABEL[e.kind] ?? e.kind;
        const detail = document.createElement("span");
        detail.textContent = e.detail;
        li.append(time, kind, detail);
        return li;
      }),
    );
  } catch {
    /* idem */
  }
}

// ---------- Commandes ----------

async function sendCommand(cmd) {
  try {
    const res = await fetch("/api/cmd", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cmd),
    });
    const body = await res.json();
    setText("feedback", body.message, body.ok ? "ok" : "bad");
  } catch {
    setText("feedback", "Backend injoignable", "bad");
  }
  setTimeout(refreshEvents, 500);
}

document.querySelectorAll("button[data-cmd]").forEach((btn) => {
  btn.addEventListener("click", () => sendCommand(JSON.parse(btn.dataset.cmd)));
});

$("settings").addEventListener("submit", (event) => {
  event.preventDefault();
  const cmd = { action: "set" };
  for (const [key, value] of new FormData(event.target)) {
    if (value !== "") cmd[key] = Number(value);
  }
  sendCommand(cmd);
});

setupGrafana();
refreshStatus();
refreshHistory();
refreshEvents();
setInterval(refreshStatus, STATUS_PERIOD_MS);
setInterval(refreshHistory, HISTORY_PERIOD_MS);
setInterval(refreshEvents, HISTORY_PERIOD_MS);
