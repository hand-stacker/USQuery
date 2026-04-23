const congressField = document.getElementById('id_congress');
const chamberField = document.getElementById('id_chamber');
const stateField = document.getElementById('id_state');

// Listen for form changes
congressField.addEventListener('change', updateMembersList);
chamberField.addEventListener('change', updateMembersList);
stateField.addEventListener('change', updateMembersList);

// On initial load, if congress is not selected, set it to 119 and load members
document.addEventListener('DOMContentLoaded', function() {
    if (!congressField.value) {
        // Select the 119th congress by default
        const options = congressField.querySelectorAll('option');
        for (let option of options) {
            if (option.textContent.includes('119')) {
                congressField.value = option.value;
                break;
            }
        }
    }
    
    // If congress is now selected and chamber is selected, load members
    if (congressField.value && chamberField.value) {
        updateMembersList();
    }
});

function updateMembersList() {
    const congressId = congressField.value;
    const chamber = chamberField.value;
    const state = stateField.value || 'All';
    
    // Don't fetch if congress or chamber are not selected
    if (!congressId || !chamber) {
        document.getElementById('members-list').innerHTML = '';
        document.getElementById('members-empty').classList.remove('d-none');
        return;
    }
    
    const url = `get-filtered/${congressId}/${chamber}/${state}/`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            renderMembersList(data.members);
        })
        .catch(error => {
            console.error('Error fetching members:', error);
            document.getElementById('members-list').innerHTML = '';
            document.getElementById('members-empty').classList.remove('d-none');
        });
}

function renderMembersList(members) {
    const membersList = document.getElementById('members-list');
    const emptyMessage = document.getElementById('members-empty');
    
    if (members.length === 0) {
        membersList.innerHTML = '';
        emptyMessage.classList.remove('d-none');
        return;
    }
    
    emptyMessage.classList.add('d-none');
    
    membersList.innerHTML = members.map(member => createMemberCardHTML(member, true)).join('');
    
    // Initialize lazy loading for the newly rendered images
    initializeLazyLoad('#members-list', {
        bufferPx: 500
    });
}