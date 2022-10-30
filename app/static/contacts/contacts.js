style_css()

function style_css() {
    let detect = new MobileDetect(window.navigator.userAgent)
    let link = document.createElement('link')
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.media = 'all';

    if (detect.mobile()) {
        link.href = '/app/static/contacts/contacts_phone.css';
    } else {
        link.href = '/app/static/contacts/contacts_desktop.css'
    }
    document.getElementById('style').append(link)
}

