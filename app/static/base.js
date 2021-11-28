(function () {
    document.addEventListener('DOMContentLoaded', set_vw)
    window.addEventListener('resize', set_vw)
    window.addEventListener('orientationchange', set_vw)
    set_vw()

    function set_vw() {
        let vw = document.documentElement.clientWidth / 100
        document.documentElement.style.setProperty('--vw', `${vw}px`)
    }

    let detect = new MobileDetect(window.navigator.userAgent)

    let link = document.createElement('link')
    link.rel  = 'stylesheet';
    link.type = 'text/css';
    link.media = 'all';

    if (detect.mobile()) {
        link.href = '/app/static/main/phone.css'
    } else {
        link.href = '/app/static/main/desktop.css'
    }

    document.head.append(link)

})()



