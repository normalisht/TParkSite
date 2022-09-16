// блок navigation buttons


// изменение цвета кнопок при наведении
const primary_color = getComputedStyle(document.getElementById('services-button'))
    .getPropertyValue('--primary-color') // цвет при наведении
const font_size = getComputedStyle(document.getElementById('services-button'))
    .getPropertyValue('--font-size') // размер шрифта
const time_animation = 400

const elements = $('#all_buttons a')
elements.each(function (index, element) {
    $(element).mouseenter(function () {
        console.log(index)
        if (index !== 0) {
            $(elements[index - 1]).css('border-right-color', primary_color)
            $(element).css('border-left-color', primary_color)
        }
        if (index !== elements.length - 1) {
            $(elements[index + 1]).css('border-left-color', primary_color)
            $(element).css('border-right-color', primary_color)
        }

        // $(this).toggleClass('button_main_hover')
    })

    $(element).mouseleave(function () {
        if (index !== 0) {
            $(elements[index - 1]).css('border-right-color', 'black')
            $(element).css('border-left-color', 'black')
        }
        if (index !== elements.length - 1) {
            $(elements[index + 1]).css('border-left-color', 'black')
            $(element).css('border-right-color', 'black')
        }

        // $(this).toggleClass('button_main_hover')
    })
})

//
// // кнопка "Услуги"
// let services_button = $('#services-button')
// services_button.hover(
//     function () {
//         let about_us = $('#about-us-button')
//         about_us.css('border-left-color', primary_color)
//
//         $(this).parent().toggleClass('button_main_hover')
//
//     }, function () {
//         let about_us = $('#about-us-button')
//         about_us.css('border-left-color', 'black')
//
//         $(this).parent().toggleClass('button_main_hover')
//     })
//
// // кнопка "Контакты"
// let contact_button = $('#contact-button')
// contact_button.mouseenter(function () {
//     let about_us = $('#about-us-button')
//     about_us.css('border-right-color', primary_color)
//
//     $(this).parent().toggleClass('button_main_hover')
// })
// contact_button.mouseout(function () {
//     let about_us = $('#about-us-button')
//     about_us.css('border-right-color', 'black')
//
//     $(this).parent().toggleClass('button_main_hover')
// })
//
// // кнопка "О нас"
// let about_us = $('#about-us-button')
// about_us.mouseover(function () {
//     $(this).css('border-color', primary_color)
//
//     $(this).toggleClass('button_main_hover')
// })
// about_us.mouseout(function () {
//     $(this).css('border-color', 'black')
//
//     $(this).toggleClass('button_main_hover')
// })
//
