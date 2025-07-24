let house_pred = JSON.parse(document.getElementById('house_pred').textContent);

var house_trace = {
    x: house_pred,
    type: 'histogram',
    histnorm : 'probability',
    marker: {
        color: 'rgb(102,128,155)',
    }
};

let histLayoutHouse = {
    height: 0,
    width: 0,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: {
        color: 'rgb(250,250,250)',

    },
    title: {
        text : "Predicted Total Votes (House)"
        },
    margin: { b: 30, t: 30 },
    showlegend: false,
    grid: { rows: 1, columns: 1},
    yaxis: { fixedrange: true },
    xaxis: { fixedrange: true }
};
function makeHist() {
    histLayoutHouse['height'] = Math.max(site_width * graph_scale * 0.5, 150);
    histLayoutHouse['width'] = Math.max(site_width * graph_scale, 300);
    Plotly.newPlot('hist', [house_trace], histLayoutHouse, { displayModeBar: false });
    document.getElementById("hist").getElementsByClassName("plot-container")[0].style["width"] = String(histLayoutHouse['width']) + "px";
}