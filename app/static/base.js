
detected_phone()

function detected_phone() {
    let detect = new MobileDetect(window.navigator.userAgent)
    let link = document.createElement('link')
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.media = 'all';

    if (detect.mobile()) {

        if (detect.phone()) {
            link.href = '/app/static/main/phone.css'
            generate_mobile_upper()
        } else if (detect.tablet()) {
            link.href = '/app/static/main/desktop.css'
        }
    } else {
        link.href = '/app/static/main/desktop.css'
    }

    document.head.append(link)
}


document.addEventListener('DOMContentLoaded', set_vw)
window.addEventListener('resize', set_vw)
window.addEventListener('orientationchange', set_vw)


document.addEventListener("DOMContentLoaded", top_footer)
window.addEventListener('resize', top_footer)
window.addEventListener("orientationchange", top_footer)
window.addEventListener("change", top_footer)


set_vw()

window.addEventListener('resize', generate_upper)
window.addEventListener("orientationchange", generate_upper)
document.addEventListener("DOMContentLoaded", generate_upper)

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

    if (document.documentElement.scrollTop <= el.offsetTop) {
        el.style.height = '0'
        buttons.style.position = 'relative'
        buttons.style.margin = 'auto'
        //
        let detect = new MobileDetect(window.navigator.userAgent)
        if (detect.mobile()) {
            buttons.style.paddingBottom = '12px'
            buttons.style.marginTop = '5px'
        }
    }

    if (buttons.offsetTop < document.documentElement.scrollTop) {
        el.style.height = window.getComputedStyle(buttons).height
        buttons.style.position = 'fixed'
        buttons.style.top = buttons.style.left = buttons.style.right = '0'
        buttons.style.marginTop = '0'
        buttons.style.paddingBottom = '0'
    }

}

function generate_upper(event) {
    if (document.documentElement.clientWidth < 900)
        generate_mobile_upper()
    else
        generate_desktop_upper()
}


function generate_mobile_upper() {
    let phone_numbers = document.getElementById('phone_numbers'),
        block_info = document.getElementById('upper_block_info'),
        navigation_buttons = document.getElementById('navigation_buttons'),
        upper = document.getElementById('upper')

    block_info.style.flexDirection =
        block_info.firstElementChild.style.flexDirection = 'column'

    block_info.firstElementChild.style.alignItems = 'center'
    block_info.firstElementChild.lastElementChild.innerHTML =
        block_info.firstElementChild.lastElementChild.innerHTML.slice(0)

    document.getElementById('logo').parentElement.style.width =
        block_info.style.width = '50%'

    navigation_buttons.style.paddingBottom = '12px'

    upper.after(document.createElement('div'))
    upper.after(navigation_buttons)
    upper.after(phone_numbers)
    upper.style.justifyContent = 'space-around'

    phone_numbers.style.display = 'none'
}

function generate_desktop_upper() {
    let phone_numbers = document.getElementById('phone_numbers'),
        block_info = document.getElementById('upper_block_info'),
        navigation_buttons = document.getElementById('navigation_buttons'),
        upper = document.getElementById('upper')

    block_info.append(phone_numbers)
    phone_numbers.style.flexDirection =
        block_info.firstElementChild.style.flexDirection = 'row'
    block_info.firstElementChild.style.alignItems = 'left'

    block_info.firstElementChild.lastElementChild.innerHTML = ' ' +
        block_info.firstElementChild.lastElementChild.innerHTML

    navigation_buttons.style.paddingBottom = '0'

    navigation_buttons.nextElementSibling.remove()
    upper.firstElementChild.after(navigation_buttons)
    block_info.style.width = 'max-content'
    navigation_buttons.style.margin = 'auto'
    phone_numbers.style.display = 'flex'
}

