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

document.addEventListener('DOMContentLoaded', function () {
    let services = $('.button_1'),
        time_animation = 1000

    services.each(function(index, value) {
        $(this).click(function () {
            let description = $(this).find('.description').stop()

            if ($(this).attr('status') === '0') {
                description.animate({
                    'height': `${description.prop('scrollHeight')}`
                }, time_animation)
                $(this).attr('status', '1')
            } else {
                description.animate({
                    'height': '0'
                }, time_animation)
                $(this).attr('status', '0')
            }
        })
    })
})