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
    
    membersList.innerHTML = members.map(member => {
        const chamber = member.house ? 'House+of+Representatives' : 'Senate';
        const memberURL = `/member-query/results/?congress=119&member=${member.member_id}&chamber=${chamber}`;
        const districtText = member.house && member.district_num ? ` - District ${member.district_num}` : '';
        const imageSrc = member.image_link && member.image_link !== 'empty' ? member.image_link : '';
        
        return `
            <div class="col-md-4 mb-4">
                <a href="${memberURL}" class="starred-item text-decoration-none">
                    <div class="starred-member-card" style="cursor: pointer;">
                        ${imageSrc ? `<img src="${imageSrc}" alt="${member.name}" class="starred-member-image" onerror="this.style.display='none'">` : `<div class="starred-member-image" style="display: flex; align-items: center; justify-content: center; background: rgba(150, 150, 150, 0.3);"><span style="color: rgba(250, 250, 250, 0.5);">No Image</span></div>`}
                        <div class="starred-member-name">${member.name}</div>
                        <div class="starred-member-info">
                            <div>${member.party}</div>
                            <div class="starred-member-location">
                                ${member.state}${districtText}
                            </div>
                            <div style="font-size: 11px; color: rgba(250, 250, 250, 0.5); margin-top: 6px;">
                                ${member.house ? 'House' : 'Senate'}
                            </div>
                        </div>
                    </div>
                </a>
            </div>
        `;
    }).join('');
}