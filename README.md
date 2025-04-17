![Logo](annotated-logo.png)

This is the Test GUI for the S25-26 CMOS Readout System. Intended to run on a desktop computer as a demonstration, use of the software illustrates the possible interactions with the readout system, and the code illustrates how they can be implemented into other systems. 

Packet transactions occur via UDP. There must be a DHCP server between the readout system and the computer to assign IP addresses. If there is no physical router to perform DHCP functionality, use Nicco Kunzmann's implementation of a DHCP server which can be found [here.](https://github.com/niccokunzmann/simple_dhcp_server) The port/IP assigned by the system (which can be found using ipconfig) must match the port/IP flashed onto the readout system.

To package into a standalone executable with pyinstaller, use:
```
pyinstaller --onefile --windowed gui.py
```



