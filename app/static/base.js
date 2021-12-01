let detect = new MobileDetect(window.navigator.userAgent)
let link = document.createElement('link')
link.rel = 'stylesheet';
link.type = 'text/css';
link.media = 'all';

if (detect.mobile()) {
    link.href = '/app/static/main/phone.css'
} else {
    link.href = '/app/static/main/desktop.css'
}

document.head.append(link)


document.addEventListener('DOMContentLoaded', set_vw)
window.addEventListener('resize', set_vw)
window.addEventListener('orientationchange', set_vw)


document.addEventListener("DOMContentLoaded", top_footer)
window.addEventListener('resize', top_footer)
window.addEventListener("orientationchange", top_footer)


set_vw()



function set_vw() {
    let vw = document.documentElement.clientWidth / 100
    document.documentElement.style.setProperty('--vw', `${vw}px`)
}

function top_footer() {
    let footer = $('#footer')
    if (!footer) return

    let footer_height = footer.outerHeight(),
        footer_top = footer.css('margin-top').slice(0, 2)

    footer.css('display', 'none')
    let height = document.documentElement.scrollHeight < document.documentElement.clientHeight ?
        document.documentElement.clientHeight : document.documentElement.scrollHeight
    footer.css('top', height - footer_height - footer_top + 'px')
    footer.css('display', 'block')
}


document.addEventListener('scroll', buttons_position)

let buttons = document.getElementById('navigation_buttons')
let el = document.createElement('div')
el.style.height = '0'
buttons.after(el)

function buttons_position() {
    let buttons = document.getElementById('navigation_buttons')
    let el = buttons.nextElementSibling


    if(document.documentElement.scrollTop <= el.offsetTop) {
        el.style.height = '0'
        buttons.style.position = 'relative'
    }

    if (buttons.offsetTop < document.documentElement.scrollTop) {
        el.style.height =  window.getComputedStyle(buttons).height
        buttons.style.position = 'fixed'
        buttons.style.top = buttons.style.left = buttons.style.right = '0'
    }
}




