function launch(options) {

    // активирует кнопки изменения текста
    $('[type=change_text]').each(function (index, element) {
        element.click(function () {
            change_text(element.attr('filed'))
        })
    })

    // активирует кнопки изменения услуги
    $('[type=service]').each(function(index, element) {
        element.click(function () {
            change_service(element.attr('filed'))
        })
    })

    // активирует кнопки изменения фото
}

function create_input(id, type, value) {

    let element = document.createElement('input')
    element.value = value
    element.setAttribute('type', type)
    // element.setAttribute('type', type)

    return element
}


function change_service(id) {
    let service_element = $(`#${id}`),
        price = change_service.price,
        name = change_service.name,
        description = change_service.description,
        short_description = change_service.short_description,
        status = change_service.status,
        // categories = change_service.categories,
        number = change_service.number

    if (service_element.attr('status') === 'static') {

        service_element.after(create_input(`${id}_price`, 'price', price))



    } else {



    }
}
change_service.name = null
change_service.price = null
change_service.short_description = null
change_service.description = null
change_service.status = null
change_service.categories = null
change_service.number = null


function change_text(id) {

    let text_element = $(`#${id}`),
        textarea = change_text.textarea,
        display_status = change_text.display_status

    if (text_element.attr('status') === 'static') {
        let text = text_element.html()
        display_status = text_element.css('display')
        text_element.css('display', 'none')

        textarea = document.createElement('textarea')
        textarea.innerText = text
        textarea.setAttribute('status', 'change')
        text_element.after(textarea)
    } else {
        $.post('/admin_panel/update_text', {
            id: id
        }).done(function (response) {

            text_element.css('display', display_status).html(textarea.innerText)
            textarea.remove()

        }).fail(function () {
            alert('Error AJAX request')
        })
    }
}

change_text.display_status = null
change_text.textarea = null
