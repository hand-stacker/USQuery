let senate_pred = JSON.parse(document.getElementById('senate_pred').textContent);

var senate_trace = {
    x: senate_pred,
    type: 'histogram',
    marker: {
        color: 'rgb(102,128,155)',
    },
    xaxis: 'x2',
    yaxis: 'y2',
};

let histLayoutSenate = {
    height: 0,
    width: 0,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: {
        color: 'rgb(250,250,250)',

    },
    title: {
        text: "Predicted Total Votes (Senate)"
    },
    margin: { b: 30, t: 30 },
    showlegend: false,
    grid: { rows: 1, columns: 1 },
    yaxis: { fixedrange: true },
    xaxis: { fixedrange: true }
};

function makeHist2() {
    histLayoutSenate['height'] = Math.max(site_width * graph_scale * 0.5, 150);
    histLayoutSenate['width'] = Math.max(site_width * graph_scale, 300);
    Plotly.newPlot('hist2', [senate_trace], histLayoutSenate, { displayModeBar: false });
    document.getElementById("hist2").getElementsByClassName("plot-container")[0].style["width"] = String(histLayoutSenate['width']) + "px";
}

updateWidth();