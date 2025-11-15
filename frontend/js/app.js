const API_STORAGE_KEY = "compstat_api_base";
let API_BASE = "http://localhost:8000";
let lastStatusTimeout = null;

function resolveInitialApiBase() {
    const bodyAttr = document.body?.dataset?.apiBase;
    const stored = window.localStorage.getItem(API_STORAGE_KEY);
    const globalVar = window.API_BASE_URL;
    API_BASE = (globalVar || stored || bodyAttr || API_BASE).replace(/\/$/, "");
    const input = document.getElementById("apiBaseInput");
    if (input) input.value = API_BASE;
}

function setApiStatus(message, isError = false) {
    const el = document.getElementById("apiStatusMessage");
    if (!el) return;
    el.textContent = message;
    el.style.color = isError ? "#f87171" : "#94a3b8";
    if (lastStatusTimeout) clearTimeout(lastStatusTimeout);
    if (!isError && message) {
        lastStatusTimeout = setTimeout(() => {
            el.textContent = "";
        }, 7000);
    }
}
const DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

async function fetchJSON(path) {
    const response = await fetch(`${API_BASE}${path}`);
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }
    return response.json();
}

function formatChange(value) {
    if (value === null || value === undefined) return { text: "N/A", className: "pill" };
    const percent = (value * 100).toFixed(1);
    const direction = value >= 0 ? "up" : "down";
    const prefix = value >= 0 ? "+" : "";
    return {
        text: `${prefix}${percent}%`,
        className: `pill ${direction}`,
    };
}

function updateApiBase(url) {
    if (!url) return;
    API_BASE = url.replace(/\/$/, "");
    window.localStorage.setItem(API_STORAGE_KEY, API_BASE);
    const input = document.getElementById("apiBaseInput");
    if (input) input.value = API_BASE;
    setApiStatus(`Using ${API_BASE} – refreshing data...`);
    loadDashboard();
}

function updateCompstatTable(entries) {
    const tbody = document.querySelector("#compstatTable tbody");
    tbody.innerHTML = "";
    entries.forEach((entry) => {
        const periodChange = formatChange(entry.period_change);
        const yoyChange = formatChange(entry.yoy_change);
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${entry.window_days}-day</td>
            <td>${entry.current_count.toLocaleString()}</td>
            <td><span class="${periodChange.className}">${periodChange.text}</span></td>
            <td><span class="${yoyChange.className}">${yoyChange.text}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

function renderLineChart(data) {
    const svg = d3.select("#trendChart");
    svg.selectAll("*").remove();
    const width = parseInt(svg.style("width"), 10);
    const height = parseInt(svg.style("height"), 10);
    const margin = { top: 20, right: 20, bottom: 30, left: 40 };

    const parsed = data.map((d) => ({
        period: d3.timeParse("%Y-%m-%d")(d.period),
        count: d.count,
    }));

    const x = d3.scaleTime()
        .domain(d3.extent(parsed, (d) => d.period))
        .range([margin.left, width - margin.right]);

    const y = d3.scaleLinear()
        .domain([0, d3.max(parsed, (d) => d.count) || 1])
        .nice()
        .range([height - margin.bottom, margin.top]);

    const line = d3.line()
        .x((d) => x(d.period))
        .y((d) => y(d.count))
        .curve(d3.curveMonotoneX);

    svg.append("path")
        .datum(parsed)
        .attr("fill", "none")
        .attr("stroke", "#38bdf8")
        .attr("stroke-width", 2.5)
        .attr("d", line);

    svg.append("g")
        .attr("transform", `translate(0, ${height - margin.bottom})`)
        .call(d3.axisBottom(x).ticks(6).tickFormat(d3.timeFormat("%b %d")))
        .attr("color", "#94a3b8");

    svg.append("g")
        .attr("transform", `translate(${margin.left}, 0)`)
        .call(d3.axisLeft(y))
        .attr("color", "#94a3b8");
}

function renderBarChart(selector, values, labelKey, labelFormatter = (d) => d[labelKey]) {
    const svg = d3.select(selector);
    svg.selectAll("*").remove();
    if (!values || !values.length) return;

    const width = parseInt(svg.style("width"), 10);
    const height = parseInt(svg.style("height"), 10);
    const margin = { top: 20, right: 20, bottom: 30, left: 120 };

    const x = d3.scaleLinear()
        .domain([0, d3.max(values, (d) => d.count) || 1])
        .range([margin.left, width - margin.right]);

    const y = d3.scaleBand()
        .domain(values.map((d) => labelFormatter(d)))
        .range([margin.top, height - margin.bottom])
        .padding(0.2);

    svg.append("g")
        .attr("transform", `translate(${margin.left},0)`)
        .call(d3.axisLeft(y))
        .attr("color", "#94a3b8");

    svg.append("g")
        .attr("transform", `translate(0,${height - margin.bottom})`)
        .call(d3.axisBottom(x).ticks(5))
        .attr("color", "#94a3b8");

    svg.selectAll("rect")
        .data(values)
        .enter()
        .append("rect")
        .attr("x", margin.left)
        .attr("y", (d) => y(labelFormatter(d)))
        .attr("width", (d) => x(d.count) - margin.left)
        .attr("height", y.bandwidth())
        .attr("fill", "#38bdf8");
}

function orderAxisValues(values, dimension) {
    const unique = Array.from(new Set(values));
    if (dimension === "day_of_week") {
        return DAY_ORDER.filter((day) => unique.includes(day));
    }
    if (dimension === "hour_of_day" || dimension === "hour") {
        return unique.map((val) => Number(val)).sort((a, b) => a - b);
    }
    return unique;
}

function formatAxisLabel(value, dimension) {
    if (dimension === "hour_of_day" || dimension === "hour") {
        return `${String(value).padStart(2, "0")}:00`;
    }
    return value;
}

function renderHeatmap(selector, payload) {
    const svg = d3.select(selector);
    svg.selectAll("*").remove();
    const values = payload.values || [];
    if (!values.length) return;

    const width = parseInt(svg.style("width"), 10);
    const height = parseInt(svg.style("height"), 10);
    const margin = { top: 20, right: 20, bottom: 50, left: 120 };

    const xValues = orderAxisValues(values.map((d) => d.x), payload.dim_x);
    const yValues = orderAxisValues(values.map((d) => d.y), payload.dim_y);

    const x = d3.scaleBand().domain(xValues).range([margin.left, width - margin.right]).padding(0.05);
    const y = d3.scaleBand().domain(yValues).range([margin.top, height - margin.bottom]).padding(0.05);
    const color = d3.scaleSequential()
        .domain([0, d3.max(values, (d) => d.count) || 1])
        .interpolator(d3.interpolateCool);

    svg.append("g")
        .attr("transform", `translate(0, ${height - margin.bottom})`)
        .call(d3.axisBottom(x).tickFormat((val) => formatAxisLabel(val, payload.dim_x)))
        .attr("color", "#94a3b8");

    svg.append("g")
        .attr("transform", `translate(${margin.left},0)`)
        .call(d3.axisLeft(y).tickFormat((val) => formatAxisLabel(val, payload.dim_y)))
        .attr("color", "#94a3b8");

    svg.selectAll("rect")
        .data(values)
        .enter()
        .append("rect")
        .attr("x", (d) => x(d.x))
        .attr("y", (d) => y(d.y))
        .attr("width", x.bandwidth())
        .attr("height", y.bandwidth())
        .attr("fill", (d) => color(d.count));
}

function renderDonut(selector, values, labelKey) {
    const svg = d3.select(selector);
    svg.selectAll("*").remove();
    if (!values.length) return;

    const width = parseInt(svg.style("width"), 10);
    const height = parseInt(svg.style("height"), 10);
    const radius = Math.min(width, height) / 2 - 20;
    const color = d3.scaleOrdinal().domain(values.map((d) => d[labelKey])).range(["#38bdf8", "#f87171", "#facc15"]);

    const pie = d3.pie().value((d) => d.count);
    const arc = d3.arc().innerRadius(radius * 0.6).outerRadius(radius);

    const chart = svg.append("g").attr("transform", `translate(${width / 2}, ${height / 2})`);

    chart.selectAll("path")
        .data(pie(values))
        .enter()
        .append("path")
        .attr("d", arc)
        .attr("fill", (d) => color(d.data[labelKey]))
        .append("title")
        .text((d) => `${d.data[labelKey]}: ${d.data.count.toLocaleString()}`);

    const legend = svg.append("g").attr("transform", `translate(10, 10)`);
    values.forEach((entry, index) => {
        const legendRow = legend.append("g").attr("transform", `translate(0, ${index * 20})`);
        legendRow.append("rect").attr("width", 12).attr("height", 12).attr("fill", color(entry[labelKey]));
        legendRow.append("text").attr("x", 18).attr("y", 10).text(`${entry[labelKey]} (${entry.count.toLocaleString()})`).attr("fill", "#94a3b8").attr("font-size", "12px");
    });
}

function renderStackedArea(selector, data) {
    const svg = d3.select(selector);
    svg.selectAll("*").remove();
    if (!data.length) return;

    const width = parseInt(svg.style("width"), 10);
    const height = parseInt(svg.style("height"), 10);
    const margin = { top: 20, right: 20, bottom: 40, left: 50 };

    const groups = Array.from(new Set(data.map((d) => d.group)));
    const periods = Array.from(new Set(data.map((d) => d.period))).sort();

    const stackedData = periods.map((period) => {
        const row = { period: d3.timeParse("%Y-%m-%d")(period) };
        groups.forEach((group) => {
            const match = data.find((d) => d.group === group && d.period === period);
            row[group] = match ? match.count : 0;
        });
        return row;
    });

    const stack = d3.stack().keys(groups);
    const series = stack(stackedData);

    const x = d3.scaleTime()
        .domain(d3.extent(stackedData, (d) => d.period))
        .range([margin.left, width - margin.right]);

    const y = d3.scaleLinear()
        .domain([0, d3.max(series[series.length - 1], (d) => d[1]) || 1])
        .nice()
        .range([height - margin.bottom, margin.top]);

    const color = d3.scaleOrdinal().domain(groups).range(d3.schemeTableau10);

    svg.selectAll("path")
        .data(series)
        .enter()
        .append("path")
        .attr("fill", (d) => color(d.key))
        .attr("d", d3.area()
            .x((d) => x(d.data.period))
            .y0((d) => y(d[0]))
            .y1((d) => y(d[1]))
            .curve(d3.curveCatmullRom));

    svg.append("g")
        .attr("transform", `translate(0, ${height - margin.bottom})`)
        .call(d3.axisBottom(x).ticks(6).tickFormat(d3.timeFormat("%b %d")))
        .attr("color", "#94a3b8");

    svg.append("g")
        .attr("transform", `translate(${margin.left}, 0)`)
        .call(d3.axisLeft(y))
        .attr("color", "#94a3b8");

    const legend = svg.append("g").attr("transform", `translate(${width - margin.right - 120}, ${margin.top})`);
    groups.forEach((group, index) => {
        const row = legend.append("g").attr("transform", `translate(0, ${index * 18})`);
        row.append("rect").attr("width", 12).attr("height", 12).attr("fill", color(group));
        row.append("text").attr("x", 18).attr("y", 10).text(group).attr("fill", "#94a3b8").attr("font-size", "12px");
    });
}

function updateForecastCard(forecast) {
    const total = forecast.next_week_forecast.reduce((sum, d) => sum + d.predicted_count, 0);
    document.getElementById("forecastTotal").textContent = Math.round(total).toLocaleString();
    document.getElementById("forecastDetail").textContent = `${forecast.next_week_forecast[0].date} - ${forecast.next_week_forecast.at(-1).date}`;
    const list = document.getElementById("forecastList");
    list.innerHTML = "";
    forecast.next_week_forecast.forEach((item) => {
        const div = document.createElement("div");
        div.textContent = `${item.date}: ${item.predicted_count.toFixed(1)} incidents`;
        list.appendChild(div);
    });
}

function renderCaseResults(results) {
    const container = document.getElementById("caseResults");
    if (!results.length) {
        container.innerHTML = "<p>No matching cases found.</p>";
        return;
    }
    const table = document.createElement("table");
    table.innerHTML = `
        <thead>
            <tr>
                <th>Case</th>
                <th>Date/Time</th>
                <th>Category</th>
                <th>Beat</th>
                <th>Violent</th>
                <th>Description</th>
            </tr>
        </thead>
        <tbody>
            ${results.map((row) => `
                <tr>
                    <td>${row.case_number}</td>
                    <td>${row.occurred_ts}</td>
                    <td>${row.crime_category}</td>
                    <td>${row.beat}</td>
                    <td>${row.violent ? "Yes" : "No"}</td>
                    <td>${row.description || ""}</td>
                </tr>
            `).join("")}
        </tbody>
    `;
    container.innerHTML = "";
    container.appendChild(table);
}

function setupTabs() {
    const buttons = document.querySelectorAll(".tab-button");
    const sections = document.querySelectorAll(".tab-section");
    buttons.forEach((button) => {
        button.addEventListener("click", () => {
            buttons.forEach((btn) => btn.classList.remove("active"));
            sections.forEach((section) => section.classList.remove("active"));
            button.classList.add("active");
            const target = document.getElementById(button.dataset.target);
            if (target) target.classList.add("active");
        });
    });
}

function setupCaseSearch() {
    const form = document.getElementById("caseSearchForm");
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const query = document.getElementById("caseQuery").value.trim();
        if (!query || query.length < 2) {
            renderCaseResults([]);
            return;
        }
        try {
            const result = await fetchJSON(`/cases/search?q=${encodeURIComponent(query)}&limit=25`);
            renderCaseResults(result.results || []);
        } catch (error) {
            console.error("Case search failed", error);
            renderCaseResults([]);
        }
    });
}

function setupApiConfig() {
    const form = document.getElementById("apiConfigForm");
    if (!form) return;
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const input = document.getElementById("apiBaseInput");
        if (!input || !input.value) return;
        updateApiBase(input.value.trim());
    });
}

async function loadDashboard() {
    try {
        setApiStatus(`Loading analytics from ${API_BASE}...`);
        const [
            health,
            compstat,
            series,
            distributions,
            forecast,
            hourCounts,
            dayHourHeatmap,
            beatCounts,
            beatHourHeatmap,
            violentSplit,
            categorySeries,
        ] = await Promise.all([
            fetchJSON("/health"),
            fetchJSON("/compstat"),
            fetchJSON("/timeseries?freq=D&periods=90"),
            fetchJSON("/eda/distributions"),
            fetchJSON("/ml/random-forest"),
            fetchJSON("/aggregates/count-by?dimension=hour_of_day"),
            fetchJSON("/aggregates/heatmap?dim_x=day_of_week&dim_y=hour_of_day"),
            fetchJSON("/aggregates/count-by?dimension=Beats&limit=12"),
            fetchJSON("/aggregates/heatmap?dim_x=Beats&dim_y=hour_of_day"),
            fetchJSON("/aggregates/count-by?dimension=violent_flag"),
            fetchJSON("/timeseries?freq=W&group_by=crime_category&periods=26"),
        ]);

        const compstatEntries = compstat["All"] || [];
        if (compstatEntries.length) {
            const stats7 = compstatEntries.find((entry) => entry.window_days === 7);
            const stats28 = compstatEntries.find((entry) => entry.window_days === 28);
            if (stats7) {
                document.getElementById("sevenDayCount").textContent = stats7.current_count.toLocaleString();
                const change = formatChange(stats7.period_change);
                const el = document.getElementById("sevenDayChange");
                el.textContent = change.text;
                el.className = change.className;
            }
            if (stats28) {
                document.getElementById("twentyEightDayCount").textContent = stats28.current_count.toLocaleString();
                const change = formatChange(stats28.period_change);
                const el = document.getElementById("twentyEightDayChange");
                el.textContent = change.text;
                el.className = change.className;
            }
            updateCompstatTable(compstatEntries);
        }

        document.getElementById("totalIncidents").textContent = health.records.toLocaleString();
        document.getElementById("coverageRange").textContent = `${health.earliest?.split("T")[0]} - ${health.latest?.split("T")[0]}`;

        renderLineChart(series);
        renderCategoryChart(distributions.crime_category.slice(0, 5));
        updateForecastCard(forecast);

        renderBarChart("#hourBarChart", hourCounts.values.map((v) => ({
            label: `${String(v.hour_of_day).padStart(2, "0")}:00`,
            count: v.count,
        })), "label", (d) => d.label);

        renderHeatmap("#dayHourHeatmap", dayHourHeatmap);
        renderBarChart("#beatBarChart", beatCounts.values, "Beats", (d) => d.Beats || "Unknown");
        renderHeatmap("#beatHourHeatmap", beatHourHeatmap);

        renderDonut("#violenceDonut", violentSplit.values.map((v) => ({
            label: v.violent_flag ? "Violent" : "Non-Violent",
            count: v.count,
        })), "label");

        renderStackedArea("#categoryStackedArea", categorySeries);
        setApiStatus(`Last synced from ${API_BASE} at ${new Date().toLocaleTimeString()}`);
    } catch (error) {
        console.error("Dashboard failed to load", error);
        setApiStatus(`Failed to load from ${API_BASE}: ${error.message}`, true);
    }
}

function renderCategoryChart(data) {
    const payload = data || [];
    const formatted = payload.map((d) => ({
        label: d.crime_category || d.label,
        count: d.count,
    }));
    renderBarChart("#categoryChart", formatted, "label", (d) => d.label);
}

document.addEventListener("DOMContentLoaded", () => {
    resolveInitialApiBase();
    setupTabs();
    setupCaseSearch();
    setupApiConfig();
    loadDashboard();
});
