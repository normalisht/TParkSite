

(function(){
    'use strict';

    document.addEventListener('DOMContentLoaded', function() {

        let modal_win = document.getElementById('navigation_buttons')

        modal_win.addEventListener('click', EasyTogglerHandler);
    })

    function EasyTogglerHandler(event) {

        let EY_BTN=event.target.closest('[data-easy-toggle]');

        if(!EY_BTN) return;

        event.preventDefault();
        let ey_target=EY_BTN.getAttribute('data-easy-toggle');
        let ey_class=EY_BTN.getAttribute('data-easy-class');
        document.querySelector(ey_target).classList.toggle(ey_class)
    }
})()