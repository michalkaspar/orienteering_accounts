from django import template, forms
from django.conf import settings
from django.utils.encoding import force_str
from django.utils.safestring import mark_safe
from django.utils.text import capfirst as cf

from orienteering_accounts.core.utils.forms import add_class

register = template.Library()


@register.filter
def label_tag(bf, classes=None, capfirst=True):
    """ HTML <label> for form BoundField

    """
    classes = classes.split(' ') if classes else []
    classes.append("c-field__label")
    contents = force_str(bf.label)

    if capfirst:
        contents = cf(contents)

    if bf.field.required:
        contents = "<strong>%s</strong>" % contents

    bf.is_checkbox = isinstance(bf.field.widget, forms.CheckboxInput)
    if bf.is_checkbox:
        classes.append('always-show-label')
        bf.field.label_suffix = ''

    attrs = classes and {'class': ' '.join(classes)} or {}
    if hasattr(bf.field, 'label_attrs'):
        attrs.update(bf.field.label_attrs)

    return mark_safe(bf.label_tag(contents=mark_safe(contents), attrs=attrs))


@register.inclusion_tag('base/forms/form_field.html')
def form_field(bound_field, css_classes='', icon='', label_on_left=True, label=True, label_bf=None, display_errors=True,
               show_help_text=False):

    if not isinstance(bound_field, list) and bound_field.errors:
        add_class(bound_field.field.widget, "c-input--danger")

    context = {}

    if isinstance(bound_field, (list, tuple)):
        required = False
        clear = False
        help_text_bf = None
        if not help_text_bf:
            help_text_bf = bound_field[0]
        if not label_bf:
            label_bf = bound_field[0]
        for bf in bound_field:
            if bf.field.required:
                required = True
            bf.is_checkbox = isinstance(bf.field.widget, forms.CheckboxInput)
            if bf.is_checkbox:
                clear = True

        def fields_iter():
            for bf in bound_field:
                label_classes = css_classes
                if bf.is_checkbox:
                    label_classes += ' c-choice__label'
                yield bf, label_classes

        context.update({
            'multi': True,
            'fields': fields_iter(),
            'required': required,
            'clear': clear,
            'label_bf': label_bf,
            'help_text_bf': help_text_bf,
        })
    else:
        bound_field.is_checkbox = isinstance(bound_field.field.widget, forms.CheckboxInput)
        bound_field.custom_validation = False

        if bound_field.errors and bound_field.is_mulit_lang:
            if bound_field.field.required_languages != [lang[0] for lang in settings.LANGUAGES]:
                bound_field.custom_validation = True
                for i, subwidget in enumerate(bound_field.field.widget.widgets):
                    if not bound_field.field.field_errors[i]:
                        subwidget.attrs['ignore_errors'] = True
                    else:
                        subwidget.errors = bound_field.field.field_errors[i]

        if bound_field.is_checkbox:
            css_classes += ' c-choice__label'
            label_on_left = False

        if show_help_text and bound_field.help_text:
            context.update({'help_text': bound_field.help_text})

        context.update({
            'multi': False,
            'field': bound_field,
            'required': bound_field.field.required,
            'clear': isinstance(bound_field.field.widget, forms.CheckboxInput),
        })

    if not isinstance(bound_field, list) and bound_field.is_hidden:
        css_classes += " u-hidden-visually"

    context.update({
        'css_classes': css_classes,
        'icon': icon,
        'display_errors': display_errors,
        'label_on_left': label_on_left,
        'label': label,
    })

    return context