const congressField = document.getElementById('id_congress');
const representativeField = document.getElementById('id_representative');

congressField.addEventListener('change', updateRepChoices);
function updateRepChoices() {
    const congressId = congressField.value;
    const url = `update-reps/${congressId}/`;

    fetch(url)
            .then(response => console.log(response.status) || response.json())
            .then(data => {
                const representativeOptions = data.representatives.map(representative => `
                    <option value="${representative.id}">${representative.full_name}</option>
                `);
                representativeField.innerHTML = `<option value="">Select a representative</option>${representativeOptions.join('')}`;
            });
}