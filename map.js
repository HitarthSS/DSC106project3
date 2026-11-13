const data = await d3.json("data/california_grid.json");
const map = d3.select("#map");
const panel = document.querySelector("#map-panel");
const tooltip = d3.select("#tooltip");
const yearInput = d3.select("#year");
const scenarioInput = d3.select("#scenario");
const scenarioLabels = { ssp126: "Low emissions", ssp585: "High emissions" };
const color = d3.scaleSequential(d3.interpolateYlOrRd).domain(data.colorRange);
const projection = d3.geoMercator().fitExtent([[24, 12], [616, 518]], data.boundary);
const path = d3.geoPath(projection);
let selectedCell;

yearInput.attr("min", data.historicalStart).attr("max", data.endYear);
d3.select(".endpoints span:first-child").text(data.historicalStart);
d3.select(".endpoints span:last-child").text(data.endYear);

const cells = map.append("g").selectAll("path")
  .data(data.cells)
  .join("path")
  .attr("class", "cell")
  .attr("d", path)
  .on("pointerenter pointermove click", (event, cell) => {
    selectedCell = data.cells.indexOf(cell);
    updateTooltip(currentTemperatures());

    const [x, y] = d3.pointer(event, panel);
    const { offsetWidth, offsetHeight } = tooltip.node();
    const left = Math.max(0, Math.min(x + 12, panel.clientWidth - offsetWidth));
    const top = y >= offsetHeight + 12 ? y - offsetHeight - 12 : y + 12;
    tooltip.style("left", `${left}px`).style("top", `${top}px`);
  })
  .on("pointerleave", () => {
    selectedCell = undefined;
    tooltip.property("hidden", true);
  });
map.append("path")
  .datum(data.boundary)
  .attr("d", path)
  .attr("fill", "none")
  .attr("stroke", "#324b52")
  .attr("stroke-width", 1.1)
  .attr("pointer-events", "none");

function currentTemperatures() {
  const year = +yearInput.property("value");
  return year < data.projectionStart
    ? data.temperatures.historical[year - data.historicalStart]
    : data.temperatures[scenarioInput.property("value")][year - data.projectionStart];
}

function updateTooltip(temperatures) {
  if (selectedCell === undefined) return;
  const location = data.cells[selectedCell].properties;
  tooltip.text(`Grid center ${location.latitude.toFixed(2)}°N, ${Math.abs(location.longitude).toFixed(2)}°W\n` +
    `Annual mean ${temperatures[selectedCell].toFixed(2)} °C`)
    .property("hidden", false);
}

function update() {
  const year = +yearInput.property("value");
  const temperatures = currentTemperatures();
  const phase = year < data.projectionStart ? "Historical" : scenarioLabels[scenarioInput.property("value")];
  cells.attr("fill", (cell, index) => color(temperatures[index]));
  d3.select("#year-value").text(year);
  d3.select("#period").text(phase);
  d3.select("#map-title").text(`California annual average temperature, ${year}, ${phase}`);
  updateTooltip(temperatures);
}

const legend = d3.select("#legend");
const gradient = legend.append("defs").append("linearGradient").attr("id", "temperature-scale");
gradient.selectAll("stop").data(d3.range(0, 1.01, .05)).join("stop")
  .attr("offset", value => `${value * 100}%`)
  .attr("stop-color", value => color(data.colorRange[0] + value * (data.colorRange[1] - data.colorRange[0])));
legend.append("rect").attr("x", 20).attr("y", 4).attr("width", 300).attr("height", 10)
  .attr("fill", "url(#temperature-scale)");
const legendScale = d3.scaleLinear().domain(data.colorRange).range([20, 320]);
legend.append("g").attr("transform", "translate(0,14)")
  .call(d3.axisBottom(legendScale)
    .tickValues([data.colorRange[0], d3.mean(data.colorRange), data.colorRange[1]])
    .tickFormat(value => `${value} °C`).tickSize(0).tickPadding(10))
  .call(axis => axis.select(".domain").remove());

yearInput.on("input", update);
scenarioInput.on("change", update);
update();
