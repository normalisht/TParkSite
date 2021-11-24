(function(){

    let modal_window = {
        status: false,
        modal_window_name: '',
        change_status() {
            this.status = !this.status
        }
    }

    document.addEventListener('DOMContentLoaded', function() {

        let modal_win = document.getElementById('navigation_buttons')
        modal_win.addEventListener('click', modal_window_toggle);
    })

    function modal_window_toggle(event) {

        let modal_window_btn=event.target.closest('[data-modal-window-toggle]');

        if(!modal_window_btn) return;

        event.preventDefault();
        let modal_window_target=modal_window_btn.getAttribute('data-modal-window-toggle');

        document.querySelector(modal_window_target).classList.toggle('show_modal_window')
        modal_window.change_status()
        modal_window.modal_window_name = modal_window_target.split('-')[0]

        // если модальное окно активно изменяем url, иначе откатываем
        if (modal_window.status)
            window.location.hash += modal_window.modal_window_name
        else
            history.back()
    }

    window.addEventListener('hashchange', function (event) {
        // история откатилась, но окно открыто, значит закрываем
        if (window.location.hash.search(modal_window.modal_window_name) === -1 && modal_window.status) {
            document.querySelector(".show_modal_window").classList
                .toggle('show_modal_window')
            modal_window.change_status()
        }
    })
})()
