# dnmlb by drageon@disowned.net. Based off of the work of reticulatingspline@github.
import urllib3
import sys
import json, ast
from pytz import timezone
from datetime import datetime, timedelta
from lxml import html, etree
import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
from supybot.i18n import PluginInternationalization, internationalizeDocstring
import commands

_ = PluginInternationalization('dnmlb')

@internationalizeDocstring
class dnmlb(callbacks.Plugin):
    """Shows mlb scores and standings"""
    threaded = True

    def __init__(self, irc):
      self.__parent = super(dnmlb, self)
      self.__parent.__init__(irc)
      # Valid game statuses.
      self.upcoming_status = [ 'Preview', 'Pre-Game', 'Warmup' ]
      self.inprogress_status = [ 'Delayed Start', 'In Progress', 'Manager Challenge', 'Suspended', 'Review' ]
      self.final_status = [ 'Final', 'Game Over', 'Completed Early' ]
      self.postponed_status = [ 'Postponed', 'Delayed', 'Cancelled' ]
      self.leagues = [ 'al', 'nl' ]
      self.divisions = [ 'east', 'central', 'west' ]

    """ {{{ Small methods for colors/misc stuff.
    """
    def _red(self, string):
      return ircutils.mircColor(string, 'red')

    def _redpad(self, string):
      return ircutils.mircColor(string, 'red') + ''

    def _yellow(self, string):
      return ircutils.mircColor(string, 'yellow')

    def _yellowpad(self, string):
      return ircutils.mircColor(string, 'yellow') + ''

    def _green(self, string):
      return ircutils.mircColor(string, 'green')

    def _greenpad(self, string):
      return ircutils.mircColor(string, 'green') + ''

    def _bold(self, string):
      return ircutils.bold(string)

    def _uline(self, string):
      return ircutils.underline(string)

    def _buline(self, string):
      return ircutils.bold(ircutils.underline(string))

    def _stripf(self, string):
      return ircutils.stripFormatting(string)

    def _searchlist(self, wmatch, wlist):
      self.log.info('_searchlist: called with word: %s list: %s', wmatch, wlist)
      for word in wlist:
        if word == wmatch:
          self.log.info('_searchlist: matched word: %s in list: %s', word, wlist)
          return word
          break
      self.log.info('_searchlist: no match for word: %s in list: %s', wmatch, wlist)
      return False

    def _log(self, lt, text):
      self.log.info("dnmlb::%s %s", lt, text)

    """ }}} """
  
    """ {{{ Get current date.
    Get our date to search for. If before 6am Eastern, show yesterday's scores.
    """
    def _getdate(self, period=None):
      tz = timezone('America/New_York')
      todaytime = datetime.now(tz)

      if int(todaytime.hour) in [ 0, 1, 2, 3, 4 , 5 ]:
	todaytime = todaytime - timedelta(days=1)

      tomorrowtime = todaytime + timedelta(days=1)
      yesterdaytime = todaytime - timedelta(days=1)

      if (period in [ 'yesterday', 'tomorrow' ]):
        if (period == 'yesterday'):
          date = yesterdaytime.strftime('%Y %m %d')
        if (period == 'tomorrow'):
          date = tomorrowtime.strftime('%Y %m %d')
      else:
        date = todaytime.strftime('%Y %m %d')
        
      return date

    """ }}} """

    """ {{{ Build URL.
    """
    def _buildurl(self, utype, date, gid=False):
      year = date.split(' ')[0]
      month = date.split(' ')[1]
      day = date.split(' ')[2]
      begin_url = "http://gd2.mlb.com/components/game/mlb"
      date_url = "/year_" + year + "/month_" + month + "/day_" + day + "/"
      if (utype == 'scoreboard'):
        end_url = "master_scoreboard.json"
      elif (utype == 'rawbox'):
        gid = gid.replace('/', '_').replace('-', '_')
        end_url = "gid_%s/rawboxscore.xml" % (gid)

      url = begin_url + date_url + end_url
    
      return url
    """ }}} """
    
    """ {{{ Fetch our URL.
    """
    def _fetchurl(self, utype, date=False, gid=False):
      if utype == 'scoreboard':
        url = self._buildurl(utype, date)
        #url = 'http://192.168.69.1/master_scoreboard.json'
      elif utype == 'rawbox':
        url = self._buildurl(utype, date, gid)
        #url = 'http://192.168.69.1/rawboxscore.xml'
      elif utype == 'standings':
        url = "http://m.mlb.com/standings/"
      uagent = 'Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0'
      headers = urllib3.make_headers(user_agent=uagent)
      http = urllib3.PoolManager()
      
      try:
        self.log.info('_fetchurl: Fetching %s', url)
        #print "Fetching URL: %s" % (url)
        req = http.request('GET', url, headers=headers)
      except:
        return 'error_fetch'
    
      req.close()
     
      #print "HTTP Response: %s" % (req.status)
      if req.status != 200:
        self.log.info('_fetchurl: Error fetching %s: %s', url, req.status)
        return 'error_%i' % (req.status)
    
      return req.data
    """ }}} """

    """ {{{ Parse info from scoreboard.
    End result here is to create a master dict with indexing by game id as we'll
    reference that later on to get specific game data.
    """
    def _getscoreboardinfo(self, date):
      self.log.info('_getscoreboardinfo: called with date %s', date)
      """ {{{ Build TV feed information
      """
      def __buildtv(feed):
        lt = '_getscoreboardinfo::__buildtv'
        # Shorten up some channel names.
        if 'ESPN' in feed:
          feed = 'ESPN'
        elif 'SportsNet LA' in feed:
          feed = 'SportsNet LA'
        elif 'FOX Deportes San Diego' in feed:
          feed = 'FSSD'
        elif 'ROOT SPORTS' in feed:
          feed = 'ROOT'
        elif type(feed) == dict:
          feed = '--'
        elif 'out-of-market' in feed:
          feed = feed.replace(' (out-of-market only)','')
        elif 'Fox  Sports Sun' in feed:
          feed = 'FSSun'
        else:
          feed = feed

        #self._log(lt, "feed: %s" % (feed))
        return feed
      """ }}} """
    
      """ {{{ Build HR list.
      """
      def __buildhrs(team_code, hr_data):
        hrs = []
    
        # Single home runs or just hrs by one player on one team come across as a dict.
        if type(hr_data) == list:
          for homerun in hr_data:
            if homerun['team_code'] == team_code:
              hrs.append(homerun)
        else:
         hrs.append(hr_data)
    
        hrs_output = []
        for player in hrs:
          name = player['name_display_roster']
          hr = player['hr']
          yr_hr = player['std_hr']
          player_item = "%s(%s/%s)" % (name, hr, yr_hr)
          hrs_output.append(player_item)
    
        return hrs_output
      """ }}} """
    
      """ {{{ Build Runners on Base.
      """
      def __buildrunners(runners):
        if runners in [ '1', '2', '3', '4', '5', '6', '7' ]:
          if (runners == '4'):
            runners = '1 & 2'
          elif (runners == '5'):
            runners = 'Corners'
          elif (runners == '6'):
            runners = '2 & 3'
          elif (runners == '7'):
            runners = 'Loaded'
          else:
            runners = runners
        else:
          runners = None
    
        return runners
    
      """ }}} """
      """ {{{ Append add list of gids to dicts with team names """
      def __add_gid_team(datadict, team, gid):
        gids = []
        if datadict.has_key(team):
          gids = datadict[team]
        gids.append(gid)
        datadict[team] = gids
      """ }}} """

      # Get scoreboard json file.
      scoreboard_json = self._fetchurl('scoreboard', date)
    
      # Bail if we can't get our scoreboard.
      if 'error_' in scoreboard_json:
        error = "ERROR: Couldn't get scoreboard! Code: %s" % (scoreboard_json)
        self.log.info('_getscoreboardinfo: %s', error)
        return error
    
      # Date can now be YYYYMMDD, without spaces.
      rawdate = date
      date = date.replace(' ','')
    
      #scoreboard_json = json.loads(scoreboard_json)
      scoreboard_json = ast.literal_eval(scoreboard_json)
      if (scoreboard_json['data']['games'].has_key('game')):
        games = scoreboard_json['data']['games']['game']
      else:
        self.log.info('_getscoreboardinfo: no games found')
        return 'ERROR: No games found'

      # if there is only one game, games is a dict, make it a list.
      if type(games) == dict:
        games = [ games ]
      elif type(games) == list:
        self.log.info('_getscoreboardinfo: games type: %s' % (type(games)))
      else:
        self.log.info('_getscoreboardinfo: games is an unknown type: %s' % (type(games)))
	return 'ERROR: Issue parsing scoreboard info'
     
      numgames = len(games)
      self.log.info('_getscoreboardinfo: numgames: %s date: %s', numgames, date)
      # Loop through games if we have some. We'll want gid to be our primary key.
      # this means we'll need to reconstruct the json for our needs. I also add in
      # a few other nice to have data points/easier to use data.
      if numgames > 0:
        self.log.info('_getscoreboardinfo: Found %i Game(s) for %s', numgames, date)
        all_games = {}
        all_gids = []
        all_games['total'] = numgames
        away_team_cities = {}
        away_team_abbrevs = {}
        away_team_names = {}
        home_team_cities = {}
        home_team_abbrevs = {}
        home_team_names = {}
        for game in games:
          gid = game['id']
          status = game['status']['status']
          status_ind = game['status']['ind']
          self.log.info('_getscoreboardinfo: gid %s status %s', gid, status)
          # Compile a 'all_gids' list.
          all_gids.append(gid)
          # Data we'll need no matter the game status.
          all_games[gid] = { 
            'gid': gid,
            'date': rawdate,
            'status': status,
            'status_ind': status_ind,
            'away_name_abbrev': game['away_name_abbrev'],
            'home_name_abbrev': game['home_name_abbrev'],
            'away_team_code': game['away_code'],
            'home_team_code': game['home_code'],
            'away_team_name': game['away_team_name'],
            'home_team_name': game['home_team_name'],
            'away_team_city': game['away_team_city'],
            'home_team_city': game['home_team_city'],
            'away_team_wl': game['away_win'] + '-' + game['away_loss'],
            'home_team_wl': game['home_win'] + '-' + game['home_loss'] }
          away_team_city = game['away_team_city'].lower()
          away_team_abbrev = game['away_name_abbrev'].lower()
          away_team_name = game['away_team_name'].lower()
         
          home_team_city = game['home_team_city'].lower()
          home_team_abbrev = game['home_name_abbrev'].lower()
          home_team_name = game['home_team_name'].lower()
    
          __add_gid_team(away_team_cities, away_team_city, gid)
          __add_gid_team(away_team_abbrevs, away_team_abbrev, gid)
          __add_gid_team(away_team_names, away_team_name, gid)
          __add_gid_team(home_team_cities, home_team_city, gid)
          __add_gid_team(home_team_abbrevs, home_team_abbrev, gid)
          __add_gid_team(home_team_names, home_team_name, gid)

          # Data needed in multiple statuses
          if (status in self.inprogress_status) or (status in self.final_status):
            all_games[gid]['away_score'] = game['linescore']['r']['away']
            all_games[gid]['home_score'] = game['linescore']['r']['home']
            all_games[gid]['inning'] = game['status']['inning']
            if (status in self.final_status):
              all_games[gid]['inning_state'] = 'Final'
            else:
              all_games[gid]['inning_state'] = game['status']['inning_state']
          if (status in self.upcoming_status):
            # Pitchers.
            all_games[gid]['away_pitcher'] = {
              'name': game['away_probable_pitcher']['name_display_roster'],
              'era': game['away_probable_pitcher']['era'],
              'hand': game['away_probable_pitcher']['throwinghand'],
              'wl': game['away_probable_pitcher']['wins'] + '-' + game['away_probable_pitcher']['losses'] }
            all_games[gid]['home_pitcher'] = {
              'name': game['home_probable_pitcher']['name_display_roster'],
              'era': game['home_probable_pitcher']['era'],
              'hand': game['home_probable_pitcher']['throwinghand'],
              'wl': game['home_probable_pitcher']['wins'] + '-' + game['home_probable_pitcher']['losses'] }
    
          # {{{ Handle games in upcoming_status.
          if status in self.upcoming_status:
            # Data only available to upcoming_status games.
            all_games[gid]['time'] = game['time'] + game['ampm']
	    if (all_games[gid]['time'] == '3:33AM'):
	      all_games[gid]['time'] = 'TBD'
            # TV feeds.
            if game.has_key('broadcast'):
              if game['broadcast']['away'].has_key('tv'):
                away_tv_feed = __buildtv(game['broadcast']['away']['tv'])
              else:
                away_tv_feed = '--'
              if game['broadcast']['home'].has_key('tv'):
                home_tv_feed = __buildtv(game['broadcast']['home']['tv'])
              else:
                home_tv_feed = '--'
              all_games[gid]['away_tv_feed'] = away_tv_feed
              all_games[gid]['home_tv_feed'] = home_tv_feed
            else:
              all_games[gid]['away_tv_feed'] = '--'
              all_games[gid]['home_tv_feed'] = '--'

            #print all_games
            #sys.exit(0)
            #_printscore_upcoming(all_games[gid])
          # }}}  
          # {{{ Handle games in inprogress_status.
          elif status in self.inprogress_status:
            # Data only available to inprogress_status games.
            all_games[gid]['runners'] = __buildrunners(game['runners_on_base']['status'])
            all_games[gid]['pitching'] = game['pitcher']['name_display_roster']
            all_games[gid]['pitching_id'] = game['pitcher']['id']
            all_games[gid]['batting'] = game['batter']['name_display_roster']
            all_games[gid]['balls'] = game['status']['b']
            all_games[gid]['strikes'] = game['status']['s']
            all_games[gid]['outs'] = game['status']['o']
            all_games[gid]['last_play'] = game['pbp']['last'].replace('  ',' ').replace('.  ','. ')
            if (status == 'Suspended') or (status == 'Delayed Start'):
              if (game['status']['reason'] != ''):
                all_games[gid]['reason'] = game['status']['reason']
            #_printscore_inprogress(all_games[gid])
          # }}}
          # {{{ Handle games in final_status.
          elif status in self.final_status:
            # Homeruns.
            all_games[gid]['away_hrs'] = { 'total': game['linescore']['hr']['away'] }
            all_games[gid]['home_hrs'] = { 'total': game['linescore']['hr']['home'] }
            if int(all_games[gid]['away_hrs']['total']) > 0:
              all_games[gid]['away_hrs']['players'] = __buildhrs(game['away_code'], game['home_runs']['player'])
            if int(all_games[gid]['home_hrs']['total']) > 0:
              all_games[gid]['home_hrs']['players'] = __buildhrs(game['home_code'], game['home_runs']['player'])
            # Pitchers.
            all_games[gid]['win_pitcher'] = {
              'name': game['winning_pitcher']['name_display_roster'],
              'era': game['winning_pitcher']['era'],
              'wl': game['winning_pitcher']['wins'] + '-' + game['winning_pitcher']['losses'] }
            all_games[gid]['lose_pitcher'] = {
              'name': game['losing_pitcher']['name_display_roster'],
              'era': game['losing_pitcher']['era'],
              'wl': game['losing_pitcher']['wins'] + '-' + game['losing_pitcher']['losses'] }
            # If we have a saving pitcher, gather that data too.
            if game['save_pitcher']['name_display_roster']:
              all_games[gid]['save_pitcher'] = {
                'name': game['save_pitcher']['name_display_roster'],
                'era': game['save_pitcher']['era'],
                'wl': game['save_pitcher']['wins'] + '-' + game['save_pitcher']['losses'],
                'sso': game['save_pitcher']['saves'] + '-' + game['save_pitcher']['svo'] }
            # If game completed early, say why
            if status == 'Completed Early':
              all_games[gid]['reason'] = game['status']['note']
            #_printscore_final(all_games[gid])
          # }}}
          
          # {{{ Handle games in postponed_status.
          elif status in self.postponed_status:
             all_games[gid]['reason'] = game['status']['reason']
             all_games[gid]['time'] = game['time'] + game['ampm']
             #print all_games[gid]['status']
             if (all_games[gid]['status_ind'] == 'IR'):
               all_games[gid]['away_score'] = game['linescore']['r']['away']
               all_games[gid]['home_score'] = game['linescore']['r']['home']
               all_games[gid]['inning'] = game['status']['inning']
               all_games[gid]['inning_state'] = game['status']['inning_state']
               all_games[gid]['runners'] = __buildrunners(game['runners_on_base']['status'])
               all_games[gid]['pitching'] = game['pitcher']['name_display_roster']
               all_games[gid]['batting'] = game['batter']['name_display_roster']
               all_games[gid]['balls'] = game['status']['b']
               all_games[gid]['strikes'] = game['status']['s']
               all_games[gid]['outs'] = game['status']['o']
               all_games[gid]['last_play'] = game['pbp']['last'].replace('  ',' ').replace('.  ','. ')
          # }}}
          else:
            error =  "ERROR: Unknown gamestatus for game %s: %s" % (gid, status)
            return error
    
        all_games['gids'] = all_gids
        all_games['away_team_cities'] = away_team_cities
        all_games['away_team_abbrevs'] = away_team_abbrevs
        all_games['away_team_names'] = away_team_names
    
        all_games['home_team_cities'] = home_team_cities
        all_games['home_team_abbrevs'] = home_team_abbrevs
        all_games['home_team_names'] = home_team_names
    
        #_printscore_all(all_games).
        return all_games
    
      else:
        error = "ERROR: No games found for date %s" % (date)
        return error
    """ }}} """
    
    """ {{{ Search for game
    """
    def _searchgame(self, term, games):
      self.log.info('_searchgame: called with term %s', term)
      # Alternate names
      alt_names = { 'fish': 'mia', 'barves': 'atl', 'matts': 'nym',
                    'friars': 'sd', 'dads': 'sd', 'mountains': 'col',
		    'beers': 'mil', 'brews': 'mil', 'shittsburgh': 'pit',
		    'gigantes': 'sf', 'gnats': 'wsh', 'dbags': 'D-backs',
                    'sfo': 'sf', 'doyers': 'Dodgers' }
      if term in alt_names.keys():
        term = alt_names[term]
      try:
        search_sources = [ games['away_team_cities'], games['away_team_abbrevs'],
                           games['away_team_names'], games['home_team_cities'],
                           games['home_team_abbrevs'], games['home_team_names'] ]
        term = term.lower()
        match_gid = []
        for si in search_sources:
          for name, gid in si.iteritems():
            if term in name:
              for g in gid:
                match_gid.append(g)
              break
    
        if match_gid:
          result = list(set(match_gid))
          return result
        else:
          return None
      except:
        return None
    """ }}} """
    
    """ {{{ Determine proper print function for search query of games
    """
    def _procsearchresult(self, results, games):
      gameresults = []
      self.log.info('_procsearchresult: called with results %s', results)
      #try:
      if results:
        for gid in results:
          game = games[gid]
          status = game['status']
          self.log.info('_procsearchresult: gid: %s status: %s', gid, status)
          if status in self.upcoming_status:
           gameresults.append(self._printscore_upcoming(game))
          elif status in self.inprogress_status:
           gameresults.append(self._printscore_inprogress(game))
          elif status in self.final_status:
           gameresults.append(self._printscore_final(game))
          elif status in self.postponed_status:
           gameresults.append(self._printscore_postponed(game))
          else:
            gameresults.append("ERROR: gameid %s has unknown status %s" % (gid, status))
      else:
        gameresults.append("ERROR: Found no results.")
      #except:
      #  gameresults.append("ERROR: Found no results.")

      return gameresults
    
    """ }}} """
    
    """ {{{ Print all scores in a line
    """
    def _printscore_all(self, all_games):
      self.log.info('_printscore_all: called with datatype %s', type(all_games))
      if (type(all_games) != dict):
        output_line = 'ERROR: Found no results.'
	return output_line
      else:
        output_line = []
        output_line2 = []
        counter = 0
        for gid in all_games['gids']:
          counter += 1
          game = all_games[gid]
          away = game['away_name_abbrev']
          home = game['home_name_abbrev']
          status = game['status']
          self.log.info('_printscore_all: gid %s status %s', gid, status)
          if (status in self.final_status) or (status in self.inprogress_status):
            away_score_data = int(game['away_score'])
            home_score_data = int(game['home_score'])
            # Operators don't work when irc colors are in use.
            if (home_score_data > away_score_data): 
              home_score = self._bold(home_score_data)
              home = self._bold(home)
            else:
              home_score = home_score_data
            if (away_score_data > home_score_data): 
              away_score = self._bold(away_score_data)
              away = self._bold(away)
            else:
              away_score = away_score_data
            if (status in self.final_status):
              if (int(game['inning']) > 9) or (int(game['inning']) < 9):
                inning_state = game['inning_state'][0] + '/' + game['inning']
              else:
                inning_state = game['inning_state'][0]
              inning_state = self._red(inning_state)
            else:
              if (status == 'Suspended'):
                susp = self._red('SUSP')
                inning_state = game['inning_state'][0] + game['inning'] + ' ' + susp
              elif (status == 'Delayed Start'):
                inning_state = self._yellow('DLY')
                if game.has_key('reason'):
                  inning_state = '%s (%s)' % (inning_state, game['reason'])
              else:
                inning_state = game['inning_state'][0] + game['inning']
                if (game['inning_state'][0] == 'M'):
                  inning_state = self._yellow(inning_state)
                elif (game['inning_state'][0] == 'E'):
                  inning_state = self._red(inning_state)
                else:
                  inning_state = self._green(inning_state)
            status = inning_state
            line = "%s %s %s %s %s |" % (away, away_score, home, home_score, status)
          elif (status in self.upcoming_status):
            time = game['time']
            line =  "%s @ %s %s |" % (away, home, time)
          elif (status in self.postponed_status):
	    if game.has_key('status_ind') and (status != 'Postponed') and (status != 'Cancelled'):
              away_score_data = int(game['away_score'])
              home_score_data = int(game['home_score'])
              # Operators don't work when irc colors are in use.
              if (home_score_data > away_score_data): 
                home_score = self._bold(home_score_data)
                home = self._bold(home)
              else:
                home_score = home_score_data
              if (away_score_data > home_score_data): 
                away_score = self._bold(away_score_data)
                away = self._bold(away)
              else:
                away_score = away_score_data
            if game.has_key('delay_reason'):
              line = "%s @ %s %s (%s) |" % (away, home, self._yellow('DLY'), game['delay_reason'])
            elif (game['status_ind'] == 'IR'):
              inning_state = game['inning_state'][0] + game['inning']
              if (game['inning_state'][0] == 'M'):
                inning_state = self._yellow(inning_state)
              elif (game['inning_state'][0] == 'E'):
                inning_state = self._red(inning_state)
              else:
                inning_state = self._green(inning_state)
              status = "%s %s (%s)" % (inning_state, self._yellow('DLY'), game['reason'])
              line = "%s %s %s %s %s |" % (away, away_score, home, home_score, status)
            else:
              if (status == 'Cancelled'):
                line = "%s @ %s %s |" % (away, home, self._red('CAN'))
              else:
                line = "%s @ %s %s |" % (away, home, self._red('PPD'))
          else:
            line = "%s %s %s |" % (away, home, status)

          # if >16 games, we need to made two lines.
          if (counter < 16):
            output_line.append(line)
          else:
            output_line2.append(line)

      if output_line2:
        output_line = ' '.join(output_line).rstrip('|')
        output_line2 = ' '.join(output_line2).rstrip('|')
        output = [ output_line, output_line2 ]
      else:
        output_line = ' '.join(output_line).rstrip('|')
        output = output_line

      return output
    """ }}} """  
    
    """ {{{ Game in upcoming status.
    """
    def _printscore_upcoming(self, game):
      status = game['status']
      away = game['away_team_city']
      home = game['home_team_city']
    
      if game['away_tv_feed'] == game['home_tv_feed']:
        tv_feed = "%s" % (game['home_tv_feed'])
      else:
        tv_feed = "%s/%s" % (game['away_tv_feed'], game['home_tv_feed'])

      # NY Mets (0-0) @ Atlanta (0-0)
      team_line = "%s (%s) @ %s (%s)" % (away, game['away_team_wl'], home, game['home_team_wl'])
    
      # Gee RHP (-.--/0-0) vs Teheran RHP (-.--/0-0)
      ap = game['away_pitcher']
      hp = game['home_pitcher']
    
      if ap['name'] == '':
        away_pitcher = 'TBD'
      else:
        away_pitcher = "%s %s (%s/%s)" % (ap['name'], ap['hand'], ap['era'], ap['wl'])
      if hp['name'] == '': 
        home_pitcher = 'TBD'
      else:
        home_pitcher = "%s %s (%s/%s)" % (hp['name'], hp['hand'], hp['era'], hp['wl'])
    
      if home_pitcher == away_pitcher:
        pitcher_line = None
      else:
        pitcher_line = "%s vs %s" % (away_pitcher, home_pitcher)
    
      if status == 'Warmup':
        if pitcher_line:
          # NY Mets @ Atlanta 7:10PM :: Gee (-.--/0-0) vs Teheran (1.50/1-0) :: Warmup
          status_line = "%s %s :: %s :: %s" % (team_line, game['time'], pitcher_line, status)
        else:
          status_line = "%s %s :: %s" % (team_line, game['time'], status)
      else:
        if pitcher_line:
          # NY Mets @ Atlanta 7:10PM :: Gee (-.--/0-0) vs Teheran (1.50/1-0) :: TV: SNY/FSSO
          status_line = "%s %s :: %s :: TV: %s" % (team_line, game['time'], pitcher_line, tv_feed)
        else:
          status_line = "%s %s :: TV: %s" % (team_line, game['time'], tv_feed)
    
      return status_line
    """ }}} """
    
    """ {{{ Game in in-progress status.
    """
    def _printscore_inprogress(self, game):
      lt = '_printscore_inprogress'
      print game['pitching_id']
      gid = game['gid']
      status = game['status']
      away = game['away_team_city']
      away_score_data = int(game['away_score'])
      home = game['home_team_city']
      home_score_data = int(game['home_score'])
      runners = game['runners']
      lastplay = game['last_play']
      if (status != 'Delayed Start'):
        inning_state = game['inning_state'][0]
        inning = inning_state + game['inning']
        if (inning_state == 'M'): 
          inning = self._yellow(inning)
        elif (inning_state == 'E'):
          inning = self._red(inning)
        else: 
          #def _fetchurl(self, utype, date=False, gid=False):
          rawbox_xml = self._fetchurl('rawbox', game['date'], gid)
          pitcher_data = {}
          if 'error_' in rawbox_xml:
            self.log.info('_printscore_inprogress: error fetching rawbox %s', rawbox_xml)
          else:
            rawbox_xml = etree.fromstring(rawbox_xml)
            inning = self._green(inning)
            # Assemble pitcher data
            for p in rawbox_xml.xpath('//team//pitcher'):
              p_id = p.attrib['id']
              self._log(lt, 'pitcher_data: %s' % p.attrib)
              pitcher_data[p_id] = { 'era': p.attrib['bam_era'], 'pitches': p.attrib['np'] }
      else:
        inning_state = None
        inning = None
    
      if (away_score_data > home_score_data):
        away = self._bold(away)
        away_score = self._bold(away_score_data)
      else:
        away_score = away_score_data
   
      if (home_score_data > away_score_data):
        home = self._bold(home)
        home_score = self._bold(home_score_data)
      else:
        home_score = home_score_data
        
      # NY Yankees 1 Boston 2 M7
      if (status == 'Suspended'):
        score_line = "%s %s %s %s %s %s (%s)" % (away, away_score, home, home_score, inning, self._red('Suspended'), game['reason'])
      elif (status == 'Delayed Start'):
        score_line = "%s %s %s %s %s (%s)" % (away, away_score, home, home_score, self._yellow('Delayed'), game['reason'])
      else:
        score_line = "%s %s %s %s %s" % (away, away_score, home, home_score, inning)
      # B:1 S:2 O:2
      count_line = "%s%s %s%s %s%s" % (self._greenpad('B:'), game['balls'], self._redpad('S:'), game['strikes'], self._yellowpad('O:'), game['outs'])
      
      if runners:
        # RO: 3 :: B:1 S:2 O:2
        runner_line = "%s %s" % (self._yellow('RO:'), game['runners'])
        count_line = "%s :: %s" % (runner_line, count_line)
      
      # If middle or end of inning, remove batter/pitcher
      if inning_state: 
        if inning_state in [ 'M', 'E' ]:
          if lastplay:
            # Mike Napoli grounds out sharply.
            info_line = "%s" % (lastplay)
            # NY Yankees 1 Boston 2 M7 :: Mike Napoli grounds out sharply.
            status_line = "%s :: %s" % (score_line, info_line)
          else:
            status_line = "%s" % (score_line)
        else:
          ab = self._bold('AB:')
	  cp = self._bold('P:')

          if pitcher_data:
            pitcher_id = game['pitching_id']
            pitch_count = pitcher_data[pitcher_id]['pitches']
	    if (int(pitch_count) >= 100):
	      pitch_count = self._red(pitch_count)
	    play_line = "%s %s %s %s (%s)" % (ab, game['batting'], cp, game['pitching'], pitch_count)
          else:
            play_line = "%s %s %s %s" % (ab, game['batting'], cp, game['pitching'])

          if lastplay:
            # AB: Napoli P: Martin, C :: Mike Napoli grounds out sharply.
            info_line = "%s :: %s" % (play_line, lastplay)
          else:
            # AB: Napoli P: Martin, C.
            info_line = play_line
          # Boston 8 NY Yankees 4 T9 :: RO: 2 :: B:0 S:0 O:2 :: AB: Craig P: Varvaro :: Pablo Sandoval strikes out swinging.
          status_line = "%s :: %s :: %s" % (score_line, count_line, info_line)
      else:
         status_line = score_line
    
      return status_line
      """ }}} """
    
    """ {{{ Game in final status.
    """
    def _printscore_final(self, game):
      status = game['status']
      away = game['away_team_city']
      ascore_data = int(game['away_score'])
      home = game['home_team_city']
      hscore_data = int(game['home_score'])

      if (ascore_data > hscore_data):
        ascore = self._bold(ascore_data)
        away = self._bold(away)
      else:
        ascore = ascore_data
      if (hscore_data > ascore_data):
        hscore = self._bold(hscore_data)
        home = self._bold(home)
      else:
        hscore = hscore_data

      wp = game['win_pitcher']
      lp = game['lose_pitcher']
    
      wp_line = "%s (%s/%s)" % (wp['name'], wp['era'], wp['wl'])
      lp_line = "%s (%s/%s)" % (lp['name'], lp['era'], lp['wl'])
    
      # If we have a saving pitcher, grab stats.
      if game.has_key('save_pitcher'):
        sp = game['save_pitcher']
        sp_line = "%s (%s/%s/%s)" % (sp['name'], sp['era'], sp['wl'], sp['sso'])
      else:
        sp_line = None
    
      # Deal with home runs.
      if game['away_hrs'].has_key('players'):
        ahr = game['away_hrs']
        ahrplayers = ' '.join(ahr['players'])
        away_team_hr_line = "%s(%s): %s" % (self._stripf(away), ahr['total'], ahrplayers)
      else:
        away_team_hr_line = None
    
      if game['home_hrs'].has_key('players'):
        hhr = game['home_hrs']
        hhrplayers = ' '.join(hhr['players'])
        home_team_hr_line = "%s(%s): %s" % (self._stripf(home), hhr['total'], hhrplayers)
      else:
        home_team_hr_line = None
      
      innings = 'F/' + game['inning']
      innings = self._red(innings)
    
      # Boston 8 NY Yankees 4 F/9  
      score_line = "%s %s %s %s %s" % (away, ascore, home, hscore, innings)
      if sp_line:
        pitcher_line = "%s %s %s %s %s %s" % (self._green('W:'), wp_line, self._red('L:'), lp_line, self._yellow('SV:'), sp_line)
      else:
        # W: Kelly, J (1.29/1-0) L: Warren (1.69/0-1)
        pitcher_line = "%s %s %s %s" % (self._green('W:'), wp_line, self._red('L:'), lp_line)
      
      # NY Yankees: Young C(1) Boston: Oritz D(1)
      if away_team_hr_line or home_team_hr_line:
        hr_line = ""
        if away_team_hr_line:
          hr_line += " %s %s" % (self._bold('HR:'), away_team_hr_line)
        if home_team_hr_line:
          hr_line += " %s %s" % (self._bold('HR:'), home_team_hr_line)
        hr_line = hr_line.lstrip(' ')
      else:
        hr_line = None
    
      if game.has_key('reason'):
        reason = game['reason']
      else:
        reason = False

      # Show homeruns if any.
      if hr_line:
        # Boston 8 NY Yankees 4 F :: W: Kelly, J (1.29/1-0) L: Warren (1.69/0-1)HR NY Yankees: Young C(1)
        status_line = "%s :: %s :: %s" % (score_line, pitcher_line, hr_line)
        if reason:
          status_line = status_line + " :: " + reason
      else:
        status_line = "%s :: %s" % (score_line, pitcher_line)
        if reason:
          status_line = status_line + " :: " + reason
      
      return status_line
      """ }}} """
    
    """ {{{ Game in postponed or delayed status.
    """
    def _printscore_postponed(self, game):
      away = game['away_team_city']
      arec = game['away_team_wl']
      home = game['home_team_city']
      hrec = game['home_team_wl']
      # Kansas City (0-0) @ Chi White Sox (0-0) 1:10PM Postponed (Rain)
      status_line = "%s (%s) @ %s (%s) %s %s" % (away, arec, home, hrec, game['time'], self._red(game['status']))
      if game.has_key('reason'):
        status_line = "%s (%s)" % (status_line, game['reason'])

      # If game in progress with a rain delay, do a long line status.
      if (game['status_ind'] == 'IR'):
         away_score_data = int(game['away_score'])
         home_score_data = int(game['home_score'])
         if (away_score_data > home_score_data):
           away = self._bold(away)
           away_score = self._bold(away_score_data)
         else:
           away_score = away_score_data
         if (home_score_data > away_score_data):
           home = self._bold(home)
           home_score = self._bold(home_score_data)
         else:
           home_score = home_score_data

         inning_state = game['inning_state'][0]
         inning = inning_state + game['inning']
         
         if (inning_state == 'M'):
           inning = self._yellow(inning)
         elif (inning_state == 'E'):
           inning = self._red(inning)
         else:
           inning = self._green(inning)

         inning = "%s %s (%s)" % (inning, self._yellow('Delayed'), game['reason'])

         runners = game['runners'] 
         pitcher = game['pitching']
         batter = game['batting']
         b = game['balls']
         s = game['strikes']
         o = game['outs']
         lp = game['last_play']

         score_line = "%s %s %s %s %s" % (away, away_score, home, home_score, inning)
         count_line = "%s%s %s%s %s%s" % (self._greenpad('B:'), b, self._redpad('S:'), s, self._yellowpad('O:'), o)
         batter_line = "AB: %s P: %s" % (batter, pitcher)

         if runners:
           runner_line = "%s %s" % (self._yellow('RO:'), runners)
           count_line = "%s :: %s" % (runner_line, count_line)

         if (inning_state == 'M') or (inning_state == 'E'):
            status_line = "%s" % (score_line)
            if lp:
              status_line = "%s :: %s" % (score_line, lp)
         else:
           status_line = "%s :: %s :: %s" % (score_line, count_line, batter_line)
           if lp:
             status_line = "%s :: %s :: %s :: %s" % (score_line, count_line, batter_line, lp)

      return status_line
      """ }}} """
    
    """ {{{ Get the mlb standings.
    """
    def _getstandings(self, league, division=False):

      """ {{{ Return standings.
      """
      def __returnstandings(standings_html, league, division):

        lt = "__returnstandings"
        output = []
        playoffs = False

        date = self._getdate()
        # If october, we're in playoff run season.
        if (date[1] == 10):
          playoffs = True

        self._log(lt, "date: %s playoffs: %s" % (date, playoffs))

        if (league == 'al'):  page_path = '//section[@id="league-103"]/table/tbody'
        if (league == 'nl'):  page_path = '//section[@id="league-104"]/table/tbody'

        if (division == 'east'): num = 0
        if (division == 'central'): num = 1
        if (division == 'west'): num = 2

        if (league == 'al'): league = 'AL'
        if (league == 'nl'): league = 'NL'
        if (league == 'NL') and (division == 'east'): division = 'Least'
        if (division == 'east'): division = 'East'
        if (division == 'central'): division = 'Central'
        if (division == 'west'): division = 'West'

        title = "%s %s" % (league, division)
        if (playoffs):
          banner = "%-16s %-5s %-5s %-5s %-5s %-5s %-5s %-4s" % (title, 'W', 'L', 'PCT', 'GB', 'WCGB', 'L10', 'STRK')
        else:
          banner = "%-16s %-5s %-5s %-5s %-5s %-5s %-4s" % (title, 'W', 'L', 'PCT', 'GB', 'L10', 'STRK')

        banner = self._buline(banner)
        output.append(banner)

        div_data = standings_html.xpath(page_path)[num]
        div_teams = div_data.cssselect('td.standings-col-division span.title')
        num_teams = len(div_teams)
        div_wins = div_data.cssselect('td.standings-col-w')
        div_losses = div_data.cssselect('td.standings-col-l')
        div_pct = div_data.cssselect('td.standings-col-pct')
        div_gb = div_data.cssselect('td.standings-col-gb')
	div_wcgb = div_data.cssselect('td.standings-col-wcgb')
        div_l10 = div_data.cssselect('td.standings-col-l10')
        div_strk = div_data.cssselect('td.standings-col-strk')

        counter = 0
        while num_teams > counter:
          team = div_teams[counter].text
          wins = div_wins[counter].text
          losses = div_losses[counter].text
          pct = div_pct[counter].text
          gb = div_gb[counter].text
	  wcgb = div_wcgb[counter].text
	  if wcgb == None: wcgb = '-'
          l10 = div_l10[counter].text
          strk = div_strk[counter].text
          #self._log(lt, "team: %s w: %s l: %s pct: %s gb: %s wcgb: %s l10: %s strk: %s" % (team, wins, losses, pct, gb, wcgb, l10, strk))

          if ('W' in strk): strk = self._green(strk)
          if ('L' in strk): strk = self._red(strk)

          if (not playoffs and gb == '-'):
            team = self._bold(team)
            line = "%-18s %-5s %-5s %-5s %-5s %-5s %-5s" % (team, wins, losses, pct, gb, l10, strk)
          # Hunt for october, start showing wild card contenders.
          elif (playoffs and gb == '-'):
            team = self._bold(team)
            line = "%-18s %-5s %-5s %-5s %-5s %-5s %-5s %-5s" % (team, wins, losses, pct, gb, wcgb, l10, strk)
          elif (playoffs and gb == '-' and wcgb == '-'):
            team = self._bold(team)
            line = "%-18s %-5s %-5s %-5s %-5s %-5s %-5s %-5s" % (team, wins, losses, pct, gb, wcgb, l10, strk)
          elif ('+' in wcgb and playoffs) or (wcgb == '-' and gb != '-' and playoffs):
	    team = '*' + team
	    team = self._bold(team)
            line = "%-18s %-5s %-5s %-5s %-5s %-5s %-5s %-5s" % (team, wins, losses, pct, gb, wcgb, l10, strk)
          elif (playoffs):
            line = "%-16s %-5s %-5s %-5s %-5s %-5s %-5s %-5s" % (team, wins, losses, pct, gb, wcgb, l10, strk)
          else:
            line = "%-16s %-5s %-5s %-5s %-5s %-5s %-5s" % (team, wins, losses, pct, gb, l10, strk)

          output.append(line)
          counter += 1

        return output
      """ }}} """

      self.log.info('_getstandings called. league: %s division: %s', league, division)
      standings_html = self._fetchurl('standings')

      if 'error_' in standings_html:
        error = "ERROR: Couldn't get standings! Code: %s" % (standings_html)
        self.log.info('_getstandings: %s', error)
        return error

      results = []

      standings_html = html.fromstring(standings_html)
      if (league == 'al') and (division == False):
        for d in self.divisions:
          results.append(__returnstandings(standings_html, 'al', d))
      elif (league == 'nl') and (division == False):
        for d in self.divisions:
          results.append(__returnstandings(standings_html, 'nl', d))
      else:
        results.append(__returnstandings(standings_html, league, division))

      return results

    """ }}} """

    """ {{{ Parse mlb arguments.
    """
    def _parseargsmlb(self, args):
       """ Evaluate if argument is a date.
       """
       def __evaldate(date):
         try:
           if date in [ 'yesterday', 'tomorrow']:
             return True
           datetime.strptime(date, '%Y%m%d')
           return True
         except:
           return False

       self.log.info('_parseargs args: %s %s %s', args, len(args), type(args))
       self.log.info('_parseargs: %s', type(len(args)))

       if (type(args) == str):
         self.log.info('_parseargs: called with no arguments, defaulting to all')
         arg1 = 'all'
       elif (len(args) == 1):
         self.log.info('_parseargs: called with 1 argument: %s', args[0])
         arg1 = str(args[0]).lower()
       elif (len(args) == 2):
         self.log.info('_parseargs: called with 2 arguments: %s %s', args[0], args[1])
         arg1 = str(args[0]).lower()
         arg2 = str(args[1]).lower()
       else:
         self.log.info('_parseargs: called with more than 2 arguments')
	 result = 'ERROR: Too many arguments. See .help mlb'
	 return result
       # All games.
       if arg1 == 'all':
         self.log.info('_parseargs: parse all games for today')
         date = self._getdate()
         all_games = self._getscoreboardinfo(date)
         result = self._printscore_all(all_games)
       elif __evaldate(arg1):
         if (arg1 in [ 'yesterday', 'tomorrow' ]):
           date = self._getdate(arg1)
         else:
           date = arg1[:4] + ' ' + arg1[4:6] + ' ' + arg1[6:9]
         all_games = self._getscoreboardinfo(date)
         if (len(args) == 1):
           result = self._printscore_all(all_games)
         elif (len(args) == 2):
           arg2 = str(args[1]).lower()
           if arg2 == 'all':
             self.log.info('_parseargs: parse all games for %s', date)
             result = self._printscore_all(all_games)
           else:
             self.log.info('_parseargs: parse game for %s for date %s', arg2, date)
             try:
               search = self._searchgame(arg2, all_games)
               result = self._procsearchresult(search, all_games)
             except:
               result = 'ERROR: No gamedata found.'
             return result
       # Otherwise arg1 is a team, and we want today's game.
       else:
         date = self._getdate()
         all_games = self._getscoreboardinfo(date)
         search = self._searchgame(arg1, all_games)
         result = self._procsearchresult(search, all_games)

       return result
    """ }}} """

    """ {{{ Parse arguments for mlb standings from irc.
    """
    def _parseargsstandings(self, args):
      self.log.info('_parseargsstandings: args: %s', args)

      arg1 = False
      arg2 = False

      if (len(args) > 2):
        result = "ERROR: Too many arguments, see .help mlbstandings for usage"
        return result

      if (len(args) != 2):
        result = 'ERROR: Specify a league + divison. Use .help mlbstandings for syntax'
        return result

      if (len(args) == 2):
        arg1 = str(args[0]).lower()
        if (arg1 == 'all'):
          result = 'ERROR: You can only do one league + division at a time'
          return result
        self.log.info('_parseargsstandings: arg1: %s self.leagues: %s', arg1, type(self.leagues))
        searchleagues = self._searchlist(arg1, self.leagues)

      if (len(args) == 2):
        arg2 = str(args[1]).lower()
        searchdivision = self._searchlist(arg2, self.divisions)

      if not searchleagues:
        result = 'ERROR: Invalid league: %s' % (arg1)
        return result

      if (arg2) and (searchdivision == False):
        if (arg1 == 'nl') and (arg2 == 'least'):
          arg2 = 'east'
        else:   
          result = 'ERROR: Invalid division: %s' % (arg2)
          return result

      if (arg1) and (arg2 == False):
        result = self._getstandings(arg1)
      else:
        result = self._getstandings(arg1, arg2)

      return result
    """ }}} """

    """ {{{ Actual .mlb command 
    """
    def mlb(self, irc, msg, args):
      """ <all|team> OR <date> [all|team]
      Get mlb scores. 
      
      No argument shows current day scores. <date> is in YYYYMMDD format.
      """
      self.log.info("mlb: {0} called by {1}".format(args, msg))
      if len(args) == 0:
        results = self._parseargsmlb('all')
        if (type(results) == list):
          for l in results:
            irc.reply(l)
          return
        else:
          irc.reply(results)
          return
      else:
       results = self._parseargsmlb(args)
       if (type(results) == list):
         for l in results:
           irc.reply(l)
         return
       else:
         irc.reply(results)
         return
    """ }}} """

    """ {{{ Display mlb standings. 
    """
    def mlbstandings(self, irc, msg, args):
      """ <nl <east|central|west>|al <east|central|west>>
      Get mlb standings.

      league + division is required.

      Ex: .mlbstandings nl east OR .mlbstandings al central
      """
      self.log.info("mlbstandings: {0} called by {1}".format(args, msg))
      if len(args) == 0:
        results = "ERROR: Missing argument, see .help mlbstandings for usage."
      else:
        results = self._parseargsstandings(args)
 
      # results are lists within a list
      if type(results) == str:     
        irc.reply(results)
      else:
        for r1 in results:
          for r in r1:
            irc.reply(r)

    """" }}} """

Class = dnmlb
