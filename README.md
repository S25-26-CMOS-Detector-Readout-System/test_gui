![Logo](annotated-logo.png)

This is the Test GUI for the S25-26 CMOS Readout System. Intended to run on a desktop computer as a demonstration, use of the software illustrates the possible interactions with the readout system, and the code illustrates how they can be implemented into other systems. 

Currently, the test software exists in two versions. There are the gui.py and CMOSReadoutInterface.py files. gui.py is the entry point, creating the GUI, while CMOSReadoutInterface is an interface with the CMOS Readout System, intended to be able to be integrated into other scripts, such as the software on the flight computer. This is untested with the development board, and probably contains several bugs and issues as it stands. What is known to work is gui_old.py, contained in the "Old" folder, which packages all GUI and interface functionality into one, albeit more confusing file. 

Packet transactions occur via UDP. There must be a DHCP server between the readout system and the computer to assign IP addresses. If there is no physical router to perform DHCP functionality, use Nicco Kunzmann's implementation of a DHCP server which can be found [here.](https://github.com/niccokunzmann/simple_dhcp_server) The port/IP assigned by the system (which can be found using ipconfig) must match the port/IP flashed onto the readout system.

To package into a standalone executable with pyinstaller, use:
```
pyinstaller --onefile --windowed gui.py
```

You can contact the author, Justin Winn at justinwinn003@gmail.com



