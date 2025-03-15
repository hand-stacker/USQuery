var w = document.documentElement.clientWidth;
var site_width = 0;
var half_image_width = 0;

const width_buckets = [200, 250, 280, 320, 480, 768, 840, 1000, 1400, 2000, 3000, 4000];

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
    while (indx < width_buckets.length && width_buckets[indx+1] < w) {
        indx++;
    }
    if (width_buckets[indx] == site_width) return;
    site_width = width_buckets[indx];
    if (site_width >= 768) {
        half_image_width = site_width / 2;
    }
    else {
        half_image_width = site_width;
    }
    makeDonut();
    makeBurst();
    makeBar()
    makeCloro();
}

window.addEventListener('orientationchange', updateWidth, false);
window.addEventListener('resize', debounce(updateWidth, 200), false)