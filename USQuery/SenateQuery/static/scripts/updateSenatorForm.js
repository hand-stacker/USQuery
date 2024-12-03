const congressField = document.getElementById('id_congress_sen');
const senatorField = document.getElementById('id_senator');
congressField.addEventListener('change', updateSenatorChoices);
function updateSenatorChoices() {
    const congressId = congressField.value;
    const url = `update-senators/${congressId}/`;

    fetch(url)
            .then(response => console.log(response.status) || response.json())
            .then(data => {
                const senatorOptions = data.senators.map(senator => `
                    <option value="${senator.id}">${senator.full_name}</option>
                `);
                senatorField.innerHTML = `<option value="">Select a senator</option>${senatorOptions.join('')}`;
            });
    }

