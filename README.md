# Radio-server

Radio Server for Debian based system, RaspberryPI, CHIP 9$ Computer and more... 

It is a minimalistic wrap on mpg123//mplayer//omxplayer and a bunch of internet radio url addresses kept in a sqlite3 DB. Design is responsive by means of Twitter:Bootstrap.

Is is just a simple web interfcae to search, play, modify Internet Radios. Adding your genre, and information to search easily.


## Installation on CHIP

Starting from git repo:

	git clone https://github.com/rfdougherty/radio-server.git

Install packages

	$ sudo apt-get install build-essential python-pip python-dev python-cherrypy3 sqlite3 mpg123 i2c-tools python-pil fonts-dejavu-core wireless-tools
	$ sudo -H pip install --upgrade --ignore-installed pip setuptools
	$ sudo pip install smbus2 spidev RPi.GPIO
	$ cd git/ssd1306; sudo pip install .
	$ cd CHIP_IO; sudo pip install .
	$ cd Adafruit_Python_GPIO; sudo pip install .
	
Configure /etc files
        
	$ printf 'pcm.!default {\n  type hw\n  card AUDIO\n}\nctl.!default {\n  type hw\n  card AUDIO\n}\n' > /tmp/asound.conf
	$ sudo mv /tmp/asound.conf /etc/
	$ printf '/usr/sbin/i2cset -f -y 0 0x34 0x33 0xa3\ncd /home/chip/git/radio-server/radio-server/\n./server.py &> /tmp/radio.log &\nexit 0\n' > /tmp/rc.local
	$ sudo mv /tmp/rc.local /etc/rc.local
	
Configure parameters in radioserver.sh # it is already preconfigured if installation is in /usr/local/bin/radioserver
Anyway it is possible to change default parameters of server like

	--port 80 (default is 8804)
	--player mpg123 OR mplayer OR omxplayer (for RaspberryPi)
	--etc. see code. 

## USAGE

Just open browser and point to web address of the appliance.
	eg: http://192.168.2.123:8804

Webapp is protected:

	user: admin
	pass: webradio

User interface is pretty self-explaining.

Search for radio (null search provide full list)
Preset are 
	RAI=Italian Radio RAI, RMC=RadioMonteCarlo, NL=Nederland Radio

Just click play> and it will play on appliance

To edit just tick edit and reload search

Volume should work (but is an hack with alsamixer... well everything is an hack! and was never intended to be public)

Just enjoy!


# WARNING 

## Database
database.db is filled with Internet Radio taken from Internet

They can be changed /insert/modify/delete with User interface

It took me sometime to discover them... I guess internet radio apps make that part of their value ;)

# Miscellaneous notes 

To reflash the CHIP, see http://www.chip-community.org/index.php/Flash_from_command_line

After flashing, remove the FEL jumper, connect to USB port, and connect via 'screen /dev/tty.usb1234'. To set up wifi, run 'sudo nmtui'.

