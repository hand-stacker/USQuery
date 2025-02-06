let yeas = JSON.parse(document.getElementById('yeas_cnt').textContent);
let nays = JSON.parse(document.getElementById('nays_cnt').textContent);
let pres = JSON.parse(document.getElementById('pres_cnt').textContent);
let novt = JSON.parse(document.getElementById('novt_cnt').textContent);

const literal_colors = [
    'rgb(36, 130, 50)',
    'rgb(242, 43, 41)',
    'rgb(38, 35, 34)',
    'rgb(242, 229, 215)'
]
let donutData = [{
    values: [yeas, nays, pres, novt],
    labels: ['Yeas', 'Nays', 'Present', 'No Vote'],
    marker: {
        colors: literal_colors
    },
    domain: {
        row: 0,
        column: 0
    },
    name: 'Vote Results',
    hoverinfo: 'label+value',
    hole: .7,
    type: 'pie',
    }
];

let donutLayout = {
    height: 500,
    width: 500,
    title: {
        text: 'Vote Results'
    },
    annotations: [
        {
            font: {
                size: 20
            },
            showarrow: false,
            text: '',
            x: 0,
            y: 0
        }
    ],
    margin: {b: 50, t: 80 },
    grid: { rows: 1, columns: 1},
    showlegend: true,
};

console.log(donutData.toString)
Plotly.newPlot('donut', donutData, donutLayout, {displayModeBar: false });