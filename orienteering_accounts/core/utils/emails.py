import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.defaultfilters import striptags
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _prepare_plaintext(html_content):
    html_soup = BeautifulSoup(html_content, features="html.parser")
    for a in html_soup.findAll('a'):
        a.replaceWithChildren()

    return striptags(str(html_soup))


def send_email(recipient_list: list,
              subject: str,
              html_content: str,
              cc_list: list = [],
              bcc_list: list = []):
    """
    Sends email with subject, html_content, plain_content to recipient_list, cc_list and bcc_list.
    If settings EMAIL_DEBUG is True, recipient_list is overridden by EMAIL_DEBUG_LIST in settings.
    """

    plain_content = _prepare_plaintext(html_content=html_content)

    if not isinstance(recipient_list, list):
        recipient_list = [recipient_list]

    msg = EmailMultiAlternatives(
        subject=subject,
        body=plain_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipient_list,
        cc=cc_list,
        bcc=bcc_list
    )
    if html_content:
        msg.attach_alternative(html_content, "text/html")

    try:
        logger.debug('Sending email "{}" to {}'.format(subject, recipient_list))
        msg.send(fail_silently=False)
    except:
        logger.error('Email ("{}") failed to send'.format(subject), exc_info=True, stack_info=True)
