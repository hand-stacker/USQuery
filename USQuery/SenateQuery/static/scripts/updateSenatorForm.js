const congressField = document.getElementById('id_congress_sen');
const senatorField = document.getElementById('id_senator');
const stateSenField = document.getElementById('id_state_sen');

congressField.addEventListener('change', updateSenatorChoices);
stateSenField.addEventListener('change', updateSenatorChoices);
function updateSenatorChoices() {
    const congressId = congressField.value;
    if (congressId == '') {
        console.log("err2")
        return;
    }
    const state = stateSenField.value;
    var url_sen = `update-senators/${congressId}/`;
    if (state != '!') {
        url_sen += `${state}/`;
    }

    fetch(url_sen)
            .then(response => console.log(response.status) || response.json())
            .then(data => {
                const senatorOptions = data.senators.map(senator => `
                    <option value="${senator.id}">${senator.full_name}</option>
                `);
                senatorField.innerHTML = `<option value="">Select a senator</option>${senatorOptions.join('')}`;
            });
    }

