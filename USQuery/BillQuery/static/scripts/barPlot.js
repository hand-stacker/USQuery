let yeas_cnts = JSON.parse(document.getElementById('yeas_cnts').textContent);
let nays_cnts = JSON.parse(document.getElementById('nays_cnts').textContent);
let pres_cnts = JSON.parse(document.getElementById('pres_cnts').textContent);
let novt_cnts = JSON.parse(document.getElementById('novt_cnts').textContent);

const parties = ['Democratic', 'Republican', 'Independent', 'Libertarian', 'Green'];
const colors = {
    'Democratic': 'rgb(51,101,138)',
    'Republican': 'rgb(165,1,4)',
    'Independent': 'rgb(209,227,221)',
    'Libertarian': 'rgb(246,174,45)',
    'Green': 'rgb(162,215,41)'
};


let barData = []
let cols = 0
parties.forEach(party => {
    /// check if party has any recorded votes, else ignore this party
    if (party in yeas_cnts || party in nays_cnts || party in pres_cnts || party in novt_cnts) {
        cols++;
        let x = [];
        let y = [];
        if (party in yeas_cnts) {
            x.push('Yeas');
            y.push(yeas_cnts[party]);
        }
        if (party in nays_cnts) {
            x.push('Nays');
            y.push(nays_cnts[party]);
        }
        if (party in pres_cnts) {
            x.push('Present');
            y.push(pres_cnts[party]);
        }
        if (party in novt_cnts) {
            x.push('No Vote');
            y.push(novt_cnts[party]);
        }
        var trace = {
            x: x,
            y: y,
            type: 'bar',
            name: party,
            hoverinfo: 'label+values',
            marker: {
                color: colors[party]
            },
            xaxis: 'x' + cols.toString(),
            yaxis: 'y' + cols.toString(),
        };
        barData.push(trace);

    }
});

let barLayout = {
    height: 500,
    width: 625,
    title: {
        text: 'Grouped By Party'
    },
    margin: {b: 50, t: 80 },
    showlegend : true,
    grid: { rows: 1, columns: cols, pattern: 'independent' },
};

Plotly.newPlot('bar', barData, barLayout, { displayModeBar: false });