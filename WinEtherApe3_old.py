import sys
import threading
import asyncio
import math
import socket
from ipaddress import ip_address, IPv4Address
from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QGraphicsTextItem
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QPen, QColor, QFont
import pyshark

class PacketSignal(QObject):
    new_packet = pyqtSignal(str, str, str, int)

class NetworkVisualizer(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.hosts = {}
        self.lines = []
        self.data_sizes = {}
        self.protocol_legend = {}
        self.timer = QTimer()
        self.timer.timeout.connect(self.perform_lookup)
        self.hovered_node = None
        self.init_protocol_legend()

    def init_protocol_legend(self):
        protocols = ['TCP', 'UDP', 'ICMP', 'ARP']
        color_map = {
            'TCP': QColor(0, 0, 255),      # Blue
            'UDP': QColor(0, 255, 0),      # Green
            'ICMP': QColor(255, 0, 0),     # Red
            'ARP': QColor(128, 0, 128),    # Purple
        }
        y_offset = 10
        for protocol in protocols:
            color = color_map.get(protocol, QColor(128, 128, 128))  # Default to gray
            text_item = QGraphicsTextItem(f"{protocol}")
            text_item.setDefaultTextColor(color)
            text_item.setFont(QFont("Arial", 12))
            self.scene.addItem(text_item)
            self.protocol_legend[protocol] = text_item
            text_item.setPos(self.width() - 150, self.height() - y_offset)
            y_offset += 20

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_hosts()
        self.position_protocol_legend()

    def position_protocol_legend(self):
        y_offset = 10
        for protocol, text_item in self.protocol_legend.items():
            text_item.setPos(self.width() - 150, self.height() - y_offset)
            y_offset += 20

    def add_packet(self, src_ip, dst_ip, protocol, size):
        self.update_data_size(src_ip, size)
        self.update_data_size(dst_ip, size)
        src_node = self.get_or_create_host(src_ip)
        dst_node = self.get_or_create_host(dst_ip)
        line_color = self.get_protocol_color(protocol)
        line = self.scene.addLine(src_node.x() + src_node.rect().width() / 2, src_node.y() + src_node.rect().height() / 2,
                                  dst_node.x() + dst_node.rect().width() / 2, dst_node.y() + dst_node.rect().height() / 2,
                                  QPen(line_color))
        self.lines.append((line, src_ip, dst_ip))

    def update_data_size(self, ip, size):
        if ip in self.data_sizes:
            self.data_sizes[ip] += size
        else:
            self.data_sizes[ip] = size
        self.update_node_size(ip)

    def update_node_size(self, ip):
        if ip in self.hosts:
            node, text, domain_text = self.hosts[ip]
            size = self.data_sizes[ip]
            new_size = min(10 + size / 1000, 200)  # Linear scale for node size, clamped to 200 pixels max
            node.setRect(0, 0, new_size, new_size)
            text.setPos(node.x(), node.y() + new_size + 5)
            domain_text.setPos(node.x() + new_size + 5, node.y())

    def get_or_create_host(self, ip):
        if ip not in self.hosts:
            node, text, domain_text = self.create_host(ip)
            self.hosts[ip] = (node, text, domain_text)
            self.scene.addItem(node)
            self.scene.addItem(text)
            self.scene.addItem(domain_text)
        return self.hosts[ip][0]

    def create_host(self, ip):
        color = self.get_ip_color(ip)
        size = self.data_sizes.get(ip, 0)
        initial_size = min(10 + size / 1000, 200)  # Initial size, clamped to 200 pixels max
        node = QGraphicsEllipseItem(0, 0, initial_size, initial_size)
        node.setBrush(color)
        text = QGraphicsTextItem(ip)
        domain_text = QGraphicsTextItem("")
        domain_text.setDefaultTextColor(QColor(0, 0, 255))
        domain_text.setFont(QFont("Arial", 10))
        domain_text.setVisible(False)
        return node, text, domain_text

    def get_ip_color(self, ip):
        ip_obj = ip_address(ip)
        if ip_obj.is_multicast or ip == '255.255.255.255':
            return QColor(128, 128, 128)  # Grey for broadcast
        elif ip_obj.is_private:
            return QColor(0, 0, 0)  # Black for LAN
        else:
            return QColor(128, 0, 128)  # Purple for outside LAN

    def get_protocol_color(self, protocol):
        color_map = {
            'TCP': QColor(0, 0, 255),      # Blue
            'UDP': QColor(0, 255, 0),      # Green
            'ICMP': QColor(255, 0, 0),     # Red
            'ARP': QColor(128, 0, 128),    # Purple
            # Add more protocols and their colors as needed
        }
        return color_map.get(protocol, QColor(128, 128, 128))  # Default to gray

    def position_hosts(self):
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(center_x, center_y) - 200  # Adjust radius to account for max node size
        num_hosts = len(self.hosts)
        positions = {}
        
        for i, (ip, (node, text, domain_text)) in enumerate(self.hosts.items()):
            angle = i * (2 * math.pi / num_hosts)
            x = center_x + radius * math.cos(angle) - node.rect().width() / 2
            y = center_y + radius * math.sin(angle) - node.rect().height() / 2
            node.setPos(x, y)
            text.setPos(x, y + node.rect().height() + 5)
            domain_text.setPos(x + node.rect().width() + 5, y)
            positions[ip] = (x + node.rect().width() / 2, y + node.rect().height() / 2)

        for line, src_ip, dst_ip in self.lines:
            if src_ip in positions and dst_ip in positions:
                src_pos = positions[src_ip]
                dst_pos = positions[dst_ip]
                line.setLine(src_pos[0], src_pos[1], dst_pos[0], dst_pos[1])

    def perform_lookup(self):
        if self.hovered_node:
            ip = self.hovered_node[1]
            try:
                domain = socket.gethostbyaddr(ip)[0]
                self.hovered_node[2].setPlainText(domain)
                self.hovered_node[2].setVisible(True)
            except socket.herror:
                self.hovered_node[2].setPlainText("No domain")
                self.hovered_node[2].setVisible(True)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        item = self.itemAt(event.pos())
        if isinstance(item, QGraphicsEllipseItem):
            for ip, (node, text, domain_text) in self.hosts.items():
                if node == item:
                    self.hovered_node = (node, ip, domain_text)
                    self.timer.start(3000)  # Start timer for 3 seconds
                    return
        self.timer.stop()
        if self.hovered_node:
            self.hovered_node[2].setVisible(False)
            self.hovered_node = None
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WinEtherApe")
        self.setGeometry(100, 100, 800, 600)
        self.visualizer = NetworkVisualizer(self)
        self.setCentralWidget(self.visualizer)
        
        self.packet_signal = PacketSignal()
        self.packet_signal.new_packet.connect(self.handle_new_packet)
        
        self.start_capture()

    def handle_new_packet(self, src_ip, dst_ip, protocol, size):
        self.visualizer.add_packet(src_ip, dst_ip, protocol, size)

    def start_capture(self):
        threading.Thread(target=self.capture_packets, daemon=True).start()

    def capture_packets(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        capture = pyshark.LiveCapture(interface='\\Device\\NPF_{53573073-74B9-4784-BF6A-F0F01473EBED}')  # Replace with the correct interface name
        for packet in capture.sniff_continuously():
            try:
                src_ip = packet.ip.src
                dst_ip = packet.ip.dst
                protocol = packet.transport_layer
                size = int(packet.length)
                self.packet_signal.new_packet.emit(src_ip, dst_ip, protocol, size)
            except AttributeError:
                continue

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
