(function () {
    document.addEventListener('DOMContentLoaded', set_vw)
    window.addEventListener('resize', set_vw)
    window.addEventListener('orientationchange', set_vw)
    set_vw()

    function set_vw() {
        let vw = document.documentElement.clientWidth / 100
        document.documentElement.style.setProperty('--vw', `${vw}px`)
    }
})()


