document.addEventListener('DOMContentLoaded', set_vw)
// window.addEventListener('resize', set_vw)
window.addEventListener('orientationchange', set_vw)


document.addEventListener("DOMContentLoaded", top_footer)
window.addEventListener('resize', top_footer)
window.addEventListener("orientationchange", top_footer)
window.addEventListener("change", top_footer)

document.addEventListener("DOMContentLoaded", main_block_height)
window.addEventListener('resize', main_block_height)
window.addEventListener("orientationchange", main_block_height)
window.addEventListener("change", main_block_height)

// window.addEventListener('resize', generate_upper)
window.addEventListener("orientationchange", generate_upper)
document.addEventListener("DOMContentLoaded", generate_upper)


document.addEventListener('DOMContentLoaded', function() {
    $('.slider__control_prev').each(function (index, element) {
        element.click()
    })
    // setTimeout(function() {
    //     $('.slider__control_next').each(function (index, element) {
    //         element.click()
    //     })
    // }, 1000)
})


setInterval(top_footer, 1)

set_vw()
detected_phone()
main_block_height()

document.addEventListener('scroll', buttons_position)

let buttons = document.getElementById('navigation_buttons')
let el = document.createElement('div')
el.setAttribute('id', 'for_nav_btns')
el.style.height = '0'

buttons.after(el)

let footer_2
function set_vw() {
    let vw = document.documentElement.clientWidth / 100,
        vh = document.documentElement.clientHeight / 100
    document.documentElement.style.setProperty('--vw', `${vw}px`)
    document.documentElement.style.setProperty('--vh', `${vh}px`)
}
document.addEventListener('DOMContentLoaded', function () {
    footer_2 = document.getElementById('footer').cloneNode(true)
    document.getElementById('footer').after(footer_2)
    footer_2.setAttribute('id', 'footer-2')
    footer_2.style.display = 'block'
    footer_2.style.visibility = 'hidden'
    footer_2.style.zIndex = '-1000'
    footer_2.style.position = 'absolute'
})

function top_footer() {
    // делает подвал плавающим(я думаю, что это какой-то костыль)
    let footer = $('#footer')
    if (!footer) return

    let footer_height = footer.outerHeight(),
        footer_top = footer.css('margin-top').slice(0, -2)

    if (document.documentElement.clientHeight > $('#upper_container').outerHeight() + $('#main_block').outerHeight() + footer_height + +footer_top) {
        footer_2.style.top = document.documentElement.clientHeight - footer_height - footer_top + 'px'
        footer_2.style.visibility = 'visible'
        footer_2.style.zIndex = '1'
        footer.css({'visibility': 'hidden',
            'z-index': '-1000'})
    } else {
        footer.css({
            'visibility': 'visible',
            'z-index': '1',
            // 'bottom': '0'
        })
        try {
            footer_2.style.visibility = 'hidden'
            footer_2.style.zIndex = '-1000'
        } catch (e) {

        }
    }
}

let butt = document.getElementById('navigation_buttons')
butt.style.boxSizing = 'border-box'
let bottom_coord =  butt.offsetTop + butt.offsetHeight

function buttons_position() {
    // оставляет навигационные кнопки на верху экарана
    let buttons = document.getElementById('navigation_buttons')

    buttons.style.boxSizing = 'border-box'

    let el = document.getElementById('for_nav_btns')

    if (document.documentElement.scrollTop <= el.offsetTop) {
        buttons.style.position = 'relative'
        buttons.style.margin = 'auto'

        el.style.height = '0'
        el.style.width = '0'

        if (generate_upper.type == 'desktop') {
            el.style.minWidth = '0'
        }
    }

    if (buttons.offsetTop < document.documentElement.scrollTop) {

        buttons.style.position = 'fixed'
        buttons.style.top = buttons.style.left = buttons.style.right = '0'

        el.style.height = buttons.offsetHeight + 'px'
        el.style.width = buttons.offsetWidth + 'px'
        if (generate_upper.type == 'desktop') {
            el.style.minWidth = 360 + 'px'
        }
    }

}

generate_upper.type = null
function generate_upper(event) {
    // функция для генерации нужной шапки в зависимости от разрешения экрана
    if (document.documentElement.clientWidth < 900) {
        generate_mobile_upper()
        generate_upper.type = 'mobile'
        console.log('mobile')
    } else {
        generate_desktop_upper()
        generate_upper.type = 'desktop'
        console.log('desk')
    }
}


function generate_mobile_upper() {
    // шапка переделвывается в мобильную версию
    let phone_numbers = document.getElementById('phone_numbers'),
        block_info = document.getElementById('upper_block_info'),
        navigation_buttons = document.getElementById('navigation_buttons'),
        upper = document.getElementById('upper'),
        logo = document.getElementById('block_logo')

    logo.style.width = block_info.style.width = '50%'
    // navigation_buttons.style.width = '100%'

    phone_numbers.style.flexDirection = 'row'

    block_info.style.flexDirection =
        block_info.firstElementChild.style.flexDirection = 'column'

    block_info.firstElementChild.style.alignItems = 'center'
    block_info.firstElementChild.lastElementChild.innerHTML =
        block_info.firstElementChild.lastElementChild.innerHTML.slice(0)


    // navigation_buttons.style.paddingBottom = '12px'
    document.getElementById('main_block').style.marginTop = 12 + 'px'

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

    // phone_numbers.style.display = 'none'
}

function generate_desktop_upper() {
    // шапка переделывается в десктопную версию
    let phone_numbers = document.getElementById('phone_numbers'),
        block_info = document.getElementById('upper_block_info'),
        navigation_buttons = document.getElementById('navigation_buttons'),
        upper = document.getElementById('upper'),
        logo = document.getElementById('block_logo')

    phone_numbers.style.display = 'flex'
    block_info.append(phone_numbers)

    phone_numbers.style.flexDirection = 'column'
    block_info.firstElementChild.style.flexDirection = 'column'
    navigation_buttons.style.flexDirection = 'column'
    block_info.firstElementChild.style.alignItems = 'center'

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
            document.documentElement.style.setProperty('--primary-font-size', `16px`)
        } else if (detect.tablet()) {
            add_css_file('/app/static/main/desktop.css')
            document.documentElement.style.setProperty('--primary-font-size', `20px`)
        }
    } else {
        add_css_file('/app/static/main/desktop.css')
        add_js_file('/app/static/base_desktop.js')
        document.documentElement.style.setProperty('--primary-font-size', `24px`)
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // делает всю область кнопки в выпадающем меню кликабельной
    let categories = $('#services-modal-win').find('.submenu-item')
    categories.each(function () {
        $(this).click(function () {
            window.location = $(this).find('a').attr('href')
        })
    })
})

function main_block_height() {
    // если main блок по высоте не достаёт до подвала,
    // то он увеличивается
    let main_block = $('#main_block'),
        footer = $('#footer'),
        upper = $('#upper_container')

    if (upper.outerHeight(true) + main_block.outerHeight(true) < $(window).height()) {
        let height

        console.log(footer.outerHeight())

        height = $(window).height() - footer.outerHeight() * 2 - upper.outerHeight(true)

        main_block.css({'min-height': height + 'px'})
    } else {
        main_block.css({'min-height': '0'})
    }
}



let months = ['Января', 'Февраля', 'Марта', 'Апреля', 'Мая', 'Июня', 'Июля',
    'Августа', 'Сентября', 'Октября', 'Ноября', 'Декабря']

document.addEventListener('DOMContentLoaded', function () {
    $('.event_date').each(function (index, element) {
        let content = element.innerHTML

        content += ' ' + months[element.getAttribute(
            'data-date-month') - 1]

        element.innerHTML = content
    })
})

function copy_number(number, el) {
    let tmp = $("<textarea>");
    $("body").append(tmp);
    tmp.val(number).select();
    document.execCommand("copy");
    tmp.remove();

    el.setAttribute('title', 'Скопировано')

    el.onmouseover = function() {
        el.setAttribute('title', 'Нажмите, чтобы скопировать')
    }
}

document.addEventListener('click', function () {
    let slider_items = $('#event_items'),
        slider_item_active = slider_items.find('.slider__item_active')

    slider_items.css({'height': slider_item_active.outerHeight() + 'px'}, 1000)
})

document.addEventListener('DOMContentLoaded', function () {
    let slider_items = $('#event_items'),
        slider_item_active = slider_items.find('.slider__item_active')

    setTimeout(function () {slider_items.css({'height': slider_item_active.outerHeight() + 'px'}, 1000)},
        100)
})
