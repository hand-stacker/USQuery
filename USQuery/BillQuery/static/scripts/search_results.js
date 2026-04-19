// search_results.js - Display bill search results with proper client-side pagination

const ITEMS_PER_PAGE = 10;

// Global pagination state
let billsState = {
    currentPage: 0,
    data: [],
    totalPages: 0,
    totalResults: 0
};

let selectedSubjects = [];

// Initialize pagination state
function initializePagination() {
    // Parse JSON from script tags
    const billsScriptElement = document.getElementById('bills_json');
    const selectedSubjectsElement = document.getElementById('selected_subjects_json');
    
    billsState.data = billsScriptElement ? JSON.parse(billsScriptElement.textContent) : [];
    selectedSubjects = selectedSubjectsElement ? JSON.parse(selectedSubjectsElement.textContent) : [];
    
    // Calculate total pages based on ALL results (from server pagination context)
    billsState.totalResults = TOTAL_RESULTS;
    billsState.totalPages = Math.ceil(TOTAL_RESULTS / ITEMS_PER_PAGE);
    
    // Get current page from URL parameters, default to 1 (global page 1)
    const urlParams = new URLSearchParams(window.location.search);
    const serverPage = parseInt(urlParams.get('page')) || 1;
    
    // Convert server page (1-indexed, 50 items per page) to global page (0-indexed, 10 items per page)
    const firstItemIndex = (serverPage - 1) * 50;
    billsState.currentPage = Math.floor(firstItemIndex / ITEMS_PER_PAGE);
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

// Update pagination button states based on current page
function updatePaginationButtons() {
    const firstBtn = document.getElementById('bills-first');
    const prevBtn = document.getElementById('bills-prev');
    const nextBtn = document.getElementById('bills-next');
    const lastBtn = document.getElementById('bills-last');
    
    const firstItem = document.getElementById('bills-first-item');
    const prevItem = document.getElementById('bills-prev-item');
    const nextItem = document.getElementById('bills-next-item');
    const lastItem = document.getElementById('bills-last-item');
    
    // Disable first/prev at start
    if (billsState.currentPage === 0) {
        firstBtn.disabled = true;
        prevBtn.disabled = true;
        firstItem.classList.add('disabled');
        prevItem.classList.add('disabled');
    } else {
        firstBtn.disabled = false;
        prevBtn.disabled = false;
        firstItem.classList.remove('disabled');
        prevItem.classList.remove('disabled');
    }
    
    // Disable next/last at end
    if (billsState.currentPage >= billsState.totalPages - 1) {
        nextBtn.disabled = true;
        lastBtn.disabled = true;
        nextItem.classList.add('disabled');
        lastItem.classList.add('disabled');
    } else {
        nextBtn.disabled = false;
        lastBtn.disabled = false;
        nextItem.classList.remove('disabled');
        lastItem.classList.remove('disabled');
    }
}

// Render bills for current page
function renderBillsPage() {
    const list = document.getElementById('bills-list');
    const empty = document.getElementById('bills-empty');
    const pagination = document.getElementById('bills-pagination');
    const pageInfo = document.getElementById('bills-page-info');

    if (billsState.data.length === 0 && billsState.totalResults === 0) {
        empty.classList.remove('d-none');
        list.innerHTML = '';
        pagination.classList.add('d-none');
        return;
    }

    empty.classList.add('d-none');
    pagination.classList.remove('d-none');

    // Calculate which bills to show based on global page number
    const start = billsState.currentPage * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    
    // Calculate which server page we need to be on
    const serverPageNeeded = Math.floor(start / 50) + 1;
    const currentServerPage = CURRENT_SERVER_PAGE;
    
    // If we need a different server page, navigate to it
    if (serverPageNeeded !== currentServerPage) {
        // Build URL to the correct server page
        let newUrl = (URL_PARAMS + `page=${serverPageNeeded}`).replaceAll("amp;", "");
        window.location.href = `?${newUrl}`;
        return;
    }
    
    // Now calculate position within current server page's data
    const positionInServerPage = start % 50;
    const positionEnd = positionInServerPage + ITEMS_PER_PAGE;
    const pageItems = billsState.data.slice(positionInServerPage, positionEnd);

    list.innerHTML = pageItems.map(bill => {
        const billURL = getBillURL(bill.bill_id);
        const latestActionDate = bill.latest_action 
            ? new Date(bill.latest_action).toLocaleDateString() 
            : 'N/A';
        
        // Render matching subjects horizontally
        const subjectsHtml = bill.subjects && bill.subjects.length > 0
            ? `<div class="search-bill-subjects">
                <div class="subjects-scroll">
                    ${bill.subjects.map(subject => 
                        `<span class="subject-tag">${subject.name}</span>`
                    ).join('')}
                </div>
            </div>`
            : '';

        return `
            <div class="col-md-6 mb-4">
                <a href="${billURL}" class="starred-item">
                    <div class="starred-bill-card">
                        <div class="starred-bill-title">${bill.title}</div>
                        <div class="starred-bill-meta">
                            <span>Latest Action:</span>
                            <span class="px-2">${latestActionDate}</span>
                        </div>
                        ${subjectsHtml}
                    </div>
                </a>
            </div>
        `;
    }).join('');

    // Update page info - show the GLOBAL page number
    pageInfo.textContent = `Page ${billsState.currentPage + 1} of ${billsState.totalPages}`;
    
    // Update button states
    updatePaginationButtons();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializePagination();
    
    // Render initial page
    renderBillsPage();

    // Handle pagination button clicks
    document.getElementById('bills-first').addEventListener('click', function() {
        billsState.currentPage = 0;
        renderBillsPage();
        window.scrollTo(0, 0);
    });

    document.getElementById('bills-prev').addEventListener('click', function() {
        if (billsState.currentPage > 0) {
            billsState.currentPage--;
            renderBillsPage();
            window.scrollTo(0, 0);
        }
    });

    document.getElementById('bills-next').addEventListener('click', function() {
        if (billsState.currentPage < billsState.totalPages - 1) {
            billsState.currentPage++;
            renderBillsPage();
            window.scrollTo(0, 0);
        }
    });

    document.getElementById('bills-last').addEventListener('click', function() {
        billsState.currentPage = billsState.totalPages - 1;
        renderBillsPage();
        window.scrollTo(0, 0);
    });
});


