const API_BASE = window.API_BASE_URL || "http://localhost:8000";

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

function updateCompstatTable(entries) {
    const tbody = document.querySelector("#compstatTable tbody");
    tbody.innerHTML = "";
    entries.forEach((entry) => {
        const tr = document.createElement("tr");
        const periodChange = formatChange(entry.period_change);
        const yoyChange = formatChange(entry.yoy_change);
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
    const width = parseInt(svg.style("width"));
    const height = parseInt(svg.style("height"));
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

function renderCategoryChart(data) {
    const svg = d3.select("#categoryChart");
    svg.selectAll("*").remove();
    const width = parseInt(svg.style("width"));
    const height = parseInt(svg.style("height"));
    const margin = { top: 20, right: 20, bottom: 30, left: 120 };

    const x = d3.scaleLinear()
        .domain([0, d3.max(data, (d) => d.count) || 1])
        .range([margin.left, width - margin.right]);

    const y = d3.scaleBand()
        .domain(data.map((d) => d.Beats ? `${d.Beats}` : d.crime_category || d.label))
        .range([margin.top, height - margin.bottom])
        .padding(0.15);

    svg.append("g")
        .attr("transform", `translate(${margin.left},0)`)
        .call(d3.axisLeft(y))
        .attr("color", "#94a3b8");

    svg.append("g")
        .attr("transform", `translate(0,${height - margin.bottom})`)
        .call(d3.axisBottom(x).ticks(5))
        .attr("color", "#94a3b8");

    svg.selectAll("rect")
        .data(data)
        .enter()
        .append("rect")
        .attr("x", margin.left)
        .attr("y", (d) => y(d.crime_category || d.label))
        .attr("width", (d) => x(d.count) - margin.left)
        .attr("height", y.bandwidth())
        .attr("fill", "#38bdf8");
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

async function loadDashboard() {
    try {
        const [health, compstat, series, distributions, forecast] = await Promise.all([
            fetchJSON("/health"),
            fetchJSON("/compstat"),
            fetchJSON("/timeseries?freq=D&periods=90"),
            fetchJSON("/eda/distributions"),
            fetchJSON("/ml/random-forest"),
        ]);

        const compstatEntries = compstat["All"] || compstat["Crime_Category"] || [];
        if (compstatEntries.length) {
            const stats7 = compstatEntries.find((entry) => entry.window_days === 7);
            const stats28 = compstatEntries.find((entry) => entry.window_days === 28);
            document.getElementById("sevenDayCount").textContent = stats7.current_count.toLocaleString();
            document.getElementById("twentyEightDayCount").textContent = stats28.current_count.toLocaleString();

            const sevenChange = formatChange(stats7.period_change);
            const twentyEightChange = formatChange(stats28.period_change);
            const sevenElement = document.getElementById("sevenDayChange");
            const twentyEightElement = document.getElementById("twentyEightDayChange");
            sevenElement.textContent = sevenChange.text;
            sevenElement.className = sevenChange.className;
            twentyEightElement.textContent = twentyEightChange.text;
            twentyEightElement.className = twentyEightChange.className;
            updateCompstatTable(compstatEntries);
        }

        document.getElementById("totalIncidents").textContent = health.records.toLocaleString();
        document.getElementById("coverageRange").textContent = `${health.earliest?.split("T")[0]} - ${health.latest?.split("T")[0]}`;

        renderLineChart(series);
        const categoryData = distributions.crime_category.slice(0, 5);
        renderCategoryChart(categoryData);
        updateForecastCard(forecast);
    } catch (error) {
        console.error("Dashboard failed to load", error);
    }
}

document.addEventListener("DOMContentLoaded", loadDashboard);

