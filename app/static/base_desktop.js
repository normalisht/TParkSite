// блок navigation buttons


// изменение цвета кнопок при наведении
const primary_color = '#ffa200' // цвет при наведении

// кнопка "Услуги"
let services_button = $('#services-button')
services_button.mouseenter(function () {
    let about_us = $('#about-us-button')
    about_us.css('border-left-color', primary_color)
})
services_button.mouseout(function () {
    let about_us = $('#about-us-button')
    about_us.css('border-left-color', 'black')
})

// кнопка "Контакты"
let contact_button = $('#contact-button')
contact_button.mouseenter(function () {
    let about_us = $('#about-us-button')
    about_us.css('border-right-color', primary_color)
})
contact_button.mouseout(function () {
    let about_us = $('#about-us-button')
    about_us.css('border-right-color', 'black')
})

// кнопка "О нас"
let about_us = $('#about-us-button')
about_us.mouseover(function () {
    $(this).css('border-color', primary_color)
})
about_us.mouseout(function () {
    $(this).css('border-color', 'black')
})

