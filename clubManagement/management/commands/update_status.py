import sys

import os
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.datetime_safe import date

from clubManagement.models import StatusUpdate

from _gmail_module import get_status_update_emails
from fosswebsite import settings


class Command(BaseCommand):
    help = 'Checks and updates the status updates'

    def add_arguments(self, parser):
        # optional argument to set a date

        parser.add_argument(
            '--date',
            action='store',
            dest='date',
            default='',
            help='Date to check status update (dd-mm-yyyy)'
        )

    def handle(self, *args, **options):
        if options['date']:
            try:
                day, month, year = map(int, options['date'].split('-'))
                status_date = date(day=day, month=month, year=year)
            except ValueError:
                print('Date given is wrong, format is dd-mm-yyyy')
                sys.exit()
        else:
            status_date = date.today() - timedelta(days=1)

        email_list = get_status_update_emails(status_date)

        if not email_list:
            sys.exit()

        user_list = User.objects.filter(email__in=email_list)

        status_string = ''

        for user in user_list:
            status_string += str(user.pk) + ' Y, '

        status_string = status_string[:-2]

        # create and process status update data
        status_update, created = StatusUpdate.objects.get_or_create(
            date=status_date)
        status_update.value = status_string
        status_update.process_report()

        mailing_list = settings.MAILING_LIST

        if not mailing_list:
            print('MAILING_LIST needs to be set as your environment variable')
            sys.exit()

        domain = settings.DOMAIN

        url = 'https://%s%s' % (domain, reverse('status-update-detail',
                                                kwargs={
                                                    'day': status_date.day,
                                                    'month': status_date.month,
                                                    'year': status_date.year
                                                }))

        # Send status report
        # render with dynamic value
        html_content = render_to_string(
            'clubManagement/status-report-mail-template.html', {
                'status_update': status_update.get_report(),
                'date': status_date,
                'url': url
            })

        # render text only mail
        text_content = render_to_string(
            'clubManagement/status-report-mail-template.txt', {
                'status_update': status_update.get_report(),
                'date': status_date,
                'url': url
            })

        subject = 'Status update report %s' % status_date.strftime('%d-%m-%Y')

        from_email = settings.EMAIL

        email = EmailMultiAlternatives(
            subject, text_content, from_email, [mailing_list])
        email.attach_alternative(html_content, "text/html")
        email.send()

        # Send next status update reminder
        subject = 'Status Update [%s]' % status_date.strftime('%d-%m-%Y')

        text_content = 'Please reply to this thread to sent your status ' \
                       'updates for %s' % date.today().strftime('%d-%m-%Y')

        send_mail(
            subject,
            text_content,
            from_email,
            [mailing_list],
            fail_silently=False,
        )

        print("Status update processing successful")
