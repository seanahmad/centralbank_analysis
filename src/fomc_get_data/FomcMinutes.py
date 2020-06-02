from datetime import date
import threading
import sys
import os
import pickle
import re

import requests
from bs4 import BeautifulSoup

import numpy as np
import pandas as pd

# Import parent class
from .FomcBase import FomcBase

class FomcMinutes(FomcBase):
    '''
    A convenient class for extracting minutes from the FOMC website
    Example Usage:  
        fomc = FomcMinutes()
        df = fomc.get_contents()
    '''
    def __init__(self, verbose = True, max_threads = 10, base_dir = '../data/FOMC/'):
        super().__init__('minutes', verbose, max_threads, base_dir)

    def _get_links(self, from_year):
        '''
        Override private function that sets all the links for the contents to download on FOMC website
         from from_year (=min(2015, from_year)) to the current most recent year
        '''
        self.links = []
        self.title = []
        self.speaker = []

        r = requests.get(self.calendar_url)
        soup = BeautifulSoup(r.text, 'html.parser')

        # Getting links from current page. Meetin scripts are not available.
        if self.verbose: print("Getting links for minutes...")
        contents = soup.find_all('a', href=re.compile('^/monetarypolicy/fomcminutes\d{8}.htm'))
        
        self.links = [content.attrs['href'] for content in contents]
        self.speaker = [self._speaker_from_date(self._date_from_link(x)) for x in self.links]
        self.title = [self.content_type] * len(self.links)
        if self.verbose: print("{} links found in the current page.".format(len(self.links)))

        # Archived before 2015
        if from_year <= 2014:
            for year in range(from_year, 2015):
                yearly_contents = []
                fomc_yearly_url = self.base_url + '/monetarypolicy/fomchistorical' + str(year) + '.htm'
                r_year = requests.get(fomc_yearly_url)
                soup_yearly = BeautifulSoup(r_year.text, 'html.parser')
                yearly_contents = soup_yearly.find_all('a', href=re.compile('(^/monetarypolicy/fomcminutes|^/fomc/minutes|^/fomc/MINUTES)'))
                for yearly_content in yearly_contents:
                    self.links.append(yearly_content.attrs['href'])
                    self.speaker.append(self._speaker_from_date(self._date_from_link(yearly_content.attrs['href'])))
                    self.title.append(self.content_type)
            if self.verbose: print("YEAR: {} - {} links found.".format(year, len(yearly_contents)))
        print("There are total ", len(self.links), ' links for ', self.content_type)

    def _add_article(self, link, index=None):
        '''
        Override a private function that adds a related article for 1 link into the instance variable
        The index is the index in the article to add to. 
        Due to concurrent prcessing, we need to make sure the articles are stored in the right order
        '''
        if self.verbose:
            sys.stdout.write(".")
            sys.stdout.flush()

        link_url = self.base_url + link
        article_date = self._date_from_link(link)
        # print(link_url)

        # date of the article content
        self.dates.append(article_date)

        res = requests.get(self.base_url + link)
        html = res.text
        # p tag is not properly closed in many cases
        html = html.replace('<P', '<p').replace('</P>', '</p>')
        html = html.replace('<p', '</p><p').replace('</p><p', '<p', 1)

        # remove all after appendix or references
        x = re.search(r'(<b>references|<b>appendix|<strong>references|<strong>appendix)', html.lower())
        if x:
            html = html[:x.start()]
            html += '</body></html>'
        # Parse html text by BeautifulSoup
        article = BeautifulSoup(html, 'html.parser')
    
        # Remove footnote
        for fn in article.find_all('a', {'name': re.compile('fn\d')}):
            if fn.parent:
                fn.parent.decompose()
            else:
                fn.decompose()
            # Get all p tag
            paragraphs = article.findAll('p')
            self.articles[index] = "\n\n[SECTION]\n\n".join([paragraph.get_text().strip() for paragraph in paragraphs])