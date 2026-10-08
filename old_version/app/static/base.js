document.addEventListener('DOMContentLoaded', set_vw)
window.addEventListener('orientationchange', set_vw)

window.addEventListener("orientationchange", generate_upper)
// window.addEventListener('resize', generate_upper)
document.addEventListener("DOMContentLoaded", generate_upper)

document.addEventListener('DOMContentLoaded', function () {
    $('.slider__control_prev').each(function (index, element) {
        element.click()
    })

    $('#container_base').css('opacity', 1)
    $('#footer').css('opacity', 1)

    back_button()
})

set_vw()
detected_phone()

window.addEventListener('resize', function() {
    set_vw()
})


let buttons = document.getElementById('navigation_buttons')
let el = document.createElement('div')
el.setAttribute('id', 'for_nav_btns')
el.style.height = '0'


function set_vw() {
    let vw = document.documentElement.clientWidth / 100,
        vh = document.documentElement.clientHeight / 100
    document.documentElement.style.setProperty('--vw', `${vw}px`)
    document.documentElement.style.setProperty('--vh', `${vh}px`)
}

generate_upper.type = null

function generate_upper(event) {
    // функция для генерации нужной шапки в зависимости от разрешения экрана
    if (document.documentElement.clientWidth < 900) {
        generate_mobile_upper()
        generate_upper.type = 'mobile'
        console.log('mobile')
    } else {
        // generate_desktop_upper()
        // window.addEventListener('resize', set_vw)
        // generate_upper.type = 'desktop'
        // console.log('desk')
    }
}


function generate_mobile_upper() {

}

function generate_desktop_upper() {
    // шапка переделывается в десктопную версию
    let phone_numbers = $('#phone_numbers'),
        block_info = $('#upper_block_info'),
        navigation_buttons = $('#navigation_buttons'),
        upper = $('#upper'),
        logo = $('#block_logo')

    phone_numbers.css('display', 'flex')
    block_info.append(phone_numbers)

    block_info.children().first().css({
        'flex-direction': 'column',
        'align-items': 'center',
    })

    navigation_buttons.css({
        'flex-direction': 'column',
        'padding-bottom': 0, 'margin': 'auto'
    })

    block_info.find('#dmitry').html(block_info.find('#dmitry').html() + '<span>&nbsp;</span></span>')

    upper.children().first().after($('#for_nav_btns'))
    upper.children().first().after(navigation_buttons)

    logo.css('width', 'calc(100% / 3)')
    block_info.css('width', 'calc(100% / 3)')

    setTimeout(function () {
        phone_numbers.css({
            'flex-direction' : 'column',
            'width':  block_info.find('.name').outerWidth() + 'px'
        })
    }, 50)
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
            // generate_mobile_upper()
            document.documentElement.style.setProperty('--primary-font-size', `14px`)
        } else if (detect.tablet()) {
            add_css_file('/app/static/main/desktop.css')
            document.documentElement.style.setProperty('--primary-font-size', `14px`)
        }
    } else {
        add_css_file('/app/static/main/desktop.css')
        add_js_file('/app/static/base_desktop.js')
        document.documentElement.style.setProperty('--primary-font-size', `16px`)
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

document.addEventListener('click', function () {
    let slider_items = $('#event_items'),
        slider_item_active = slider_items.find('.slider__item_active')

    slider_items.css({'height': slider_item_active.outerHeight() + 'px'}, 1000)
})


window.addEventListener('load', function () {
    let slider_items = $('#event_items'),
        slider_item_active = slider_items.find('.slider__item_active')

    slider_items.css({'height': slider_item_active.outerHeight() + 'px'}, 1000)

    slider_items.find('.slider__item').each(function () {
        let name_event = $(this).find('.event_name')
        name_event.css({'top': $(this).find('.slider__img').outerHeight(true) - name_event.outerHeight() + 'px'})
    })
})

function back_button() {
    let detect = new MobileDetect(window.navigator.userAgent)
    if (detect.mobile()) {
        let scrollPos = 0,
            bb_status = true,
            bb = $('#back_button')
            // bb_2 = $('#back_button_2')

        bb.css({'position': 'fixed'})
        bb.addClass('back_button_active')
        bb.stop().animate({'bottom': '17px'})

        $(window).scroll(function () {
            let st = $(this).scrollTop()

            if (st > scrollPos) {
                if (bb_status) {

                    bb.stop().animate({'bottom': -bb.outerHeight(true)}, 200)
                    bb_status = false
                }

            } else {
                if (!bb_status) {
                    bb.css({'bottom': -bb.height()})
                    bb.stop().animate({'bottom': '17px'}, 200)
                    bb_status = true
                }
            }
            scrollPos = st;
        });

        bb.click(function () {
            history.back();
            return false;
        })



    } else {


    }
}

function isScrolledIntoView(elem)
{
    let docViewTop = $(window).scrollTop(),
        docViewBottom = docViewTop + $(window).height(),

        elemTop = $(elem).offset().top,
        elemBottom = elemTop + $(elem).height();

    return (elemBottom <= docViewBottom) || (elemTop <= docViewBottom);
}

document.addEventListener('DOMContentLoaded', function() {
    let st = false,
        phone_numbers = $('#phone_numbers')
    phone_numbers.stop().slideUp(0)
    console.log(phone_numbers)

    $('#contacts').click(function() {
        if (st) {
            phone_numbers.stop().slideUp(500)
            st = !st
        }
        else {
            phone_numbers.stop().slideDown(500)
            st = !st
        }
    })
})
