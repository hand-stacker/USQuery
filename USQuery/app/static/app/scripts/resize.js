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

const updateHeight = () => {
    document.getElementById("action_table").style["height"] = "100px";
    var leftSize = document.getElementById("left-column").offsetHeight;
    var rightOffset = document.getElementById("right-title-space").offsetHeight;
    document.getElementById("action_table").style["height"] = String(leftSize - rightOffset) + "px";
}

updateHeight();
window.addEventListener('orientationchange', updateHeight, false);
window.addEventListener('resize', debounce(updateHeight, 200), false)