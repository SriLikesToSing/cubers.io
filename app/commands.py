""" Utility Flask commands for administrating the app. """

import click
from random import randrange, choice

from slugify import slugify

from app import app
from app.persistence.models import UserSolve, UserEventResults
from app.business.user_results.blacklisting import __AUTO_BLACKLIST_THRESHOLDS
from app.business.user_results.personal_bests import recalculate_user_pbs_for_event
from app.persistence.comp_manager import get_complete_competitions, get_all_comp_events_for_comp,\
    get_competition, override_title_for_next_comp, set_all_events_flag_for_next_comp, get_comp_event_by_id,\
    get_active_competition
from app.persistence.events_manager import get_all_events
from app.persistence.user_results_manager import get_event_results_for_user, save_event_results
from app.persistence.user_manager import get_all_users, get_all_admins, set_user_as_admin,\
    unset_user_as_admin, UserDoesNotExistException, set_user_as_results_moderator, unset_user_as_results_moderator,\
    get_user_by_username, update_or_create_user_for_reddit
from app.business.user_results import set_medals_on_best_event_results
from app.business.user_results.creation import process_event_results
from app.tasks.competition_management import post_results_thread_task,\
    generate_new_competition_task, wrap_weekly_competition, run_user_site_rankings
from app.tasks.scramble_generation import check_scramble_pool

# -------------------------------------------------------------------------------------------------
# Below are admin commands for creating new competitions, and scoring previous ones
# -------------------------------------------------------------------------------------------------

@app.cli.command()
@click.option('--all_events', is_flag=True, default=False)
def set_all_events_flags(all_events):
    """ Sets the all-events flag next competition. """

    set_all_events_flag_for_next_comp(all_events)


@app.cli.command()
@click.option('--title', '-t', type=str)
def set_title_override(title):
    """ Sets an override title for the next competition. """

    title = title if title else None
    override_title_for_next_comp(title)


@app.cli.command()
@click.option('--all_events', is_flag=True, default=False)
@click.option('--title', '-t', type=str)
def score_and_generate_new_comp(all_events, title):
    """ Scores the previous competition, and generates a new competition. """

    title = title if title else None
    override_title_for_next_comp(title)
    set_all_events_flag_for_next_comp(all_events)

    wrap_weekly_competition()


@app.cli.command()
@click.option('--comp_id', '-i', type=int)
@click.option('--rerun', '-r', is_flag=True, default=False)
def score_comp_only(comp_id, rerun):
    """ Score only the specified competition, optionally as a re-run. """

    comp = get_competition(comp_id)
    post_results_thread_task(comp.id, comp.title, is_rerun=rerun)


@app.cli.command()
@click.option('--all_events', is_flag=True, default=False)
@click.option('--title', '-t', type=str, default=None)
def generate_new_comp_only(all_events, title):
    """ Only generate a new competition, don't score the previous one. """

    title = title if title else None
    override_title_for_next_comp(title)
    set_all_events_flag_for_next_comp(all_events)

    generate_new_competition_task()
    run_user_site_rankings()


@app.cli.command()
def calculate_all_user_site_rankings():
    """ Calculates UserSiteRankings for all users as of the current comp. """

    run_user_site_rankings()


@app.cli.command()
def top_off_scrambles():
    """ Kicks off a task to check the scramble pool and generate scrambles. """

    check_scramble_pool()

# -------------------------------------------------------------------------------------------------
# Below are admin commands for one-off app administration needs
# -------------------------------------------------------------------------------------------------

@app.cli.command()
@click.option('--username', '-u', type=str)
def set_admin(username):
    """ Sets the specified user as an admin. """

    try:
        set_user_as_admin(username)
    except UserDoesNotExistException as ex:
        print(ex)


@app.cli.command()
@click.option('--username', '-u', type=str)
def remove_admin(username):
    """ Removes admin status for the specified user. """

    try:
        unset_user_as_admin(username)
    except UserDoesNotExistException as ex:
        print(ex)


@app.cli.command()
@click.option('--username', '-u', type=str)
def set_results_mod(username):
    """ Sets the specified user as a results moderator. """

    try:
        set_user_as_results_moderator(username)
    except UserDoesNotExistException as ex:
        print(ex)


@app.cli.command()
@click.option('--username', '-u', type=str)
def remove_results_mod(username):
    """ Removes results moderator status for the specified user. """

    try:
        unset_user_as_results_moderator(username)
    except UserDoesNotExistException as ex:
        print(ex)


@app.cli.command()
def list_admins():
    """ Lists all the admin users. """

    admins = get_all_admins()
    if not admins:
        print('\nNo admins set')
    else:
        print('\nThe following users are admins:')
        for user in get_all_admins():
            print(user.username)


@app.cli.command()
def recalculate_pbs():
    """ Works through every user, every event type, and re-calculates PB averages and singles
    and sets appropriate flags on UserEventResults. """

    all_users = get_all_users()
    user_count = len(all_users)

    all_events = get_all_events()

    for i, user in enumerate(all_users):
        print("\nRecalculating PBs for {} ({}/{})".format(user.username, i + 1, user_count))
        for event in all_events:
            recalculate_user_pbs_for_event(user.id, event.id)

# -------------------------------------------------------------------------------------------------
# Below are utility commands intended to just be one-offs, to backfill or fix broken data
# -------------------------------------------------------------------------------------------------

@app.cli.command()
@click.option('--comp_id', '-i', type=int)
def rerun_podiums_for_comp(comp_id):
    """ Utility command to backfill all UserEventResults for a specific past competitions with
    gold, silver, bronze medal flags. """

    set_medals_on_best_event_results(get_all_comp_events_for_comp(comp_id))


@app.cli.command()
def backfill_results_medals():
    """ Utility command to backfill all UserEventResults for past competitions with
    gold, silver, bronze medal flags. """

    all_comps = get_complete_competitions()
    total_num = len(all_comps)
    for i, comp in enumerate(all_comps):
        print('\nBackfilling for comp {} ({}/{})'.format(comp.id, i + 1, total_num))
        set_medals_on_best_event_results(get_all_comp_events_for_comp(comp.id))


@app.cli.command()
@click.option('--username', '-u', type=str)
@click.option('--comp_event_id', '-i', type=int)
def reprocess_results_for_user_and_comp_event(username, comp_event_id):
    """ Reprocesses the event results for the specified user and competition event. """

    user = get_user_by_username(username)
    if not user:
        print("Oops, that user doesn't exist.")

    comp_event = get_comp_event_by_id(comp_event_id)
    if not comp_event:
        print("Oops, that comp event doesn't exist.")

    results = get_event_results_for_user(comp_event_id, user)
    results = process_event_results(results, comp_event, user)
    save_event_results(results)

# -------------------------------------------------------------------------------------------------
# Below are utility commands intended just for development use
# -------------------------------------------------------------------------------------------------

# This is a list of multiplicative factors for determining "how fast" a given test user is compared
# to the world record, starting at 1.25x WR at the fastest, and getting slower
__TEST_USER_SPEEDS = [1.25 + (0.45 * i) for i in range(10)]

__TEST_USER_NAMES = [
    'sonic_the_hedgehog',
    'crash_bandicoot',
    'Mari0',
    'Earthworm_Jim',
    'parappa_the_rappa',
    'guile_sonic_BOOM',
    'pacman',
    'lara-croft',
    'kirby',
    'Luigi'
]

def __build_solve(user_num, wr_average, event_name, scramble_id):
    """ Returns a UserSolve for an event, for the specified test user number, given the WR average
    for that event. Basically just a multiplicative factor against the WR average with a little random
    variation. Hardcoded DNF and +2 rates, because that seems reasonable for fake data.
    Return format is (centiseconds, was_dnf, was_plus_two). """

    # hardcoded multiplicative factor against WR average, within +/- 30% random adjustment
    factor = __TEST_USER_SPEEDS[user_num] * randrange(700, 1300) / 1000
    centiseconds = int(factor * wr_average)

    # 1/3 DNF rate for BLD events, 1/30 for everything else
    dnf_rate = 3 if 'BLD' in event_name else 30

    # 1/<dnf_rate> chance of DNF
    # 1/20 chance of +2 if not DNF
    was_dnf = choice(range(dnf_rate)) == 0
    was_plus_two = False if was_dnf else choice(range(20)) == 0

    return UserSolve(time=centiseconds, is_dnf=was_dnf, is_plus_two=was_plus_two,
        scramble_id=scramble_id, is_inspection_dnf=False)


@app.cli.command()
def generate_fake_comp_results():
    """ Generates a bunch of fake results for the current competition with realistic-ish results. """

    test_users = [update_or_create_user_for_reddit(__TEST_USER_NAMES[i], '') for i in range(10)]

    for comp_event in get_all_comp_events_for_comp(get_active_competition().id):
        event_name = comp_event.Event.name

        if event_name in ('FMC', 'MBLD'):
            continue

        thresholds = __AUTO_BLACKLIST_THRESHOLDS.get(event_name)
        if not thresholds:
            continue

        wr_average = thresholds[1]

        for i, user in enumerate(test_users):
            results = UserEventResults(comp_event_id=comp_event.id, user_id=user.id, comment='')
            for solve in [__build_solve(i, wr_average, event_name, s.id) for s in comp_event.scrambles]:
                results.solves.append(solve)

            process_event_results(results, comp_event, user)
            save_event_results(results)

# -------------------------------------------------------------------------------------------------
# Other useful stuff
# -------------------------------------------------------------------------------------------------

@app.cli.command()
def show_slugified_event_names():
    """ Utility command to slugify all event names and display them in the terminal. """

    for event in get_all_events():
        print(slugify(event.name))
