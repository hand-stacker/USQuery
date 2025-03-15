let geoids = JSON.parse(document.getElementById('geoids').textContent);
let text = JSON.parse(document.getElementById('cloro_text').textContent);

function makeCloro() {
    var cloroData = [{
        type: "choroplethmap",
        name: cloroName,
        showscale: false,
        geojson: geojson,
        locations: geoids,
        z: values,
        text : text,
        zmin: 0,
        zmax: zmax,
        colorscale: cloroColorscale,
        marker: cloroMarker
    }
    ];

    var cloroLayout = {
        paper_bgcolor: "rgba(0,0,0,0)",
        map: {
            style: "dark",
            center: { lon: -98, lat: 39 },
            zoom: 3.6 * site_width / 1400
        },
        font: {
            color: 'rgb(250,250,250)',
        },
        width: site_width * 0.85,
        height: site_width * 0.65 * 0.85,
        margin: { t: 25, b: 0, l: 0, r: 0 }
    };

    Plotly.newPlot('cloro', cloroData, cloroLayout, { displayModeBar: false });
}

updateWidth();