# ITLA-PPCL550
Software to control the PurePhotonics PPCL550 ITLA

The two most useful files I wrote are ``laser.py`` and ``gui.py``. The others have some examples that may be useful, but may also be outdated. ``pure_photonics_utils.py`` is a modified/improved version of the Python code supplied on the PurePhotonics website. 
 
``laser.py`` contains a lot of user-friendly methods for operating the laser. You will first need to update the definitions at the top of the file for the COM port # and paths to the calibration files you generated. Then, you can instantiate an instance of the Laser class with no parameters and it will establish a serial connection with the laser. Then, call the laser_on method to power on the laser. 
 
## Important methods: 
- ``check_nop``: this reads the laser's ``NOP`` register, which contains flags about the laser's status. A value of 16 indicates that the laser is ready. Values higher than 16 indicate that the laser is still stabilizing or turning on, or potentially that there is an error. The ``wait_nop`` method can be used to wait until the ``NOP`` register reads 16. 

- ``check_power``: returns the laser's reported optical power in dBm. The laser's actual power as measured by a power meter is generally significantly lower than this for unknown reasons. 

- ``startup_begin``: powers on the laser. After calling this method, you should use ``check_nop`` or ``wait_nop`` to wait until the ``NOP`` register reads 16, and then call ``startup_finish``. 

- ``laser_on``: does the entire startup process and returns when the laser is ready to use. 

- ``laser_off``: turns off the laser. Always close the serial connection when finished by calling ``itla_disconnect``. 

- ``send``: sends a command to the laser. The register is set by the first argument, which should be one of the constant ``REG_*`` values defined in ``pure_photonics_utils.py``. The second argument is the value to send, and the third optional argument, if true, will treat the response from the laser as a signed value. 

- ``read``: read a register from the laser. The argument should be one of the constant ``REG_*`` values defined in ``pure_photonics_utils.py``. 

- ``clean_jump``: quickly jumps the laser from the current frequency to the frequency passed to it. During the jump, you can call ``offset`` to watch the laser's reported difference from the goal frequency in GHz 

- ``clean_sweep_prep``, ``clean_sweep_start``: ``clean_sweep_prep`` sets the sweep range (in GHz) and speed (in MHz/s), and ``clean_sweep_start`` begins the sweep 

- ``clean_sweep_pause``: pause the clean sweep either immediately (if not parameter) or at the ``offset`` value you pass the method 

- ``clean_sweep_stop``: stop the clean sweep 
 
## GUI 
The file ``gui.py`` can be run to open a graphical user interface for operating the laser, specifically for use with frequency combs. Clicking _Laser On_ powers on the laser to 195 THz and 10 dBm. From there, you can execute _Clean Jump_, _Clean Scan_, or a mode finding routine. The mode finding routine will attempt to connect to a Thorlabs PM100D power meter over USB. If successful, it will open a transmission vs frequency plot, and the laser will automatically stitch together clean sweeps and clean jumps to cover the desired frequency range. While it is sweeping, it will record the transmitted power at each frequency and plot it on the graph. This is very useful for locating the modes of a new chip. It takes several minutes per THz, but can be left to run on its own, and when it finishes it will put a CSV file of the data in the working directory. 
 
Additionally, the left and right arrow keys can be used to make 100 MHz jumps, and ``SHIFT``+``arrow`` does 1 GHz jumps. When performing a sweep, the arrow keys will pause the laser, and change the pause setpoint in 1 GHz increments, so repeatedly pressing the arrow keys can slowly walk the laser's frequency up or down. 
