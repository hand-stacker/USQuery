var w = document.documentElement.clientWidth;
var site_width = 0;
var half_image_width = 0;
var graph_scale = 0.6;

const width_buckets = [280, 320, 340, 360, 380, 400, 440, 480, 500, 550, 600, 640, 768, 840, 1000, 1200, 1400, 2000, 3000, 4000];


const debounce = (func, wait, immediate) => {
    var timeout;
    return () => {
        var context = this, args = this.arguments;
        var later = function () {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
};

const updateWidth = () => {
    w = document.documentElement.clientWidth;
    let indx = 0;
    while (indx < width_buckets.length && width_buckets[indx + 1] < w) {
        indx++;
    }
    if (width_buckets[indx] == site_width) return;
    site_width = width_buckets[indx];
    if (site_width < 840) {
        graph_scale = 0.8;
    }
    else {
        graph_scale = 0.6;
    }
    makeHist();
    makeHist2();
}
window.addEventListener('orientationchange', updateWidth, false);
window.addEventListener('resize', debounce(updateWidth, 200), false)