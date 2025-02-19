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
        title: cloroTitle,
        map: {
            center: { lon: -98, lat: 39 },
            zoom: 3.3
        },
        width: 1000,
        height: 650,
        margin: { t: 25, b: 0, l: 0, r: 0 }
    };

    Plotly.newPlot('cloro', cloroData, cloroLayout, { displayModeBar: false });
}

makeCloro()