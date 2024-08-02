# WinEtherApe
Windows Ether Ape

WinEtherApe is a basic network visualization tool inspired by the Linux-based EtherApe. It captures and displays network traffic in real-time, showing the connections between devices on your network.

## Features

- Real-time Packet Capture**: Intercepts network packets as they flow through your network.
- Interactive Visualization**: Displays devices as nodes and connections as lines, color-coded by protocol.
- Dynamic Node Sizing**: Adjusts the size of nodes based on bandwidth usage.
- Protocol Legend**: Provides a color-coded legend for different network protocols.
- Dark Mode Theme**: Features a black background for a modern look.

## Requirements

- Python 3.6+
- PyQt5
- Pyshark

## Installation

Clone the Repository:
```sh
git clone https://github.com/Powellga/WinEtherApe.git
cd WinEtherApe
```

Install Dependencies:
```sh
pip install -r requirements.txt
```

Usage
Run the App:
```sh
python WinEtherApe.py
```

Network Interface:

Ensure you have the correct network interface specified in the capture_packets method within the code.
Troubleshooting
No Packets Captured: Run the app with administrative privileges.
Nodes Not Appearing: Verify the network interface is correctly specified and active. Restart the app or your device if issues persist.
License
This project is licensed under the MIT License. See the LICENSE file for more details.

Use the slider bar at the bottom to rotate the ring to make the addresses easier to read.

Enjoy using WinEtherApe for your basic network visualization needs!


Addemdum etc.
I made this because I always wanted a Windows version of the Linux based Etherape.
