#!/usr/bin/env python
"""
usage: ghe-delete-user.py [-h] [-no-confirm] [-ghe-host HOST] [-ghe-user USER]
                          [-ghe-pass PASS] [-debug]
                          [USERNAME]

Tool to delete a Github Enterprise user.

positional arguments:
  USERNAME        username to delete

optional arguments:
  -h, --help      show this help message and exit
  -no-confirm     skip dialog requesting confirmation of deletion.
  -ghe-host HOST  the hostname to your GitHub Enterprise server (default:
                  value from `ghe-host` environment variable)
  -ghe-user USER  username of a Github Enterprise user with admin priveleges.
  -ghe-pass PASS  password of user passed in with -ghe-user.
  -debug          enable debug mode
"""

import argparse, os, pyotp, sys
from builtins import input
from seleniumrequests import PhantomJS

class DeleteUser(object):

    def __init__(self, **kwargs): #token, source_org):
        ''' Constructor. '''

        self.ghe_host = kwargs.get('ghe_host')
        self.ghe_user = kwargs.get('ghe_user')
        self.ghe_pass = kwargs.get('ghe_pass')
        self.ghe_totp = kwargs.get('ghe_totp')
        self.debug = kwargs.get('debug', False)

    def delete(self, user):
        ''' Delete the user on Github Enterprise '''

        # Initialize the PhantomJS selenium driver
        driver = PhantomJS()
        driver.implicitly_wait(10)
        driver.set_window_size(1400, 850)

        # Login as the admin user
        driver.get('https://%s/login' % (self.ghe_host))
        driver.find_element_by_name('login').send_keys(self.ghe_user)
        driver.find_element_by_name('password').send_keys(self.ghe_pass)
        driver.find_element_by_name('commit').click()

        # Check for two-factor auth code request
        if driver.current_url == 'https://%s/sessions/two-factor' % self.ghe_host:
            if self.ghe_totp:
                base = '.auth-form-body input'
                u = driver.find_element_by_css_selector('%s[name=utf8]' % base)
                t = driver.find_element_by_css_selector('%s[name=authenticity_token]' % base)
                otp = pyotp.TOTP(self.ghe_totp)

                driver.request('POST', 'https://%s/sessions/two-factor' % self.ghe_host,
                    data={
                        'utf8': u.get_attribute('value'),
                        'otp': otp.now(),
                        'authenticity_token': t.get_attribute('value')
                    }
                )
            else:
                print('Two-Factor authentication required.')
                sys.exit()

        # Retrieve the admin page for the designated user to be deleted
        driver.get('https://%s/stafftools/users/%s/admin' % (self.ghe_host, user))

        # Ensure that we were able to access the requested admin page
        if 'Page not found' in driver.title or user.lower() not in driver.title.lower():
            print('User not found, or insufficient access rights.')
            sys.exit()

        # Locate the necessary inputs to be able to delete a user
        base = '#confirm_deletion form input'
        u = driver.find_element_by_css_selector('%s[name=utf8]' % base)
        m = driver.find_element_by_css_selector('%s[name=_method]' % base)
        t = driver.find_element_by_css_selector('%s[name=authenticity_token]' % base)

        # Send the delete user request
        driver.request('POST', 'https://%s/stafftools/users/%s' % (self.ghe_host, user),
            data={
                'utf8': u.get_attribute('value'),
                '_method': m.get_attribute('value'),
                'authenticity_token': t.get_attribute('value')
            }
        )

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Tool to delete a Github Enterprise user.'
    )
    parser.add_argument('user',
        help='username to delete',
        nargs='?',
        metavar='USERNAME'
    )
    parser.add_argument('-no-confirm',
        help='skip dialog requesting confirmation of deletion.',
        action='store_true'
    )
    parser.add_argument('-ghe-host',
        help=(
            'the hostname to your GitHub Enterprise server '
            '(default: value from `ghe-host` environment variable)'
        ),
        metavar='HOST',
        default=os.getenv('ghe-host')
    )
    parser.add_argument('-ghe-user',
        help='username of a Github Enterprise user with admin priveleges.',
        metavar='USER',
        type=str,
        default=os.getenv('ghe-user')
    )
    parser.add_argument('-ghe-pass',
        help='password of user passed in with -ghe-user.',
        metavar='PASS',
        type=str,
        default=os.getenv('ghe-pass')
    )
    parser.add_argument('-ghe-totp',
        help='base 32 secret to generate two-factor key',
        metavar='KEY',
        type=str,
        default=os.getenv('ghe-totp')
    )
    parser.add_argument('-debug',
        help='enable debug mode',
        action='store_true'
    )

    args, unknown = parser.parse_known_args()

    if not (args.ghe_host):
        parser.error(
            'GitHub Enterprise host not set. Please use -ghe-host HOST.'
        )

    if not (args.ghe_user):
        parser.error(
            'GitHub Enterprise admin user not set. Please use -ghe-user USER.'
        )

    if not (args.ghe_pass):
        parser.error(
            'GitHub Enterprise admin password not set. Please use -ghe-pass PASS.'
        )

    app = DeleteUser(
        ghe_host=args.ghe_host,
        ghe_user=args.ghe_user,
        ghe_pass=args.ghe_pass,
        ghe_totp=args.ghe_totp,
        debug=args.debug
    )

    if args.user:
        if not args.no_confirm:
            answer = input('Are you sure you want to delete the user "%s"? [y/n] ' % args.user)
            if not answer or answer[0].lower() != 'y':
                print('Aborting...')
                sys.exit(1)

        print('Deleting user: %s' % args.user)
        app.delete(args.user)

    print('Err: No username specified.')
    parser.print_help()
