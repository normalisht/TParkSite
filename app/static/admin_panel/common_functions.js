function launch(options) {

    // активирует кнопки изменения текста
    $('[type=change_text]').each(function (index, element) {
        element.click(function () {
            change_text(element.attr('filed'))
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
