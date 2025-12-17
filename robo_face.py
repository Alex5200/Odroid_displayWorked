#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import threading
import random
from PyQt5.QtWidgets import (
    QApplication, QWidget, QGraphicsView, QGraphicsScene, QGraphicsProxyWidget
)
from PyQt5.QtCore import Qt, QTimer, QRectF, pyqtSignal, QObject
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QTransform

# ROS 2 импорты
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# Используем framebuffer напрямую
os.environ["QT_QPA_PLATFORM"] = "linuxfb"


# --- ROS 2 Worker (в отдельном потоке) ---
class ROS2Worker(QObject):
    command_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.node = None
        self.executor = None
        self.thread = None

    def start_ros(self):
        self.thread = threading.Thread(target=self._ros_spin, daemon=True)
        self.thread.start()

    def _ros_spin(self):
        try:
            rclpy.init()
            self.node = rclpy.create_node('robo_face_node')
            self.node.create_subscription(
                String,
                '/robo_face/command',
                self.listener_callback,
                10
            )
            self.executor = rclpy.executors.SingleThreadedExecutor()
            self.executor.add_node(self.node)
            self.executor.spin()
        except Exception as e:
            print(f"[ROS ERROR] {e}")

    def listener_callback(self, msg):
        command = msg.data.strip().lower()
        self.command_received.emit(command)

    def shutdown(self):
        if self.executor:
            self.executor.shutdown()
        if self.node:
            self.node.destroy_node()
        rclpy.try_shutdown()


# --- Анимированный интерфейс ---
class AnimatedFace(QWidget):
    def __init__(self, width, height):
        super().__init__()
        self.setFixedSize(width, height)
        self.display_w = width
        self.display_h = height

        # Состояния
        self.eye_state = "open"
        self.mouth_state = "smile"
        self.talk_phase = 0

        # Текст
        self.display_text = ""

        # Таймеры
        self.auto_blink_timer = QTimer(self)
        self.auto_blink_timer.timeout.connect(self.auto_blink)
        self.auto_blink_timer.start(5000 + random.randint(0, 3000))

        self.blink_end_timer = QTimer(self)
        self.blink_end_timer.setSingleShot(True)
        self.blink_end_timer.timeout.connect(self.end_blink)

        self.talk_timer = QTimer(self)
        self.talk_timer.timeout.connect(self.animate_talk)
        self.talk_timer.setInterval(300)

        self.text_clear_timer = QTimer(self)
        self.text_clear_timer.setSingleShot(True)
        self.text_clear_timer.timeout.connect(self.clear_text)

        # Цвета
        self.bg_color = Qt.white
        self.eye_color = QColor("#0a2a66")
        self.mouth_color = QColor("#333333")

    def set_display_text(self, text: str, auto_clear_sec: int = 5):
        self.display_text = text
        self.update()
        if auto_clear_sec > 0:
            self.text_clear_timer.start(auto_clear_sec * 1000)
        else:
            self.text_clear_timer.stop()

    def clear_text(self):
        self.display_text = ""
        self.update()

    def handle_ros_command(self, command: str):
        """ПОДДЕРЖИВАЕТ ВСЕ КОМАНДЫ!"""
        print(f"[ROS] Получена команда: {command}")
        if command.startswith("text:"):
            text = command[5:].strip()
            if text:
                self.set_display_text(text, auto_clear_sec=5)
            else:
                self.clear_text()
        elif command == "blink":
            self.eye_state = "closed"
            self.update()
            self.blink_end_timer.start(150)
        elif command == "smile":
            self.mouth_state = "smile"
            self.talk_timer.stop()
        elif command == "talk":
            self.mouth_state = "talk"
            self.talk_timer.start()
        elif command == "neutral":
            self.mouth_state = "neutral"
            self.talk_timer.stop()
        elif command == "open":
            self.mouth_state = "open"
            self.talk_timer.stop()
        else:
            print(f"[WARN] Неизвестная команда: {command}")

    def auto_blink(self):
        if self.eye_state == "open":
            self.eye_state = "closed"
            self.update()
            self.blink_end_timer.start(150)
            self.auto_blink_timer.start(2000 + random.randint(0, 3000))

    def end_blink(self):
        self.eye_state = "open"
        self.update()

    def animate_talk(self):
        self.talk_phase = 1 - self.talk_phase
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.fillRect(self.rect(), self.bg_color)

        center_x = self.display_w // 2
        # 🔼 Глаза ВВЕРХУ!
        eye_y = int(self.display_h * 0.1)
        eye_radius = int(min(self.display_w, self.display_h) * 0.08)
        eye_spacing = int(self.display_w * 0.25)

        # Глаза
        for dx in [-eye_spacing, eye_spacing]:
            x = center_x + dx
            y = eye_y
            if self.eye_state == "open":
                painter.setBrush(QBrush(self.eye_color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(x - eye_radius, y - eye_radius, eye_radius * 2, eye_radius * 2)
                hl_r = eye_radius // 3
                painter.setBrush(Qt.white)
                painter.drawEllipse(x - eye_radius + hl_r, y - eye_radius + hl_r, hl_r * 2, hl_r * 2)
            else:
                pen_w = max(3, eye_radius // 12)
                painter.setPen(QPen(self.eye_color, pen_w))
                painter.drawLine(x - eye_radius, y, x + eye_radius, y)

        # Рот — выше центра
        mouth_y = int(self.display_h * 0.42)
        mouth_w = int(self.display_w * 0.35)
        mouth_h = int(mouth_w * 0.2)
        painter.setPen(QPen(self.mouth_color, max(3, eye_radius // 10)))
        painter.setBrush(Qt.NoBrush)

        if self.mouth_state == "smile":
            painter.drawArc(center_x - mouth_w // 2, mouth_y, mouth_w, mouth_h, 0, -180 * 16)
        elif self.mouth_state == "open":
            painter.drawEllipse(center_x - mouth_w // 2, mouth_y, mouth_w, mouth_h)
        elif self.mouth_state == "neutral":
            painter.drawLine(
                center_x - mouth_w // 2, mouth_y + mouth_h // 2,
                center_x + mouth_w // 2, mouth_y + mouth_h // 2
            )
        elif self.mouth_state == "talk":
            if self.talk_phase == 0:
                painter.drawArc(center_x - mouth_w // 2, mouth_y, mouth_w, mouth_h, 0, -200 * 16)
            else:
                painter.drawEllipse(center_x - mouth_w // 2, mouth_y, mouth_w, mouth_h)

        # Текст — компактно
        painter.setPen(self.eye_color)
        font = painter.font()
        font.setPointSize(int(self.display_h * 0.06))
        painter.setFont(font)
        painter.drawText(
            QRectF(0, int(self.display_h * 0.60), self.display_w, int(self.display_h * 0.25)),
            Qt.AlignCenter,
            self.display_text
        )


# --- Вспомогательные функции ---
def get_fb_size():
    try:
        with open("/sys/class/graphics/fb0/virtual_size", "r") as f:
            w, h = map(int, f.read().strip().split(","))
            if w > 0 and h > 0:
                return w, h
    except Exception as e:
        print(f"[ERROR] Не удалось прочитать fb0: {e}")
    return 800, 480  # fallback


# --- Основной запуск ---
def main():
    app = QApplication(sys.argv)

    fb_w, fb_h = get_fb_size()
    logical_w = 12000
    logical_h = 10

    face = AnimatedFace(600, 400)

    # Поворот на 90°
    scene = QGraphicsScene()
    proxy = scene.addWidget(face)
    proxy.setTransform(QTransform().rotate(90))
    scene.setSceneRect(0, 0, logical_h, logical_w)

    view = QGraphicsView(scene)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    view.setFrameShape(view.NoFrame)
    view.setViewportMargins(0, 0, 0, 0)
    view.setFixedSize(logical_h, logical_w)
    view.setStyleSheet("background: white;")
    view.showFullScreen()

    # Запуск ROS
    ros_worker = ROS2Worker()
    ros_worker.command_received.connect(face.handle_ros_command)
    ros_worker.start_ros()

    def cleanup():
        ros_worker.shutdown()

    app.aboutToQuit.connect(cleanup)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
