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
        paper_bgcolor: "rgba(0,0,0,0)",
        map: {
            style: "dark",
            center: { lon: -98, lat: 39 },
            zoom: 3.3
        },
        font: {
            color: 'rgb(250,250,250)',
        },
        width: 1000,
        height: 650,
        margin: { t: 25, b: 0, l: 0, r: 0 }
    };

    Plotly.newPlot('cloro', cloroData, cloroLayout, { displayModeBar: false });
}

makeCloro()