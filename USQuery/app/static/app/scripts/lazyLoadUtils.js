/**
 * Lazy Load Utility Functions
 * Provides reusable lazy loading functionality for images and content
 */

/**
 * Initialize lazy loading for images within a container
 * @param {string|HTMLElement} containerSelector - Container element or selector
 * @param {Object} options - Configuration options
 * @param {number} options.bufferPx - Pixels below viewport to start loading (default: 500)
 * @param {string} options.imageSelector - Selector for images to lazy load (default: 'img[data-src]')
 * @param {Function} options.onImageLoad - Callback when image loads
 * @param {Function} options.onImageError - Callback when image fails to load
 * @returns {IntersectionObserver} The observer instance for manual cleanup if needed
 */
function initializeLazyLoad(containerSelector, options = {}) {
    const {
        bufferPx = 500,
        imageSelector = 'img[data-src]',
        onImageLoad = null,
        onImageError = null
    } = options;

    const container = typeof containerSelector === 'string' 
        ? document.querySelector(containerSelector) 
        : containerSelector;

    if (!container) {
        console.warn('Lazy load container not found:', containerSelector);
        return null;
    }

    // Create Intersection Observer with buffer
    const observerOptions = {
        root: null,
        rootMargin: `${bufferPx}px 0px`,
        threshold: 0.01
    };

    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                const src = img.getAttribute('data-src');

                if (src) {
                    img.src = src;
                    img.removeAttribute('data-src');

                    img.addEventListener('load', () => {
                        img.classList.add('lazy-loaded');
                        if (onImageLoad) onImageLoad(img);
                    }, { once: true });

                    img.addEventListener('error', () => {
                        img.classList.add('lazy-error');
                        if (onImageError) onImageError(img);
                    }, { once: true });

                    imageObserver.unobserve(img);
                }
            }
        });
    }, observerOptions);

    // Observe all images in container
    const images = container.querySelectorAll(imageSelector);
    images.forEach(img => imageObserver.observe(img));

    return imageObserver;
}

/**
 * Convert image src to data-src for lazy loading
 * @param {HTMLElement} element - Image element or container
 * @param {string} imageSelector - Selector for images (default: 'img')
 */
function prepareImagesForLazyLoad(element, imageSelector = 'img') {
    const images = element.querySelectorAll ? element.querySelectorAll(imageSelector) : [element];
    
    images.forEach(img => {
        if (img.src && !img.getAttribute('data-src')) {
            img.setAttribute('data-src', img.src);
            img.src = ''; // Clear src to prevent immediate load
        }
    });
}

/**
 * Re-initialize lazy loading after DOM updates (e.g., after rendering new cards)
 * @param {string|HTMLElement} containerSelector - Container element or selector
 * @param {Object} options - Same options as initializeLazyLoad
 * @returns {IntersectionObserver} The observer instance
 */
function reinitializeLazyLoad(containerSelector, options = {}) {
    return initializeLazyLoad(containerSelector, options);
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeLazyLoad,
        prepareImagesForLazyLoad,
        reinitializeLazyLoad
    };
}