const congressField = document.getElementById('id_congress');
const chamberField = document.getElementById('id_chamber');
const stateField = document.getElementById('id_state');
const memberField = document.getElementById('id_member');

congressField.addEventListener('change', updateChoices);
chamberField.addEventListener('change', updateChoices);
stateField.addEventListener('change', updateChoices);
function updateChoices() {
    const congressId = congressField.value;
    if (congressId == '') {return;}
    const state = stateField.value;
    const chamber = chamberField.value;
    var url = `update-mems/${congressId}/${chamber}/${state}/`;
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const memberOptions = data.members.map(member => `
                    <option value="${member.id}">${member.full_name}</option>
                `);
            memberField.innerHTML = `<option value="">Select a member</option>${memberOptions.join('')}`;
        });
}