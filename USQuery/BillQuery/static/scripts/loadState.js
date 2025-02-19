let cloroChoiceField = document.getElementById('id_cloro_choice');
let allValues = JSON.parse(document.getElementById('values').textContent);
let values = allValues[1];

cloroChoiceField.addEventListener('change', updateCloro);
function updateCloro() {
    const cloroId = cloroChoiceField.value;
    values = allValues[cloroId];
    cloroColorscale = [
        [0, 'rgb(255,255,255)'],
        [1, literal_colors[cloroId]]
    ];
    makeCloro()
}

let cloroColorscale = [
    [0, 'rgb(255,255,255)'],
    [1, literal_colors[1]]
];

const cloroMarker = {
    line: {
        color: 'rgb(48,53,54)',
        width: 2
    }

};

const zmax = 2;

const cloroName = "US States";

const cloroTitle = {
    text: 'Vote Result by US STATES (count of YEAS)'
};