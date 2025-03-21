const origins = ['Nays', 'Yeas', 'Present', 'No Vote'];
const vote_objs = [nays_cnts, yeas_cnts, pres_cnts, novt_cnts];
const origin_vals = [nays, yeas, pres, novt]
let burst_vals = [];
let burst_ids = [];
let burst_labels = [];
let parents = [];
let burst_colors = []

for (let i = 0; i < 4; i++) {
    let k = Object.keys(vote_objs[i]).length;
    if (k !== 0) {
        burst_ids.push(origins[i]);
        burst_vals.push(origin_vals[i]);
        burst_labels.push(origins[i]);
        parents.push('');
        burst_colors.push(literal_colors[i]);
        for (let key in vote_objs[i]) {
            burst_ids.push(origins[i] + '-' + key);
            burst_vals.push(vote_objs[i][key]);
            burst_labels.push(key);
            parents.push(origins[i]);
            burst_colors.push(colors[key]);
        }
    }
}

var burstData = [{
    type: "sunburst",
    theme: 'plotly_dark',
    ids : burst_ids,
    labels: burst_labels,
    parents: parents,
    values: burst_vals,
    outsidetextfont: { size: 20, color: "#377eb8" },
    leaf: { opacity: 1.0 },
    marker: {
        line: { width: 1.5 ,color : 'rgb(200,200,200)'},
        colors: burst_colors
    },
    "branchvalues": 'total',

}];


var burstLayout = {
    title: {
        text: 'Grouped By Vote'
    },
    paper_bgcolor: "rgba(0,0,0,0)",
    font: {
        color: 'rgb(250,250,250)',
    },
    margin: { l: 50, r: 50, b: 50, t: 80 },
    grid: { rows: 1, columns: 1 },
    width: 0,
    height: 0
};

function makeBurst() {
    burstLayout['height'] = half_image_width * 0.9 ;
    burstLayout['width'] = half_image_width * 0.9 ;
    Plotly.newPlot('sunburst', burstData, burstLayout, { displayModeBar: false });
}
