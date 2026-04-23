/**
 * Card Utility Functions
 * Provides reusable functions for card-based UI components
 */

// Create a dark card container
function createDarkCard(content, className = '', attributes = {}) {
    const card = document.createElement('div');
    card.className = `card-dark ${className}`;
    card.innerHTML = content;
    
    Object.entries(attributes).forEach(([key, value]) => {
        card.setAttribute(key, value);
    });
    
    return card;
}

// Create a small dark card container
function createSmallDarkCard(content, className = '', attributes = {}) {
    const card = document.createElement('div');
    card.className = `card-dark-sm ${className}`;
    card.innerHTML = content;
    
    Object.entries(attributes).forEach(([key, value]) => {
        card.setAttribute(key, value);
    });
    
    return card;
}

// Add hover effect to cards
function addCardHoverEffect(cardElement) {
    cardElement.style.transition = 'all 0.2s ease';
    
    cardElement.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-2px)';
        this.style.boxShadow = '0 6px 40px rgba(0, 0, 0, 0.15)';
    });
    
    cardElement.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
        this.style.boxShadow = '0 12px 30px rgba(0, 0, 0, 0.18)';
    });
}

// Create a glass button
function createGlassButton(text, iconClass = '', onClick = null, disabled = false, href = null) {
    const button = href ? document.createElement('a') : document.createElement('button');
    button.className = 'btn-glass';
    button.disabled = disabled;
    
    if (href) {
        button.href = href;
    }
    
    if (onClick && !href) {
        button.addEventListener('click', onClick);
    }
    
    let buttonHTML = '';
    if (iconClass) {
        buttonHTML += `<i class="${iconClass}"></i>`;
    }
    buttonHTML += text;
    
    button.innerHTML = buttonHTML;
    
    return button;
}

// Create a featured section header
function createSectionHeader(title, iconClass = '') {
    const header = document.createElement('div');
    header.className = 'mb-4';
    
    let headerHTML = `<h3 class="d-flex align-items-center">`;
    if (iconClass) {
        headerHTML += `<i class="${iconClass} me-2"></i>`;
    }
    headerHTML += title + '</h3>';
    
    header.innerHTML = headerHTML;
    return header;
}

// Shared member card HTML. lazyLoad=true uses data-src (deferred), false uses src (immediate).
function createMemberCardHTML(member, lazyLoad = false) {
    const chamber = member.house ? 'House+of+Representatives' : 'Senate';
    const memberURL = `/member-query/results/?congress=119&member=${member.member_id}&chamber=${chamber}`;
    const districtText = member.house && member.district_num ? `-${member.district_num}` : '';
    const imageSrc = member.image_link && member.image_link !== 'empty' ? member.image_link : '';
    const imgAttr = lazyLoad ? `data-src="${imageSrc}"` : `src="${imageSrc}"`;
    const activeDotHTML = member.is_active ? '<span class="member-active-dot"></span>' : '';

    const imageInnerHTML = imageSrc
        ? `<img ${imgAttr} alt="${member.name}" class="starred-member-image" onerror="this.style.display='none'">`
        : `<div class="starred-member-image starred-member-image--empty"><span>No Image</span></div>`;

    const imageHTML = `<div class="starred-member-image-wrap">${imageInnerHTML}${activeDotHTML}</div>`;

    return `
        <div class="col-md-4 mb-4">
            <a href="${memberURL}" class="starred-item text-decoration-none">
                <div class="starred-member-card">
                    ${imageHTML}
                    <div class="starred-member-body">
                        <div class="starred-member-name">${member.name}</div>
                        <div class="starred-member-info">
                            <span class="subject-tag subject-tag--muted">${member.party}</span>
                            <span class="subject-tag subject-tag--muted">${member.state}${districtText}</span>
                            <span class="subject-tag subject-tag--muted">${member.house ? 'House' : 'Senate'}</span>
                        </div>
                    </div>
                </div>
            </a>
        </div>
    `;
}

// Export functions (for use in modules)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        createDarkCard,
        createSmallDarkCard,
        addCardHoverEffect,
        createGlassButton,
        createSectionHeader,
        createMemberCardHTML
    };
}