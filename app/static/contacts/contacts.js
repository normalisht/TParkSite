style_css()
style_css_dop()

function style_css() {
    let detect = new MobileDetect(window.navigator.userAgent)
    let link = document.createElement('link')
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.media = 'all';

    if (detect.mobile()) {
        link.href = '/app/static/contacts/contacts_phone.css';
    } else {
        link.href = '/app/static/contacts/contacts.css'
    }
    document.getElementById('style').append(link)
}


function style_css_dop() {
    let detect = new MobileDetect(window.navigator.userAgent)
    let link = document.createElement('link')
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.media = 'all';

    if (detect.mobile()) {
        link.href = '/app/static/comments/comments_phone.css';
    } else {
        link.href = '/app/static/comments/comments.css';
    }
    document.getElementById('style').append(link)
}

style_css_desctop()

function style_css_desctop() {
    let detect = new MobileDetect(window.navigator.userAgent)
    let link = document.createElement('link')
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.media = 'all';

    if (detect.mobile()) {
        link.href = '';
    } else {
        link.href = '/app/static/main/desktop.css';
    }
    document.getElementById('style').append(link)
}


