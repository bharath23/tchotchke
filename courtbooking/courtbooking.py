#!/usr/bin/env python
"""
Book courts using the bay club
"""
import argparse
import datetime
import logging
import sys
import time

from netrc import netrc
from smtplib import SMTP

from pyvirtualdisplay import Display
from splinter import Browser

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587

def send_courtbooking_mail(recp, sub):
    """
    Send email to recepient about courtbooking attempt
    """
    creds = netrc()
    login, _, passwd = creds.authenticators(GMAIL_SMTP_HOST)
    if login is None or passwd is None:
        logging.error("send_courtbooking_mail: Unable to get login and password "
                      "from netrc")
        return
    smtp = SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT)
    smtp.starttls()
    smtp.login(login, passwd)
    headers = "\r\n".join(["from: " + login,
                           "to: " + recp,
                           "subject: " + sub,
                           "mime-version: 1.0",
                           "content-type: text/plain"])
    mail = headers
    smtp.sendmail(login, recp, mail)
    smtp.quit()

def wait_for_browser_element(element, timeout):
    """
    Wait for the element to be visible or for timeout
    """
    sleep_time = timeout // 5
    count = 0
    while not element.visible:
        time.sleep(sleep_time)
        count += 1
        if count > 5:
            break

def book_court(browser, court):
    """
    Book the selected court.
    """
    court.click()
    if browser.is_element_present_by_id("length45", wait_time=15):
        button = browser.find_by_id("length45")
        wait_for_browser_element(button, 15)
        if not button.visible:
            logging.error("book_court: Unable to select court")
            return False

        alerts = browser.find_by_css(".alert.alert-info")
        for alert in alerts:
            if alert.visible:
                logging.info("book_court: Court selection alert, cancelling "
                             "selection")
                button = browser.find_by_id("clearselection")
                break

        button.click()

    error = browser.find_by_id("myModalBody")
    wait_for_browser_element(error, 15)
    if error.visible:
        logging.error("book_court: Unable to book selected court")
        close_buttons = browser.find_by_css(".btn.btn-default")
        for close in close_buttons:
            if close.visible:
                close.click()
                break
        return False

    if browser.is_element_present_by_id("backToCourtSheet", wait_time=15):
        button = browser.find_by_id("backToCourtSheet")
        wait_for_browser_element(button, 15)
        if not button.visible:
            logging.error("book_court: Unable to get booking confirmation")
            return False

        button.click()
        return True

    logging.error("book_court: Court booking failed")
    return False

def court_booking_login(user, passwd):
    """
    Create a new browser instance and login to the website
    """
    browser = Browser()
    browser.visit("https://courtbooking.bayclubs.com")
    if browser.status_code != 200:
        logging.error("court_booking_login: Unable to open court booking "
                      "website")
        browser.quit()
        return None

    input_email = browser.find_by_id("InputEmail1")
    input_email.fill(user)
    input_passwd = browser.find_by_id("InputPassword1")
    input_passwd.fill(passwd)
    login_button = browser.find_by_id("loginButton")
    login_button.click()
    if browser.status_code != 200:
        logging.error("court_booking_login: Error unable to login into court "
                      "booking website")
        browser.quit()
        return None

    if browser.is_element_present_by_id("loginresult", wait_time=5):
        logging.error("court_booking_login: Incorrect login credentials")
        browser.quit()
        return None

    return browser

def gen_bccu_court_ids(date, start, end):
    """
    BCCU courts are court ids 025, 026, 027, 028
    Each 15 minute slot has an id starting from 5:00am on weekdays and 6:00am on
    weekends.

    Ids are created using the following format
    a_<COURT_ID>_<HH>_<MM>_<YYYY>-<MM>-<DD>_<SLOT_ID>
    """
    if date.weekday() < 5:
        base_datetime = datetime.datetime.combine(date, datetime.time(5))
    else:
        base_datetime = datetime.datetime.combine(date, datetime.time(6))
    start_datetime = datetime.datetime.combine(date, start)
    end_datetime = datetime.datetime.combine(date, end)
    start_id = int((start_datetime - base_datetime).total_seconds() / 900) + 1
    offset = start_id % 3
    start_id = (start_id // 3) * 3
    if offset == 0 or offset == 1:
        start_id += 1
    else:
        start_id += 4

    end_id = int((end_datetime - base_datetime).total_seconds() / 900) + 1
    ids = []
    court_ids = ['025', '026', '028', '027']
    for slot in range(start_id, end_id + 1, 3):
        for court in court_ids:
            court_datetime = base_datetime + datetime.timedelta(minutes=(slot - 1) * 15)
            court_id = "a_{}_{}_{}".format(court,
                                           datetime.datetime.strftime(court_datetime,
                                                                      "%H_%M_%Y-%m-%d"),
                                           slot)
            ids.append(court_id)

    return ids

def bccu_reserve_court(user, passwd, start, end):
    """
    Reserve a court at the Cupertino club
    """
    booking_date = datetime.date.today() + datetime.timedelta(days=7)
    court_ids = gen_bccu_court_ids(booking_date, start, end)
    subject = ""
    if len(court_ids) == 0:
        logging.error("bccu_reserve_court: Empty court_ids")
        subject = "[courtbooking] no bookable court for given start and end" \
                  " time"
        return

    browser = court_booking_login(user, passwd)
    if browser is None:
        logging.error("bccu_reserve_court: Login into court booking website " \
                      "failed.")
        return

    # Location id 3 - BCCU, 17 - BCSC
    if not browser.is_element_present_by_id("squashlocation", wait_time=10):
        logging.error("bccu_reserve_court: Unable to get club selection")
        return

    location = browser.find_by_id("squashlocation")
    location.select("3")
    if not browser.is_element_present_by_id("myid", wait_time=10):
        logging.error("bccu_reserve_court: Unable to get date selection")
        return

    date_select = browser.find_by_id("myid")
    date_select.select(datetime.datetime.strftime(booking_date, "%Y-%m-%d"))
    if browser.status_code != 200 and browser.status_code != 302:
        logging.error("bccu_reserve_court: status_code: %s",
                      browser.status_code)
        logging.error("bccu_reserve_court: Unable to get court booking page "
                      "for %s", datetime.datetime.strftime(booking_date,
                                                           "%Y-%m-%d"))
        browser.quit()
        return

    subject = "[courtbooking] unable to reserve a court successfully, check" \
              " manually"
    for court_id in court_ids:
        court = browser.find_by_id(court_id)
        if len(court) == 0:
            continue

        if book_court(browser, court):
            logging.info("bccu_reserve_court: Court successfully booked")
            subject = "[courtbooking] court reserved successfully"
            break

        time.sleep(3)

    send_courtbooking_mail(user, subject)
    browser.quit()

def bcsc_reserve_court(user, passwd, start, end):
    """
    Reserve a court at the Santa Clara club
    """
    logging.info("bcsc_reserve_court: UNIMPLEMENTED")

def validate_time(inp):
    """
    Validate the input time and round it to the nearest quarter of an hour
    """
    inp.strip()
    inp = "".join(inp.split())
    inp_time = datetime.datetime.strptime(inp, "%I:%M%p")
    min_15 = (inp_time.minute // 15) * 15
    if min_15 != inp_time.minute:
        min_15 = min_15 + 15
        inp_time = inp_time.replace(minute=min_15)

    return inp_time.time()

def main():
    """
    Entry point
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--club", choices=['bccu', 'bcsc'], default="bccu",
                        help="Which gym for the court booking")
    parser.add_argument("--user", required=True,
                        help="User name for court booking website")
    parser.add_argument("--password", required=True,
                        help="Password for court booking website")
    parser.add_argument("--start-time", type=validate_time, required=True,
                        help="Start time for booking - format HH:MM AM/PM")
    parser.add_argument("--end-time", type=validate_time, required=True,
                        help="End time for booking - format HH:MM AM/PM")
    parser.add_argument("--headless", action="store_true",
                        help="Run in headless mode without requiring display")
    parser.add_argument("--logfile", help="Log file to be used for logging")
    args = parser.parse_args()
    if args.logfile is not None:
        logging.basicConfig(filename=args.logfile, level=logging.INFO,
                            format="[%(asctime)s %(levelname)s] %(message)s")
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                            format="[%(asctime)s %(levelname)s] %(message)s")
    display = None
    if args.headless:
        display = Display(visible=False, size=(1280, 800))
        display.start()

    if args.club == "bccu":
        bccu_reserve_court(args.user, args.password, args.start_time,
                           args.end_time)
    elif args.club == "bcsc":
        bcsc_reserve_court(args.user, args.password, args.start_time,
                           args.end_time)

    if display is not None:
        display.stop()

if __name__ == "__main__":
    main()
    sys.exit(0)

# vim: ts=4:sts=4:sw=4:tw=80
