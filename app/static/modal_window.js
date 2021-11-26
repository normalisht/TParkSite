(function(){

    let time_animation_modal_window = 500
    document.documentElement.style
        .setProperty('--modal_window_time', `${time_animation_modal_window}ms`)

    let current_modal_window = {
        status: false,
        modal_window_name: '',
        modal_window_fullname: '',
        set_modal_window_name(full_name) {
            this.modal_window_fullname = full_name
            this.modal_window_name = full_name.split('-')[0]
        },
        change_status(modal_window_name) {

            let time = !this.status ? 0: time_animation_modal_window
            setTimeout( () => {
                document.querySelector(modal_window_name).classList.toggle('show_modal_window')
            }, time)

            this.set_modal_window_name(modal_window_name)

            this.status = !this.status

            this.animation(this.modal_window_fullname)

            if (!this.status)
                this.modal_window_fullname = this.modal_window_name = null
        },

        animation(modal_window_name) {
            try {
                if (!modal_window_name) return

                let name = modal_window_name.slice(0),
                    modal_window = document.querySelector(name),
                    overlay = modal_window.lastElementChild.style

                if (this.status) {
                    modal_window.firstElementChild.style.left = '0'
                    overlay.zIndex = '1'
                    overlay.opacity = '1'                }
                else {
                    modal_window.firstElementChild.style.left = -modal_window.offsetWidth + 'px'
                    overlay.opacity = '0'
                    setTimeout(() => {
                        overlay.zIndex = '-1'
                    }, time_animation_modal_window)                }
            }
            catch (e) {
                console.error('Modal window: animation error')
            }
        },
    }

    window.addEventListener('resize', modal_windows_position)
    window.addEventListener('orientationchange', modal_windows_position)

    document.addEventListener('DOMContentLoaded', function() {

        let modal_window_events = document.getElementById('navigation_buttons')
        modal_window_events.addEventListener('click', modal_window_toggle);

        if (!current_modal_window.status)
            window.location.hash = ''

        modal_windows_position()
    })

    window.addEventListener('hashchange', function (event) {
        // история откатилась, но окно открыто, значит закрываем
        if (window.location.hash.search(current_modal_window.modal_window_name) === -1
            && current_modal_window.status) {

            let m_window = document.querySelector(".show_modal_window")
            if (!m_window) return

            current_modal_window.change_status(
                '#' + m_window.getAttribute('id'))
        }
    })

    document.addEventListener('DOMContentLoaded', function () {
        // возможность закрыть модальное окно свайпом
        let modal_windows = document.getElementsByClassName('modal')

        for (let modal_window of modal_windows) {
            Hammer(modal_window).on('swipe', function () {
                if (current_modal_window.status) {
                    history.back()
                }
            })
        }
    })

    function modal_window_toggle(event) {

        let modal_window_btn=event.target.closest('[data-modal-window-toggle]');

        if(!modal_window_btn) return;

        event.preventDefault();
        let modal_window_target=modal_window_btn.getAttribute('data-modal-window-toggle');

        current_modal_window.change_status(modal_window_target)

        // если модальное окно активно изменяем url, иначе откатываем
        if (current_modal_window.status)
            window.location.hash += current_modal_window.modal_window_name
        else
            history.back()
    }

    function modal_windows_position() {
        let modal_windows = document.getElementsByClassName('modal')

        for (let modal_window of modal_windows) {
            modal_window.firstElementChild.style.left = -modal_window.offsetWidth + 'px'
        }
    }
})()
