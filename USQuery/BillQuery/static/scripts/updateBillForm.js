const congressField = document.getElementById('id_congress');
const typeField = document.getElementById('id_bill_type_2');
const subField = document.getElementById('id_bill_subjects');
const numField = document.getElementById('id_bill_num');

congressField.addEventListener('change', updateChoices);
typeField.addEventListener('change', updateChoices);
subField.addEventListener('change', updateChoices);
function getSelectedValues(selectElement) {
    return Array.from(selectElement.selectedOptions).map(option => option.value);
}

document.addEventListener("DOMContentLoaded", function () {
    const selectElement = document.querySelector("#id_bill_subjects");

    if (selectElement) {
        new TomSelect(selectElement, {
            plugins: ["remove_button"],
            persist: false,
            create: false,
            maxItems: null,
            searchField: "text",
            closeAfterSelect: false,
        });
    }
});
function updateChoices() {
    const congressId = congressField.value;
    if (congressId == '') { return; }
    var type_2 = typeField.value;
    var subjects = getSelectedValues(subField);
    var url = `update-bills/${congressId}?type_2=${type_2}&subjects=${subjects}`;
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const billOptions = data.bills.map(bill => `
                    <option value="${bill.id}">${bill.str}</option>
                `);
            numField.innerHTML = `<option value="">Select a bill</option>${billOptions.join('')}`;
        });
}

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('id_BillForm');
    if (form) {
        form.addEventListener('submit', function (e) {
            // List the IDs of the fields to clear
            ['id_bill_subjects', 'id_bill_type_2'].forEach(function (fieldId) {
                const field = document.getElementById(fieldId);
                if (field) {
                    // For multi-select, deselect all options
                    if (field.multiple) {
                        Array.from(field.options).forEach(option => option.selected = false);
                    } else {
                        field.value = '';
                    }
                }
            });
        });
    }
});