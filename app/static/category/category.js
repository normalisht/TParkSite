style_css()

function style_css() {
    let detect = new MobileDetect(window.navigator.userAgent)
    let link = document.createElement('link')
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.media = 'all';

    if (detect.mobile()) {
        link.href = '/app/static/category/category_phone.css';
    } else {
        link.href = '/app/static/category/category_desktop.css'
    }
    document.head.append(link)
}


function close_all() {
    let services = $('.button')

    services.each(function () {
        let description = $(this).find('.description').stop()

        description.animate({
            'height': '0'
        }, 1000)
        $(this).attr('status', '0')

        $(this).find('.price_switch').removeClass('price_switch_active')
    })
}

document.addEventListener('click', function (event) {
    if(event.target.closest('.button')) return

    close_all()
})


document.addEventListener('DOMContentLoaded', function () {
    let services = $('.button'),
        time_animation = 1000

    services.each(function () {
        $(this).click(function () {
            let description = $(this).find('.description').stop()

            if ($(this).attr('status') === '0') {
                close_all()

                description.stop().animate({
                    'height': `${description.prop('scrollHeight')}`
                }, time_animation)
                $(this).attr('status', '1')

                $(this).find('.price_switch').toggleClass('price_switch_active')

            } else {
                description.stop().animate({
                    'height': '0'
                }, time_animation)
                $(this).attr('status', '0')

                $(this).find('.price_switch').toggleClass('price_switch_active')
            }
        })
    })
})

document.addEventListener('DOMContentLoaded', function () {
    let services = $('.price')

    services.each(function (index, element) {


        if (+$(element).outerHeight() > 20) {

            let el_text = $(element).find('.cost').children().first(),
                text = el_text.html()

            text = text.split(' / ').join("<br>")
            el_text.html(text)

            el_text.css('text-align', 'center')
        }
    })
})
