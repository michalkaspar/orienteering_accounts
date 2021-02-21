import logging

from django import template
from django.template import Variable, NodeList

from orienteering_accounts.account import perms

logger = logging.getLogger(__name__)
register = template.Library()


class IfPermNode(template.Node):
    child_nodelists = ['nodelist_true', 'nodelist_false']

    def __init__(self, nodelist_true, nodelist_false, negation, *args):
        self.nodelist_true = nodelist_true
        self.nodelist_false = nodelist_false
        self.negation = negation
        self.perm_func_name = args[1]
        self.perm_func = getattr(perms, self.perm_func_name, None)
        self.args = [Variable(arg) for arg in args[2:]]

    def render(self, context):
        employee = context.request.user
        args = [arg.resolve(context) for arg in self.args]

        if self.perm_func is None:
            logger.warning('{} permission function is not implemented'.format(self.perm_func_name))
            return ''

        if self.negation ^ self.perm_func(employee, *args):  # ^ is XOR operator
            return self.nodelist_true.render(context)
        return self.nodelist_false.render(context)


def _perm_tag(parser, token, else_tag, closing_tag):
    args = token.split_contents()
    nodelist_1 = parser.parse([else_tag, closing_tag])

    token = parser.next_token()
    if token.contents == else_tag:
        nodelist_2 = parser.parse([closing_tag])
        parser.delete_first_token()
    else:
        nodelist_2 = NodeList()
    return nodelist_1, nodelist_2, args


@register.tag
def ifperm(parser, token):
    nodelist_true, nodelist_false, args = _perm_tag(parser, token, 'else', 'endifperm')
    return IfPermNode(nodelist_true, nodelist_false, False, *args)


@register.tag
def ifnotperm(parser, token):
    nodelist_true, nodelist_false, args = _perm_tag(parser, token, 'else', 'endifnotperm')
    return IfPermNode(nodelist_true, nodelist_false, True, *args)
