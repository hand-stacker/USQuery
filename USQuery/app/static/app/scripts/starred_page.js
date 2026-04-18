// starred_page.js - Load and display starred bills and members with client-side pagination

const ITEMS_PER_PAGE = 10;

// Pagination state
let billsState = {
    currentPage: 0,
    data: [],
    totalPages: 0
};

let membersState = {
    currentPage: 0,
    data: [],
    totalPages: 0
};

// Initialize pagination state
function initializePagination() {
    // Parse JSON from script tags
    const billsScriptElement = document.getElementById('bills_json');
    const membersScriptElement = document.getElementById('members_json');
    
    billsState.data = billsScriptElement ? JSON.parse(billsScriptElement.textContent) : [];
    membersState.data = membersScriptElement ? JSON.parse(membersScriptElement.textContent) : [];
    
    billsState.totalPages = Math.ceil(billsState.data.length / ITEMS_PER_PAGE) || 1;
    membersState.totalPages = Math.ceil(membersState.data.length / ITEMS_PER_PAGE) || 1;
    
    billsState.currentPage = 0;
    membersState.currentPage = 0;
}

// Extract bill type URL from bill ID
function getBillTypeURL(billId) {
    let typeCode;
    if (billId >= 100000000) {
        typeCode = Math.floor((billId % 1000000) / 100000);
    } else {
        typeCode = Math.floor((billId % 100000) / 10000);
    }
    
    const typeMap = {
        0: 's',
        1: 'sres',
        2: 'sjres',
        3: 'sconres',
        4: 'hr',
        5: 'hres',
        6: 'hjres',
        7: 'hconres'
    };
    return typeMap[typeCode] || 'hr';
}

// Extract bill number from bill ID
function getBillNum(billId) {
    if (billId >= 100000000) {
        return billId % 100000;
    }
    return billId % 10000;
}

// Extract congress number from bill ID
function getCongress(billId) {
    if (billId >= 100000000) {
        return Math.floor(billId / 1000000);
    }
    return Math.floor(billId / 100000);
}

// Build bill URL
function getBillURL(billId) {
    const congress = getCongress(billId);
    const typeURL = getBillTypeURL(billId);
    const num = getBillNum(billId);
    return `/bill-query/bill/${congress}/${typeURL}/${num}`;
}

// Build member URL
function getMemberURL(membership) {
    const chamber = membership.house ? 'House+of+Representatives' : 'Senate';
    return `/member-query/results/?congress=119&member=${membership.member_id}&chamber=${chamber}`;
}

// Extract member_id from membership data (membership_id structure varies)
function getMemberId(membership) {
    // The membership data should contain member_id or we need to extract from membership_id
    // Looking at the data structure passed from views, it seems we need the bioguide_id
    // This should be in the member object or we need to track it separately
    return membership.member_id || '';
}

// Render bills for current page
function renderBillsPage() {
    const list = document.getElementById('bills-list');
    const empty = document.getElementById('bills-empty');
    const pagination = document.getElementById('bills-pagination');
    const pageInfo = document.getElementById('bills-page-info');

    if (billsState.data.length === 0) {
        empty.classList.remove('d-none');
        list.innerHTML = '';
        pagination.classList.add('d-none');
        return;
    }

    empty.classList.add('d-none');
    pagination.classList.remove('d-none');

    const start = billsState.currentPage * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const pageItems = billsState.data.slice(start, end);

    list.innerHTML = pageItems.map(bill => {
        const billURL = getBillURL(bill.bill_id);
        const latestActionDate = new Date(bill.latest_action).toLocaleDateString();
        return `
            <div class="col-md-6 mb-4">
                <a href="${billURL}" class="starred-item">
                    <div class="starred-bill-card">
                        <div class="starred-bill-title">${bill.title}</div>
                        <div class="starred-bill-meta">
                            <span>Latest Action:</span>
                            <span class="px-2">${latestActionDate}</span>
                        </div>
                        ${bill.summary ? `<div class="starred-bill-summary">${bill.summary.substring(0, 200)}...</div>` : '<div class="starred-bill-summary">No summary available</div>'}
                    </div>
                </a>
            </div>
        `;
    }).join('');

    pageInfo.textContent = `Page ${billsState.currentPage + 1} of ${billsState.totalPages}`;
    
    document.getElementById('bills-prev').disabled = billsState.currentPage === 0;
    document.getElementById('bills-next').disabled = billsState.currentPage >= billsState.totalPages - 1;
}

// Render members for current page
function renderMembersPage() {
    const list = document.getElementById('members-list');
    const empty = document.getElementById('members-empty');
    const pagination = document.getElementById('members-pagination');
    const pageInfo = document.getElementById('members-page-info');

    if (membersState.data.length === 0) {
        empty.classList.remove('d-none');
        list.innerHTML = '';
        pagination.classList.add('d-none');
        return;
    }

    empty.classList.add('d-none');
    pagination.classList.remove('d-none');

    const start = membersState.currentPage * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const pageItems = membersState.data.slice(start, end);

    list.innerHTML = pageItems.map(member => {
        const chamber = member.house ? 'House+of+Representatives' : 'Senate';
        const memberURL = `/member-query/results/?congress=119&member=${member.member_id}&chamber=${chamber}`;
        const districtText = member.house && member.district_num ? ` - District ${member.district_num}` : '';
        const imageSrc = member.image_link && member.image_link !== 'empty' ? member.image_link : '';
        
        return `
            <div class="col-md-4 mb-4">
                <a href="${memberURL}" class="starred-item">
                    <div class="starred-member-card">
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

    pageInfo.textContent = `Page ${membersState.currentPage + 1} of ${membersState.totalPages}`;
    
    document.getElementById('members-prev').disabled = membersState.currentPage === 0;
    document.getElementById('members-next').disabled = membersState.currentPage >= membersState.totalPages - 1;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializePagination();
    
    // Render initial pages
    renderBillsPage();
    renderMembersPage();

    // Handle bills pagination
    document.getElementById('bills-prev').addEventListener('click', function() {
        if (billsState.currentPage > 0) {
            billsState.currentPage--;
            renderBillsPage();
        }
    });

    document.getElementById('bills-next').addEventListener('click', function() {
        if (billsState.currentPage < billsState.totalPages - 1) {
            billsState.currentPage++;
            renderBillsPage();
        }
    });

    // Handle members pagination
    document.getElementById('members-prev').addEventListener('click', function() {
        if (membersState.currentPage > 0) {
            membersState.currentPage--;
            renderMembersPage();
        }
    });

    document.getElementById('members-next').addEventListener('click', function() {
        if (membersState.currentPage < membersState.totalPages - 1) {
            membersState.currentPage++;
            renderMembersPage();
        }
    });

    // Handle tab switching to reset pagination
    document.getElementById('bills-tab').addEventListener('click', function() {
        billsState.currentPage = 0;
        renderBillsPage();
    });

    document.getElementById('members-tab').addEventListener('click', function() {
        membersState.currentPage = 0;
        renderMembersPage();
    });
});