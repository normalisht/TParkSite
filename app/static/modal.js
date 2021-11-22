(function(){

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
    }
})()