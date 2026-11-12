/* FoodSafe frontend. Talks only to the gateway: /api/<service>/... */

/* ---------- helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);

function el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
        if (k === "class") n.className = v;
        else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
        else n.setAttribute(k, v);
    }
    for (const c of kids.flat()) if (c != null) n.append(c);   // strings become text nodes (XSS-safe)
    return n;
}

async function api(path, opts) {
    const r = await fetch(path, opts);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || "Request failed (" + r.status + ")");
    return body;
}
const post = (p, data) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

const LABEL = { normal: "● Normal", warning: "● Warning", danger: "● Danger" };
const ICON = { normal: "🟢", warning: "🟡", danger: "🔴" };
const ALERT_CLASS = { normal: "success", warning: "warning", danger: "danger" };
const fmtTime = (s) => new Date(s).toLocaleString();
const errorBox = (what) => el("div", { class: "notice" }, "⚠️ " + what + " is unavailable right now.");

const NAV = [["index.html", "🏠 Dashboard"], ["temperature.html", "🌡️ Temperature"],
    ["food.html", "🍗 Food Inventory"], ["alerts.html", "🚨 Alerts"], ["reports.html", "📊 Reports"]];

function shell(page, title, subtitle) {
    const content = el("div", { id: "content" });
    document.body.replaceChildren(
        el("aside", { class: "sidebar" },
            el("div", { class: "logo" }, "FOOD", el("span", {}, "SAFE")),
            el("nav", {}, NAV.map(([href, text]) => el("a", { href, class: href === page ? "active" : "" }, text)))),
        el("main", { class: "main" },
            el("header", { class: "topbar" }, el("div", {}, el("h1", {}, title), el("p", {}, subtitle))),
            content,
            el("footer", {}, "FoodSafe Monitoring System © 2026")));
    return content;
}

function unitCard(u) {
    const r = u.latest;
    const status = r ? r.status : "warning";
    return el("div", { class: "card" },
        el("div", { class: "card-top" }, el("h3", {}, u.name), el("span", {}, u.icon)),
        el("div", { class: "temperature" }, r ? r.value.toFixed(1) + "°C" : "--"),
        el("div", { class: "st-" + status }, r ? LABEL[status] : "● No data"));
}

function alertItem(a) {
    return el("div", { class: "alert-item " + ALERT_CLASS[a.level] },
        el("span", {}, ICON[a.level]),
        el("div", {}, el("strong", {}, a.title), el("p", {}, a.message)));
}

/* small SVG line chart (no libraries) */
function lineChart(points) {
    const NS = "http://www.w3.org/2000/svg", W = 600, H = 200, pad = 28;
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    const t = points.map((p) => new Date(p.recorded_at).getTime()), v = points.map((p) => p.value);
    const [t0, t1] = [Math.min(...t), Math.max(...t)];
    const [v0, v1] = [Math.min(...v) - 1, Math.max(...v) + 1];
    const x = (ti) => pad + ((ti - t0) / (t1 - t0 || 1)) * (W - 2 * pad);
    const y = (vi) => H - pad - ((vi - v0) / (v1 - v0 || 1)) * (H - 2 * pad);
    const add = (tag, attrs, text) => {
        const n = document.createElementNS(NS, tag);
        for (const [k, val] of Object.entries(attrs)) n.setAttribute(k, val);
        if (text) n.textContent = text;
        svg.append(n);
    };
    add("line", { x1: pad, y1: H - pad, x2: W - pad, y2: H - pad, stroke: "#d1d5db" });
    add("polyline", { points: points.map((p, i) => x(t[i]) + "," + y(p.value)).join(" "), fill: "none", stroke: "#22c55e", "stroke-width": 3 });
    points.forEach((p, i) => add("circle", { cx: x(t[i]), cy: y(p.value), r: 3.5, fill: p.status === "normal" ? "#22c55e" : p.status === "warning" ? "#d97706" : "#dc2626" }));
    add("text", { x: 4, y: 14, "font-size": 12, fill: "#6b7280" }, v1.toFixed(1) + "°C");
    add("text", { x: 4, y: H - pad, "font-size": 12, fill: "#6b7280" }, v0.toFixed(1) + "°C");
    return svg;
}

/* ---------- pages ---------- */
const PAGES = {
    async index() {
        const c = shell("index.html", "Food Safety Dashboard", "Monitor your food storage conditions");
        const [units, alerts] = await Promise.allSettled([api("/api/temperature/units"), api("/api/alerts/alerts")]);

        const a = alerts.status === "fulfilled" ? alerts.value : null;
        const overall = a ? a.overall : "UNKNOWN";
        const cls = { SAFE: "", WARNING: "warning", DANGER: "danger", UNKNOWN: "unknown" }[overall];
        const text = { SAFE: "All monitored areas are currently operating normally.",
            WARNING: "Some items need attention. See alerts below.", DANGER: "Immediate action required. See alerts below.",
            UNKNOWN: "Safety status could not be determined." }[overall];
        c.append(el("section", { class: "overall-status " + cls },
            el("div", {}, el("h2", {}, "Overall Food Safety"), el("p", {}, text)),
            el("div", { class: "safe-badge " + cls }, { SAFE: "🟢 SAFE", WARNING: "🟡 WARNING", DANGER: "🔴 DANGER", UNKNOWN: "⚪ UNKNOWN" }[overall])));
        if (a && a.degraded.length) c.append(errorBox(a.degraded.join(", ")));

        if (units.status === "fulfilled") c.append(el("section", { class: "cards" }, units.value.map(unitCard)));
        else c.append(errorBox("Temperature service"));

        const chart = el("div", { class: "chart" }, el("p", { class: "muted" }, "Loading…"));
        const recent = el("div", {});
        if (a) {
            if (!a.alerts.length) recent.append(alertItem({ level: "normal", title: "System Normal", message: "No active alerts." }));
            a.alerts.slice(0, 4).forEach((x) => recent.append(alertItem(x)));
        } else recent.append(errorBox("Alert service"));

        c.append(el("section", { class: "dashboard-grid" },
            el("div", { class: "panel" }, el("div", { class: "panel-header" }, el("h2", {}, "Temperature Overview"), el("span", {}, "Refrigerator 1 · last 24 hours")), chart),
            el("div", { class: "panel" }, el("div", { class: "panel-header" }, el("h2", {}, "Recent Alerts"), el("a", { href: "alerts.html" }, "View All")), recent)));

        try {
            const rs = (await api("/api/temperature/readings?unit_id=fridge-1&hours=24")).reverse();
            chart.replaceChildren(rs.length > 1 ? lineChart(rs) : el("p", { class: "muted" }, "Not enough readings yet."));
        } catch (e) { chart.replaceChildren(errorBox("Temperature service")); }
    },

    async temperature() {
        const c = shell("temperature.html", "Temperature Monitoring", "Record and monitor your storage temperatures");
        const cards = el("section", { class: "cards" });
        const select = el("select", { id: "unit" });
        const value = el("input", { id: "value", type: "number", step: "0.1", min: "-50", max: "150", placeholder: "e.g. 4.2", required: "" });
        const msg = el("p", { class: "msg", role: "status" });
        const tbody = el("tbody", {});
        const histTitle = el("h2", {}, "Temperature History");

        async function refresh() {
            const units = await api("/api/temperature/units");
            cards.replaceChildren(...units.map(unitCard));
            if (!select.options.length) units.forEach((u) => select.append(el("option", { value: u.id }, u.name)));
            const rs = await api("/api/temperature/readings?unit_id=" + select.value + "&hours=168&limit=15");
            histTitle.textContent = "Recent readings · " + select.selectedOptions[0].text;
            tbody.replaceChildren(...(rs.length ? rs.map((r) => el("tr", {}, el("td", {}, fmtTime(r.recorded_at)), el("td", {}, r.value.toFixed(1) + "°C"), el("td", { class: "st-" + r.status }, LABEL[r.status])))
                : [el("tr", {}, el("td", { colspan: "3" }, "No readings yet."))]));
        }
        const form = el("form", { class: "inline", onsubmit: async (e) => {
            e.preventDefault();
            try {
                const r = await post("/api/temperature/readings", { unit_id: select.value, value: Number(value.value) });
                msg.textContent = "Saved " + r.value.toFixed(1) + "°C for " + r.unit_name + " (" + r.status + ").";
                msg.className = "msg st-" + (r.status === "normal" ? "normal" : r.status);
                value.value = ""; await refresh();
            } catch (err) { msg.textContent = err.message; msg.className = "msg st-danger"; }
        } }, el("label", {}, "Storage unit", select), el("label", {}, "Temperature (°C)", value), el("button", { type: "submit" }, "Save Temperature"));
        select.addEventListener("change", () => refresh().catch(() => {}));

        c.append(cards, el("section", { class: "panel" }, el("h2", {}, "Record a reading"), el("br"), form, msg),
            el("section", { class: "panel" }, histTitle, el("br"),
                el("table", {}, el("thead", {}, el("tr", {}, el("th", {}, "Time"), el("th", {}, "Temperature"), el("th", {}, "Status"))), tbody)));
        try { await refresh(); } catch (e) { c.prepend(errorBox("Temperature service")); }
    },

    async food() {
        const c = shell("food.html", "Food Inventory", "Monitor stored food items and expiry dates");
        const tbody = el("tbody", {});
        const select = el("select", { id: "unit" });
        const name = el("input", { id: "name", type: "text", maxlength: "100", placeholder: "e.g. Fish", required: "" });
        const date = el("input", { id: "date", type: "date", required: "" });
        const msg = el("p", { class: "msg", role: "status" });
        const STATUS = { safe: ["st-normal", "🟢 Safe"], expiring_soon: ["st-warning", "🟡 Expiring soon"], expired: ["st-danger", "🔴 Expired"] };
        let units = [];

        async function refresh() {
            const [u, items] = await Promise.all([api("/api/temperature/units").catch(() => []), api("/api/food/items")]);
            units = u;
            if (!select.options.length) units.forEach((x) => select.append(el("option", { value: x.id }, x.name)));
            const byId = Object.fromEntries(units.map((x) => [x.id, x]));
            tbody.replaceChildren(...(items.length ? items.map((i) => {
                const unit = byId[i.unit_id], t = unit && unit.latest;
                return el("tr", {}, el("td", {}, i.name), el("td", {}, unit ? unit.name : i.unit_id),
                    el("td", {}, t ? t.value.toFixed(1) + "°C" : "–"), el("td", {}, i.expiry_date + " (" + (i.days_left < 0 ? Math.abs(i.days_left) + "d ago" : i.days_left + "d left") + ")"),
                    el("td", { class: STATUS[i.status][0] }, STATUS[i.status][1]),
                    el("td", {}, el("button", { class: "link", onclick: async () => { await api("/api/food/items/" + i.id, { method: "DELETE" }); refresh(); } }, "Remove")));
            }) : [el("tr", {}, el("td", { colspan: "6" }, "No food items yet."))]));
        }
        const form = el("form", { class: "inline", onsubmit: async (e) => {
            e.preventDefault();
            try {
                await post("/api/food/items", { name: name.value, unit_id: select.value, expiry_date: date.value });
                msg.textContent = "Food item added."; msg.className = "msg st-normal"; form.reset(); await refresh();
            } catch (err) { msg.textContent = err.message; msg.className = "msg st-danger"; }
        } }, el("label", {}, "Food name", name), el("label", {}, "Storage", select), el("label", {}, "Expiry date", date), el("button", { type: "submit" }, "+ Add Food"));

        c.append(el("section", { class: "panel" }, el("h2", {}, "Add food item"), el("br"), form, msg),
            el("section", { class: "panel" }, el("h2", {}, "Food Items"), el("br"),
                el("table", {}, el("thead", {}, el("tr", {}, ["Food", "Storage", "Temperature", "Expiry Date", "Status", ""].map((h) => el("th", {}, h)))), tbody)));
        try { await refresh(); } catch (e) { c.prepend(errorBox("Food service")); }
    },

    async alerts() {
        const c = shell("alerts.html", "Alert Center", "Food safety warnings and notifications");
        try {
            const a = await api("/api/alerts/alerts");
            if (a.degraded.length) c.append(errorBox(a.degraded.join(", ")));
            const group = (title, type) => {
                const list = a.alerts.filter((x) => x.type === type);
                c.append(el("section", { class: "panel" }, el("h2", {}, title), el("br"),
                    list.length ? list.map(alertItem) : alertItem({ level: "normal", title: "NORMAL", message: "Nothing needs attention." })));
            };
            group("🌡️ Temperature Alerts", "temperature");
            group("🍗 Food Expiry Alerts", "expiry");
        } catch (e) { c.append(errorBox("Alert service")); }
    },

    async reports() {
        const c = shell("reports.html", "Safety Reports", "Food safety monitoring report");
        const days = el("select", {}, [["1", "Last 24 hours"], ["7", "Last 7 days"], ["30", "Last 30 days"]].map(([v, t]) => el("option", { value: v, ...(v === "7" ? { selected: "" } : {}) }, t)));
        const body = el("div", {});
        const exportLink = el("a", { class: "button", href: "/api/reports/export.csv?days=7" }, "⬇ Download CSV");

        async function load() {
            exportLink.href = "/api/reports/export.csv?days=" + days.value;
            try {
                const s = await api("/api/reports/summary?days=" + days.value);
                const card = (t, v, sub, cls) => el("div", { class: "card" }, el("h3", {}, t), el("div", { class: "temperature" }, v), el("div", { class: cls }, sub));
                body.replaceChildren(
                    el("section", { class: "cards" },
                        card("Monitored Units", String(s.monitored_units), "Monitoring", "normal"),
                        card("Normal Readings", s.normal_percent == null ? "--" : s.normal_percent + "%", s.total_readings + " readings", "st-normal"),
                        card("Warning Events", String(s.warning_events), "● Attention", "st-warning"),
                        card("Critical Events", String(s.critical_events), "● Review Required", "st-danger")),
                    el("section", { class: "panel" }, el("h2", {}, "Summary"), el("br"),
                        el("p", {}, "Over the last " + s.period_days + " day(s): " + s.warning_events + " warning and " + s.critical_events + " critical temperature events."),
                        el("br"), el("p", {}, "Food inventory: " + s.food.total + " items, " + s.food.expired + " expired, " + s.food.expiring_soon + " expiring soon.")),
                    el("section", { class: "panel" }, el("h2", {}, "Per-unit statistics"), el("br"),
                        el("table", {}, el("thead", {}, el("tr", {}, ["Unit", "Readings", "Min", "Avg", "Max", "Warnings", "Critical"].map((h) => el("th", {}, h)))),
                            el("tbody", {}, s.units.map((u) => el("tr", {}, [u.name, u.readings, u.min ?? "–", u.avg ?? "–", u.max ?? "–", u.warnings, u.critical].map((x) => el("td", {}, String(x)))))))));
            } catch (e) { body.replaceChildren(errorBox("Report service")); }
        }
        days.addEventListener("change", load);
        c.append(el("section", { class: "panel" }, el("form", { class: "inline", onsubmit: (e) => e.preventDefault() }, el("label", {}, "Period", days), exportLink)), body);
        await load();
    },
};

(PAGES[document.body.dataset.page] || PAGES.index)();
