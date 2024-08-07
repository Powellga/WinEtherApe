import sys
import threading
import asyncio
import math
import dns.resolver
import psutil
import socket
import os
from ipaddress import ip_address, IPv4Address
from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QGraphicsTextItem, QVBoxLayout, QWidget, QSlider
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer, QThread
from PyQt5.QtGui import QPen, QColor, QFont
import pyshark

class PacketSignal(QObject):
    new_packet = pyqtSignal(str, str, str, int)

class DNSResolverThread(QThread):
    resolved = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(self, ip):
        super().__init__()
        self.ip = ip

    def run(self):
        try:
            url = self.resolve_dns(self.ip)
            if url:
                self.resolved.emit(self.ip, url)
            else:
                self.failed.emit(self.ip)
        except Exception:
            self.failed.emit(self.ip)

    def resolve_dns(self, ip):
        try:
            resolver = dns.resolver.Resolver()
            result = resolver.resolve_address(ip)
            return result[0].to_text()
        except Exception:
            return None

class NetworkVisualizer(QGraphicsView):
    PROTOCOL_COLORS = {
        'TCP': QColor(0, 0, 255),      # Blue
        'UDP': QColor(0, 255, 0),      # Green
        'ICMP': QColor(255, 0, 0),     # Red
        'ARP': QColor(128, 0, 128),    # Purple
        # Add more protocols and their colors as needed
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setBackgroundBrush(Qt.black)  # Set background to black
        self.hosts = {}
        self.lines = []
        self.bandwidth_usage = {}
        self.protocol_legend = {}
        self.init_protocol_legend()

        # Set up a timer to periodically update node sizes
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_all_node_sizes)
        self.update_timer.start(1000)  # Update every second

        # Set up a timer to periodically reposition hosts
        self.reposition_timer = QTimer(self)
        self.reposition_timer.timeout.connect(self.position_hosts)
        self.reposition_timer.start(1000)  # Reposition every second

        self.dns_queue = []
        self.dns_in_progress = False
        self.rotation_angle = 0

    def init_protocol_legend(self):
        y_offset = 10
        for protocol, color in self.PROTOCOL_COLORS.items():
            text_item = QGraphicsTextItem(protocol)
            text_item.setDefaultTextColor(color)
            text_item.setFont(QFont("Arial", 12))
            self.scene.addItem(text_item)
            self.protocol_legend[protocol] = text_item

        self.position_protocol_legend()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_hosts()
        self.position_protocol_legend()

    def position_protocol_legend(self):
        y_offset = 10
        x_pos = self.width() - 150
        y_pos = self.height() // 2 - (len(self.protocol_legend) * 20) // 2
        for text_item in self.protocol_legend.values():
            text_item.setPos(x_pos, y_pos + y_offset)
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
        self.queue_dns_resolution(src_ip)
        self.queue_dns_resolution(dst_ip)

    def update_data_size(self, ip, size):
        if ip not in self.bandwidth_usage:
            self.bandwidth_usage[ip] = []

        self.bandwidth_usage[ip].append(size)

        # Keep only the data for the last second
        if len(self.bandwidth_usage[ip]) > 10:
            self.bandwidth_usage[ip].pop(0)

        # Update node size immediately after adding the packet
        self.update_node_size(ip)

    def calculate_bandwidth(self, ip):
        return sum(self.bandwidth_usage.get(ip, []))

    def update_node_size(self, ip):
        if ip in self.hosts:
            node, text = self.hosts[ip]
            size = self.calculate_bandwidth(ip)
            new_size = min(10 + size / 1000, 200)  # Linear scale for node size, clamped to 200 pixels max
            node.setRect(0, 0, new_size, new_size)
            text.setPos(node.x(), node.y() + new_size + 5)

    def update_all_node_sizes(self):
        for ip in self.hosts:
            self.update_node_size(ip)

    def get_or_create_host(self, ip):
        if ip not in self.hosts:
            node, text = self.create_host(ip)
            self.hosts[ip] = (node, text)
            self.scene.addItem(node)
            self.scene.addItem(text)
        return self.hosts[ip][0]

    def create_host(self, ip):
        color = self.get_ip_color(ip)
        size = self.calculate_bandwidth(ip)
        initial_size = min(10 + size / 1000, 200)  # Initial size, clamped to 200 pixels max
        node = QGraphicsEllipseItem(0, 0, initial_size, initial_size)
        node.setBrush(color)
        text = QGraphicsTextItem(ip)
        text.setDefaultTextColor(Qt.white)  # Set text color to white
        return node, text

    def get_ip_color(self, ip):
        ip_obj = ip_address(ip)
        if ip_obj.is_multicast or ip == '255.255.255.255':
            return QColor(128, 128, 128)  # Grey for broadcast
        elif ip_obj.is_private:
            return QColor(255, 165, 0)  # Orange for LAN
        else:
            return QColor(128, 0, 128)  # Purple for outside LAN

    def get_protocol_color(self, protocol):
        return self.PROTOCOL_COLORS.get(protocol, QColor(128, 128, 128))  # Default to gray

    def position_hosts(self):
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(center_x, center_y) - 200  # Adjust radius to account for max node size
        num_hosts = len(self.hosts)
        positions = {}

        for i, (ip, (node, text)) in enumerate(self.hosts.items()):
            angle = i * (2 * math.pi / num_hosts) + self.rotation_angle
            x = center_x + radius * math.cos(angle) - node.rect().width() / 2
            y = center_y + radius * math.sin(angle) - node.rect().height() / 2
            node.setPos(x, y)
            text.setRotation(math.degrees(angle + math.radians(15)) - 90)  # Adjust angle by 15 degrees
            text.setPos(x + node.rect().width() / 2 * math.cos(angle), y + node.rect().height() / 2 * math.sin(angle))
            positions[ip] = (x + node.rect().width() / 2, y + node.rect().height() / 2)

        for line, src_ip, dst_ip in self.lines:
            if src_ip in positions and dst_ip in positions:
                src_pos = positions[src_ip]
                dst_pos = positions[dst_ip]
                line.setLine(src_pos[0], src_pos[1], dst_pos[0], dst_pos[1])

    def queue_dns_resolution(self, ip):
        if ip not in self.dns_queue:
            self.dns_queue.append(ip)
            if not self.dns_in_progress:
                self.process_dns_queue()

    def process_dns_queue(self):
        if self.dns_queue:
            self.dns_in_progress = True
            ip = self.dns_queue.pop(0)
            resolver_thread = DNSResolverThread(ip)
            resolver_thread.resolved.connect(self.handle_dns_resolved)
            resolver_thread.failed.connect(self.handle_dns_failed)
            resolver_thread.start()
            QTimer.singleShot(5000, lambda: resolver_thread.terminate())  # Timeout after 5 seconds
        else:
            self.dns_in_progress = False

    def handle_dns_resolved(self, ip, url):
        if ip in self.hosts:
            node, text = self.hosts[ip]
            text.setPlainText(url)
        self.process_dns_queue()

    def handle_dns_failed(self, ip):
        if ip in self.hosts:
            node, text = self.hosts[ip]
            text.setPlainText(ip)
        self.process_dns_queue()

    def rotate_nodes(self, angle):
        self.rotation_angle = math.radians(angle)
        self.position_hosts()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WinEtherApe")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.visualizer = NetworkVisualizer(self)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(-180, 180)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self.handle_slider_change)

        layout = QVBoxLayout()
        layout.addWidget(self.visualizer)
        layout.addWidget(self.slider)
        self.central_widget.setLayout(layout)
        
        self.packet_signal = PacketSignal()
        self.packet_signal.new_packet.connect(self.handle_new_packet)
        
        self.start_capture()

    def handle_slider_change(self, value):
        self.visualizer.rotate_nodes(value)

    def handle_new_packet(self, src_ip, dst_ip, protocol, size):
        self.visualizer.add_packet(src_ip, dst_ip, protocol, size)

    def start_capture(self):
        threading.Thread(target=self.capture_packets, daemon=True).start()

    def capture_packets(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        interfaces = psutil.net_if_addrs()
        active_interface = None
        for interface_name, interface_addresses in interfaces.items():
            if any(addr.family == socket.AF_INET for addr in interface_addresses):
                # Check if the interface is up and running
                if psutil.net_if_stats()[interface_name].isup:
                    active_interface = interface_name
                    break

        # Clear screen and move cursor to the top left
        os.system('cls' if os.name == 'nt' else 'clear')
        if active_interface:
            print(f"\033[97mUsing interface: {active_interface}\033[0m")
        else:
            print("\033[97mNo active network interface found.\033[0m")

        if not active_interface:
            return

        capture = pyshark.LiveCapture(interface=active_interface)
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
