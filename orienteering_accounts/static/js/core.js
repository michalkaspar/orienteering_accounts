$(document).ready(function() {

    $(document).on('click', '.js-text-copy', function (e) {
      e.preventDefault();

      function copyTextToClipboard(elementClicked) {
      var temp = $("<input>");
      var textToCopy = elementClicked.data('text-to-copy')
      var message = elementClicked.data('text-copied-message')
      $("body").append(temp);
      temp.val(textToCopy).select();
      document.execCommand("copy");
      temp.remove();
      elementClicked.tooltip('hide')
              .attr('title', message)
              .tooltip('show');
    }

      copyTextToClipboard($(this));
    });

});