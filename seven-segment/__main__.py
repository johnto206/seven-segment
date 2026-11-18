#!/usr/bin/python

# seven-segment module Main function
# Author: Eddy Ferre - ferree@seattleu.edu

from traceback import print_exc
from sys import stdout
from os import path
from re import compile
from argparse import ArgumentParser
from time import monotonic, sleep
from threading import Thread, Event

from .display import *
from .clock import Clock



class LedBlinkThread(Thread):
    """Blink the LED independently until stop() is called."""
    def __init__(self, interval=0.5):
        super().__init__()
        self.interval = interval
        self.stop_event = Event()
        self.led_state = False

    def run(self):
        try:
            while not self.stop_event.is_set():
                self.led_state = not self.led_state
                set_led(self.led_state)
                self.stop_event.wait(self.interval)
        finally:
            self.led_state = False
            set_led(False)

    def stop(self):
        self.stop_event.set()


def stop_led_thread(worker):
    """Stop a blinking LED thread and wait for it to finish."""
    if worker is not None:
        worker.stop()
        worker.join()


def run_timer(start_seconds):
    """Count down in MM:SS and blink the LED when the timer reaches zero."""
    start_time = monotonic()
    was_pressed = False
    led_thread = None

    print("Running 'timer' mode ...")
    try:
        while True:
            now = monotonic()
            elapsed = int(now - start_time)
            remaining = max(0, start_seconds - elapsed)

            minutes = remaining // 60
            seconds = remaining % 60
            digits = f"{minutes:02d}{seconds:02d}"
            colon_on = int(now * 2) % 2 == 0

            if remaining == 0 and led_thread is None:
                led_thread = LedBlinkThread(interval=0.5)
                led_thread.start()

            pressed = get_button_pressed()
            button_released = was_pressed and not pressed
            was_pressed = pressed

            activate_displays(digits, set_colon=colon_on)

            if remaining == 0 and button_released:
                break

            sleep(0.01)
    finally:
        stop_led_thread(led_thread)
        set_led(False)
        set_colon(False)


def run_stopwatch():
    """Stopwatch states: reset, running, and stopped."""
    state = "reset"
    elapsed_tenths = 0
    start_time = 0.0
    was_pressed = False
    led_thread = None

    print("Running 'stopwatch' mode ...")
    try:
        while True:
            now = monotonic()

            pressed = get_button_pressed()
            button_released = was_pressed and not pressed
            was_pressed = pressed

            if button_released:
                if state == "reset":
                    state = "running"
                    start_time = now
                    led_thread = LedBlinkThread(interval=0.5)
                    led_thread.start()
                elif state == "running":
                    elapsed_tenths = min(9999, int((now - start_time) * 10))
                    state = "stopped"
                    stop_led_thread(led_thread)
                    led_thread = None
                    set_led(True)
                else:
                    state = "reset"
                    elapsed_tenths = 0
                    set_led(False)

            if state == "running":
                elapsed_tenths = min(9999, int((now - start_time) * 10))
            elif state == "reset":
                elapsed_tenths = 0

            whole_seconds = elapsed_tenths // 10
            tenths = elapsed_tenths % 10
            digits = f"{whole_seconds:03d}{tenths}"

            set_colon(False)
            activate_displays(digits, decimal_point=[False, False, True, False])
            sleep(0.01)
    finally:
        stop_led_thread(led_thread)
        set_led(False)
        set_colon(False)


def main():
    clock = None
    channels_set = False
    clock_pattern = compile(r"([12]?)(\d):([0-5])(\d)")
    timer_pattern = compile(r"(\d{1,2}):([0-5]\d)")

    try:
        parser = ArgumentParser(description='Seven-Segment Clock Display')
        parser.add_argument('mode',
                            default='clock',
                            const='clock',
                            nargs='?',
                            choices=['clock', 'timer', 'stopwatch', 'freeform'],
                            help='list of modes (default: %(default)s)')
        parser.add_argument('-a',
                            '--alarm',
                            action='store',
                            help="Alarm time, H:MM format (24hr)")
        parser.add_argument('-m',
                            '--music',
                            action='store',
                            help="Music to play as alarm")
        parser.add_argument('-t',
                            '--timerstart',
                            action='store',
                            help="Timer start, MM:SS format")

        args = parser.parse_args()

        timer_seconds = None
        if args.mode == 'timer':
            if args.timerstart is None:
                raise ValueError("Timer mode requires --timerstart MM:SS (or -t MM:SS)")
            match = timer_pattern.fullmatch(args.timerstart)
            if match is None:
                raise ValueError("Invalid timer start. Use MM:SS with seconds from 00 to 59")
            timer_seconds = int(match.group(1)) * 60 + int(match.group(2))

        # Setup and Initialize the GPIO pins after validating arguments.
        init_display(channels_set)

        if args.mode == 'clock':
            alarm = None
            music_file = None
            if args.alarm is not None:
                m = clock_pattern.match(args.alarm)
                if m is None:
                    print(f"ERROR: Invalid alarm argument '{args.alarm}'. Must be 'H:MM'")
                else:
                    print(f"Alarm set to {args.alarm}")
                    alarm = args.alarm.replace(":", "")
                    if m.group(1) == '':
                        alarm = " " + alarm
                    if args.music is not None:
                        if path.isfile(args.music):
                            music_file = args.music
                        else:
                            print(f"ERROR: Cannot find '{args.music}' file")

            print("Running 'clock' mode ...")
            clock = Clock()
            clock.set_alarm(alarm)
            clock.set_music(music_file)
            clock.start()
            # Stay in 'clock' mode until Ctrl+c
            while True:
                sleep(1.0)

        elif args.mode == 'stopwatch':
            run_stopwatch()

        elif args.mode == 'timer':
            run_timer(timer_seconds)

        else:   # args.mode == 'freeform'

            # Let user enter 4 characters
            string = input("Enter what you want the clock display to print: ")

            # Parse Clock entry
            m = clock_pattern.match(string)
            if m is None:
                pass
            elif m.group(1) == '2' and m.group(2) not in "0123":
                raise ValueError("Clock - Invalid entry")
            else:
                print("Valid clock entry")
                # Sets the Digits
                if m.group(1) == '':
                    digits = " "
                else:
                    digits = m.group(1)
                for i in range(2, 5):
                    digits += m.group(i)
                while True:
                    activate_displays(digits, set_colon=True)
            print("not a clock entry")

            # Parse number
            try:
                # noinspection PyUnusedLocal
                value = float(string)
                print("Valid number")
                # TODO: write your code here!
                # Watch for negative values, floating points...
            except ValueError:
                pass
                print("not a number")

            # Parse anything else
            valid_char = ''.join(list(SEGS_FOR_CHAR.keys())).replace("-", "\\-").replace("[","\\[").replace("]","\\]")
            print(valid_char)
            pattern = compile(
                rf"([{valid_char}])?(\\.)?([{valid_char}])?(\\.)?(:)?([{valid_char}])?(\\.)?(')?([{valid_char}])?(\\.)?")
            m = pattern.match(string)
            if m is None:
                pass
            elif m.groups() != (None, None, None, None, None, None, None, None, None, None):
                digit_group_indexes = [1, 3, 6, 9]
                dp_group_indexes = [2, 4, 7, 10]
                print(m.groups())
                digits = ""
                dp = [False] * 4
                for i in digit_group_indexes:
                    if m.group(i) is None:
                        digits += " "
                    else:
                        digits += m.group(i)
                dp_idx = 0
                for i in dp_group_indexes:
                    dp[dp_idx] = m.group(i) is not None
                    dp_idx += 1
                set_colon = m.group(5) is not None
                set_thousand = m.group(8) is not None
                while True:
                    activate_displays(digits, decimal_point=dp, set_colon=set_colon, set_thousand=set_thousand)

            digits = "-Err"
            print(f"Could not parse entry, showing: '{digits}'")
            while True:
                activate_displays(digits)

    except KeyboardInterrupt:
        if clock is not None:
            clock.stop()
        print("\b\b  \nCtrl+c pressed, exiting")
    except ValueError as e:
        print(e)
    except Exception:
        print("-" * 60)
        print_exc(file=stdout)
        print("-" * 60)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
