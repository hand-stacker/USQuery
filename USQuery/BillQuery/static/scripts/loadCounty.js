let values = JSON.parse(document.getElementById('values').textContent);
const cloroColorscale = [

    [0, literal_colors[0]],
    [0.33, literal_colors[1]],
    [0.66, literal_colors[2]],
    [1, literal_colors[3]]
];

const cloroMarker = {
    line: {
        color: 'rgb(48,53,54)',
        width: 1
    }
};

const zmax = 3;

const cloroName = "US Counties";

const cloroTitle = {
    text: 'Vote Result by Congressional Districts'
};