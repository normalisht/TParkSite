document.addEventListener('DOMContentLoaded', function () {
    $('#phone_numbers').css('margin', '10px 0 -8px')
        .find('a').each(function (index, element) {
        $(element).css('margin', '15px auto 12px')
    })

    style_css()
})

function style_css() {
    let detect = new MobileDetect(window.navigator.userAgent)
    let link = document.createElement('link')
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.media = 'all';

    if (detect.mobile()) {
        link.href = '/app/static/category/admin_panel_phone.css';
    } else {
        link.href = '/app/static/category/admin_panel.css'
    }
    document.head.append(link)
}