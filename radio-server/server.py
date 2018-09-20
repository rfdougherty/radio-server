#!/usr/bin/env python
"""
  My radio server application
  For my eyes only
"""

#CREATE TABLE Radio(id integer primary key autoincrement, radio text, genre text, url text);
uuid='56ty66ba-6kld-9opb-ak29-0t7f5d294686'

# Import CherryPy global namespace
import os
import sys
import time
import socket
import cherrypy
import sqlite3 as lite
import re
import urllib2
import json
import subprocess
from random import shuffle
from oled.serial import i2c
from oled.device import ssd1306
from oled.render import canvas
from PIL import ImageFont
from math import log10
from tempfile import mkstemp
import threading


class Oled(threading.Thread):
    def __init__(self, blank=False):
        threading.Thread.__init__(self)
        self.device = i2c(port=1, address=0x3C)
        self.oled = ssd1306(self.device)
        self.font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
        self.statfont = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
        self.botfont = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
        self.blank = blank
        self.msg_genre = ''
        self.msg_station = ''
        self.sleep_time = .05
        self.volume = 0
        self.msg_pos = 0
        self.brightness(1)

    def brightness(self, brightness):
        contrast = brightness * 1.171 if brightness < 128 else brightness * 1.171 - 43
        precharge = 241 if brightness > 0 else 0
        comdetect = brightness / 8
        self.oled.command(self.oled._const.SETPRECHARGE, precharge,
                          self.oled._const.SETCONTRAST, int(round(contrast)),
                          self.oled._const.SETVCOMDETECT, int(round(comdetect)),
                          self.oled._const.DISPLAYALLON_RESUME,
                          self.oled._const.NORMALDISPLAY)
	
    def set_message(self, msg_genre, msg_station):
        self.msg_genre = msg_genre.split(',')[0] if ',' in msg_genre else msg_genre
        self.msg_station = msg_station
        self.msg_pos = 0

    def run(self):
        # rectanges are (Left,Top,Right,Bottom)
        disp_width = self.oled.bounding_box[2]
        disp_height = self.oled.bounding_box[3]
        bat_bar = 0
        while True:
            if self.blank:
                with canvas(self.oled) as draw:
                    draw.rectangle(self.oled.bounding_box, outline="black", fill="black")
            else:
                link = os.popen('/sbin/iwconfig wlan0').read()
                m = re.search('Link Quality=(.*?/)', link)
                link_quality = int(m.groups()[0].split('/')[0])
                bars = int(round(link_quality/100.*5))
                bat = int(round(int(os.popen('/usr/sbin/i2cget -y -f 0 0x34 0xb9').read(), 16)/100.*12))
                d_msb = int(os.popen('/usr/sbin/i2cget -y -f 0 0x34 0x7c').read(), 16)<<5
                d_lsb = int(os.popen('/usr/sbin/i2cget -y -f 0 0x34 0x7d').read(), 16)&0x1f
                bat_discharge_ma = int(round((d_msb|d_lsb)*0.5))
                c_msb = int(os.popen('/usr/sbin/i2cget -y -f 0 0x34 0x7a').read(), 16)<<4
                c_lsb = int(os.popen('/usr/sbin/i2cget -y -f 0 0x34 0x7b').read(), 16)&0x1f
                bat_charge_ma = int(round((c_msb|c_lsb)*0.5))
                if bat_charge_ma>bat_discharge_ma:
                    if bat_charge_ma<1000:
                        bat_cur = '+%dmA' % bat_charge_ma
                    else:
                        bat_cur = '+%0.1fA' % (bat_charge_ma/1000.)
                else:
                    if bat_discharge_ma<1000:
                        bat_cur = '-'+str(bat_discharge_ma)+'mA'
                    else:
                        bat_cur = '-%0.1fA' % (bat_discharge_ma/1000.)
                temperature = os.popen("sudo axp209 --temperature").read()
                temperature = temperature[:-3].strip()
                temperature = str(int(round(float(temperature))))+"\xb0"
                with canvas(self.oled) as draw:
                    # WIFI signal strength
                    for b in range(bars):
                        draw.rectangle((111 + (b*3), 14-(b*3), 111+(b*3)+2, 15), fill=255)
                    # Battery meter
                    # horizontal battery:
                    #draw.rectangle((91,1,110,7), fill=0, outline=255)
                    #draw.rectangle((89,3,91,5), fill=255)
                    #for b in range(bat):
                    #    draw.rectangle((91 + (b*4), 1, 91+(b*4)+1, 7), fill=255)
                    draw.rectangle((99,1,106,15), fill=0, outline=255)
                    draw.rectangle((101,0,104,1), fill=255)
                    draw.rectangle((99, 12-bat+3, 105, 14), fill=255)
                    # Volume
                    draw.rectangle((85,14,87,14), fill=255)
                    draw.polygon([(86,14), (83,11), (89,11), (86,14)], fill=255)
                    if self.volume>0:
                        vol = max(1,int(round(log10(float(self.volume))*5)))
                        #wide = max(1,vol/2)
                        wide = vol
                        draw.polygon([(85,10), (86-wide,10-vol), (86+wide,10-vol), (87,10)], fill=128)

                    # CPU temperature
                    draw.text((0,2), temperature, font=self.statfont, fill=255)
                    # Battery current
                    draw.text((27,2), bat_cur, font=self.statfont, fill=255)
                    # Message area
                    w,h = self.statfont.getsize(self.msg_genre)
                    pos = 0 if w>disp_width else (disp_width-w)/2
                    draw.text((pos,16), self.msg_genre, font=self.statfont, fill=255)
                    w,h = self.font.getsize(self.msg_station)
                    if w<=disp_width:
                        pos = (disp_width-w)/2
                        draw.text((pos,29), self.msg_station, font=self.font, fill=255)
                    else:
                        spacing = max(20, disp_width-w)
                        draw.text((self.msg_pos,29), self.msg_station, font=self.font, fill=255)
                        draw.text((self.msg_pos+w+spacing,29), self.msg_station, font=self.font, fill=255)
                        self.msg_pos -= 1
                        if self.msg_pos <= -(w+spacing):
                            self.msg_pos = 0
                    # Bottom status area
                    tm = time.strftime("%a %b %-d %H:%M:%S")
                    w,h = self.botfont.getsize(tm)
                    draw.text(((disp_width-w)/2,disp_height-h+1), tm, font=self.botfont, fill=255)
                time.sleep(self.sleep_time)

# Globals
version = "4.2.1"
database = "database.db"
#player = 'omxplayer'
#player = 'mplayer'
player = 'mpg123'
display = Oled(blank=True)
display.daemon = True
display.start()

header = '''<!DOCTYPE html>
<html lang="en">
<head>
  <title>My Radio Web Server</title>
  <meta name="generator" content="Vim">
  <meta charset="UTF-8">
  <link rel="icon" type="image/png" href="/static/css/icon.png" />
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="/static/js/jquery-2.0.3.min.js"></script>
  <script src="/static/js/bootstrap.min.js"></script>
  <link rel="stylesheet" href="/static/css/bootstrap.min.css">

<!-- Custom styles for this template -->
<link href="/static/css/sticky-footer.css" rel="stylesheet">
<style media="screen" type="text/css">
#radio-playing { display: none; }
#radio-table  { display: none; }
#radio-volume { display: none; }
.jumbotron { padding: 10px 10px; }
</style>

<script type="text/javascript">
     function fmodradio(rid) {
        $.post('/m/', {id: rid},
            function(data){
                $("#radio-table").html(data);
                $("#radio-table").show();
            },
            "html"
        );
     }
     function fdelradio(rid) {
       var r = confirm("DELETING " + rid);
       if (r != true) { return; }
       $.post('/d/', {id: rid},
            function(data){
                $("#radio-table").html(data);
                $("#radio-table").show();
            },
            "html"
        );
     }
     function fplayradio(rid) {
        $.post('/p/', {id: rid},
            function(data){
                $("#radio-playing").html(data);
                $("#radio-playing").show();
                $("#radio-volume").hide();
            },
            "html"
        );
     }
     function faddfav(i, g) {
       $.post('/haddfav/', {id: i},
            function(data){
                $("#radio-playing").html(data);
                $("#radio-playing").show();
                $("#radio-volume").hide();
            },
            "html"
        );
     }
     function fvolradio(updown) {
        $.post('/v/', {vol: updown},
            function(data){
                $("#radio-volume").html(data);
                $("#radio-volume").show();
            },
            "html"
        );
     }
     function fkilradio() {
        $.post('/k/',
            function(data){
                $("#radio-volume").html(data);
                $("#radio-volume").show();
            },
            "html"
        );
     }
     function fsearch(nam, gen) {
        $.post('/g/', {name: nam, genre: gen},
            function(data) {
                $("#radio-table").html(data);
                $("#radio-table").show();
            },
            "html"
        );
     }
     function frandom(n, g) {
       $.post('/g/', {name: n, genre: g, randomlist:'true'},
            function(data){
                $("#radio-table").html(data);
                $("#radio-table").show();
            },
            "html"
        );
     }
     function fstatus() {
        $.post('/stat/',
            function(data){
                $("#radio-status").html(data);
                $("#radio-status").show();
            },
            "html"
        );
     }

// ----------------------------------------------------------
     $(document).ready(function() {
         $('body').on('click', '#button-modify', function(e) {
             i = $("#idm").val()
             n = $("#namem").val()
             g = $("#genrem").val()
             u = $("#urlm").val()
             $.post("/f/", {id: i, name: n, genre: g, url: u})
              .done(function(data) {
                $("#radio-table").html(data);
                $("#radio-table").show();
            });
            e.preventDefault();
         });
         $('#namem').keyup(function(e){
            if(e.keyCode == 13) {
                $('#button-modify').click();
            }
         });
         $('#genrem').keyup(function(e){
            if(e.keyCode == 13) {
                $('#button-modify').click();
            }
         });
         $('#urlm').keyup(function(e){
            if(e.keyCode == 13) {
                $('#button-modify').click();
            }
         });
         $('#button-search').click(function(e) {
             n = $("#name").val()
             g = $("#genre").val()
             $.post("/g/", {name: n, genre: g})
              .done(function(data) {
                  $("#radio-table").html(data);
                  $("#radio-table").show();
            });
            e.preventDefault();
         });
         $('#name').keyup(function(e){
            if(e.keyCode == 13) {
                $('#button-search').click();
            }
         });
         $('#genre').keyup(function(e){
            if(e.keyCode == 13) {
                $('#button-search').click();
            }
         });
         $("#button-insert").click(function(e) {
             n = $("#namei").val()
             g = $("#genrei").val()
             u = $("#urli").val()
             $.post("/i/", {name: n, genre: g, url: u})
              .done(function(data) {
                  $("#radio-table").html(data);
                  $("#radio-table").show();
            });
            e.preventDefault();
         });
         $("#play-radio").click(function(e) {
             i = $("#idp").val()
             $.post("/p/", {id: i})
              .done(function(data) {
                  $("#radio-playing").html(data);
                  $("#radio-playing").show();
            });
            e.preventDefault();
         });
         window.setInterval(function(){
            fstatus();
         }, 10000);

       });
     </script>
</head>
<body>

<div class="container-fluid">
   <div class='jumbotron'>
      <h2><a href="/">Radio</a>
      <a href="#" onClick="fvolradio('down')"><span class="glyphicon glyphicon-volume-down"></span></a>
      <a href="#" onClick="fvolradio('up')"><span class="glyphicon glyphicon-volume-up"></span></a>
      <a href="#" onClick="fkilradio('up')"> <span class="glyphicon glyphicon-record"></span></a>
      </h2>
      <p>
      <div class="form-group">
        <input type="text" id="name" name="name" placeholder="radio to search">
        <input type="text" id="genre" name="genre" placeholder="genre" >
        <button id="button-search">Search</button>
      </div>
      </p>
      <p>
      <div class="form-group">
      <input type="text" id="namei" name="name" placeholder="Radio Name">
       <input type="text" id="genrei" name="genre" placeholder="genre">
        <input type="text" id="urli" name="url" placeholder="http://radio.com/stream.mp3">
       <button id="button-insert">Insert</button>
       <p>
      [
      <a href="#" onClick="fsearch('', 'rai')"> rai </a>|
      <a href="#" onClick="fsearch('','fav')"> fav </a> |
      <a href="#" onClick="fsearch('','rmc')"> rmc </a> |
      <a href="#" onClick="fsearch('','class')"> class </a> |
      <a href="#" onClick="fsearch('','jazz')"> jazz </a> |
      <a href="#" onClick="fsearch('','chill')"> chill </a> |
      <a href="#" onClick="fsearch('','nl')"> nl </a> |
      <a href="#" onClick="fsearch('','bbc')"> bbc </a> |
      <a href="#" onClick="fsearch('','uk')"> uk </a> |
      <a href="#" onClick="fsearch('','italy')"> italy </a>
      ]
      </p>
      </div>
    <small><div id="radio-playing"> </div></small>
    </br>
   </div> <!-- Jumbotron END -->

 <div id="radio-volume"> </div>
 <div id="radio-status"> </div>
 <div id="radio-table"> </div>
'''

footer = '''<p></div></body></html>'''

def npr_playlist(url, start=0):
    page = urllib2.urlopen(url).read()
    m = re.search('data-play-all=\'(.*)\'', page)
    pl = json.loads(m.groups()[0])
    urls = [d['audioUrl'] for d in pl['audioData']][start:]
    fd,playlist = mkstemp(suffix='.m3u')
    with open(playlist,'w') as fp:
        for url in urls:
           u = 'http'+url.split('?')[0][5:]
           fp.write(u+'\n')
    os.close(fd)
    fp.close()
    return playlist


def isplayfile(pathname) :
    if os.path.isfile(pathname) == False:
        return False
    ext = os.path.splitext(pathname)[1]
    ext = ext.lower()
    if (ext == '.mp2') : return True;
    if (ext == '.mp3') : return True;
    if (ext == '.ogg') : return True;
    return False

# ------------------------ AUTHENTICATION --------------------------------
from cherrypy.lib import auth_basic

#  Password is: webradio
users = {'admin':'29778a9bdb2253dd8650a13b8e685159'}

def validate_password(self, login, password):
    if login in users :
        if encrypt(password) == users[login] :
            cherrypy.session['username'] = login
            cherrypy.session['database'] = userdatabase(login)
            return True

    return False

def encrypt(pw):
    from md5 import md5
    return md5(pw).hexdigest()

# ------------------------ CLASS --------------------------------
class Root:
    @cherrypy.expose
    def index(self):
        html = header
        (_1, _2, id) = getradio('0')
        (radio, genre, url) = getradio(id)

        if id != 0:
            html += '''<h3><a href="#" onClick="fplayradio('%s')"> ''' % id
            html += '''Play Last Radio %s <span class="glyphicon glyphicon-play"></span></a></h3>''' % radio
        html += getfooter()
        return html

    @cherrypy.expose
    def music(self, directory='/mnt/Media/Music/'):
        html = header
        count = 0
        html += '''<table class="table table-condensed">'''
        filelist = os.listdir(directory)
        filelist.sort()
        for f in filelist:
          file = os.path.join(directory, f)
          html += '''<tr>'''
          if isplayfile(file):
            html += '''<td ><a href="#" onClick="fplayradio('%s')">''' % file
            html += '''Play %s<span class="glyphicon glyphicon-play"></span></a></td>''' % (file)
          if os.path.isdir(file):
            html += '''<td ><a href="/music?directory=%s">%s</a> </td>''' % (file, f)
          html += '''</tr>'''
          count += 1

        html += '''</table>'''
        html += '''</div> </div>'''

        html += getfooter()
        return html

    @cherrypy.expose
    def g(self, name="", genre="", randomlist='false'):
        list = searchradio(name.decode('utf8'), genre)
        count = 0

        # Randomlist
	if randomlist == 'true' : shuffle(list)

        listhtml = '''<table class="table table-condensed">'''
        for id,radio,gen,url in list:
            listhtml += '''<tr>'''
            listhtml += '''<td width="200px"><a href="#" onClick="fmodradio('%s')" alt="%s">%s</a></td>''' % (id, url, radio)
            listhtml += '''<td width="100px">%s</td>''' % gen
            listhtml += '''<td ><a href="#" onClick="fplayradio('%s')">Play <span class="glyphicon glyphicon-play"></span></a></td>''' % (id)
            listhtml += '''</tr>'''
            count += 1
        listhtml += '''</table>'''
        listhtml += '''</div> </div>'''

        html = ''
        html += '''<div class="row"> <div class="col-md-8"> '''
        if randomlist == 'false':
            html += '''<h2><a href="#" onClick="frandom(name='%s', genre='%s', randomlist='true')">%d Results for '%s' + '%s'</a></h2>''' % (name, genre, count, name, genre)
        else:
            html += '''<h2><a href="#" onClick="fsearch(name='%s', genre='%s')">%d Random for '%s' + '%s'</a></h2>''' % (name, genre, count, name, genre)

        html += listhtml

        return html

    @cherrypy.expose
    def i(self, name="", genre="", url=""):
        html = "<h2>Insert</h2>"
        if name == "" or name == None :
          html += "Error no name"
          return html

        if insert(name, genre, url) == False:
            html += "Error db "
            return html

        html += '''<h3>This radio has been inserted</h3>'''
        html += '''<p><table class="table table-condensed">'''
        html += ''' <tr> '''
        html += '''  <td>radio: <strong>%s</strong></td> ''' % name
        html += '''  <td>genre: <strong>%s</strong></td> ''' % genre
        html += '''  <td>url: <strong><a href="%s" target="_blank">%s</a></strong></td> ''' % (url, url)
        html += '''  <td width="300px"><a href="#" onClick="fplayradio('%s')"> Play ''' % url
        html += '''<span class="glyphicon glyphicon-play"></span></a></td>'''
        html += ''' </tr> '''
        html += '''</table>'''

        return html

    @cherrypy.expose
    def d(self, id=""):
        html = "<h2>Delete</h2>"
        if id == "" or id == None :
            html += "Error"
            return html

        if id == "0" :
          html += "0 is reserved, sorry"
          return html

        #if delete(id) == False:
        if nonexist(id) == False:
            html += "Delete error in id" % id
            html += getfooter()
            return html

        html += "Item %s set as non existent" % id
        return html

    @cherrypy.expose
    def p(self, id):
        global display
        html = ""
        if id == "" or id == None :
            html += "Error no radio id"
            return html
        if id == "0" :
          html += "0 is reserved, sorry"
          return html

        (radio, genre, url) = playradio(id)
        if  url == '':
            html += "Error in parameter %s" % url
            return html

        display.blank = False
        display.set_message(genre, radio)

        cherrypy.session['playing'] = id
        html += '''<h3>Now Playing: '''
        html += '''<a href="%s">%s</a>''' % (url, radio)
        html += '''<a href="#" onClick="fplayradio('%s')">''' % id
        html += '''<span class="glyphicon glyphicon-play"></span></a>'''
        html += '''&nbsp;<a href="#" onClick="fmodradio('%s')"><span class="glyphicon glyphicon-pencil"></span></a></small>&nbsp;''' % id
        html += '''<a href="#" onClick="fdelradio('%s')"><span class="glyphicon glyphicon-trash"></span></a>&nbsp;''' % id
        html += '''<a href="#" onClick="faddfav('%s')"><span class="glyphicon glyphicon-star"></span></a>''' % id
        html += '''</h3>'''
        print html
        return html

    @cherrypy.expose
    def v(self, vol=""):
        html = ""
        if vol == "" or vol == None :
           html += "Error"
        v = volume(vol)
        html += "<h6>%s (%s) </h6>" % (v, vol)
        return html

    @cherrypy.expose
    def stat(self):
        html = ""
        try:
            bat = ' bat=%d%%' % int(subprocess.check_output('/usr/sbin/i2cget -y -f 0 0x34 0xb9', shell=True), 16)
        except:
            bat = 'bat=ERR'

        html += "<h6> %s</h6>" % (bat)
        return html

    @cherrypy.expose
    def m(self, id):
        html = '''<h2>Modify</h2>'''

        if id == "" or id == None :
          html += "Error"
          return html
        if id == "0" :
          html += "0 is reserved, sorry"
          return html

        (name, genre, url) = getradio(id)
        html += '<h3>%s | %s | %s</h3>' % (name, genre, url)
        html += '''<input type="hidden" id="idm" name="id" value="%s">''' % id
        html += '''<input type="text" id="namem" name="name" value="%s">''' % name
        html += '''genre: <input type="text" id="genrem" name="genre" value="%s"> ''' % genre
        html += '''url: <input type="text" style="min-width: 280px" id="urlm" name="url" value="%s"> ''' % url
        html += '''<button id="button-modify">Change</button>'''
        html += '''<h3><a href="#" onClick="fdelradio('%s')">Delete? <span class="glyphicon glyphicon-trash"></span></a></h3>''' % id
        html += '''<h3><a href="%s" target="_blank">Play in browser <span class="glyphicon glyphicon-music"></span></a>''' % url


        return html

    @cherrypy.expose
    def f(self, id="", name="", genre="", url=""):
        html = '''<h2>Modified</h2>'''
        if id == "" or id == None :
          html += "Error missing id"
          return html

        if id == "0" :
          html += "0 is reserved, sorry"
          return html

        if modify(id, name, url, genre) == False:
            html += "Error in DB"
            return html

        (name, genre, url) = getradio(id)
        html += '''<p><table class="table table-condensed">'''
        html += '''<tr>'''
        html += '''<td width="100px"><a href="#" onClick="fmodradio('%s')">''' % id
        html += '''Mod <span class="glyphicon glyphicon-pencil"></span></a></td>'''
        html += '''<td width="200px">%s</td>''' % name
        html += '''<td width="200px">%s</td>''' % genre
        html += '''<td><a href="%s" target="_blank">%s</a></td>''' % (url, url)
        html += '''<td width="300px"><a href="#" onClick="fplayradio('%s')">'''% url
        html += '''Play <span class="glyphicon glyphicon-play"></span></a></td>'''
        html += '''</tr>'''
        html += '''</table>'''

        return html

    @cherrypy.expose
    def haddfav(self, id=""):
        if id == "" or id == None :
          html += "Error missing id"
          return html

        if id == "0" :
          html += "0 is reserved, sorry"
          return html

        (name, genre, url) = getradio(id)
        if 'Fav' in genre:
            genre = genre.replace(', Fav', '')
            star = False
        else:
            genre += ', Fav'
            star = True

        if addgen(id, genre) == False:
            return ''

        (name, genre, url) = getradio(id)
        cherrypy.session['playing'] = id
        html = '<h3>Now Playing: '
        html += '''<a href="%s">%s</a>''' % (url, name)
        html += '''<a href="#" onClick="fplayradio('%s')">''' % url
        html += '''<span class="glyphicon glyphicon-play"></span></a>'''
        html += '''&nbsp;<a href="#" onClick="fmodradio('%s')"><span class="glyphicon glyphicon-pencil"></span></a></small>&nbsp;''' % id
        html += '''<a href="#" onClick="fdelradio('%s')"><span class="glyphicon glyphicon-trash"></span></a>&nbsp;''' % id
        html += '''<a href="#" onClick="faddfav('%s')"><span class="glyphicon glyphicon-star"></span></a>''' % id
        if star:
            html += '''Starred'''
        html += '''</h3>'''

        return html

    @cherrypy.expose
    def k(self):
        html = "<h2>Stopping</h2>"
        killall()
        return html

# ------------------------ DATABASE --------------------------------
def getfooter() :
    global footer, version

    db = cherrypy.session['database']
    try:
        con = lite.connect( db )
        cur = con.cursor()
        sql = "select radio, genre, url from Radio where id=0"
        cur.execute(sql)
        (radio, genre, url) = cur.fetchone()
    except:
        (radio, genre, url) = ('ERROR', sql, '')

    con.close()

    hostname = socket.gethostname()
    f = '''<footer class="footer"> <div class="container">'''
    f += '''<p class="text-muted">'''
    f += '''Session id: %s - Session Database %s<br>''' % (cherrypy.session.id, cherrypy.session['database'])
    f += '''Host: %s - Version: %s - Updated: %s // Last: %s''' % (hostname, version, genre, url)
    f += '''</p>'''
    f += '''</div></footer>'''
    return f + footer

def updateversiondb(cur) :
    db = cherrypy.session['database']
    username = cherrypy.session['username']

    dt = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        sql = "UPDATE Radio SET radio='%s', genre='%s' WHERE id = 0" % (hostname, dt)
        cur.execute(sql)
    except:
        return

def delete(id) :
    db = cherrypy.session['database']
    try:
        con = lite.connect( db )
        cur = con.cursor()
        sql =  "DELETE from Radio WHERE id = '%s'" % (id)
        cur.execute(sql)
        ret = True
    except:
        print "Error deleting sql %s" % sql
        ret = False

    updateversiondb(cur)
    con.commit()
    con.close()
    return ret

def nonexist(id) :
    db = cherrypy.session['database']
    sql =  "UPDATE Radio set exist = 0 WHERE id = '%s'" % (id)
    try:
        con = lite.connect( db )
        cur = con.cursor()
        cur.execute(sql)
        ret = True
    except:
        print "Error in sql %s" % sql
        ret = False

    updateversiondb(cur)
    con.commit()
    con.close()
    return ret

def insert(radio, genre, url) :
    db = cherrypy.session['database']
    sql =  "INSERT INTO Radio (radio, genre, url, exist) VALUES('%s', '%s', '%s', 1)" % (radio, genre, url)
    try:
        con = lite.connect( db )
        cur = con.cursor()
        cur.execute(sql)
        ret = True
    except:
        print "Error inserting sql %s" % sql
        ret = False

    updateversiondb(cur)
    con.commit()
    con.close()
    return ret

def modify(id, radio, url, genre) :
    db = cherrypy.session['database']

    sql = "UPDATE Radio SET radio='%s', url='%s', genre='%s', exist=1 WHERE id = %s" % (radio, url, genre, id)
    try:
        con = lite.connect( db )
        cur = con.cursor()
        cur.execute(sql)
        ret = True
    except:
        print "Error modify sql %s" % sql
        ret = False

    updateversiondb(cur)
    con.commit()
    con.close()
    return ret

def addgen(id, genre) :
    db = cherrypy.session['database']

    sql = "UPDATE Radio SET genre='%s' WHERE id = %s" % (genre, id)
    try:
        con = lite.connect( db )
        cur = con.cursor()
        cur.execute(sql)
        ret = True
    except:
        print "Error modify sql %s" % sql
        ret = False

    updateversiondb(cur)
    con.commit()
    con.close()
    return ret

def getradio(id) :
    db = cherrypy.session['database']
    if id.isdigit() :
    	sql = "select radio, genre, url from Radio where id=%s" % id
    else:
    	sql = "select radio, genre, url from Radio where url=%s" % id
    try:
        con = lite.connect( db )
        cur = con.cursor()
        cur.execute(sql)
    except:
        rows = [('Not Found', '', '')]

    rows = cur.fetchone()
    if rows == None:
        rows = ('Not Found', '', '')

    con.close()

    return rows

def searchradio(radio, genre) :
    db = cherrypy.session['database']
    #o = 'order by radio'
    o = ''
    sql = "select id, radio, genre, url from Radio where exist > 0 and radio like '%%%s%%' and genre like '%%%s%%' and id > 0 %s" % (radio, genre, o)
    try:
        con = lite.connect( db )
        cur = con.cursor()
        cur.execute(sql)
    except:
        return [(0, sql, o, genre)]

    rows = cur.fetchall()
    con.close()
    return rows


def updatelastradio(url) :
    db = cherrypy.session['database']
    sql = "UPDATE Radio SET url='%s' WHERE id=0" % (url)
    try:
        con = lite.connect( db )
        cur = con.cursor()
        cur.execute(sql)
        con.commit()
        con.close()
    except:
        return

def userdatabase(user) :
    db = database
    if not os.path.isfile(db):
        return None
    return db

def getshort(code) :
    maxl = 5
    newcode = code.replace('http://', '')
    if len(newcode) > maxl :
          newcode = newcode[0:maxl]
    return str(newcode)

def setplayer(p):
    global player
    player = p

def playradio(urlid):
    global player

    (radio, genre, url) = getradio(urlid)

    status = 0
    killall()

    if url[-1]=='/':
        playme = npr_playlist(url)
        ispl = True
    else:
        playme = url
        ispl = False

    if player == 'mpg123':
        command = "/usr/bin/mpg123 -q --list " if ispl else  "/usr/bin/mpg123 -q "
        shell = True
    if player == 'mplayer':
        command = "/usr/bin/mplayer -really-quiet -cache 256 --playlist=" if ispl else "/usr/bin/mplayer -really-quiet -cache 256 "
        shell = True
    if player == 'omxplayer':
        # Process is in background
        command = 'omxplayer '
        shell = False

    subprocess.Popen(command+playme, shell=shell)

    updatelastradio(urlid)
    return (radio, genre, urlid)

def killall():
    global player, display
    display.blank = True
    status = 0
    if player == 'omxplayer':
        control = "/usr/local/bin/omxcontrol"
        status = subprocess.call([control,  "stop"])
    status = subprocess.call(["pkill", player])

    return status

def volume(vol) :
    global player, display
    if player == 'omxplayer':
        v = volume_omxplayer(vol)
    else:
        v = volume_alsa(vol)
    display.volume = int(v[v.find('[')+1:v.find('%]')])
    return v

def volume_alsa(vol):
    # With ALSA on CHIP
    if vol == 'up':
        db = subprocess.check_output(["amixer set 'PCM' 1%+"], shell=True)
        #db = os.system("amixer set 'Power Amplifier' 5%+")
    if vol == 'down':
        db = subprocess.check_output(["amixer set 'PCM' 1%-"], shell=True)
        #db = os.system("amixer set 'Power Amplifier' 5%-")
    i = db.rfind(':')
    return db[i+1:]

def volume_omxplayer(vol) :
    import math
    control = "/usr/local/bin/omxcontrol"
    if vol == 'up' :
        db = subprocess.check_output([control, "volumeup"])
    else :
        db = subprocess.check_output([control, "volumedown"])

    v = subprocess.check_output([control, "volume"])
    i = v.rfind(':')
    db = 10.0 * math.log(float(v[i+1:]), 10)
    volstring = "%-2.2f dB" % db
    return volstring

# ------------------------ SYSTEM --------------------------------
def writemypid(pidfile):
    pid = str(os.getpid())
    with open(pidfile, 'w') as f:
        f.write(pid)
    f.close

# Cherrypy Management
def error_page_404(status, message, traceback, version):
    html = header
    html += "%s<br>" % (status)
    html += "%s" % (traceback)
    html += getfooter()
    return html

def error_page_401(status, message, traceback, version):
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <title>My Radio Web Server</title>
  <meta name="generator" content="Vim">
  <meta charset="UTF-8">
</head>
<body>
   '''
    html += "<h1>%s</h1>" % (status)
    html += "%s<br>" % (message)

    return html

# Secure headers!
def secureheaders():
    headers = cherrypy.response.headers
    headers['X-Frame-Options'] = 'DENY'
    headers['X-XSS-Protection'] = '1; mode=block'
    headers['Content-Security-Policy'] = "default-src='self'"


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--player', action="store", dest="player", default="mpg123")
    parser.add_argument('--stage', action="store", dest="stage", default="production")
    parser.add_argument('--database', action="store", dest="database",  default="database.db")
    parser.add_argument('--root', action="store", dest="root", default=".")
    parser.add_argument('--pid', action="store", dest="pid", default="/tmp/80.pid")
    parser.add_argument('--port', action="store", dest="port", type=int, default=80)

    # get args
    args = parser.parse_args()

    # Where to start, what to get
    root = os.path.abspath(args.root)
    database = os.path.join(root, args.database)
    os.chdir(root)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    setplayer(args.player)
    # Trick to set the initial volume
    volume('down')
    volume('up')

    writemypid(args.pid)

    settings = {'global': {'server.socket_host': "0.0.0.0",
                           'server.socket_port' : args.port,
                           'log.screen': True,
                          },
               }

    conf = {'/static': {'tools.staticdir.on': True,
                     'tools.staticdir.root': current_dir,
                     'tools.staticfile.filename': 'icon.png',
                     'tools.staticdir.dir': 'static'
                    },
            '/':    {
                     'tools.auth_basic.on': True,
                     'tools.auth_basic.realm': 'localhost',
                     'tools.auth_basic.checkpassword': validate_password,
                     'tools.secureheaders.on' : True,
                     'tools.sessions.on': True,
                    },
           }

    cherrypy.config.update(settings)
    cherrypy.config.update({'error_page.404': error_page_404})
    cherrypy.config.update({'error_page.401': error_page_401})
    cherrypy.tools.secureheaders = cherrypy.Tool('before_finalize', secureheaders, priority=60)

    # To make it ZERO CPU usage
    #cherrypy.engine.timeout_monitor.unsubscribe()
    #cherrypy.engine.autoreload.unsubscribe()

    # Cherry insert pages
    serverroot = Root()

    # Start the CherryPy server.
    cherrypy.quickstart(serverroot, config=conf)

