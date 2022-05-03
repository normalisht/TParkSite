$(function(){
    $('.minimized').click(function(event) {
        var i_path = $(this).attr('src');
        $('body').append('<div id="overlay"></div><div id="magnify"><img src="'+i_path+'">');
        $('#magnify').css({
            left: ($(document).width() - $('#magnify').outerWidth())/2,
            top: ($('#magnify').outerHeight())*2
        });
        $('#overlay, #magnify').fadeIn('fast');
    });

    $('body').on('click', '#overlay', function(event) {
        event.preventDefault();
        $('#overlay, #magnify').fadeOut('fast', function() {
            $('#magnify, #overlay').remove();
        });
    });
});