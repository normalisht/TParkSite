document.addEventListener('DOMContentLoaded', set_vw)
window.addEventListener('resize', set_vw)
window.addEventListener('orientationchange', set_vw)

document.addEventListener("DOMContentLoaded", top_footer)
window.addEventListener('resize', top_footer)
window.addEventListener("orientationchange", top_footer)
window.addEventListener("change", top_footer)

window.addEventListener('resize', generate_upper)
window.addEventListener("orientationchange", generate_upper)
document.addEventListener("DOMContentLoaded", generate_upper)

setInterval(top_footer, 1)

set_vw()
detected_phone()

document.addEventListener('scroll', buttons_position)

let buttons = document.getElementById('navigation_buttons')
let el = document.createElement('div')
el.setAttribute('id', 'for_nav_btns')
el.style.height = '0'

buttons.after(el)


function set_vw() {
    let vw = document.documentElement.clientWidth / 100
    document.documentElement.style.setProperty('--vw', `${vw}px`)
}

let footer_2 = document.getElementById('footer').cloneNode(true)
document.getElementById('footer').after(footer_2)
footer_2.setAttribute('id', 'footer-2')
footer_2.style.display = 'block'
footer_2.style.visibility = 'hidden'
footer_2.style.zIndex = '-1000'
footer_2.style.position = 'absolute'

function top_footer() {
    let footer = $('#footer')
    if (!footer) return

    let footer_height = footer.outerHeight(),
        footer_top = footer.css('margin-top').slice(0, 2)

    if (document.documentElement.clientHeight > footer.offset().top + footer_height + footer_top) {
        footer_2.style.top = document.documentElement.clientHeight - footer_height - footer_top + 'px'
        footer_2.style.visibility = 'visible'
        footer_2.style.zIndex = '1'
        footer.css({'visibility': 'hidden',
            'z-index': '-1000'})
    } else {
        footer.css({'visibility': 'visible',
            'z-index': '1'})
        footer_2.style.visibility = 'hidden'
        footer_2.style.zIndex = '-1000'
    }
}

let butt = document.getElementById('navigation_buttons')
butt.style.boxSizing = 'border-box'
let bottom_coord =  butt.offsetTop + butt.offsetHeight

function buttons_position() {
    let buttons = document.getElementById('navigation_buttons')

    buttons.style.boxSizing = 'border-box'

    let el = document.getElementById('for_nav_btns')
    // let bottom_coord = buttons.offsetTop + buttons.offsetHeight
    let  padding_top = 0, padding_bottom = 0

    if (document.documentElement.scrollTop <= el.offsetTop) {
        buttons.style.position = 'relative'
        buttons.style.margin = 'auto'

        if (generate_upper.type == 'mobile') {

            if (12 - document.documentElement.scrollTop + bottom_coord > 0)
                padding_bottom = Math.min(12 - document.documentElement.scrollTop + bottom_coord, 12)
            else padding_bottom = 0

            if (document.documentElement.scrollTop + 5 - buttons.offsetTop > 0)
                padding_top = Math.min(document.documentElement.scrollTop + 5 - buttons.offsetTop, 5)
            else padding_top = 5

            buttons.style.paddingBottom = '12px'
            buttons.style.paddingTop = 0 + 'px'
            el.style.height = '0'
            el.style.paddingBottom = '0'
        }
    }

    if (buttons.offsetTop < document.documentElement.scrollTop) {

        if (generate_upper.type == 'mobile') {
            el.style.height = buttons.offsetHeight + 'px'
        }
        buttons.style.position = 'fixed'
        buttons.style.top = buttons.style.left = buttons.style.right = '0'

        if (12 - document.documentElement.scrollTop + bottom_coord > 0)
            padding_bottom = Math.min(12 - document.documentElement.scrollTop + bottom_coord, 12)
        else padding_bottom = 0

        if (document.documentElement.scrollTop + 5 - buttons.scrollTop > 0)
            padding_top = Math.min(document.documentElement.scrollTop + 5 - buttons.offsetTop, 5)
        else padding_top = 0

        buttons.style.paddingBottom = padding_bottom + 'px'
        buttons.style.paddingTop = '0px'
    }
}

generate_upper.type = null
function generate_upper(event) {
    if (document.documentElement.clientWidth < 900) {
        generate_mobile_upper()
        generate_upper.type = 'mobile'
    } else {
        generate_desktop_upper()
        generate_upper.type = 'desktop'
    }
}


function generate_mobile_upper() {
    let phone_numbers = document.getElementById('phone_numbers'),
        block_info = document.getElementById('upper_block_info'),
        navigation_buttons = document.getElementById('navigation_buttons'),
        upper = document.getElementById('upper'),
        logo = document.getElementById('block_logo')

    logo.style.width = block_info.style.width = '50%'
    navigation_buttons.style.width = '100%'

    block_info.style.flexDirection =
        block_info.firstElementChild.style.flexDirection = 'column'

    block_info.firstElementChild.style.alignItems = 'center'
    block_info.firstElementChild.lastElementChild.innerHTML =
        block_info.firstElementChild.lastElementChild.innerHTML.slice(0)


    navigation_buttons.style.paddingBottom = '12px'

    let el
    if (!document.getElementById('for_nav_btns')) {
        el = document.createElement('div')
        el.setAttribute('id', 'for_nav_btns')
    }

    upper.after(document.getElementById('for_nav_btns') ?
        document.getElementById('for_nav_btns') : el)
    upper.after(navigation_buttons)
    upper.after(phone_numbers)
    upper.style.justifyContent = 'space-around'

    phone_numbers.style.display = 'none'
}

function generate_desktop_upper() {
    let phone_numbers = document.getElementById('phone_numbers'),
        block_info = document.getElementById('upper_block_info'),
        navigation_buttons = document.getElementById('navigation_buttons'),
        upper = document.getElementById('upper'),
        logo = document.getElementById('block_logo')

    phone_numbers.style.display = 'flex'
    block_info.append(phone_numbers)

    phone_numbers.style.flexDirection =
        block_info.firstElementChild.style.flexDirection = 'row'
    block_info.firstElementChild.style.alignItems = 'left'

    block_info.firstElementChild.lastElementChild.innerHTML = ' ' +
        block_info.firstElementChild.lastElementChild.innerHTML

    navigation_buttons.style.paddingBottom = '0'

    upper.firstElementChild.after(document.getElementById('for_nav_btns'))
    upper.firstElementChild.after(navigation_buttons)
    navigation_buttons.style.margin = 'auto'
    block_info.style.width = logo.style.width = 100 / 3 + '%'
}

function add_css_file(path) {
    let link = document.createElement('link')
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.media = 'all';
    link.href = path
    document.head.append(link)
}

function add_js_file(path) {
    let script = document.createElement('script')
    script.type = 'text/javascript'
    script.defer = true
    script.src = path
    document.head.append(script)
}

function detected_phone() {
    let detect = new MobileDetect(window.navigator.userAgent)


    if (detect.mobile()) {

        if (detect.phone()) {
            add_css_file('/app/static/main/phone.css')
            generate_mobile_upper()
        } else if (detect.tablet()) {
            add_css_file('/app/static/main/desktop.css')
        }
    } else {
        add_css_file('/app/static/main/desktop.css')
        add_js_file('/app/static/base_desktop.js')
    }
}
