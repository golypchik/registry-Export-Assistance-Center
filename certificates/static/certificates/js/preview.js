(function() {
    'use strict';
    
    // Ждем загрузки DOM
    document.addEventListener('DOMContentLoaded', function() {
        // Проверяем наличие jQuery
        var $ = window.django && window.django.jQuery || window.jQuery || window.$;
        
        if (!$) {
            console.warn('jQuery не найден, используем vanilla JS');
            initWithoutJQuery();
            return;
        }
        
        initWithJQuery($);
    });
    
    function initWithJQuery($) {
        // Обработчики для удаления файлов
        $('.delete-file').on('click', function(e) {
            e.preventDefault();
            
            var fileField = $(this).data('file-field');
            var certificateId = window.location.pathname.match(/\/(\d+)\//);
            
            if (!certificateId) {
                alert('Не удалось определить ID сертификата');
                return;
            }
            
            if (confirm('Вы уверены, что хотите удалить этот файл?')) {
                $.ajax({
                    url: '/admin/certificates/' + certificateId[1] + '/delete-file/',
                    type: 'POST',
                    data: {
                        'file_field': fileField,
                        'csrfmiddlewaretoken': $('[name=csrfmiddlewaretoken]').val()
                    },
                    success: function(response) {
                        location.reload();
                    },
                    error: function(xhr, status, error) {
                        alert('Ошибка при удалении файла: ' + error);
                    }
                });
            }
        });
        
        // Предпросмотр изображений
        $('.preview-image').on('click', function() {
            var src = $(this).attr('src');
            var modal = $('<div class="modal fade" tabindex="-1"><div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-body text-center"><img src="' + src + '" class="img-fluid"></div></div></div></div>');
            $('body').append(modal);
            modal.modal('show');
            modal.on('hidden.bs.modal', function() {
                modal.remove();
            });
        });
    }
    
    function initWithoutJQuery() {
        // Обработчики без jQuery
        document.querySelectorAll('.delete-file').forEach(function(button) {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                var fileField = this.getAttribute('data-file-field');
                var certificateId = window.location.pathname.match(/\/(\d+)\//);
                
                if (!certificateId) {
                    alert('Не удалось определить ID сертификата');
                    return;
                }
                
                if (confirm('Вы уверены, что хотите удалить этот файл?')) {
                    var formData = new FormData();
                    formData.append('file_field', fileField);
                    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
                    
                    fetch('/admin/certificates/' + certificateId[1] + '/delete-file/', {
                        method: 'POST',
                        body: formData
                    })
                    .then(function(response) {
                        if (response.ok) {
                            location.reload();
                        } else {
                            throw new Error('Ошибка сервера');
                        }
                    })
                    .catch(function(error) {
                        alert('Ошибка при удалении файла: ' + error.message);
                    });
                }
            });
        });
    }
})();