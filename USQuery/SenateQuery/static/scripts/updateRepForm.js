const congressFieldRep = document.getElementById('id_congress_rep');
const representativeField = document.getElementById('id_representative');
const stateRepField = document.getElementById('id_state_rep');

congressFieldRep.addEventListener('change', updateRepChoices);
stateRepField.addEventListener('change', updateRepChoices);
function updateRepChoices() {
    const congressId = congressFieldRep.value;
    if (congressId == '') { return;}
    const state = stateSenField.value;
    var url_rep = `update-reps/${congressId}/`;
    if (state != null) {
        url_rep += `${state}/`;
    }
    fetch(url_rep)
            .then(response => console.log(response.status) || response.json())
            .then(data => {
                const representativeOptions = data.representatives.map(representative => `
                    <option value="${representative.id}">${representative.full_name}</option>
                `);
                representativeField.innerHTML = `<option value="">Select a representative</option>${representativeOptions.join('')}`;
            });
}