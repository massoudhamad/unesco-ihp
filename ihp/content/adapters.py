# -*- coding: utf-8 -*-
"""Custom account adapters for django-allauth.

These are used in order to extend the default authorization provided by
django-allauth.

"""
import string
import logging
import traceback

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.module_loading import import_string
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.utils import user_field
from allauth.account.utils import user_email
from allauth.account.utils import user_username
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from geonode.people.adapters import LocalAccountAdapter

logger = logging.getLogger(__name__)


def populate_username(first_name, last_name):
    fname = u''.join(e for e in first_name if e in string.ascii_letters or '-' == e).lower()
    lname = u''.join(e for e in last_name if e in string.ascii_letters or '-' == e).lower()
    printable = set(string.printable)
    return filter(lambda x: x in printable, u'{}.{}'.format(fname, lname).encode('utf-8').strip())


def get_user_lookup_kwargs(kwargs):
    result = {}
    username_field = getattr(get_user_model(), "USERNAME_FIELD", "username")
    for key, value in kwargs.items():
        result[key.format(username=username_field)] = value
    return result


class UnescoLocalAccountAdapter(LocalAccountAdapter):
    """Customizations for local accounts

    Check `django-allauth's documentation`_ for more details on this class.

    .. _django-allauth's documentation:
       http://django-allauth.readthedocs.io/en/latest/advanced.html#creating-and-populating-user-instances

    """
    def __init__(self, *args, **kwargs):
        super(UnescoLocalAccountAdapter, self).__init__(*args, **kwargs)

    def clean_recommendation(self, recommendation):
        return recommendation

    def populate_username(self, request, user):
        # validate the already generated username with django validation
        # if it passes use that, otherwise use django-allauth's way of
        # generating a unique username

        # safe_username = user_username(user)
        try:
            safe_username = populate_username(user_field(user, 'first_name'), user_field(user, 'last_name'))
        except Exception, e:
            traceback.print_exc()
            raise forms.ValidationError(e)
            # safe_username = self.generate_unique_username([
            #     user_field(user, 'first_name'),
            #     user_field(user, 'last_name'),
            #     user_email(user),
            #     user_username(user)
            # ])

        User = get_user_model()

        lookup_kwargs = get_user_lookup_kwargs({
            "{username}__iexact": safe_username
        })
        qs = User.objects.filter(**lookup_kwargs)

        _user_name_is_valid = False
        if not qs.exists():
            user.username = safe_username
            user.full_clean()
            user_username(user, safe_username)
            _user_name_is_valid = True
        else:
            lookup_kwargs = get_user_lookup_kwargs({
                "{username}__startswith": safe_username
            })
            qs = User.objects.filter(**lookup_kwargs)
            safe_username += '_{}'.format((qs.count()))
            try:
                User.objects.get(username__iexact=safe_username)
            except User.DoesNotExist:
                user.username = safe_username
                user.full_clean()
                user_username(user, safe_username)
                _user_name_is_valid = True

        if not _user_name_is_valid:
            raise forms.ValidationError(_("This username already exists."))

    def save_user(self, request, sociallogin, form=None):
        user = super(UnescoLocalAccountAdapter, self).save_user(request, sociallogin, form=form)
        if form:
            recommendation = form.cleaned_data["recommendation"]
            user_field(user, 'recommendation', recommendation or None)
            user.save()
        return user
