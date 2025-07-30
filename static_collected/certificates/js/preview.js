(function($) {
    $(document).ready(function() {
        var previewButton = $('<button type="button" id="preview-button" class="btn btn-info">Предпросмотр</button>');
        $('.submit-row').prepend(previewButton);

        $('#preview-button').click(function(e) {
            e.preventDefault();
            var formData = new FormData($('form')[0]);

            $.ajax({
                url: '/admin/generate-preview/',
                type: 'POST',
                data: formData,
                processData: false,
                contentType: false,
                success: function(data) {
                    $('#preview-container').html(
                        '<h3>Предпросмотр документов:</h3>' +
                        '<iframe src="' + data.certificate_url + '" width="100%" height="300px"></iframe>' +
                        '<iframe src="' + data.permission_url + '" width="100%" height="300px"></iframe>' +
                        '<iframe src="' + data.audit_url + '" width="100%" height="300px"></iframe>'
                    );
                }
            });
        });
    });
})(django.jQuery);