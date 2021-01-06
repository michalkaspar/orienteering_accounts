
def add_class(widget, css_class):
    """ Helper function - adds CSS class to widget

    """
    attrs = widget.attrs or {}
    if 'class' in attrs:
        attrs['class'] = '%s %s' % (attrs['class'], css_class)
    else:
        attrs['class'] = css_class
    widget.attrs = attrs
