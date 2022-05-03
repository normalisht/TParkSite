style_css()

function style_css() {
    let detect = new MobileDetect(window.navigator.userAgent)
    let link = document.createElement('link')
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.media = 'all';

    if (detect.mobile()) {
        link.href = '/app/static/comments/comments_phone.css';
        document.head.append(link)
    } else {
        // link.href = '/app/static/category/category_desktop.css'
    }
    // document.head.append(link)
}