# dnmlb

Limnoria / Supybot plugin for displaying MLB scores and standings using 
mlb.com's gameday data.

This plugin is based off of the work by
[spline](https://github.com/reticulatingspline). Namely his
[hardball](https://github.com/reticulatingspline/Hardball) and
[scores](https://github.com/reticulatingspline/Scores) plugins.

## Installation

Requires Python 2.7+ (developed on 2.7.8, older versions of 2.7 might not work)
and a working Limnoria bot.

Clone this repo and then install the required Python modules via pip:

**Note:** You can omit `--user` from pip if you wish to install the modules
globally.


```
~ $ cd ~/supybot/plugins
~/supybot/plugins $ git clone https://github.com/drageon/dnmlb
~/supybot/plugins $ pip install --user -r requirements.txt
```

Then enable the module:

```
<@Drageon> .load dnmlb
<@sukores> 10-4
```

## Usage

Examples of usage below.

**Note:** control codes are used for color + bold/underline that is not
displayed here, as I didn't feel like making pngs of the output.

#### Current day scores:

```
<@Drageon> .mlb
<@sukores> CWS 1 NYY 2 F | HOU 5 BOS 4 B9 | MIA 4 WSH 6 F | MIA @ WSH 7:05PM | PIT 2 CHC 6 E7 | MIN 0 CLE 0 T2 | OAK @ TB 6:10PM | CIN @ PHI 7:05PM | DET @ BAL 7:05PM | SD @ MIL 7:10PM | ATL @ KC 7:15PM | TOR @ TEX 8:05PM | NYM @ COL 8:10PM | SF @ ARI 8:10PM | LAA @ SEA 9:10PM

```

#### Game in progress line:
```
<@Drageon> .mlb hou
<@sukores> Houston 5 Boston 5 B9 :: RO: 3 :: B:0 S:0 O:2 :: AB: Ramirez, H P: Gregerson (17) :: David Ortiz triples (1) on a fly ball to center fielder Jake Marisnick. Xander Bogaerts scores. 
```

#### Game final line:
```
<@Drageon> .mlb nyy
<@sukores> Chi White Sox 1 NY Yankees 2 F/9 :: W: Nova (3.70/2-1) L: Quintana (1.54/5-2) SV: Chapman, A (3.00/0-0/2-2) :: HR: Chi White Sox(1): Frazier(1/12)
```

#### Standings:
```
<@Drageon> .mlbstandings nl
<@sukores>  
<@sukores> NL Least         W     L     PCT   GB    L10   STRK
<@sukores> Washington       23    13    .639  -     5-5   W3
<@sukores> NY Mets          21    14    .600  1.5   5-5   L2
<@sukores> Philadelphia     21    15    .583  2.0   6-4   W2
<@sukores> Miami            18    17    .514  4.5   5-5   L2
<@sukores> Atlanta          8     26    .235  14.0  2-8   L2
<@sukores>  
<@sukores> NL Central       W     L     PCT   GB    L10   STRK
<@sukores> Chi Cubs         26    8     .765  -     8-2   W1
<@sukores> Pittsburgh       18    16    .529  8.0   3-7   L1
<@sukores> St. Louis        19    17    .528  8.0   6-4   L1
<@sukores> Milwaukee        15    21    .417  12.0  4-6   W1
<@sukores> Cincinnati       14    21    .400  12.5  4-6   L2
<@sukores>  
<@sukores> NL West          W     L     PCT   GB    L10   STRK
<@sukores> LA Dodgers       19    17    .528  -     6-4   W2
<@sukores> San Francisco    20    18    .526  -     5-5   W3
<@sukores> Colorado         17    18    .486  1.5   5-5   W2
<@sukores> Arizona          17    21    .447  3.0   5-5   L3
<@sukores> San Diego        16    21    .432  3.5   5-5   L1
<@Drageon> .mlbstandings al central
<@sukores>  
<@sukores> AL Central       W     L     PCT   GB    L10   STRK
<@sukores> Chi White Sox    24    13    .649  -     5-5   L1
<@sukores> Cleveland        17    15    .531  4.5   7-3   W1
<@sukores> Kansas City      17    18    .486  6.0   4-6   W1
<@sukores> Detroit          15    20    .429  8.0   1-9   L3
<@sukores> Minnesota        8     26    .235  14.5  1-9   L8
```

## TODO:
* Fix parsing of time and date units ex: `.mlb tomorrow atl` works, but not
  `.mlb atl tomorrow`.
* Clean up commandline parsing.
* Add current batter batting average to `AB` line.
* Clean up info logging. A lot of it exists just for debugging when things go
  sideways parsing mlb's data.
* Clean up a lot of other messy coding. This was my first real python project.
