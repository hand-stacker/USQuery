/**
 * Carousel Utility Functions
 * Provides reusable carousel/slider functionality
 */

class SimpleCarousel {
    constructor(containerSelector, options = {}) {
        this.container = document.querySelector(containerSelector);
        this.slides = this.container?.querySelectorAll('.feature-slide') || [];
        this.dots = document.querySelectorAll('.carousel-dot');
        
        this.currentSlide = 0;
        this.slideCount = this.slides.length;
        this.autoAdvanceTimer = null;
        this.autoAdvanceInterval = options.autoAdvanceInterval || 6000;
        this.pauseOnHover = options.pauseOnHover !== false;
        
        if (this.slideCount > 0) {
            this.init();
        }
    }
    
    init() {
        this.attachDotListeners();
        this.setupHoverPause();
        this.startAutoAdvance();
    }
    
    showSlide(index) {
        // Validate and wrap index
        index = ((index % this.slideCount) + this.slideCount) % this.slideCount;
        this.currentSlide = index;
        
        // Hide all slides and deactivate all dots
        this.slides.forEach(slide => slide.classList.remove('active'));
        this.dots.forEach(dot => dot.classList.remove('active'));
        
        // Show current slide and activate current dot
        if (this.slides[this.currentSlide]) {
            this.slides[this.currentSlide].classList.add('active');
        }
        if (this.dots[this.currentSlide]) {
            this.dots[this.currentSlide].classList.add('active');
        }
    }
    
    nextSlide() {
        this.showSlide(this.currentSlide + 1);
        this.resetAutoAdvance();
    }
    
    prevSlide() {
        this.showSlide(this.currentSlide - 1);
        this.resetAutoAdvance();
    }
    
    goToSlide(index) {
        this.showSlide(index);
        this.resetAutoAdvance();
    }
    
    startAutoAdvance() {
        if (this.autoAdvanceTimer) {
            clearInterval(this.autoAdvanceTimer);
        }
        this.autoAdvanceTimer = setInterval(() => this.nextSlide(), this.autoAdvanceInterval);
    }
    
    stopAutoAdvance() {
        if (this.autoAdvanceTimer) {
            clearInterval(this.autoAdvanceTimer);
            this.autoAdvanceTimer = null;
        }
    }
    
    resetAutoAdvance() {
        this.stopAutoAdvance();
        this.startAutoAdvance();
    }
    
    attachDotListeners() {
        this.dots.forEach((dot, index) => {
            dot.addEventListener('click', () => this.goToSlide(index));
        });
    }
    
    setupHoverPause() {
        if (!this.pauseOnHover || !this.container) return;
        
        this.container.addEventListener('mouseenter', () => this.stopAutoAdvance());
        this.container.addEventListener('mouseleave', () => this.startAutoAdvance());
    }
    
    destroy() {
        this.stopAutoAdvance();
        this.dots.forEach(dot => {
            dot.replaceWith(dot.cloneNode(true));
        });
    }
}

// Auto-initialize carousels on DOM load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new SimpleCarousel('.feature-carousel', {
            autoAdvanceInterval: 6000,
            pauseOnHover: true
        });
    });
} else {
    new SimpleCarousel('.feature-carousel', {
        autoAdvanceInterval: 6000,
        pauseOnHover: true
    });
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SimpleCarousel;
}