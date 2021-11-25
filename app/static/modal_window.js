(function(){

    let current_modal_window = {
        status: false,
        modal_window_name: '',
        modal_window_fullname: '',
        set_modal_window_name(full_name) {
            this.modal_window_fullname = full_name
            this.modal_window_name = full_name.split('-')[0]
        },
        change_status() {
            this.status = !this.status

            if (!status)
                this.modal_window_fullname = this.modal_window_name = null
        }
    }

    document.addEventListener('DOMContentLoaded', function() {

        let modal_win = document.getElementById('navigation_buttons')
        modal_win.addEventListener('click', modal_window_toggle);

        if (!current_modal_window.status)
            window.location.hash = ''
    })

    function modal_window_toggle(event) {

        let modal_window_btn=event.target.closest('[data-modal-window-toggle]');

        if(!modal_window_btn) return;

        event.preventDefault();
        let modal_window_target=modal_window_btn.getAttribute('data-modal-window-toggle');

        document.querySelector(modal_window_target).classList.toggle('show_modal_window')
        current_modal_window.change_status()
        current_modal_window.set_modal_window_name(modal_window_target)

        // если модальное окно активно изменяем url, иначе откатываем
        if (current_modal_window.status)
            window.location.hash += current_modal_window.modal_window_name
        else
            history.back()
    }

    window.addEventListener('hashchange', function (event) {
        // история откатилась, но окно открыто, значит закрываем
        if (window.location.hash.search(current_modal_window.modal_window_name) === -1
            && current_modal_window.status) {

            document.querySelector(".show_modal_window").classList
                .toggle('show_modal_window')
            current_modal_window.change_status()
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

})()
