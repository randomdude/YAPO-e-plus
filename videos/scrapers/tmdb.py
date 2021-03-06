import os
from datetime import datetime

import django
import tmdbsimple as tmdb

from utils import Constants

import logging

from videos.scrapers.scanner_common import scanner_common

log = logging.getLogger(__name__)

django.setup()

from videos.models import Actor

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "YAPO.settings")

tmdb.API_KEY = '04308f6d1c14608e9f373b84ad0e4e4c'

class scanner_tmdb(scanner_common):

    def search_alias(self, actor_in_question, alias, force):
        success = False
        if force:
            success = self.search_person(actor_in_question, alias, force)
        elif not actor_in_question.last_lookup:
            success = self.search_person(actor_in_question, alias, force)
        return success

    def search_person_with_force_flag(self, actor_in_question : Actor, force : bool):
        success = False
        log.info(f"Looking for: {actor_in_question.name}")
        if force:
            log.info("Force flag is true, ignoring last lookup")
            success = self.search_person(actor_in_question, None, force)
        elif not actor_in_question.last_lookup:
            log.info(f"Actor: {actor_in_question.name} was not yet searched... Searching now!")
            success = self.search_person(actor_in_question, None, force)

        return success

    # Search for an actor on TMDB. Return False if the actor was not found.
    def search_person(self, actor_in_question, alias, force) -> bool:

        log.info(f"Looking for: {actor_in_question.name}")
        search = tmdb.Search()
        if not alias:
           search.person(query=actor_in_question.name, include_adult='true')
        else:
           search.person(query=alias.name, include_adult='true')

        # We're only interesed in 'adult' results.
        results = [ x for x in search.results if x.get('adult', False) ]

        if len(results) == 0:
            log.info(f"Actor: {actor_in_question.name} could not be found on TMDb\r\n")
            return False

        person_info_list = map(lambda x: tmdb.People(str(x['id'])).info(), results)
        self.add_search_results_to_actor(actor_in_question, force, person_info_list)
    
        return True

    def add_search_results_to_actor(self, actor_in_question: Actor, force: bool, person_info_list) -> None:
        for person_info in person_info_list:
            self.add_search_result_to_actor(actor_in_question, force, person_info)

        actor_in_question.last_lookup = datetime.now()
        actor_in_question.save()

    def add_search_result_to_actor(self, actor_in_question: Actor, force: bool, person_info: dict) -> None:
        if actor_in_question.id is None:
            actor_in_question.save()

        actor_in_question.tmdb_id = person_info['id']
        actor_in_question.imdb_id = person_info['imdb_id']

        # Image download
        if actor_in_question.thumbnail == Constants().unknown_person_image_path or force:
            if person_info['profile_path'] is not None:
                picture_link = f"https://image.tmdb.org/t/p/original/{person_info['profile_path']}"
                log.info(f"Trying to get image from TMDB: {picture_link}")
                self.save_actor_profile_image_from_web(picture_link, actor_in_question, force)

        if person_info['biography'] is not None:
            if not actor_in_question.description or (len(actor_in_question.description) < 48):
                actor_in_question.description = person_info['biography']
            log.info("There's no description or it's too short, so added it from TMDB.")

        if not person_info['birthday'] == "":
            actor_in_question.date_of_birth = person_info['birthday']
            log.info(f"Added Birthday to: {actor_in_question.name}")

        if not actor_in_question.gender:
            person_gender = person_info['gender']
            if person_gender == 2:
                actor_in_question.gender = 'M'
                log.info(f"Added Gender to: {actor_in_question.name}")
            elif person_gender == 1:
                actor_in_question.gender = 'F'
                log.info(f"Added Gender to: {actor_in_question.name}")

        if person_info['homepage']:
            actor_in_question.official_pages = person_info['homepage']
            log.info(f"Added Homepage to: {actor_in_question.name}")

        for aka in person_info['also_known_as']:
            actor_in_question.createOrAddAlias(aka.strip())

